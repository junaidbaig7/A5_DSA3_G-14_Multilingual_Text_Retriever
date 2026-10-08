# Dynamic Meaning Graph: links the meanings of words in documents that are added at runtime.
#
# The curated SynonymGraph (synonyms.py) only knows the clusters typed into the source code. This module
# learns links from Wiktionary instead, in BOTH directions, and keeps them in a graph:
#   - when a document is added, every content word in it is resolved once and linked to its lemma
#     (cost 0: "kittens" -- "kitten") and to its translations / glosses / synonyms (cost 1);
#   - at search time the query word is resolved the same way (without being stored) and the graph is
#     expanded with a 0-1 BFS, so  हाथी -> elephant -> elefante  connects documents that never share a word.
# Because edges are undirected and live in the graph, the result does not depend on the order in which
# the documents were added or on which side of a translation the query is.

import json
import os
import tempfile
import threading
import unicodedata
from collections import deque
from concurrent.futures import ThreadPoolExecutor, wait

from modules.tokenizer import tokenize
from modules import wiktionary

COST_INFLECTION = 0     # same lexeme, different surface form
COST_MEANING = 1        # translation / gloss / synonym
MAX_EXPANSION_COST = 2  # at most two meaning hops: hi -> en pivot -> es

# Ranking weight by total path cost. Exact query terms weigh 1.0 and curated synonyms 0.85.
WEIGHT_BY_COST = {0: 0.95, 1: 0.80, 2: 0.65}

MAX_TERMS_PER_DOC = 40
HIGH_DF_MIN_DOCS = 8        # a term in >= 8 docs ...
HIGH_DF_RATIO = 0.20        # ... and >= 20% of the corpus is function-word-like, not a concept
LINK_DEADLINE_SECONDS = 10  # how long add_document waits; unfinished terms keep resolving in the background
SEARCH_WAIT_SECONDS = 20    # a search first waits (bounded) for terms still being linked, so it never misses them

# Function words that carry no concept. Skipping them only saves network calls: the Wiktionary
# stopword filters already stop them from creating links.
FUNCTION_WORDS = set("""
the and for are was were with that this from they have has had not but you your our their his her its who what
when where which will would can could into onto over under about after before during near every each some any
all one two very just also than then there here been being she him them out off per via
el la los las un una unos unas del con por para que como pero sus este esta esto ese esa muy más mas sin sobre
entre desde hasta toda todo todos todas está están fue ser hay
les des une dans pour avec sur qui pas par aux ces cette ses mais où elle ils elles nous vous est sont
der die das dem des ein eine einen einem einer und ist sind mit von für auf nicht auch bei aus nach zum zur
uma uns umas dos das nos nas em são não mais como
में के का की है हैं से को और पर यह वह एक रहा रही रहे था थी थे कि भी तो ने हो कर
في من على إلى عن مع هذا هذه ذلك
""".split())


def _is_latin_script(term):
    return all(ord(c) < 0x250 for c in term)


def _worth_linking(term):
    """A token is worth a dictionary lookup only if it is a real word, not a number, URL or fragment."""
    if term in FUNCTION_WORDS:
        return False
    # letters, combining marks (matras, virama) and ZWJ/ZWNJ (category Cf) used inside Indic/Persian words
    if not all(c.isalpha() or unicodedata.category(c).startswith('M') or unicodedata.category(c) == 'Cf'
               or c in "-'’" for c in term):
        return False
    if _is_latin_script(term):
        return len(term) >= 3
    return len(term) >= 2 or wiktionary._is_cjk(term)


def merge_edge(old, new):
    """
    Combines two (cost, hub) descriptions of the same word pair. The cheaper edge wins; equal-cost
    edges that disagree about the hub lose it (the relation is ambiguous, so it may not be pivoted on).
    """
    if old is None or new[0] < old[0]:
        return new
    if new[0] == old[0] and new[1] != old[1]:
        return (old[0], None)
    return old


