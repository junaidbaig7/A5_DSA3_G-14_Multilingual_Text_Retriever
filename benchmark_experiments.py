"""
Reproduces the performance and accuracy measurements reported in the project documentation:

  1. index build time against collection size
  2. indexed query latency against a naive linear scan
  3. typo-correction accuracy by query length, and the effect of length pruning
  4. graph traversal time (curated BFS, synthetic meaning-graph 0-1 BFS)

The first 112 documents of data/corpus.json are the seed corpus; documents added later are ignored so the
numbers stay comparable. Nothing is written to disk.

Absolute timings depend on machine load and can differ by a factor of two or more between runs, so the report
uses the median of several runs; the speed-up ratios and the seeded typo counts are the stable results.

Run:  python benchmark_experiments.py            (human-readable)
      python benchmark_experiments.py --json     (one JSON line, for aggregating several runs)
"""
import json
import os
import random
import statistics as st
import sys
import time

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from modules.index import InvertedIndex
from modules.matcher import edit_distance, find_closest_word
from modules.ranker import rank_documents
from modules.semantic import MeaningGraph
from modules.synonyms import synonym_graph
from modules.tokenizer import tokenize

SEED_DOCS = 112
JSON_MODE = '--json' in sys.argv
RESULT = {'build': [], 'query': [], 'typo': [], 'prune': {}, 'curated': {}, 'expand': []}
CORPUS = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'corpus.json')
docs = sorted(json.load(open(CORPUS, encoding='utf-8')), key=lambda d: int(d['id']) if str(d['id']).isdigit() else 10**9)
docs = docs[:SEED_DOCS]


def build(n):
    index = InvertedIndex()
    for i in range(n):
        d = docs[i % len(docs)]
        index.add_document(str(i), d['text'], {'title': d['title'], 'lang': d['lang']})
    return index


def say(text):
    if not JSON_MODE:
        print(text)


def section(title):
    say('\n' + title)
    say('-' * len(title))


base = build(len(docs))
stats = base.get_stats()
say('Seed corpus: %d documents, %d languages, %d terms, %d postings, %.1f tokens per document'
    % (len(docs), stats['languages_count'], stats['vocab_size'], stats['total_postings'], stats['avg_doc_length']))

# 1. index build time ------------------------------------------------------------------------------------------
section('1. Index build time (median of 3, ms)')
for n in (112, 1000, 5000, 10000, 20000):
    times = []
    for _ in range(3):
        started = time.perf_counter()
        build(n)
        times.append((time.perf_counter() - started) * 1000)
    RESULT['build'].append({'n': n, 'ms': st.median(times)})
    say('  %6d documents: %8.1f ms' % (n, st.median(times)))

# 2. indexed vs naive query latency --------------------------------------------------------------------------
section('2. Mean query latency over 6 queries: inverted index vs naive scan (ms)')
queries = ['chocolate', 'travel', 'recipe', 'technology', 'बिरयानी', 'স্মার্টফোন']
for n in (112, 1000, 5000, 10000):
    index = build(n)

    def naive(query):
        terms = tokenize(query)
        hits = []
        for doc_id, d in index.documents.items():
            tokens = tokenize(d['title'] + ' ' + d['text'])
            score = sum(1 for t in terms if t in tokens)
            if score:
                hits.append((doc_id, score))
        return hits

    indexed_ms, naive_ms = [], []
    for q in queries:
        terms = tokenize(q)
        started = time.perf_counter()
        for _ in range(300):
            rank_documents(terms, index)
        indexed_ms.append((time.perf_counter() - started) * 1000 / 300)
        reps = 5 if n >= 5000 else 20
        started = time.perf_counter()
        for _ in range(reps):
            naive(q)
        naive_ms.append((time.perf_counter() - started) * 1000 / reps)
    RESULT['query'].append({'n': n, 'indexed_ms': st.mean(indexed_ms), 'naive_ms': st.mean(naive_ms)})
    say('  %6d documents: indexed %8.4f ms | naive %9.3f ms | %4.0fx faster'
        % (n, st.mean(indexed_ms), st.mean(naive_ms), st.mean(naive_ms) / st.mean(indexed_ms)))

# 3. typo correction ----------------------------------------------------------------------------------------------
section('3. Typo correction by query length (250 random single-edit typos per class)')
vocab = list(base.index.keys())
latin = [w for w in vocab if w.isascii() and w.isalpha() and len(w) >= 3]
rng = random.Random(7)
alphabet = 'abcdefghijklmnopqrstuvwxyz'


