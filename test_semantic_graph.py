"""
Offline, deterministic tests for dynamic meaning linking (no network: a fake dictionary replaces Wiktionary).

Run:  python test_semantic_graph.py
"""
import os
import sys
import tempfile
import threading
import time

os.environ['SEMANTIC_STORE_PATH'] = os.path.join(tempfile.mkdtemp(prefix='sem_test_'), 'semantic_links.json')
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

import app as app_module                                   # noqa: E402
from modules import semantic                               # noqa: E402
from modules import wiktionary as W                        # noqa: E402
from modules.semantic import MeaningGraph, SemanticLinker, merge_edge   # noqa: E402
from modules.tokenizer import tokenize                     # noqa: E402

app_module.save_corpus = lambda: None   # never touch data/corpus.json

# term -> what the (fake) dictionary says. links are (other, cost, hub) with hub in {'self','other',None}.
FAKE_DICTIONARY = {
    'elephant': {'summary_definition': 'a large mammal',
                 'links': [('elefante', 1, 'self'), ('हाथी', 1, 'self'), ('éléphant', 1, 'self')]},
    'elefante': {'summary_definition': 'elephant', 'direct_glosses': ['elephant'], 'links': [('elephant', 1, 'other')]},
    'हाथी': {'summary_definition': 'elephant', 'direct_glosses': ['elephant'], 'links': [('elephant', 1, 'other')]},
    'éléphant': {'summary_definition': 'elephant', 'links': [('elephant', 1, 'other')]},
    'kitten': {'summary_definition': 'a young cat', 'links': [('gatito', 1, 'self')]},
    'kittens': {'summary_definition': 'plural of kitten', 'inflection_roots': ['kitten'], 'links': [('kitten', 0, None)]},
    'gatito': {'summary_definition': 'kitten', 'links': [('kitten', 1, 'other')]},
    'gatitos': {'summary_definition': 'plural of gatito', 'inflection_roots': ['gatito'], 'links': [('gatito', 0, None)]},
    # Arabic bustan means BOTH garden and orchard: chaining through it must not make them synonyms
    'garden': {'summary_definition': 'a plot of land', 'links': [('بستان', 1, 'self')]},
    'orchard': {'summary_definition': 'a fruit garden', 'links': [('بستان', 1, 'self')]},
    'بستان': {'summary_definition': 'garden, orchard',
              'links': [('garden', 1, 'other'), ('orchard', 1, 'other')]},
}


class FakeDictionary:
    def __init__(self, delay=0.0, fail_first=(), slow=None):
        self.calls = []
        self.delay = delay
        self.slow = slow            # if given, only these terms are delayed
        self.fail_first = set(fail_first)
        self.lock = threading.Lock()

    def __call__(self, term, preferred_lang=None):
        if self.delay and (self.slow is None or term in self.slow):
            time.sleep(self.delay)
        with self.lock:
            self.calls.append(term)
            transient = term in self.fail_first
            self.fail_first.discard(term)
        entry = FAKE_DICTIONARY.get(term)
        if transient:
            return {'found': False, 'complete': False, 'links': []}
        if entry is None:
            return {'found': False, 'complete': True, 'links': []}
        return {'found': True, 'complete': True, 'wiktionary_url': f'https://wiktionary.test/{term}', **entry}


def fresh_linker(**kwargs):
    """Installs an empty graph + fake dictionary into the app and returns (linker, dictionary)."""
    dictionary = FakeDictionary(**kwargs)
    linker = SemanticLinker(MeaningGraph(None), resolver=dictionary)
    app_module.semantic_linker = linker
    app_module.meaning_graph = linker.graph
    return linker, dictionary


class AddedDocs:
    """Adds documents through the real /add_document route and removes them again afterwards."""
    def __init__(self):
        self.client = app_module.app.test_client()
        self.ids = {}

    def add(self, key, title, lang, text):
        res = self.client.post('/add_document', json={'title': title, 'lang': lang, 'text': text}).get_json()
        assert res['success'], res
        self.ids[key] = res['id']
        return res

    def search(self, query, **params):
        data = self.client.get('/search', query_string={'q': query, 'limit': 50, **params}).get_json()
        return {k for k, doc_id in self.ids.items() if doc_id in {r['id'] for r in data['results']}}, data

    def cleanup(self):
        for doc_id in self.ids.values():
            app_module.global_index.delete_document(doc_id)


# ---------------------------------------------------------------------------------------------
# MeaningGraph
# ---------------------------------------------------------------------------------------------