class MeaningGraph:
    """
    Undirected graph: word -> {neighbour: (cost, hub)}, a Hash Map of Hash Maps.
      cost 0 = inflection of the same lexeme, cost 1 = same meaning.
      hub    = the endpoint that is the English headword other languages hang off (None for peers).
    expand() is a 0-1 BFS on a deque: 0-cost edges go to the front, 1-cost edges to the back, so the
    deque always stays ordered by distance and no priority queue is needed. O(V + E), bounded by cost.

    A second meaning hop is only allowed when the middle word is the hub of BOTH edges:
      हाथी -> elephant -> elefante   (elephant is the hub of both)      allowed
      garden -> بستان -> orchard      (Arabic bustan = garden AND orchard) blocked: a foreign word is never a hub
    """

    def __init__(self, store_path=None):
        self.store_path = store_path
        self.adj = {}
        self.resolved = {}      # term -> {summary, url, glosses, synonyms}: terms whose meaning is known
        self._lock = threading.RLock()
        self._save_lock = threading.Lock()
        if store_path:
            self.load()

    # -- mutation ---------------------------------------------------------
    def add_link(self, a, b, cost, hub=None):
        """Adds/updates an undirected edge (see merge_edge). Returns True if the word pair was not linked before."""
        if not a or not b or a == b:
            return False
        with self._lock:
            is_new = b not in self.adj.get(a, {})
            for x, y in ((a, b), (b, a)):
                neighbours = self.adj.setdefault(x, {})
                neighbours[y] = merge_edge(neighbours.get(y), (cost, hub))
            return is_new

    def mark_resolved(self, term, info):
        with self._lock:
            self.resolved[term] = info

    def is_resolved(self, term):
        with self._lock:
            return term in self.resolved

    def get_info(self, term):
        with self._lock:
            return self.resolved.get(term)

    def is_known_word(self, term):
        """True if the dictionary positively identified this word when it was linked (so it is not a typo)."""
        info = self.get_info(term)
        return bool(info and info.get('found'))

    # -- traversal --------------------------------------------------------
    def _edges(self, node, extra):
        with self._lock:
            edges = dict(self.adj.get(node, {}))
        if extra:
            for nbr, edge in extra.get(node, {}).items():
                edges[nbr] = merge_edge(edges.get(nbr), edge)
        return edges.items()

    def expand(self, seed, max_cost=MAX_EXPANSION_COST, extra=None):
        """
        0-1 BFS from seed. `extra` is an optional overlay adjacency (node -> {nbr: (cost, hub)}) holding links
        that were resolved live for this query only and are not stored.
        Returns {node: (cost, parent, at_hub)} for every node reachable within max_cost (seed excluded).
        `at_hub` records that the last meaning hop arrived at the hub of its edge, which is what permits
        the next meaning hop to pivot on this node.
        """
        best = {seed: (0, None, False)}
        queue = deque([(seed, 0, False)])
        while queue:
            node, dist, at_hub = queue.popleft()
            if (dist, not at_hub) > (best[node][0], not best[node][2]):
                continue    # stale entry: a better state for this node was found after it was queued
            for nbr, (cost, hub) in self._edges(node, extra):
                new_dist = dist + cost
                if new_dist > max_cost:
                    continue
                if cost == 1 and dist == 1 and not (at_hub and hub == node):
                    continue    # a second meaning hop must pivot on the hub of both edges
                new_at_hub = cost == 1 and hub == nbr
                if nbr not in best or (new_dist, not new_at_hub) < (best[nbr][0], not best[nbr][2]):
                    best[nbr] = (new_dist, node, new_at_hub)
                    if cost == 0:
                        queue.appendleft((nbr, new_dist, new_at_hub))
                    else:
                        queue.append((nbr, new_dist, new_at_hub))
        del best[seed]
        return best

    @staticmethod
    def path_to(reached, seed, node):
        """Reconstructs seed -> ... -> node from the parent pointers returned by expand()."""
        chain = [node]
        while chain[-1] != seed:
            chain.append(reached[chain[-1]][1])
        return chain[::-1]

    # -- persistence ------------------------------------------------------
    def load(self):
        try:
            with open(self.store_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            for a, b, cost, hub in data.get('links', []):
                self.add_link(a, b, cost, hub)
            self.resolved = dict(data.get('resolved', {}))
        except (OSError, ValueError, TypeError):
            self.adj, self.resolved = {}, {}    # missing or corrupt store: start empty and re-learn

    def save(self):
        if not self.store_path:
            return
        with self._lock:
            links = [[a, b, cost, hub] for a, nbrs in self.adj.items()
                     for b, (cost, hub) in nbrs.items() if a < b]
            resolved = dict(self.resolved)
        with self._save_lock:
            os.makedirs(os.path.dirname(self.store_path) or '.', exist_ok=True)
            fd, tmp_path = tempfile.mkstemp(dir=os.path.dirname(self.store_path) or '.', suffix='.tmp')
            try:
                with os.fdopen(fd, 'w', encoding='utf-8') as f:
                    json.dump({'version': 2, 'links': links, 'resolved': resolved}, f, ensure_ascii=False)
                os.replace(tmp_path, self.store_path)   # atomic: a crash never leaves a half-written store
            except OSError:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)

    def get_stats(self):
        with self._lock:
            return {
                'total_nodes': len(self.adj),
                'total_edges': sum(len(n) for n in self.adj.values()) // 2,
                'resolved_terms': len(self.resolved)
            }


