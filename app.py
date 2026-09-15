from flask import Flask, request, render_template, jsonify
import time
import json
import os
from modules.tokenizer import tokenize
from modules.index import InvertedIndex
from modules.matcher import find_closest_word
from modules.ranker import rank_documents
from modules.synonyms import synonym_graph
import re

app = Flask(__name__)

def highlight_text(text, terms):
    if not terms:
        return text
    terms = sorted(list(set(terms)), key=len, reverse=True)
    escaped_terms = [re.escape(t) for t in terms]
    pattern = re.compile(r'(' + '|'.join(escaped_terms) + r')', re.IGNORECASE)
    return pattern.sub(r'<mark>\1</mark>', text)

# Load and build index
def build_initial_index():
    index = InvertedIndex()
    corpus_path = os.path.join(os.path.dirname(__file__), 'data', 'corpus.json')
    if os.path.exists(corpus_path):
        with open(corpus_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            for doc in data:
                index.add_document(doc['id'], doc['text'], metadata={'title': doc['title'], 'lang': doc['lang']})
    return index

global_index = build_initial_index()

@app.route('/')
def index_page():
    return render_template('index.html')

@app.route('/search', methods=['GET'])
def search():
    query = request.args.get('q', '')
    lang_filter = request.args.get('lang', 'all')
        
    start_time = time.time()
    
    if not query:
        # Browse mode
        ranked_doc_ids = [(doc_id, 0) for doc_id in global_index.documents.keys()]
        ranked_doc_ids.sort(key=lambda x: int(x[0]))
        resolved_terms = []
        corrections = {}
        raw_terms = []
    else:
        # 1. Tokenize query
        raw_terms = tokenize(query)
        
        # 1b. Query Expansion (Cross-Lingual Synonyms)
        expanded_terms = set(raw_terms)
        for term in raw_terms:
            for syn in synonym_graph.get_synonyms(term):
                expanded_terms.add(syn)
        
        resolved_terms = []
        corrections = {}
        vocab_keys = list(global_index.index.keys())
        
        # 2. Exact match or fuzzy match fallback
        for term in expanded_terms:
            if term in global_index.index:
                resolved_terms.append(term)
            else:
                closest = find_closest_word(term, vocab_keys, max_distance=2)
                if closest:
                    resolved_terms.append(closest)
                    corrections[term] = closest
        
        # 3. TF-IDF Ranking
        ranked_doc_ids = rank_documents(resolved_terms, global_index)
    
    # Format results
    results = []
    for doc_id, score in ranked_doc_ids:
        doc_metadata = global_index.documents[doc_id]
        
        # Apply language filter
        if lang_filter != 'all' and doc_metadata['lang'] != lang_filter:
            continue
            
        text = doc_metadata['text']
        snippet = text[:150] + "..." if len(text) > 150 else text
        
        highlighted_title = highlight_text(doc_metadata['title'], resolved_terms)
        highlighted_snippet = highlight_text(snippet, resolved_terms)
        
        results.append({
            'id': doc_id,
            'title': highlighted_title,
            'lang': doc_metadata['lang'],
            'snippet': highlighted_snippet,
            'score': round(score, 4) if score > 0 else "N/A"
        })
        
        # Limit to 10 results for searches, 50 for browse mode
        limit = 10 if query else 50
        if len(results) >= limit:
            break
            
    latency_ms = (time.time() - start_time) * 1000
    
    corrected_query_str = None
    if corrections:
        corrected_query_str = " ".join([corrections.get(t, t) for t in raw_terms])
        
    return jsonify({
        'results': results,
        'latency': round(latency_ms, 2),
        'corrected_query': corrected_query_str
    })

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
    queries = ["chocolate", "tecnología", "बिरयानी", "travel"]
    
    # Indexed
    start = time.time()
    for q in queries:
        terms = tokenize(q)
        rank_documents(terms, global_index)
    idx_time = (time.time() - start) * 1000 / len(queries)
    
    # Naive
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
        "receipe": "recipe",      # english
        "tecnologia": "tecnología",# spanish (missing accent)
        "machne": "machine",      # english
        "paela": "paella"         # spanish
    }
    correct_count = 0
    for typo, target in test_typos.items():
        closest = find_closest_word(typo, vocab_keys, max_distance=2)
        if closest == target:
            correct_count += 1
            
    fuzzy_accuracy = (correct_count / len(test_typos)) * 100 if len(test_typos) > 0 else 0
    
    return jsonify({
        'build_times': build_times,
        'indexed_latency_ms': round(idx_time, 3),
        'naive_latency_ms': round(naive_time, 3),
        'fuzzy_accuracy_pct': round(fuzzy_accuracy, 1)
    })

if __name__ == '__main__':
    app.run(debug=True, port=5000)