def reach(graph, seed, **kw):
    return {node: cost for node, (cost, _p, _h) in graph.expand(seed, **kw).items()}


def test_zero_one_bfs_costs():
    g = MeaningGraph(None)
    g.add_link('kittens', 'kitten', 0)                # inflection
    g.add_link('kitten', 'gatito', 1, hub='kitten')   # translation under hub 'kitten'
    g.add_link('gatito', 'gatitos', 0)
    assert reach(g, 'kittens') == {'kitten': 0, 'gatito': 1, 'gatitos': 1}, reach(g, 'kittens')
    assert reach(g, 'gatitos') == {'gatito': 0, 'kitten': 1, 'kittens': 1}, reach(g, 'gatitos')


def test_second_hop_requires_shared_hub():
    g = MeaningGraph(None)
    g.add_link('elefante', 'elephant', 1, hub='elephant')
    g.add_link('हाथी', 'elephant', 1, hub='elephant')
    assert reach(g, 'elefante') == {'elephant': 1, 'हाथी': 2}

    # garden -> bustan -> orchard: bustan is not a hub of either edge, so the chain is refused
    g.add_link('garden', 'بستان', 1, hub='garden')
    g.add_link('orchard', 'بستان', 1, hub='orchard')
    assert 'orchard' not in reach(g, 'garden'), reach(g, 'garden')
    assert reach(g, 'garden') == {'بستان': 1}


def test_max_cost_bounds_the_expansion():
    g = MeaningGraph(None)
    g.add_link('a', 'hub1', 1, hub='hub1')
    g.add_link('b', 'hub1', 1, hub='hub1')
    g.add_link('b', 'hub2', 1, hub='b')        # third hop away from 'a'
    assert 'hub2' not in reach(g, 'a')
    assert reach(g, 'a', max_cost=1) == {'hub1': 1}


def test_cheapest_path_wins_and_path_is_reconstructed():
    g = MeaningGraph(None)
    g.add_link('x', 'y', 0)
    g.add_link('y', 'z', 1, hub='z')
    g.add_link('x', 'z', 1, hub='z')
    reached = g.expand('x')
    assert reached['z'][0] == 1
    assert g.path_to(reached, 'x', 'z') in (['x', 'z'], ['x', 'y', 'z'])
    assert g.path_to(g.expand('x'), 'x', 'y') == ['x', 'y']


def test_merge_edge_conflicting_hub_is_dropped():
    assert merge_edge(None, (1, 'a')) == (1, 'a')
    assert merge_edge((1, 'a'), (1, 'a')) == (1, 'a')
    assert merge_edge((1, 'a'), (1, 'b')) == (1, None)       # ambiguous: cannot be pivoted on
    assert merge_edge((1, 'a'), (0, None)) == (0, None)      # cheaper edge replaces
    assert merge_edge((0, None), (1, 'a')) == (0, None)


def test_persistence_roundtrip_and_corrupt_store():
    path = os.path.join(tempfile.mkdtemp(), 'store.json')
    g = MeaningGraph(path)
    g.add_link('kitten', 'gatito', 1, hub='kitten')
    g.add_link('kittens', 'kitten', 0)
    g.mark_resolved('kitten', {'summary': 'young cat'})
    g.save()
    again = MeaningGraph(path)
    assert again.adj == g.adj and again.resolved == g.resolved
    assert reach(again, 'kittens') == {'kitten': 0, 'gatito': 1}

    with open(path, 'w', encoding='utf-8') as f:
        f.write('{ this is not json')
    assert MeaningGraph(path).get_stats()['total_edges'] == 0       # corrupt store: start empty, never crash


# ---------------------------------------------------------------------------------------------
# SemanticLinker
# ---------------------------------------------------------------------------------------------

def test_learn_resolves_lemma_and_does_not_repeat_calls():
    linker, dictionary = fresh_linker()
    linker.learn('gatitos', 'es')
    assert dictionary.calls == ['gatitos', 'gatito'], dictionary.calls          # lemma resolved too
    assert linker.graph.is_resolved('gatitos') and linker.graph.is_resolved('gatito')
    linker.learn('gatitos', 'es')
    linker.learn('gatito', 'es')
    assert dictionary.calls == ['gatitos', 'gatito']                            # nothing resolved twice


def test_transient_failure_is_retried_not_remembered():
    linker, dictionary = fresh_linker(fail_first={'elephant'})
    linker.learn('elephant')
    assert not linker.graph.is_resolved('elephant')          # a timeout must not look like "word has no meaning"
    linker.learn('elephant')
    assert linker.graph.is_resolved('elephant')
    assert 'elefante' in linker.graph.adj['elephant']


