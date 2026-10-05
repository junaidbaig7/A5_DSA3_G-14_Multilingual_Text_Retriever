# Project Context: Multilingual Intelligent Text Retriever

## 1. Project Overview
The **Multilingual Intelligent Text Retriever** is a lightweight, high-performance search engine built strictly using classical **Data Structures & Algorithms (DSA)** in Python and Flask. It avoids external machine learning (ML), neural embeddings, or heavy natural language processing (NLP) libraries.

The project demonstrates how foundational computer science techniques—such as Inverted Indexes, Tries, Graph BFS, Dynamic Programming, and TF-IDF weighting—can deliver fast, multilingual, cross-lingual, and typo-tolerant search across **20 languages**.

---

## 2. Supported Languages (20 Total)

The search engine indexes and cross-retrieves documents across 20 languages, partitioned into 13 Indian languages and 7 global languages:

| Category | Languages & Codes |
|---|---|
| **13 Indian Languages** | Hindi (`hi`), Bengali (`bn`), Telugu (`te`), Marathi (`mr`), Tamil (`ta`), Urdu (`ur`), Gujarati (`gu`), Kannada (`kn`), Malayalam (`ml`), Odia (`or`), Punjabi (`pa`), Assamese (`as`), Sanskrit (`sa`) |
| **7 Global Languages** | English (`en`), Spanish (`es`), French (`fr`), German (`de`), Portuguese (`pt`), Arabic (`ar`), Chinese (`zh`) |

---

## 3. System Architecture & Query Pipeline

```
                       User Search Query (e.g., "receta" or "automobile")
                                       │
                                       ▼
                       [Tokenizer (modules/tokenizer.py)]
                                       │
                                       ▼
                  [Exact Match vs. DP Levenshtein Fuzzy Correction]
                        (modules/index.py & modules/matcher.py)
                                       │
                                       ▼
                [Wiktionary Semantic Meaning Lookup & Expansion]
                     (modules/wiktionary.py - LRU Cache O(1))
         Extracts definitions, direct glosses, roots, & thesaurus synonyms
                                       │
                                       ▼
                    [SynonymGraph (modules/synonyms.py)]
                  BFS Graph Expansion across 20 Languages
                                       │
                                       ▼
                [Semantic Weighted TF-IDF Ranker (modules/ranker.py)]
          Scores exact (1.0), synonyms (0.85), & meaning terms (0.80)
                                       │
                                       ▼
                  [Snippet Highlighting & Reason Match Badges]
                                       │
                                       ▼
                            Web UI (Browser Rendering)
```

### Search Pipeline Steps:
1. **Tokenization**: Input text is normalized to lowercase and stripped of punctuation while preserving Unicode combining characters (matras, vowel signs, non-Latin scripts).
2. **Lookup & Fuzzy Correction**: Query tokens are matched against the Inverted Index dictionary. If a word is missing, Levenshtein edit distance (Dynamic Programming) finds the closest vocabulary term within `max_distance=2`.
3. **Wiktionary Meaning Search & Semantic Expansion**:
   - Queries the official Wiktionary REST API with in-memory LRU caching.
   - Extracts semantic headword definitions, direct glosses (e.g. *receta* $\rightarrow$ *recipe*, *agua* $\rightarrow$ *water*), and thesaurus synonyms (e.g. *automobile* $\rightarrow$ *car*, *auto*).
   - Identifies candidate same-meaning concepts in the corpus index.
4. **Cross-Lingual Query Expansion (Graph BFS)**: Propagates query seeds and verified meaning terms across the 20-language translation graph via Breadth-First Search (BFS).
5. **Weighted TF-IDF Ranking**: Matched documents are scored with term-weighted TF-IDF (exact query matches: $1.0$, cross-lingual synonyms: $0.85$, Wiktionary meaning terms: $0.80$) and sorted in descending order of relevance.
6. **Language Filtering & Match Attribution**: Documents are filtered by language selection (`all` or specific code), attributed with match reasons (`matched_by_exact`, `matched_by_meaning`, `matched_by_synonym`), highlighted via `<mark>` tags, and returned to the UI.

