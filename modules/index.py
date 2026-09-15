from modules.tokenizer import tokenize
from modules.trie import Trie

class InvertedIndex:
    def __init__(self):
        # term -> {doc_id: term_frequency}
        self.index = {}
        # doc_id -> total number of tokens in the document
        self.doc_lengths = {}
        self.total_docs = 0
        self.vocabulary = Trie()
        # doc_id -> dict of document metadata (e.g. title, lang, text)
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
        
        tokens = tokenize(text)
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

    def get_term_freqs(self, term):
        """O(1) average time complexity for hash map lookup."""
        return self.index.get(term, {})

    def get_doc_freq(self, term):
        """O(1) time complexity."""
        return len(self.index.get(term, {}))
