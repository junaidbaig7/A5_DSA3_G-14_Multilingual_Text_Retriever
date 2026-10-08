import re
import unicodedata

# Punctuation stripped from the edges of every token (kept from the original ASCII rule).
ASCII_EDGE_PUNCTUATION = ".,!?:;'\"()[]{}<>|-"

# French / Italian elision clitics glued to the next word by an apostrophe: l'éléphant, d'eau, dell'acqua.
# The clitic is a function word, so only the word behind it is kept.
ELISION_PATTERN = re.compile(
    r"^(?:[ldjmtsnc]|qu|jusqu|lorsqu|puisqu|quoiqu|dell|all|nell|sull|dall|quell|quest|un|anch|nient|tutt)['’](?=\w)"
)


def _is_edge_punctuation(ch):
    # Unicode category P* covers scripts the ASCII list misses: the Devanagari/Bengali danda (।),
    # Arabic/Urdu question mark and comma (؟ ،), guillemets, inverted ¿ ¡, curly quotes, etc.
    return ch in ASCII_EDGE_PUNCTUATION or unicodedata.category(ch).startswith('P')


def _strip_edges(word):
    start, end = 0, len(word)
    while start < end and _is_edge_punctuation(word[start]):
        start += 1
    while end > start and _is_edge_punctuation(word[end - 1]):
        end -= 1
    return word[start:end]


def tokenize(text):
    """
    O(N) time complexity where N is the length of the text.
    Splits text by whitespace and strips punctuation from the token edges to preserve
    multilingual scripts (like Devanagari) where regex \\w+ might incorrectly
    split on Unicode combining characters (vowels/matras).
    """
    text = text.lower()
    cleaned = []
    for w in text.split():
        w = _strip_edges(w)
        w = ELISION_PATTERN.sub('', w)
        if w:
            cleaned.append(w)
    return cleaned