def test_unknown_word_is_remembered_so_it_is_not_looked_up_again():
    linker, dictionary = fresh_linker()
    linker.learn('zzyzx')
    linker.learn('zzyzx')
    assert dictionary.calls == ['zzyzx']


def test_select_terms_skips_function_words_numbers_and_common_terms():
    linker, _ = fresh_linker()
    index = app_module.global_index
    text = 'the 2024 elephant and a kitten http://x.y co2 xq'
    index.add_document('tmp_select', text, metadata={'title': 'T', 'lang': 'en'})   # bypass the route: nothing gets linked
    try:
        chosen = linker.select_terms(tokenize(text), index)
    finally:
        index.delete_document('tmp_select')
    assert 'elephant' in chosen and 'kitten' in chosen
    assert not {'the', 'and', 'a', '2024', 'http://x.y', 'co2', 'xq'} & set(chosen), chosen


# ---------------------------------------------------------------------------------------------
# End to end through the Flask routes
# ---------------------------------------------------------------------------------------------

def test_new_sentence_is_linked_and_found_in_any_order():
    for order in (('es', 'hi'), ('hi', 'es')):
        fresh_linker()
        docs = AddedDocs()
        try:
            sentences = {'es': ('Elefante', 'es', 'Un elefante camina.'), 'hi': ('हाथी', 'hi', 'हाथी जंगल में है।')}
            reports = {}
            for key in order:
                reports[key] = docs.add(key, *sentences[key])['semantic_links']
            assert all(r['terms_linked'] > 0 for r in reports.values()), reports

            found, data = docs.search('elefante')
            assert found == {'es', 'hi'}, (order, found)
            found, _ = docs.search('हाथी')
            assert found == {'es', 'hi'}, (order, found)
            found, data = docs.search('elephant')           # query word is in NO document
            assert found == {'es', 'hi'}, (order, found)
            hi_result = next(r for r in data['results'] if r['id'] == docs.ids['hi'])
            assert hi_result['matched_by_meaning'] == ['हाथी']
            assert hi_result['meaning_paths']['हाथी'] == 'elephant → हाथी'
        finally:
            docs.cleanup()


def test_inflected_sentence_links_to_other_language_lemma():
    fresh_linker()
    docs = AddedDocs()
    try:
        docs.add('en', 'Playful kittens', 'en', 'The kittens play outside.')
        docs.add('es', 'Los gatitos', 'es', 'Los gatitos juegan.')
        for query in ('gatito', 'kitten', 'kittens', 'gatitos'):
            found, _ = docs.search(query)
            assert found == {'en', 'es'}, (query, found)
        _, data = docs.search('gatito')
        en_result = next(r for r in data['results'] if r['id'] == docs.ids['en'])
        assert en_result['meaning_paths']['kittens'] == 'gatito → kitten → kittens'
    finally:
        docs.cleanup()


def test_polysemous_foreign_word_does_not_merge_garden_and_orchard():
    fresh_linker()
    docs = AddedDocs()
    try:
        docs.add('garden', 'Garden', 'en', 'A quiet garden.')
        docs.add('orchard', 'Orchard', 'en', 'An old orchard.')
        docs.add('ar', 'بستان', 'ar', 'بستان جميل')
        found, _ = docs.search('garden')
        assert found == {'garden', 'ar'}, found          # orchard is NOT dragged in through the Arabic word
        found, _ = docs.search('orchard')
        assert found == {'orchard', 'ar'}, found
    finally:
        docs.cleanup()


def test_search_waits_for_links_that_are_still_resolving():
    # Only the words inside the documents are slow; the query word 'elephant' resolves instantly, so the
    # documents can only be found if the search really waits for the background linking to finish.
    linker, _ = fresh_linker(delay=0.8, slow={'हाथी', 'elefante'})
    docs = AddedDocs()
    saved_deadline = semantic.LINK_DEADLINE_SECONDS
    semantic.LINK_DEADLINE_SECONDS = 0.01        # add_document returns long before the slow dictionary answers
    try:
        reports = [
            docs.add('hi', 'हाथी', 'hi', 'हाथी')['semantic_links'],
            docs.add('es', 'Elefante', 'es', 'elefante')['semantic_links'],
        ]
        assert all(r['terms_pending'] > 0 and r['terms_linked'] == 0 for r in reports), reports
        assert not linker.graph.is_resolved('elefante')      # nothing is linked yet ...
        found, _ = docs.search('elephant')                   # ... but the search blocks until it is, then sees it
        assert found == {'es', 'hi'}, found
        assert linker.graph.is_resolved('elefante')
    finally:
        semantic.LINK_DEADLINE_SECONDS = saved_deadline
        linker.wait_for_inflight()
        docs.cleanup()


