# Multilingual Intelligent Text Retrieval System

A web-based demo of a search engine implemented from scratch using classical Data Structures & Algorithms, without relying on machine learning or heavy NLP libraries. 

This project proves that classical DSA can achieve fast, multilingual, typo-tolerant search in a lightweight pipeline.

## Features & Methodology

The system is highly modular, breaking down the search pipeline into swappable components.

### 1. Unified Multilingual Index & Fuzzy Matching
- **Inverted Index (`modules/index.py`)**: A single shared index covers all documents across English, Spanish, and Hindi. It explicitly avoids per-language siloed indexes. 
- **Edit Distance Fallback (`modules/matcher.py`)**: If an exact match isn't found in the index, a Levenshtein dynamic programming algorithm (O(m*n)) fuzzy-matches the query against the vocabulary to find the closest match.
- **TF-IDF Ranking (`modules/ranker.py`)**: Scores matching documents by evaluating term frequency and inverse document frequency, returning ranked top-k results.

### 2. Adaptability (Swappable Tokenizer)
- **Tokenizer (`modules/tokenizer.py`)**: A language-agnostic tokenizer that uses Unicode-aware regex (`\w+` with `re.UNICODE`) to split words. Adding support for a new language requires **only** touching the tokenizer, completely decoupled from the indexer or matcher.

### 3. Methodology Evaluation
- **Benchmark Route (`/benchmark`)**: An interactive evaluation page that measures empirical performance:
  - **Index Build Time**: Demonstrates time complexity as the corpus size grows.
  - **Query Latency**: A head-to-head performance comparison of the indexed lookup against a naive linear scan over the same corpus.
  - **Fuzzy-Match Accuracy**: Measures resolution accuracy on queries with deliberate typos.

### 4. Accessibility
- No external NLP/ML dependencies.
- Relies only on Flask for the web server, ensuring a single-command setup.

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