---

## 4. Comprehensive Data Structures & Algorithms (DSA) Map

| DSA Concept | Implementation File | Role & Usage | Time Complexity | Space Complexity |
|---|---|---|---|---|
| **Hash Map (Dictionary)** | [`modules/index.py`](file:///e:/Year-2%20Term-1/DSA/project/modules/index.py), [`modules/ranker.py`](file:///e:/Year-2%20Term-1/DSA/project/modules/ranker.py) | Main inverted index mapping `term -> {doc_id: tf}`, document store, and TF-IDF score accumulation. | $O(1)$ avg lookup / insert | $O(V + D)$ |
| **Trie (Prefix Tree)** | [`modules/trie.py`](file:///e:/Year-2%20Term-1/DSA/project/modules/trie.py) | Vocabulary storage and prefix indexing of indexed terms. | $O(L)$ per word ($L = \text{length}$) | $O(\Sigma \times L \times N)$ |
| **Inverted Index** | [`modules/index.py`](file:///e:/Year-2%20Term-1/DSA/project/modules/index.py) | Document index with dynamic `add_document` and `delete_document` methods with postings cleanup. | Add: $O(N)$, Delete: $O(N)$ | $O(\text{Total Postings})$ |
| **Graph (Adjacency List)** | [`modules/synonyms.py`](file:///e:/Year-2%20Term-1/DSA/project/modules/synonyms.py) | Undirected graph of translation/synonym clusters where nodes are words and edges connect multilingual equivalents. | Build: $O(k^2)$ per cluster | $O(V + E)$ |
| **Breadth-First Search (BFS)** | [`modules/synonyms.py`](file:///e:/Year-2%20Term-1/DSA/project/modules/synonyms.py) | Traversal algorithm to extract all cross-lingual synonyms reachable from query terms. | $O(V + E)$ | $O(V)$ |
| **Double-Ended Queue (`deque`)** | [`modules/synonyms.py`](file:///e:/Year-2%20Term-1/DSA/project/modules/synonyms.py) | Queue backing the BFS traversal, ensuring $O(1)$ `popleft()`. | $O(1)$ push / pop | $O(V)$ |
| **Dynamic Programming (Levenshtein Distance)** | [`modules/matcher.py`](file:///e:/Year-2%20Term-1/DSA/project/modules/matcher.py) | 2D matrix dynamic programming to compute minimum edit operations (insertion, deletion, substitution) for typo correction. | $O(m \times n)$ | $O(m \times n)$ |
| **Linear Search with Length Pruning** | [`modules/matcher.py`](file:///e:/Year-2%20Term-1/DSA/project/modules/matcher.py) | Scans vocabulary for typos, skipping words where $\mid\text{len}(w_1) - \text{len}(w_2)\mid > 2$. | $O(V \times m \times n)$ worst case | $O(1)$ auxiliary |
| **TF-IDF & Sorting** | [`modules/ranker.py`](file:///e:/Year-2%20Term-1/DSA/project/modules/ranker.py) | Relevancy scoring via $TF \times (\log(N / (1 + df)) + 1)$, followed by descending sort. | Score: $O(Q \times D)$, Sort: $O(R \log R)$ | $O(R)$ |
| **LRU Cache** | [`modules/wiktionary.py`](file:///e:/Year-2%20Term-1/DSA/project/modules/wiktionary.py) | Hash Map + Doubly-linked order list for memoizing external Wiktionary dictionary lookups with evictions. | $O(1)$ get / put | $O(\text{Capacity})$ |
| **Sets** | [`modules/synonyms.py`](file:///e:/Year-2%20Term-1/DSA/project/modules/synonyms.py), [`app.py`](file:///e:/Year-2%20Term-1/DSA/project/app.py) | Deduplication of query tokens, visited BFS nodes, and unique posting deletion tokens. | $O(1)$ membership test | $O(U)$ unique items |

---

## 5. File Structure & Responsibilities

```
project/
├── app.py                  # Main Flask application, routing, search & CRUD APIs
├── requirements.txt        # Minimal dependencies (Flask)
├── CONTEXT.md              # Project context, architecture & DSA documentation
├── README.md               # User guide & project overview
├── data/
│   └── corpus.json         # Persistent JSON document store (106+ multilingual docs)
├── modules/
│   ├── __init__.py         # Module initialization
│   ├── index.py            # InvertedIndex data structure (add, delete, query)
│   ├── matcher.py          # Levenshtein DP edit distance & fuzzy typo matching
│   ├── ranker.py           # TF-IDF mathematical relevance scoring & ranking
│   ├── synonyms.py         # Cross-lingual SynonymGraph and BFS expansion
│   ├── tokenizer.py        # Script-safe Unicode tokenizer
│   ├── trie.py             # TrieNode & Trie prefix tree implementation
│   └── wiktionary.py       # Wiktionary REST API integration & LRU Cache
├── static/
│   └── style.css           # Styling, 20 color-coded badges, modal, animations
└── templates/
    ├── index.html          # Main search UI, CRUD modal, delete card actions
    └── benchmark.html      # Interactive performance and scaling benchmark page
```

---

## 6. API Endpoints

### 1. `GET /`
Renders the primary search interface (`index.html`).

### 2. `GET /search`
Executes search or browse requests.
- **Query Parameters**:
  - `q` (string, optional): Search query. If empty, triggers browse mode.
  - `lang` (string, optional): Language filter (`all` or two-letter code such as `hi`, `bn`, `en`, `es`).
- **Response**:
  ```json
  {
    "results": [
      {
        "id": "1",
        "title": "The Ultimate <mark>Chocolate</mark> Chip Cookie Recipe",
        "lang": "en",
        "snippet": "A guide to baking the best cookies with butter, sugar, and <mark>chocolate</mark>.",
        "score": 2.1456
      }
    ],
    "latency": 0.85,
    "corrected_query": null
  }
  ```

### 3. `POST /add_document`
Appends a new document to the in-memory inverted index and persists it to `data/corpus.json`.
- **Request Body (JSON)**:
  ```json
  {
    "title": "Masala Dosa Recipe",
    "lang": "kn",
    "text": "ಮಸಾಲೆ ದೋಸೆ ಮಾಡುವ ಸುಲಭ ವಿಧಾನ ಮತ್ತು ಬೇಕಾಗುವ ಪದಾರ್ಥಗಳು."
  }
  ```
- **Response**:
  ```json
  {
    "success": true,
    "id": "107",
    "title": "Masala Dosa Recipe",
    "lang": "kn"
  }
  ```

### 4. `DELETE /delete_document/<doc_id>`
Deletes a document from the in-memory index, cleans inverted posting lists, and persists the removal to disk.
- **Response**:
  ```json
  { "success": true }
  ```

### 5. `GET /api/define/<word>`
Fetches dictionary meanings and parts of speech from Wiktionary REST API with in-memory $O(1)$ LRU caching.
- **Query Parameters**:
  - `lang` (string, optional): Priority language code (e.g., `en`, `es`, `hi`).
- **Response**:
  ```json
  {
    "found": true,
    "word": "chocolate",
    "entries": [
      {
        "language": "English",
        "lang_code": "en",
        "part_of_speech": "Noun",
        "definitions": ["A food made from ground roasted cacao beans..."]
      }
    ],
    "cached": false,
    "source": "Wiktionary (Wikimedia REST API)",
    "wiktionary_url": "https://en.wiktionary.org/wiki/chocolate"
  }
  ```

### 6. `GET /benchmark`
Renders the benchmark visualization dashboard.

### 7. `GET /api/run_benchmark`
Runs automated empirical tests comparing index scaling, indexed vs. naive search latency, and typo resolution accuracy.

---

## 7. How to Run & Verify

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Launch Application**:
   ```bash
   python app.py
   ```
   Server starts at `http://localhost:5000`.

3. **Verify via CLI Smoke Test**:
   ```bash
   python -c "from app import app; client = app.test_client(); print(client.get('/search?q=chocolate').get_json()['results'][0])"
   ```