def test_deadline_returns_early_and_background_work_completes():
    linker, _ = fresh_linker(delay=0.5)
    docs = AddedDocs()
    try:
        docs.add('seed', 'seed', 'en', 'zzseedword')
        index = app_module.global_index
        report = linker.link_document('elephant', 'elephant kitten', 'en', index, deadline=0.01)
        assert report['terms_pending'] > 0, report
        assert linker.wait_for_inflight(timeout=10) == 0
        assert linker.graph.is_resolved('elephant')
    finally:
        docs.cleanup()


def test_query_time_links_are_not_persisted():
    linker, _ = fresh_linker()
    docs = AddedDocs()
    try:
        docs.add('es', 'Elefante', 'es', 'elefante')
        before = linker.graph.get_stats()
        found, _ = docs.search('elephant')               # resolved live for this request only
        assert found == {'es'}
        assert linker.graph.get_stats() == before
        assert not linker.graph.is_resolved('elephant')
    finally:
        docs.cleanup()


def test_ranking_ties_do_not_depend_on_query_term_order():
    # Equal-score documents used to be ordered by the order the query terms were scored in, which comes from set
    # iteration and differs between processes; the top-k of a large tie therefore changed from run to run.
    from modules.index import InvertedIndex
    from modules.ranker import rank_documents
    index = InvertedIndex()
    index.add_document('3', 'alpha', metadata={'title': '', 'lang': 'en'})
    index.add_document('1', 'beta', metadata={'title': '', 'lang': 'en'})
    index.add_document('2', 'gamma', metadata={'title': '', 'lang': 'en'})
    index.add_document('10', 'alpha beta gamma delta', metadata={'title': '', 'lang': 'en'})
    forward = [d for d, _ in rank_documents(['alpha', 'beta', 'gamma'], index)]
    backward = [d for d, _ in rank_documents(['gamma', 'beta', 'alpha'], index)]
    assert forward == backward, (forward, backward)
    assert forward == ['10', '1', '2', '3'], forward      # best first, then ties by numeric document id


def test_known_dictionary_word_is_not_typo_corrected_but_real_typos_are():
    fresh_linker()
    docs = AddedDocs()
    try:
        docs.add('en', 'Kittens', 'en', 'The kittens play outside.')
        _, data = docs.search('kitten')         # 'kitten' is the lemma of the indexed 'kittens': a real word, not a typo
        assert data['corrected_query'] is None, data['corrected_query']
        assert data['query_terms'] == ['kitten']
        _, data = docs.search('kittenz')        # genuinely unknown: still corrected by Levenshtein
        assert data['corrected_query'] == 'kittens', data['corrected_query']
    finally:
        docs.cleanup()


def test_meaning_toggle_off_disables_expansion():
    fresh_linker()
    docs = AddedDocs()
    try:
        docs.add('es', 'Elefante', 'es', 'elefante')
        found, _ = docs.search('elephant', meaning='0')
        assert found == set()
    finally:
        docs.cleanup()


def test_failure_inside_meaning_expansion_degrades_instead_of_500():
    linker, _ = fresh_linker()
    docs = AddedDocs()
    original = linker.expand_query
    linker.expand_query = lambda *a, **k: (_ for _ in ()).throw(RuntimeError('unexpected bug'))
    try:
        docs.add('es', 'Elefante', 'es', 'elefante')
        client = app_module.app.test_client()
        res = client.get('/search', query_string={'q': 'elefante', 'meaning': 'true'})
        assert res.status_code == 200, res.status_code          # search still answers
        data = res.get_json()
        assert docs.ids['es'] in {r['id'] for r in data['results']}
        assert data['meaning_info']['meaning_terms'] == []
    finally:
        linker.expand_query = original
        docs.cleanup()


def test_dictionary_outage_does_not_break_search():
    def broken(term, preferred_lang=None):
        raise RuntimeError('wiktionary down')
    linker = SemanticLinker(MeaningGraph(None), resolver=broken)
    app_module.semantic_linker, app_module.meaning_graph = linker, linker.graph
    docs = AddedDocs()
    try:
        docs.add('es', 'Elefante', 'es', 'elefante')     # linking fails in the worker, add still succeeds
        found, data = docs.search('elefante')
        assert found == {'es'}                          # exact match still works
        assert data['meaning_info']['meaning_terms'] == []
    finally:
        docs.cleanup()


