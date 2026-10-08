import math

def rank_documents_with_breakdown(query_terms, index, term_weights=None):
    """
    Computes TF-IDF scores with detailed per-term mathematical breakdown.
    Supports optional term_weights dict to scale exact matches vs meaning-expansion terms.
    Time Complexity: O(Q * D) scoring + O(R log R) sorting.
    Returns: (ranked_list, doc_breakdown, term_stats)
    """
    scores = {}
    breakdowns = {}
    term_stats = {}
    N = index.total_docs

    if N == 0:
        return [], {}, {}

    for term in query_terms:
        term_freqs = index.get_term_freqs(term)
        df = index.get_doc_freq(term)

        if df == 0:
            term_stats[term] = {'df': 0, 'idf': 0.0, 'postings_count': 0, 'weight': 1.0}
            continue

        weight = term_weights.get(term, 1.0) if term_weights else 1.0

        # IDF: ln(N / (1 + df)) + 1
        idf = math.log(N / (1 + df)) + 1
        term_stats[term] = {
            'df': df,
            'idf': round(idf, 4),
            'postings_count': len(term_freqs),
            'weight': round(weight, 2)
        }

        for doc_id, tf in term_freqs.items():
            contrib = tf * idf * weight
            scores[doc_id] = scores.get(doc_id, 0.0) + contrib
            if doc_id not in breakdowns:
                breakdowns[doc_id] = []
            breakdowns[doc_id].append({
                'term': term,
                'tf': tf,
                'df': df,
                'idf': round(idf, 4),
                'weight': round(weight, 2),
                'contribution': round(contrib, 4)
            })

    # O(R log R) where R is the number of matched documents. Ties are broken by document id: the order in which
    # documents are first scored follows the order of the query terms, which comes from set iteration and differs
    # between processes, so without this the top-k of a large tie could change from one run to the next.
    # Scores are rounded so that float noise from a different summation order cannot split a tie either.
    ranked = sorted(scores.items(), key=lambda item: (-round(item[1], 9), _doc_order(item[0])))
    return ranked, breakdowns, term_stats


def _doc_order(doc_id):
    """Numeric ids sort numerically and before any non-numeric id."""
    return (0, int(doc_id), '') if str(doc_id).isdigit() else (1, 0, str(doc_id))


def rank_documents(query_terms, index, term_weights=None):
    """
    O(Q * D) time complexity where Q is the number of query terms 
    and D is the average number of documents containing a query term.
    """
    ranked, _, _ = rank_documents_with_breakdown(query_terms, index, term_weights=term_weights)
    return ranked

