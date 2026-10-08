from flask import Flask, request, render_template, jsonify
import time
import json
import os
from modules.tokenizer import tokenize
from modules.index import InvertedIndex
from modules.matcher import find_closest_word, edit_distance, get_dp_matrix_details
from modules.ranker import rank_documents, rank_documents_with_breakdown
from modules.synonyms import synonym_graph
from modules.semantic import MeaningGraph, SemanticLinker

from modules.wiktionary import lookup_word, get_wiktionary_cache_stats
import re


app = Flask(__name__)

CORPUS_PATH = os.path.join(os.path.dirname(__file__), 'data', 'corpus.json')
# Learned meaning links persist across restarts (derived data, git-ignored). Tests/audits redirect it.
SEMANTIC_STORE_PATH = os.environ.get('SEMANTIC_STORE_PATH') or os.path.join(
    os.path.dirname(__file__), 'data', 'semantic_links.json')

meaning_graph = MeaningGraph(SEMANTIC_STORE_PATH)
semantic_linker = SemanticLinker(meaning_graph)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

WORD_CHAR_PATTERN = r'[\w\u0300-\u036f\u0600-\u06ff\u0750-\u077f\u08a0-\u08ff\u0900-\u0d7f]'

def get_highlight_pattern(terms):
    if not terms:
        return None
    cleaned_terms = [t.strip() for t in terms if t and t.strip()]
    if not cleaned_terms:
        return None
    unique_terms = sorted(list(set(cleaned_terms)), key=len, reverse=True)
    parts = []
    for t in unique_terms:
        esc = re.escape(t)
        # For CJK characters, word boundaries don't apply as words are not separated by whitespace
        if any('\u4e00' <= c <= '\u9fff' for c in t):
            parts.append(esc)
        else:
            parts.append(rf'(?<!{WORD_CHAR_PATTERN}){esc}(?!{WORD_CHAR_PATTERN})')
    return re.compile(r'(' + '|'.join(parts) + r')', re.IGNORECASE)


def highlight_text(text, terms_or_pattern):
    if not text or not terms_or_pattern:
        return text
    if isinstance(terms_or_pattern, re.Pattern):
        return terms_or_pattern.sub(r'<mark>\1</mark>', text)
    pattern = get_highlight_pattern(terms_or_pattern)
    if not pattern:
        return text
    return pattern.sub(r'<mark>\1</mark>', text)


def save_corpus():
    """Persist the in-memory index back to corpus.json."""
    docs = []
    for doc_id, meta in global_index.documents.items():
        docs.append({
            'id': doc_id,
            'title': meta.get('title', ''),
            'lang': meta.get('lang', 'en'),
            'text': meta.get('text', '')
        })
    # Sort numerically where possible, then alphabetically
    docs.sort(key=lambda x: int(x['id']) if x['id'].isdigit() else float('inf'))
    with open(CORPUS_PATH, 'w', encoding='utf-8') as f:
        json.dump(docs, f, ensure_ascii=False, indent=2)