# ---------------------------------------------------------------------------------------------
# Wiktionary parsing + tokenizer
# ---------------------------------------------------------------------------------------------

ELEPHANT_WIKITEXT = """==English==
===Noun===
{{syn|en|elephantid|q1=zoology|q2=archaic}}
====Translations====
* Hindi: {{tt+|hi|हाथी|m}}, {{tt+|hi|हस्ती|m}}, {{tt+|hi|गज|m}}, {{tt+|hi|पील|m}}
* Spanish: {{tt+|es|elefante|m}}
* French: {{tt+|fr|éléphant|m}}
* Arabic: {{tt+|ar|فِيل|m}}
* German: {{t|de|Elefant}}
* Chinese: {{t|zh|[[大象]]}}
* Klingon: {{tt|tlh|ghIlab}}
==Spanish==
{{syn|es|paquidermo}}
* Other: {{t|es|noenglish}}
"""


def test_translation_templates_including_tooltip_variants():
    links = W._extract_wikitext_links(ELEPHANT_WIKITEXT, None, 'elephant')
    t = links['translations']
    assert 'हाथी' in t and 'elefante' in t and 'éléphant' in t        # {{tt+}} was missed by the old regex
    assert 'elefant' in t and '大象' in t                              # {{t}} and wiki-link markup
    assert 'فيل' in t and 'فِيل' not in t                              # Arabic vowel marks stripped
    assert 'ghilab' not in t and 'noenglish' not in t                # unsupported language / non-English section
    assert t.count('हाथी') == 1
    assert [x for x in t if x in ('हाथी', 'हस्ती', 'गज', 'पील')] == ['हाथी', 'हस्ती', 'गज']   # 3 per language cap


def test_named_template_parameters_are_not_synonyms():
    links = W._extract_wikitext_links(ELEPHANT_WIKITEXT, 'en', 'elephant')
    assert links['synonyms'] == ['elephantid'], links['synonyms']      # 'zoology' / 'archaic' were annotations
    # language unknown (a query word): synonyms of every supported language on the page are accepted
    assert W._extract_wikitext_links(ELEPHANT_WIKITEXT, None, 'elephant')['synonyms'] == ['elephantid', 'paquidermo']


def test_language_restricted_extraction():
    spanish = W._extract_wikitext_links(ELEPHANT_WIKITEXT, 'es', 'paquidermo')
    assert spanish['translations'] == []                              # translation tables only describe English words
    assert spanish['synonyms'] == []                                  # 'paquidermo' is the headword itself here
    assert W._extract_wikitext_links(ELEPHANT_WIKITEXT, 'es', 'elefante')['synonyms'] == ['paquidermo']


def test_inflection_root_parsing():
    parse = W.parse_inflection_root
    assert parse('plural of kitten') == 'kitten'
    assert parse('inflection of viajar: first-person singular present') == 'viajar'
    assert parse('nominative/accusative/genitive plural of Apfel') == 'apfel'
    assert parse('third-person singular simple present indicative of kitten') == 'kitten'
    assert parse('present participle and gerund of run') == 'run'
    assert parse('ellipsis of jardín delantero') is None
    assert parse('A young cat, especially before maturity') is None
    assert parse('Common, ordinary, domesticated.') is None
    assert parse('') is None


def test_title_variants_and_capitalised_german_noun(monkeypatch=None):
    assert W._title_variants('apfel') == ['apfel', 'Apfel']
    assert W._title_variants('हाथी') == ['हाथी']

    urls = []
    original = W._http_get_json

    def fake(url, timeout, attempts=2):
        urls.append(url)
        if url.endswith('/apfel'):
            return 'ok', {'gmh': [{'language': 'Middle High German', 'partOfSpeech': 'Noun',
                                   'definitions': [{'definition': 'apple'}]}]}
        if url.endswith('/Apfel'):
            return 'ok', {'de': [{'language': 'German', 'partOfSpeech': 'Noun',
                                  'definitions': [{'definition': 'apple (fruit)'}]}]}
        return 'missing', None

    W._http_get_json = fake
    W._wiktionary_cache.cache.clear()
    try:
        result = W.lookup_word('apfel', preferred_lang='de')
    finally:
        W._http_get_json = original
        W._wiktionary_cache.cache.clear()
    assert result['found'] and result['page_title'] == 'Apfel'
    assert {e['lang_code'] for e in result['entries']} == {'de', 'gmh'}
    assert len(urls) >= 2


