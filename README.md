# Multilingual Intelligent Text Retrieval System

A web-based demo of a search engine implemented from scratch using classical Data Structures & Algorithms, without relying on machine learning or heavy NLP libraries. 

This project proves that classical DSA can achieve fast, multilingual, typo-tolerant search in a lightweight pipeline.

> 📖 **Full System Context & DSA Guide**: See [`CONTEXT.md`](CONTEXT.md) for in-depth architecture diagrams, complete DSA maps with complexities, and API documentation.

## Features & Methodology

The system is highly modular, breaking down the search pipeline into swappable components.

### 1. Unified Multilingual Index & Fuzzy Matching
- **Inverted Index (`modules/index.py`)**: A single shared index covers all documents across English, Spanish, and Hindi. It explicitly avoids per-language siloed indexes. 
- **Edit Distance Fallback (`modules/matcher.py`)**: If an exact match isn't found in the index, a Levenshtein dynamic programming algorithm (O(m*n)) fuzzy-matches the query against the vocabulary to find the closest match.
- **TF-IDF Ranking (`modules/ranker.py`)**: Scores matching documents by evaluating term frequency and inverse document frequency, returning ranked top-k results.

### 2. Wiktionary Meaning-Based Semantic Retrieval & LRU Caching
- **Meaning Search (`modules/wiktionary.py`)**: Seamlessly integrated with Wikimedia's Wiktionary API to search the *meaning* of words. When a user queries a term, the engine extracts definitions, direct glosses, root forms, and thesaurus synonyms, then retrieves all documents in any language that share that same meaning (e.g. searching *automobile* retrieves documents about *cars*; searching *receta* retrieves English *recipes*).
- **LRU Cache ($O(1)$)**: Employs an in-memory Least Recently Used cache to memoize API responses, ensuring repeat lookups execute in $< 1\text{ ms}$.
- **Dynamic Meaning Graph (`modules/semantic.py`)**: Documents added at runtime are linked on the spot. When you add a sentence, every content word is resolved through Wiktionary and linked to its lemma (*kittens* — *kitten*) and its translations (*kitten* — *gatito*) in a persistent, undirected graph (`data/semantic_links.json`). Searches expand with a 0-1 BFS over that graph, so *हाथी*, *elephant* and *elefante* find each other regardless of which sentence was added first. A second hop may only pivot on the English headword, which stops polysemous words (Arabic *bustān* = garden **and** orchard) from merging unrelated concepts.
- **Interactive Meaning UI**: Displays a Wiktionary Meaning Search banner, visual tags indicating why a document was matched (`Matched Meaning: "recipe"`), and a dedicated "Define Word" lookup modal.

### 3. Adaptability (Swappable Tokenizer)
- **Tokenizer (`modules/tokenizer.py`)**: A language-agnostic tokenizer that uses Unicode-aware regex (`\w+` with `re.UNICODE`) to split words. Adding support for a new language requires **only** touching the tokenizer, completely decoupled from the indexer or matcher.

### 4. Methodology Evaluation
- **Benchmark Route (`/benchmark`)**: An interactive evaluation page that measures empirical performance:
  - **Index Build Time**: Demonstrates time complexity as the corpus size grows.
  - **Query Latency**: A head-to-head performance comparison of the indexed lookup against a naive linear scan over the same corpus.
  - **Fuzzy-Match Accuracy**: Measures resolution accuracy on queries with deliberate typos.

### 5. Accessibility
- No external NLP/ML dependencies.
- Relies only on Flask for the web server, ensuring a single-command setup.

### 6. Verification
- `python test_semantic_graph.py` — offline tests of the meaning graph (fake dictionary, no network).
- `python audit_semantic_links.py` — live end-to-end audit: adds fresh multilingual sentences and checks cross-lingual, inflected and late-added matches.
- `python audit_suite.py` and `python test_pipeline.py` — the existing semantic/DSA audit and pipeline smoke test.

## How to Run

1. Ensure you have Python installed.
2. Install the single dependency (Flask):
   ```bash
   pip install -r requirements.txt
   ```
3. Run the application:
   ```bash
   python app.py
   ```
4. Open your browser and navigate to `http://localhost:5000` to interact with the search UI.
5. Go to `http://localhost:5000/benchmark` to view the methodology evaluation.