def build_initial_index():
    index = InvertedIndex()
    if os.path.exists(CORPUS_PATH):
        with open(CORPUS_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
            for doc in data:
                index.add_document(
                    doc['id'], doc['text'],
                    metadata={'title': doc['title'], 'lang': doc['lang']}
                )
    return index


global_index = build_initial_index()

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route('/')
def index_page():
    return render_template('index.html')


def identify_scripts(text):
    scripts = set()
    for char in text:
        cp = ord(char)
        if (0x0041 <= cp <= 0x005A) or (0x0061 <= cp <= 0x007A):
            scripts.add('Latin')
        elif 0x0900 <= cp <= 0x097F:
            scripts.add('Devanagari')
        elif 0x0980 <= cp <= 0x09FF:
            scripts.add('Bengali-Assamese')
        elif 0x0A00 <= cp <= 0x0A7F:
            scripts.add('Gurmukhi')
        elif 0x0A80 <= cp <= 0x0AFF:
            scripts.add('Gujarati')
        elif 0x0B00 <= cp <= 0x0B7F:
            scripts.add('Odia')
        elif 0x0B80 <= cp <= 0x0BFF:
            scripts.add('Tamil')
        elif 0x0C00 <= cp <= 0x0C7F:
            scripts.add('Telugu')
        elif 0x0C80 <= cp <= 0x0CFF:
            scripts.add('Kannada')
        elif 0x0D00 <= cp <= 0x0D7F:
            scripts.add('Malayalam')
        elif 0x0600 <= cp <= 0x06FF:
            scripts.add('Arabic-Urdu')
        elif 0x4E00 <= cp <= 0x9FFF:
            scripts.add('Hanzi (CJK)')
    return sorted(list(scripts)) if scripts else ['General Script']


@app.route('/search', methods=['GET'])
def search():
    query = request.args.get('q', '').strip()
    lang_filter = request.args.get('lang', 'all')
    use_fuzzy = request.args.get('fuzzy', 'true').lower() in ('1', 'true', 'yes')
    use_synonyms = request.args.get('synonyms', 'true').lower() in ('1', 'true', 'yes')
    use_meaning = request.args.get('meaning', 'true').lower() in ('1', 'true', 'yes')
    limit_param = request.args.get('limit', '15')
    try:
        limit = int(limit_param)
    except ValueError:
        limit = 15

    start_time = time.time()

    if not query:
        # Browse mode — return all docs sorted by ID
        ranked_doc_ids = [(doc_id, 0.0) for doc_id in global_index.documents.keys()]
        ranked_doc_ids.sort(key=lambda x: int(x[0]) if x[0].isdigit() else float('inf'))
        resolved_search_terms = []
        corrections = {}
        raw_terms = []
        highlight_terms = []
        doc_breakdowns = {}
        term_stats = {}
        meaning_definitions = []
        wiktionary_meaning_terms = []
        meaning_expansions_by_word = {}
        meaning_nodes = {}
        execution_trace = {
            'mode': 'browse',
            'total_docs': global_index.total_docs,
            'stages': []
        }
    else:
        # Stage 1: Tokenize query
        s1_start = time.time()
        raw_terms = tokenize(query)
        detected_scripts = identify_scripts(query)
        s1_time = round((time.time() - s1_start) * 1000, 3)

        # Stage 2: Resolve query terms (exact match or DP Levenshtein fuzzy match)
        s2_start = time.time()
        resolved_search_terms = []
        corrections = {}
        vocab_keys = list(global_index.index.keys())
        pruned_comparisons = 0

        for term in raw_terms:
            if term in global_index.index:
                resolved_search_terms.append(term)
            elif term in synonym_graph.adj:
                # Term is a verified valid word across our 20-language synonym graph
                resolved_search_terms.append(term)
            elif use_meaning and meaning_graph.is_known_word(term):
                # The dictionary identified this word when documents were linked (e.g. 'kitten' as the lemma of
                # an indexed 'kittens'): it is a real word that merely is not an index token, so never "correct" it
                resolved_search_terms.append(term)
            elif use_fuzzy:
                # Count length pruning skipped
                pruned_comparisons += sum(1 for v in vocab_keys if abs(len(term) - len(v)) > 2)
                closest = find_closest_word(term, vocab_keys)
                if closest and closest != term:
                    resolved_search_terms.append(closest)
                    dist = edit_distance(term, closest)
                    corrections[term] = {'target': closest, 'distance': dist}
                else:
                    resolved_search_terms.append(term)
            else:
                resolved_search_terms.append(term)
        s2_time = round((time.time() - s2_start) * 1000, 3)

        # Stage 3: Meaning Graph Expansion. Words of every indexed document were linked to their lemma /
        # translations when the document was added (modules/semantic.py); here the query word is resolved
        # the same way (Wiktionary + O(1) LRU cache) and a 0-1 BFS finds every indexed word that shares its meaning.
        s3_meaning_start = time.time()
        meaning_definitions = []
        wiktionary_meaning_terms = []
        meaning_expansions_by_word = {}
        meaning_nodes = {}
        meaning_store_hits = 0

        if use_meaning:
            try:
                expansion = semantic_linker.expand_query(resolved_search_terms, global_index.index)
            except Exception:
                # Meaning expansion only enriches the exact / synonym stages: if it ever fails, answer without it
                app.logger.exception('Meaning graph expansion failed; continuing without meaning terms')
                expansion = {'definitions': [], 'expansions': {}, 'nodes': {}, 'store_hits': 0}
            meaning_definitions = expansion['definitions']
            meaning_expansions_by_word = expansion['expansions']
            meaning_nodes = expansion['nodes']
            meaning_store_hits = expansion['store_hits']
            wiktionary_meaning_terms = sorted(meaning_nodes, key=lambda n: (meaning_nodes[n]['cost'], n))
        s3_meaning_time = round((time.time() - s3_meaning_start) * 1000, 3)

        # Stage 4: Cross-lingual synonym expansion via Graph BFS
        s4_syn_start = time.time()
        ranking_terms = list(resolved_search_terms)
        term_weights = {t: 1.0 for t in resolved_search_terms}
        expansion_details = {}

        # Integrate meaning terms into candidate ranking terms; the weight falls with the number of meaning hops
        for mt in wiktionary_meaning_terms:
            if mt in global_index.index and mt not in ranking_terms:
                ranking_terms.append(mt)
                term_weights[mt] = meaning_nodes[mt]['weight']

        if use_synonyms:
            # Expand ONLY resolved search terms (DO NOT expand meaning terms into the synonym graph to prevent domain drift!)
            for term in resolved_search_terms:
                syns = synonym_graph.get_synonyms(term)
                indexed_syns = [s for s in syns if s in global_index.index and s not in ranking_terms]
                for s in indexed_syns:
                    ranking_terms.append(s)
                    if s not in term_weights:
                        term_weights[s] = 0.85
                if indexed_syns:
                    expansion_details[term] = indexed_syns
        s4_syn_time = round((time.time() - s4_syn_start) * 1000, 3)

        # Stage 5 & 6: Inverted index lookup & TF-IDF ranking with term weights and mathematical breakdown
        s5_rank_start = time.time()
        ranked_doc_ids, doc_breakdowns, term_stats = rank_documents_with_breakdown(
            ranking_terms, global_index, term_weights=term_weights
        )
        s5_rank_time = round((time.time() - s5_rank_start) * 1000, 3)

        execution_trace = {
            'mode': 'search',
            'total_docs': global_index.total_docs,
            'vocab_size': len(global_index.index),
            'scripts_detected': detected_scripts,
            'stages': [
                {
                    'id': 1,
                    'name': 'Unicode Tokenization & Normalization',
                    'dsa': 'Unicode Normalizer & Regex Boundary Scan',
                    'complexity': 'O(L) Time | O(L) Space',
                    'latency_ms': s1_time,
                    'details': f"Parsed {len(raw_terms)} tokens across scripts: {', '.join(detected_scripts)}",
                    'data': {'tokens': raw_terms, 'scripts': detected_scripts}
                },
                {
                    'id': 2,
                    'name': 'Dynamic Programming Typo Resolution',
                    'dsa': '2D Levenshtein Matrix with Length Pruning',
                    'complexity': 'O(V · m · n) Matrix | Δlen ≤ 2 Pruning',
                    'latency_ms': s2_time,
                    'details': f"Corrected {len(corrections)} typos against |V| = {len(vocab_keys)} vocabulary keys" if corrections else "Exact vocabulary matches verified",
                    'data': {'corrections': corrections, 'pruned_comparisons': pruned_comparisons, 'enabled': use_fuzzy}
                },
                {
                    'id': 3,
                    'name': 'Meaning Graph Expansion (Wiktionary)',
                    'dsa': '0-1 BFS on Meaning Graph (Deque) + In-Memory LRU Cache O(1)',
                    'complexity': 'O(V_m + E_m) BFS bounded to 2 meaning hops | O(1) Cache Hit',
                    'latency_ms': s3_meaning_time,
                    'details': f"Resolved meanings for {len(meaning_definitions)} words ({meaning_store_hits} from the learned graph); expanded {len(wiktionary_meaning_terms)} same-meaning terms",
                    'data': {
                        'definitions': meaning_definitions,
                        'meaning_terms': wiktionary_meaning_terms,
                        'expansions': meaning_expansions_by_word,
                        'paths': {n: ' → '.join(v['path']) for n, v in meaning_nodes.items()},
                        'enabled': use_meaning
                    }
                },
                {
                    'id': 4,
                    'name': 'Cross-Lingual Query Expansion',
                    'dsa': 'Graph BFS Traversal (Adjacency List + Queue)',
                    'complexity': 'O(V_g + E_g) BFS on 20 Languages',
                    'latency_ms': s4_syn_time,
                    'details': f"Expanded active seeds into {len(ranking_terms)} multilingual active terms",
                    'data': {'seed_terms': resolved_search_terms, 'expansions': expansion_details, 'enabled': use_synonyms}
                },
                {
                    'id': 5,
                    'name': 'Inverted Index & Postings Traversal',
                    'dsa': 'Hash Map Term-to-Postings Lookup',
                    'complexity': 'O(1) Avg Hash Lookup per Term',
                    'latency_ms': s5_rank_time,
                    'details': f"Retrieved postings across {len(ranking_terms)} query & meaning terms",
                    'data': {'active_terms': ranking_terms, 'term_stats': term_stats}
                },
                {
                    'id': 6,
                    'name': 'Weighted TF-IDF Relevance Scoring',
                    'dsa': 'Semantic Vector Weight Accumulator & QuickSort',
                    'complexity': 'O(Q · D) Score Accumulation + O(R log R) Rank Sort',
                    'latency_ms': s5_rank_time,
                    'details': f"Scored {len(ranked_doc_ids)} candidate documents with weighted TF-IDF",
                    'data': {
                        'matched_docs': len(ranked_doc_ids),
                        'top_score': round(ranked_doc_ids[0][1], 4) if ranked_doc_ids else 0.0
                    }
                }
            ]
        }

        highlight_terms = []
        for t in raw_terms + resolved_search_terms:
            if t and t not in highlight_terms:
                highlight_terms.append(t)
        for mt in wiktionary_meaning_terms:
            if mt and mt not in highlight_terms:
                highlight_terms.append(mt)
        if use_synonyms:
            for term in list(highlight_terms):
                for syn in synonym_graph.get_synonyms(term):
                    if syn and syn not in highlight_terms:
                        highlight_terms.append(syn)

    # Build result list
    results = []
    max_score = ranked_doc_ids[0][1] if ranked_doc_ids and ranked_doc_ids[0][1] > 0 else 1.0
    highlight_pattern = get_highlight_pattern(highlight_terms)

    for doc_id, score in ranked_doc_ids:
        doc_metadata = global_index.documents[doc_id]

        if lang_filter != 'all' and doc_metadata['lang'] != lang_filter:
            continue

        text = doc_metadata['text']
        snippet = text[:190] + '...' if len(text) > 190 else text

        highlighted_title   = highlight_text(doc_metadata['title'], highlight_pattern)
        highlighted_snippet = highlight_text(snippet, highlight_pattern)

        breakdown = doc_breakdowns.get(doc_id, [])
        score_val = round(score, 4) if score > 0 else 'N/A'
        rel_percent = round((score / max_score) * 100, 1) if (score > 0 and max_score > 0) else 0

        # Discern which terms matched by exact query vs Wiktionary meaning vs synonym graph
        doc_matched_terms = [b['term'] for b in breakdown]
        matched_by_exact = [t for t in doc_matched_terms if t in resolved_search_terms]
        matched_by_meaning = [t for t in doc_matched_terms if t in wiktionary_meaning_terms and t not in resolved_search_terms]
        matched_by_synonym = [t for t in doc_matched_terms if t not in resolved_search_terms and t not in wiktionary_meaning_terms]

        results.append({
            'id':                  doc_id,
            'title':               highlighted_title,
            'lang':                doc_metadata['lang'],
            'snippet':             highlighted_snippet,
            'score':               score_val,
            'relative_score_pct':  rel_percent,
            'breakdown':           breakdown,
            'doc_length':          global_index.doc_lengths.get(doc_id, 0),
            'matched_by_exact':    matched_by_exact,
            'matched_by_meaning':  matched_by_meaning,
            'matched_by_synonym':  matched_by_synonym,
            # How each meaning match connects back to the query, e.g. "हाथी → elephant → elefante"
            'meaning_paths':       {t: ' → '.join(meaning_nodes[t]['path']) for t in matched_by_meaning if t in meaning_nodes}
        })

        if len(results) >= limit:
            break

    latency_ms = (time.time() - start_time) * 1000

    corrected_query_str = None
    if corrections:
        corrected_query_str = ' '.join([
            corrections[t]['target'] if t in corrections else t
            for t in raw_terms
        ])

    return jsonify({
        'results':          results,
        'latency':          round(latency_ms, 2),
        'corrected_query':  corrected_query_str,
        'query_terms':      resolved_search_terms,
        'highlight_terms':  highlight_terms,
        'execution_trace':  execution_trace,
        'term_stats':       term_stats,
        'meaning_info': {
            'enabled':         use_meaning,
            'definitions':     meaning_definitions,
            'meaning_terms':   wiktionary_meaning_terms,
            'expansions':      meaning_expansions_by_word,
            'paths':           {n: ' → '.join(v['path']) for n, v in meaning_nodes.items()}
        }
    })



@app.route('/api/define/<path:word>', methods=['GET'])
def define_word(word):
    """
    Look up word definitions in Wiktionary.
    Supports ?lang=<lang_code> to prioritize or filter by language.
    """
    lang = request.args.get('lang', None)
    if lang == 'all':
        lang = None
    result = lookup_word(word, preferred_lang=lang)
    return jsonify(result)


@app.route('/add_document', methods=['POST'])
def add_document():
    data = request.get_json(force=True)
    title = (data.get('title') or '').strip()
    lang  = (data.get('lang')  or 'en').strip()
    text  = (data.get('text')  or '').strip()

    if not title or not text:
        return jsonify({'error': 'Title and text are required.'}), 400

    # Generate a new numeric ID one above the current max
    existing_numeric = [int(k) for k in global_index.documents.keys() if k.isdigit()]
    new_id = str(max(existing_numeric) + 1) if existing_numeric else '1'

    global_index.add_document(new_id, text, metadata={'title': title, 'lang': lang})
    save_corpus()

    # Link the meaning of the document's words right away so the very next search already reflects it
    semantic_report = semantic_linker.link_document(title, text, lang, global_index)

    return jsonify({'success': True, 'id': new_id, 'title': title, 'lang': lang, 'semantic_links': semantic_report})


@app.route('/delete_document/<doc_id>', methods=['DELETE'])
def delete_document(doc_id):
    success = global_index.delete_document(doc_id)
    if success:
        save_corpus()
        return jsonify({'success': True})
    return jsonify({'error': 'Document not found.'}), 404


@app.route('/benchmark')
def benchmark_page():
    return render_template('benchmark.html')


@app.route('/api/run_benchmark')
def run_benchmark():
    base_docs = list(global_index.documents.values())

    # 1. Index build time scaling
    build_times = []
    sizes = [20, 200, 2000]
    for size in sizes:
        docs = (base_docs * (size // len(base_docs) + 1))[:size]
        start = time.time()
        idx = InvertedIndex()
        for i, doc in enumerate(docs):
            idx.add_document(str(i), doc['text'], {'title': doc['title'], 'lang': doc['lang']})
        t = (time.time() - start) * 1000
        build_times.append({'size': size, 'time_ms': round(t, 2)})

    # 2. Indexed vs Naive
    queries = ['chocolate', 'tecnología', 'बिरयानी', 'travel', 'ai', 'স্মার্টফোন']

    start = time.time()
    for q in queries:
        terms = tokenize(q)
        rank_documents(terms, global_index)
    idx_time = (time.time() - start) * 1000 / len(queries)

    def naive_search(query_terms, docs):
        results = []
        for i, doc in docs.items():
            text_tokens = tokenize(doc['text'])
            score = sum(1 for t in query_terms if t in text_tokens)
            if score > 0:
                results.append((i, score))
        return results

    start = time.time()
    for q in queries:
        terms = tokenize(q)
        naive_search(terms, global_index.documents)
    naive_time = (time.time() - start) * 1000 / len(queries)

    # 3. Fuzzy match accuracy
    vocab_keys = list(global_index.index.keys())
    test_typos = {
        'receipe':    'recipe',
        'tecnologia': 'tecnología',
        'machne':     'machine',
        'paela':      'paella'
    }
    correct_count = 0
    for typo, target in test_typos.items():
        closest = find_closest_word(typo, vocab_keys, max_distance=2)
        if closest == target:
            correct_count += 1

    fuzzy_accuracy = (correct_count / len(test_typos)) * 100 if test_typos else 0

    return jsonify({
        'build_times':         build_times,
        'indexed_latency_ms':  round(idx_time, 3),
        'naive_latency_ms':    round(naive_time, 3),
        'fuzzy_accuracy_pct':  round(fuzzy_accuracy, 1)
    })


# ---------------------------------------------------------------------------
# Interactive DSA Laboratory & Analytics APIs
# ---------------------------------------------------------------------------

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Returns comprehensive real-time system telemetry across all data structures."""
    index_stats = global_index.get_stats()
    graph_stats = synonym_graph.get_graph_stats()
    cache_stats = get_wiktionary_cache_stats()
    return jsonify({
        'status': 'online',
        'engine_version': '3.2-PRO',
        'index': index_stats,
        'graph': graph_stats,
        'meaning_graph': meaning_graph.get_stats(),
        'cache': cache_stats
    })


@app.route('/api/trie/prefix', methods=['GET'])
def trie_prefix():
    """
    Queries the in-memory Trie prefix tree.
    Time Complexity: O(L + K) where L = len(prefix), K = matches in subtree.
    """
    prefix = request.args.get('prefix', '').strip().lower()
    start = time.time()
    if not prefix:
        return jsonify({
            'prefix': '',
            'matches': [],
            'count': 0,
            'nodes_visited': 0,
            'latency_ms': 0.0,
            'tree': None
        })

    words, visited = global_index.vocabulary.get_words_with_prefix(prefix, limit=60)
    tree_struct = global_index.vocabulary.get_tree_structure(prefix, max_depth=3, max_branches=6)
    latency_ms = round((time.time() - start) * 1000, 3)

    return jsonify({
        'prefix': prefix,
        'matches': words,
        'count': len(words),
        'nodes_visited': visited,
        'latency_ms': latency_ms,
        'tree': tree_struct
    })


@app.route('/api/dp/matrix', methods=['GET'])
def dp_matrix():
    """
    Generates the complete 2D Dynamic Programming Levenshtein table
    with optimal alignment traceback.
    Time Complexity: O(m * n)
    """
    w1 = request.args.get('w1', '').strip()
    w2 = request.args.get('w2', '').strip()
    if not w1 or not w2:
        return jsonify({'error': 'Both w1 and w2 parameters are required.'}), 400

    details = get_dp_matrix_details(w1, w2)
    return jsonify(details)


@app.route('/api/graph/cluster', methods=['GET'])
def graph_cluster():
    """
    Returns the BFS exploration trace and multilingual adjacency cluster
    for a given concept seed word across 20 languages.
    Time Complexity: O(V_g + E_g)
    """
    word = request.args.get('word', '').strip().lower()
    if not word:
        return jsonify({'error': 'word parameter is required.'}), 400

    details = synonym_graph.get_cluster_with_steps(word)
    return jsonify(details)


@app.route('/api/graph/clusters', methods=['GET'])
def graph_clusters():
    """Returns available cluster head seeds in the synonym graph."""
    heads = synonym_graph.get_all_cluster_heads()
    return jsonify({'clusters': heads, 'count': len(heads)})


@app.route('/api/index/term/<path:term>', methods=['GET'])
def index_term(term):
    """
    Inspects inverted index posting lists and document frequency for a given term.
    Time Complexity: O(1) Hash Map lookup.
    """
    term = term.strip().lower()
    details = global_index.get_term_details(term)
    return jsonify(details)


@app.route('/api/corpus', methods=['GET'])
def get_corpus():
    """Returns documents catalog for the Corpus Management table."""
    docs = []
    for doc_id, meta in global_index.documents.items():
        text = meta.get('text', '')
        docs.append({
            'id': doc_id,
            'title': meta.get('title', ''),
            'lang': meta.get('lang', 'en'),
            'text': text,
            'word_count': global_index.doc_lengths.get(doc_id, len(text.split())),
            'snippet': (text[:160] + '...') if len(text) > 160 else text
        })
    docs.sort(key=lambda x: int(x['id']) if x['id'].isdigit() else float('inf'))
    return jsonify({'documents': docs, 'total': len(docs)})


if __name__ == '__main__':
    app.run(debug=True, port=5000)