def test_transient_lookup_failure_is_not_cached_and_does_not_fall_through():
    original = W._http_get_json
    calls = []

    def flaky(url, timeout, attempts=2):
        calls.append(url)
        if len(calls) == 1:
            return 'error', None
        if url.endswith('/kitten'):
            return 'ok', {'en': [{'language': 'English', 'partOfSpeech': 'Noun',
                                  'definitions': [{'definition': 'A young cat'}]}]}
        return 'missing', None

    W._http_get_json = flaky
    W._wiktionary_cache.cache.clear()
    try:
        first = W.lookup_word('kitten')
        assert not first['found'] and first['transient']
        assert not any(u.endswith('/Kitten') for u in calls), calls     # never answers from a different title
        second = W.lookup_word('kitten')                                 # retried, because nothing was cached
        assert second['found'] and not second['transient']
    finally:
        W._http_get_json = original
        W._wiktionary_cache.cache.clear()


def test_english_prose_definitions_and_later_senses_are_not_glosses():
    original = W.lookup_word
    W.lookup_word = lambda word, preferred_lang=None: {
        'found': True, 'word': word, 'page_title': word, 'cached': False,
        'wiktionary_url': 'u',
        'entries': [
            {'language': 'English', 'lang_code': 'en', 'part_of_speech': 'Adjective',
             'definitions': ['Common, ordinary, domesticated.']},
            {'language': 'German', 'lang_code': 'de', 'part_of_speech': 'Noun',
             'definitions': ['apple (fruit)', 'apple tree', 'breasts']},
        ]}
    orig_links = W.get_wikitext_links
    W.get_wikitext_links = lambda *a, **k: {'synonyms': [], 'translations': [], 'complete': True}
    try:
        info = W.extract_meaning_expansion('apfel')
    finally:
        W.lookup_word, W.get_wikitext_links = original, orig_links
    assert info['direct_glosses'] == ['apple'], info['direct_glosses']     # not 'common', 'ordinary', 'breasts'


def test_headword_with_its_own_meaning_is_not_treated_as_inflection():
    original = W.lookup_word
    W.lookup_word = lambda word, preferred_lang=None: {
        'found': True, 'word': word, 'page_title': word, 'cached': False, 'wiktionary_url': 'u',
        'entries': [
            {'language': 'French', 'lang_code': 'fr', 'part_of_speech': 'Noun', 'definitions': ['apple (fruit)']},
            {'language': 'French', 'lang_code': 'fr', 'part_of_speech': 'Verb',
             'definitions': ['first-person singular present indicative/subjunctive of pommer']},
        ]}
    orig_links = W.get_wikitext_links
    W.get_wikitext_links = lambda *a, **k: {'synonyms': [], 'translations': [], 'complete': True}
    try:
        info = W.extract_meaning_expansion('pomme', preferred_lang='fr')
    finally:
        W.lookup_word, W.get_wikitext_links = original, orig_links
    assert info['inflection_roots'] == [] and info['direct_glosses'] == ['apple']


def test_tokenizer_elision_danda_and_contractions():
    assert tokenize("L'éléphant boit de l'eau.") == ['éléphant', 'boit', 'de', 'eau']
    assert tokenize('l’éléphant') == ['éléphant']                         # typographic apostrophe
    assert tokenize('हाथी जंगल में है।') == ['हाथी', 'जंगल', 'में', 'है']        # danda no longer glued to the word
    assert tokenize('«bonjour», ¿qué?') == ['bonjour', 'qué']
    assert tokenize("don't it's o'clock") == ["don't", "it's", "o'clock"]  # English contractions untouched
    assert tokenize('Hello, World!') == ['hello', 'world']


# ---------------------------------------------------------------------------------------------

if __name__ == '__main__':
    tests = [(name, fn) for name, fn in sorted(globals().items()) if name.startswith('test_') and callable(fn)]
    failed = 0
    for name, fn in tests:
        started = time.time()
        try:
            fn()
            print(f"[PASS] {name} ({time.time() - started:.2f}s)")
        except Exception as exc:     # noqa: BLE001 - report every failure, not just the first
            failed += 1
            import traceback
            print(f"[FAIL] {name}: {exc!r}")
            traceback.print_exc()
    print(f"\n{len(tests) - failed}/{len(tests)} tests passed")
    sys.exit(1 if failed else 0)
