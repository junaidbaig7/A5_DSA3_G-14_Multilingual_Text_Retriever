"""
Audit: are word *meanings* linked up for sentences that are added on the spot?

Scenario under test (live Wiktionary, no curated synonym entries for any of the words below):
  1. Add fresh sentences in several languages through the real /add_document route.
  2. Search for the same concept in a *different* language / inflection and check that every
     document expressing that concept is returned - and that unrelated documents are not.
  3. Add one more sentence AFTER those searches and confirm it is picked up immediately.

Nothing is persisted: save_corpus() is stubbed out and the semantic store is redirected to a
temp directory, so data/corpus.json and data/semantic_links.json are never touched.

Run:  python audit_semantic_links.py
"""
import io
import os
import sys
import tempfile
import time

os.environ.setdefault('SEMANTIC_STORE_PATH', os.path.join(tempfile.mkdtemp(prefix='sem_audit_'), 'semantic_links.json'))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import app as app_module  # noqa: E402

app_module.save_corpus = lambda: None   # never write the real corpus
client = app_module.app.test_client()

# key -> (title, lang, text)
DOCS = {
    'kit_en':  ('Kitten on the sofa', 'en', 'The little kitten sleeps quietly on the sofa every afternoon.'),
    'kit_es':  ('Mi gatito',          'es', 'El gatito duerme en el sofá toda la tarde.'),
    'kits_en': ('Playful kittens',    'en', 'The kittens are playing with colorful toys in the garden.'),
    'kits_es': ('Los gatitos',        'es', 'Los gatitos juegan con juguetes de colores en el jardín.'),
    'ele_en':  ('Elephant safari',    'en', 'We saw a huge elephant near the river during our safari.'),
    'ele_es':  ('Elefante en la selva', 'es', 'Un elefante camina por la selva con su cría.'),
    'ele_hi':  ('हाथी का जंगल',        'hi', 'हाथी जंगल में नदी के किनारे घूम रहा है।'),
    'app_fr':  ('La pomme rouge',     'fr', 'La pomme est rouge et sucrée.'),
    'app_de':  ('Der Apfel',          'de', 'Der Apfel ist rot und süß.'),
    'app_en':  ('Apple orchard',      'en', 'She planted an apple tree behind the house.'),
}
LATE_DOCS = {   # added only after the first round of searches
    'ele_fr':  ("L'éléphant",         'fr', "L'éléphant boit de l'eau dans la rivière."),
}

KITTEN = {'kit_en', 'kit_es', 'kits_en', 'kits_es'}
ELEPHANT = {'ele_en', 'ele_es', 'ele_hi'}
APPLE = {'app_fr', 'app_de', 'app_en'}

# (query, expected doc keys). Anything else from DOCS returned for the query counts as leakage.
CASES = [
    ('kitten',   KITTEN), ('kittens', KITTEN), ('gatito', KITTEN), ('gatitos', KITTEN),
    ('elephant', ELEPHANT), ('elefante', ELEPHANT), ('हाथी', ELEPHANT),
    ('apple',    APPLE), ('pomme', APPLE), ('apfel', APPLE), ('manzana', APPLE),
    ('garden',   {'kits_en', 'kits_es'}), ('jardín', {'kits_en', 'kits_es'}),
    ('river',    {'ele_en', 'ele_hi'}), ('नदी', {'ele_en', 'ele_hi'}),
]
LATE_CASES = [
    ('elephant', ELEPHANT | {'ele_fr'}), ('elefante', ELEPHANT | {'ele_fr'}),
    ('हाथी', ELEPHANT | {'ele_fr'}),    ('éléphant', ELEPHANT | {'ele_fr'}),
]

id_to_key = {}


def add_doc(key, title, lang, text):
    t = time.time()
    res = client.post('/add_document', json={'title': title, 'lang': lang, 'text': text}).get_json()
    id_to_key[res['id']] = key
    return round(time.time() - t, 2), res


def run_case(query, expected, universe):
    t = time.time()
    data = client.get('/search', query_string={'q': query, 'limit': 50}).get_json()
    secs = round(time.time() - t, 2)
    got = {id_to_key[r['id']] for r in data['results'] if r['id'] in id_to_key}
    missing = sorted(expected - got)
    leaked = sorted((got & universe) - expected)
    return missing, leaked, secs


def run_round(title, cases, universe):
    print(f"\n{title}")
    print('-' * 100)
    ok_count = 0
    for query, expected in cases:
        missing, leaked, secs = run_case(query, expected, universe)
        ok = not missing and not leaked
        ok_count += ok
        detail = ''
        if missing:
            detail += f" MISSING={missing}"
        if leaked:
            detail += f" LEAKED={leaked}"
        print(f"[{'PASS' if ok else 'FAIL'}] {query:<10} expected {len(expected)} docs  ({secs}s){detail}")
    return ok_count, len(cases)


print('=' * 100)
print('SEMANTIC LINKING AUDIT - sentences added on the spot')
print('=' * 100)

print('\nAdding sentences through /add_document ...')
for key, (title, lang, text) in DOCS.items():
    secs, res = add_doc(key, title, lang, text)
    linked = res.get('semantic_links', {})
    extra = f" | linked {linked.get('terms_linked', 0)} terms, +{linked.get('edges_added', 0)} edges" if linked else ''
    print(f"  #{res['id']:<4}[{lang}] {title:<22} ({secs}s){extra}")

p1, n1 = run_round('ROUND 1 - cross-lingual / inflected meaning retrieval', CASES, set(DOCS))

print('\nAdding one more sentence AFTER the searches ...')
for key, (title, lang, text) in LATE_DOCS.items():
    secs, res = add_doc(key, title, lang, text)
    print(f"  #{res['id']:<4}[{lang}] {title:<22} ({secs}s)")

p2, n2 = run_round('ROUND 2 - late-added sentence must be reflected immediately', LATE_CASES, set(DOCS) | set(LATE_DOCS))

total, passed = n1 + n2, p1 + p2
print('\n' + '=' * 100)
print(f"SEMANTIC LINKING AUDIT: {passed}/{total} queries fully correct")
print('=' * 100)
sys.exit(0 if passed == total else 1)