class SemanticLinker:
    """Resolves words through a dictionary resolver and records / expands their meaning links."""

    def __init__(self, graph, resolver=None, max_workers=6):
        self.graph = graph
        self.resolver = resolver or wiktionary.extract_meaning_expansion
        self.max_workers = max_workers
        self._pool = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix='semantic-link')
        # Separate pool so a search never queues behind documents that are still being linked.
        self._query_pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix='semantic-query')
        self._inflight = set()      # futures of terms still being linked (possibly after add_document returned)
        self._inflight_lock = threading.Lock()

    def _track(self, future):
        with self._inflight_lock:
            self._inflight.add(future)
        future.add_done_callback(self._untrack)

    def _untrack(self, future):
        with self._inflight_lock:
            self._inflight.discard(future)

    def wait_for_inflight(self, timeout=SEARCH_WAIT_SECONDS):
        """Blocks (bounded) until every term submitted so far has been linked. Returns how many are still running."""
        with self._inflight_lock:
            futures = list(self._inflight)
        if not futures:
            return 0
        _done, not_done = wait(futures, timeout=timeout)
        return len(not_done)

    # -- resolution -------------------------------------------------------
    def _resolve(self, term, lang, depth=0):
        """
        Returns a list of records (term, info, edges, complete) for `term` and, one level down, for its
        lemma, so that 'gatitos' also learns what 'gatito' means. An edge is (a, b, cost, hub_term).
        """
        info = self.resolver(term, preferred_lang=lang) or {}
        edges = []
        for link in info.get('links', []):
            other, cost = link[0], link[1]
            side = link[2] if len(link) > 2 else None
            edges.append((term, other, cost, term if side == 'self' else other if side == 'other' else None))
        record = (term, {
            'summary': info.get('summary_definition', ''),
            'url': info.get('wiktionary_url', ''),
            'glosses': list(info.get('direct_glosses', [])),
            'synonyms': list(info.get('thesaurus_synonyms', [])),
            'found': bool(info.get('found'))
        }, edges, bool(info.get('complete', True)))
        records = [record]
        if depth == 0:
            for root in info.get('inflection_roots') or []:
                if not self.graph.is_resolved(root):
                    records.extend(self._resolve(root, lang, depth=1))
        return records

    def learn(self, term, lang=None):
        """Resolves one term and stores its links. Returns the number of new edges."""
        if self.graph.is_resolved(term):
            return 0
        added = 0
        for rec_term, info, edges, complete in self._resolve(term, lang):
            for a, b, cost, hub in edges:
                added += self.graph.add_link(a, b, cost, hub)
            if complete:    # a transient failure is retried next time instead of being remembered
                self.graph.mark_resolved(rec_term, info)
        return added

    def select_terms(self, tokens, index):
        """Content words of a document that still need linking, rarest first, capped per document."""
        total_docs = max(index.total_docs, 1)
        seen, candidates = set(), []
        for term in tokens:
            if term in seen:
                continue
            seen.add(term)
            if not _worth_linking(term) or self.graph.is_resolved(term):
                continue
            df = index.get_doc_freq(term)
            if df >= HIGH_DF_MIN_DOCS and df / total_docs >= HIGH_DF_RATIO:
                continue
            candidates.append((df, term))
        candidates.sort()
        return [term for _, term in candidates[:MAX_TERMS_PER_DOC]]

    def link_document(self, title, text, lang, index, deadline=None):
        """
        Links the meanings of every new word in a freshly indexed document. Terms are resolved in
        parallel; after `deadline` seconds the call returns and unfinished terms keep resolving in
        the background (the graph is saved again when they finish).
        """
        deadline = LINK_DEADLINE_SECONDS if deadline is None else deadline
        tokens = tokenize(f"{title} {text}")
        terms = self.select_terms(tokens, index)
        edges_before = self.graph.get_stats()['total_edges']
        futures = {self._pool.submit(self.learn, term, lang): term for term in terms}
        for fut in futures:
            self._track(fut)
        done, pending = wait(futures, timeout=deadline)
        for fut in pending:
            fut.add_done_callback(lambda _f: self.graph.save())
        failed = [futures[f] for f in done if f.exception() is not None]
        self.graph.save()

        linked = [futures[f] for f in done if f.exception() is None and self.graph.is_resolved(futures[f])]
        return {
            'terms_attempted': len(terms),
            'terms_linked': len(linked),
            'terms_pending': len(pending),
            'terms_failed': len(failed),
            'edges_added': self.graph.get_stats()['total_edges'] - edges_before
        }

    # -- query time -------------------------------------------------------
    def _live_overlay(self, term):
        """Resolves a not-yet-stored query term for this request only. Returns (info, undirected overlay)."""
        overlay, info = {}, None
        try:
            records = self._resolve(term, None)
        except Exception:
            return None, {}     # dictionary unavailable: search still works from the stored graph
        for rec_term, rec_info, edges, _complete in records:
            if info is None:
                info = rec_info
            for a, b, cost, hub in edges:
                for x, y in ((a, b), (b, a)):
                    nbrs = overlay.setdefault(x, {})
                    nbrs[y] = merge_edge(nbrs.get(y), (cost, hub))
        return info, overlay

    def expand_query(self, terms, index_terms):
        """
        Finds the indexed words that carry the same meaning as the query terms.
        Returns {'definitions', 'expansions', 'nodes', 'store_hits'} where nodes maps each matching
        indexed word to its cost, ranking weight and the chain of links that connects it to the query.
        """
        self.wait_for_inflight()    # read-your-writes: a document added a moment ago must already be linked

        infos, overlay, store_hits = {}, {}, 0
        unresolved = []
        for term in terms:
            info = self.graph.get_info(term)
            if info is not None:
                infos[term] = info
                store_hits += 1
            else:
                unresolved.append(term)

        if unresolved:
            for term, (info, term_overlay) in zip(unresolved, self._query_pool.map(self._live_overlay, unresolved)):
                infos[term] = info
                for node, nbrs in term_overlay.items():
                    merged = overlay.setdefault(node, {})
                    for nbr, edge in nbrs.items():
                        merged[nbr] = merge_edge(merged.get(nbr), edge)

        definitions, expansions, nodes = [], {}, {}
        query_terms = set(terms)
        for term in terms:
            info = infos.get(term)
            if info and info.get('summary'):
                definitions.append({
                    'word': term,
                    'summary': info['summary'],
                    'direct_glosses': info.get('glosses', []),
                    'thesaurus_synonyms': info.get('synonyms', []),
                    'wiktionary_url': info.get('url')
                })

            reached = self.graph.expand(term, MAX_EXPANSION_COST, extra=overlay)
            matches = sorted(
                (cost, node) for node, (cost, _parent, _at_hub) in reached.items()
                if node in index_terms and node not in query_terms
            )
            if matches:
                expansions[term] = [node for _cost, node in matches]
            for cost, node in matches:
                if node not in nodes or cost < nodes[node]['cost']:
                    nodes[node] = {
                        'cost': cost,
                        'weight': WEIGHT_BY_COST[cost],
                        'path': self.graph.path_to(reached, term, node)
                    }

        return {'definitions': definitions, 'expansions': expansions, 'nodes': nodes, 'store_hits': store_hits}
