import math

def rank_documents(query_terms, index):
    """
    O(Q * D) time complexity where Q is the number of query terms 
    and D is the average number of documents containing a query term.
    """
    scores = {}
    N = index.total_docs
    
    if N == 0:
        return []
        
    for term in query_terms:
        term_freqs = index.get_term_freqs(term)
        df = index.get_doc_freq(term)
        
        if df == 0:
            continue
            
        # IDF (Inverse Document Frequency)
        idf = math.log(N / (1 + df)) + 1
        
        for doc_id, tf in term_freqs.items():
            # TF-IDF calculation
            tf_idf = tf * idf
            scores[doc_id] = scores.get(doc_id, 0.0) + tf_idf
            
    # O(R log R) where R is the number of matched documents
    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    return ranked
