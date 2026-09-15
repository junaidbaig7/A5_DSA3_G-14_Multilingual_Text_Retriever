def tokenize(text):
    """
    O(N) time complexity where N is the length of the text.
    Splits text by whitespace and strips common punctuation to preserve 
    multilingual scripts (like Devanagari) where regex \w+ might incorrectly 
    split on Unicode combining characters (vowels/matras).
    """
    text = text.lower()
    words = text.split()
    cleaned = []
    # Strip common punctuation characters
    punctuation = ".,!?:;'\"()[]{}<>|-"
    for w in words:
        w = w.strip(punctuation)
        if w:
            cleaned.append(w)
    return cleaned
