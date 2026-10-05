from modules.tokenizer import tokenize
from modules.trie import Trie

class InvertedIndex:
    def __init__(self):
        # term -> {doc_id: term_frequency}  (Hash Map)
        self.index = {}
        # doc_id -> total number of tokens in the document  (Hash Map)
        self.doc_lengths = {}
        self.total_docs = 0
        # Trie for vocabulary prefix storage
        self.vocabulary = Trie()
        # doc_id -> dict of document metadata (e.g. title, lang, text)  (Hash Map)
        self.documents = {}

    def add_document(self, doc_id, text, metadata=None):
        """
        O(N) time complexity where N is the length of the document text.
        """
        self.total_docs += 1
        if metadata is None:
            metadata = {}
        metadata['text'] = text
        self.documents[doc_id] = metadata

        full_content = f"{metadata.get('title', '')} {text}".strip()
        tokens = tokenize(full_content)
        self.doc_lengths[doc_id] = len(tokens)

        # Count term frequencies in this document
        term_freqs = {}
        for token in tokens:
            term_freqs[token] = term_freqs.get(token, 0) + 1

        # Add to inverted index
        for term, freq in term_freqs.items():
            if term not in self.index:
                self.index[term] = {}
                self.vocabulary.insert(term)
            self.index[term][doc_id] = freq

    def delete_document(self, doc_id):
        """
        Remove a document from the index.
        O(N) time complexity where N is the number of unique tokens in the document.
        """
        if doc_id not in self.documents:
            return False

        doc_metadata = self.documents[doc_id]
        full_content = f"{doc_metadata.get('title', '')} {doc_metadata.get('text', '')}".strip()
        tokens = tokenize(full_content)

        # Remove this doc's postings from the inverted index
        for token in set(tokens):
            if token in self.index:
                self.index[token].pop(doc_id, None)
                # Clean up empty posting lists
                if not self.index[token]:
                    del self.index[token]

        del self.documents[doc_id]
        if doc_id in self.doc_lengths:
            del self.doc_lengths[doc_id]
        self.total_docs -= 1
        return True

    def get_term_freqs(self, term):
        """O(1) average time complexity for hash map lookup."""
        return self.index.get(term, {})

    def get_doc_freq(self, term):
        """O(1) time complexity."""
        return len(self.index.get(term, {}))

    def get_stats(self):
        """Returns comprehensive index telemetry and metrics."""
        lang_counts = {}
        for doc in self.documents.values():
            l = doc.get('lang', 'en')
            lang_counts[l] = lang_counts.get(l, 0) + 1

        total_postings = sum(len(p) for p in self.index.values())
        avg_doc_len = (sum(self.doc_lengths.values()) / self.total_docs) if self.total_docs > 0 else 0

        return {
            'total_docs': self.total_docs,
            'vocab_size': len(self.index),
            'total_postings': total_postings,
            'avg_doc_length': round(avg_doc_len, 1),
            'languages_count': len(lang_counts),
            'language_distribution': lang_counts,
            'trie_stats': self.vocabulary.get_stats()
        }

    def get_term_details(self, term):
        """
        Returns posting list and document metadata for an inverted index term.
        """
        postings_map = self.index.get(term, {})
        postings_list = []
        for doc_id, tf in sorted(postings_map.items(), key=lambda x: int(x[0]) if x[0].isdigit() else float('inf')):
            doc_meta = self.documents.get(doc_id, {})
            postings_list.append({
                'doc_id': doc_id,
                'tf': tf,
                'title': doc_meta.get('title', f'Document #{doc_id}'),
                'lang': doc_meta.get('lang', 'en'),
                'snippet': (doc_meta.get('text', '')[:140] + '...') if len(doc_meta.get('text', '')) > 140 else doc_meta.get('text', '')
            })

        return {
            'term': term,
            'found': term in self.index,
            'doc_freq': len(postings_map),
            'postings': postings_list
        }