def mutate(word):
    kind = rng.choice(['sub', 'del', 'ins'])
    i = rng.randrange(len(word))
    if kind == 'sub':
        return word[:i] + rng.choice([a for a in alphabet if a != word[i]]) + word[i + 1:]
    if kind == 'del':
        return word[:i] + word[i + 1:]
    return word[:i] + rng.choice(alphabet) + word[i:]


def length_class(n):
    return 'up to 3 letters' if n <= 3 else ('4-5 letters' if n <= 5 else '6 letters or more')


pool = []
for _ in range(6000):
    word = rng.choice(latin)
    typo = mutate(word)
    if typo and typo not in base.index and typo.isalpha():
        pool.append((word, typo))
by_class = {}
for word, typo in pool:
    group = by_class.setdefault(length_class(len(typo)), [])
    if len(group) < 250:
        group.append((word, typo))
for name in ('up to 3 letters', '4-5 letters', '6 letters or more'):
    group = by_class[name]
    corrected = recovered = 0
    times = []
    for word, typo in group:
        started = time.perf_counter()
        got = find_closest_word(typo, vocab)
        times.append((time.perf_counter() - started) * 1000)
        corrected += got is not None
        recovered += got == word
    RESULT['typo'].append({'class': name, 'tested': len(group), 'corrected': corrected, 'recovered': recovered,
                           'ms': st.mean(times)})
    say('  %-18s corrected %3d/%d | original recovered %3d (%.1f%%) | %.2f ms per query'
        % (name, corrected, len(group), recovered, 100.0 * recovered / len(group), st.mean(times)))

long_typos = [typo for _, typo in by_class['6 letters or more']][:100]


def closest_without_pruning(word, vocabulary, max_distance=2):
    best, best_distance = None, 10 ** 9
    for candidate in vocabulary:
        distance = edit_distance(word, candidate)
        if distance <= max_distance and distance < best_distance:
            best, best_distance = candidate, distance
    return best


started = time.perf_counter()
for typo in long_typos:
    closest_without_pruning(typo, vocab)
without_ms = (time.perf_counter() - started) * 1000 / len(long_typos)
started = time.perf_counter()
for typo in long_typos:
    find_closest_word(typo, vocab)
with_ms = (time.perf_counter() - started) * 1000 / len(long_typos)
skipped = sum(sum(1 for v in vocab if abs(len(t) - len(v)) > 2) for t in long_typos) / (len(long_typos) * len(vocab))
RESULT['prune'] = {'without_ms': without_ms, 'with_ms': with_ms, 'skipped_pct': 100 * skipped}
say('  length pruning (100 typos of 6+ letters): %.1f ms without, %.1f ms with (%.1fx faster); %.1f%% of comparisons skipped'
    % (without_ms, with_ms, without_ms / with_ms, 100 * skipped))

# 4. graph traversal -----------------------------------------------------------------------------------------------
section('4. Graph traversal')
graph_stats = synonym_graph.get_graph_stats()
timings = []
for word in ['car', 'chocolate', 'travel', 'recipe', 'water', 'teacher']:
    started = time.perf_counter()
    for _ in range(2000):
        synonym_graph.get_synonyms(word)
    timings.append((time.perf_counter() - started) * 1e6 / 2000)
RESULT['curated'] = {'nodes': graph_stats['total_nodes'], 'edges': graph_stats['total_edges'], 'us': st.mean(timings)}
say('  curated SynonymGraph (%d nodes, %d edges): BFS %.1f us on average (car cluster: %d words)'
    % (graph_stats['total_nodes'], graph_stats['total_edges'], st.mean(timings), len(synonym_graph.get_synonyms('car'))))
for hubs in (200, 2000, 20000):
    graph = MeaningGraph(None)
    r = random.Random(1)
    for h in range(hubs):
        for k in range(8):
            graph.add_link('w%d_%d' % (h, k), 'hub%d' % h, 1, hub='hub%d' % h)
        if h:
            graph.add_link('hub%d' % h, 'hub%d' % r.randrange(h), 1, hub=None)
    sizes = graph.get_stats()
    started = time.perf_counter()
    for i in range(200):
        graph.expand('w%d_0' % ((i * 7) % hubs))
    micros = (time.perf_counter() - started) * 1e6 / 200
    RESULT['expand'].append({'nodes': sizes['total_nodes'], 'edges': sizes['total_edges'], 'us': micros})
    say('  MeaningGraph (%d nodes, %d edges): 0-1 BFS %.1f us per expansion' % (sizes['total_nodes'], sizes['total_edges'], micros))

if JSON_MODE:
    print(json.dumps(RESULT))
