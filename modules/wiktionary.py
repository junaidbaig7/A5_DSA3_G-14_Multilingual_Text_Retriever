import urllib.request
import urllib.parse
import urllib.error
import json
import re
import html
from collections import OrderedDict


class LRUCache:
    """
    Least Recently Used (LRU) Cache implementation using a Hash Map + Doubly Linked List logic
    (via collections.OrderedDict) to achieve O(1) get and O(1) put operations.
    Used to memoize Wiktionary API responses, minimizing latency and external HTTP overhead.
    """
    def __init__(self, capacity: int = 256):
        self.capacity = capacity
        self.cache = OrderedDict()
        self.hits = 0
        self.misses = 0

    def get(self, key):
        if key not in self.cache:
            self.misses += 1
            return None
        # Move accessed key to end (most recently used)
        self.hits += 1
        self.cache.move_to_end(key)
        return self.cache[key]

    def put(self, key, value):
        if key in self.cache:
            self.cache.move_to_end(key)
        self.cache[key] = value
        if len(self.cache) > self.capacity:
            # Evict oldest / least recently used (first item)
            self.cache.popitem(last=False)

    def __contains__(self, key):
        return key in self.cache

    def size(self):
        return len(self.cache)

    def get_stats(self):
        total_lookups = self.hits + self.misses
        hit_rate = round((self.hits / total_lookups * 100), 1) if total_lookups > 0 else 0.0
        return {
            'size': len(self.cache),
            'capacity': self.capacity,
            'hits': self.hits,
            'misses': self.misses,
            'hit_rate_pct': hit_rate,
            'recent_keys': list(self.cache.keys())[-10:]
        }


# In-memory LRU cache instance
_wiktionary_cache = LRUCache(capacity=300)

def get_wiktionary_cache_stats():
    return _wiktionary_cache.get_stats()



def clean_definition_html(raw_html: str) -> str:
    """
    Cleans Wiktionary HTML markup into clean, readable plaintext.
    Uses Python's standard library (re + html) without requiring external dependencies.
    """
    if not raw_html:
        return ""

    # Remove HTML comments <!-- ... -->
    text = re.sub(r'<!--.*?-->', '', raw_html, flags=re.DOTALL)
    # Remove HTML tags <...>
    text = re.sub(r'<[^>]+>', '', text)
    # Unescape HTML entities (&quot;, &amp;, etc.)
    text = html.unescape(text)
    # Collapse multiple whitespaces and newlines
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def lookup_word(word: str, preferred_lang: str = None) -> dict:
    """
    Fetches word definitions from the official Wiktionary REST API.
    
    1. Checks the LRU cache (O(1)).
    2. Queries https://en.wiktionary.org/api/rest_v1/page/definition/{word} which
       catalogs definitions in English, Spanish, Hindi, French, and hundreds of other languages.
    3. If missing and a specific preferred_lang is provided, falls back to
       https://{preferred_lang}.wiktionary.org/api/rest_v1/page/definition/{word}.
    4. Cleans HTML tags into formatted plain text definitions.
    5. Saves result in LRU Cache.
    """
    word = (word or '').strip()
    if not word:
        return {'found': False, 'word': '', 'error': 'Empty word query.'}

    cache_key = f"{word.lower()}::{preferred_lang or 'all'}"
    cached = _wiktionary_cache.get(cache_key)
    if cached is not None:
        result = dict(cached)
        result['cached'] = True
        return result

    headers = {
        'User-Agent': 'MultilingualRetriever/1.0 (Educational DSA Project; contact: student@project.local)'
    }

    encoded_word = urllib.parse.quote(word)
    endpoints = [f"https://en.wiktionary.org/api/rest_v1/page/definition/{encoded_word}"]

    # Optional fallback to specific language edition if distinct from 'en'
    if preferred_lang and preferred_lang not in ('en', 'all'):
        endpoints.append(f"https://{preferred_lang}.wiktionary.org/api/rest_v1/page/definition/{encoded_word}")

    raw_data = None
    for url in endpoints:
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=4) as resp:
                if resp.status == 200:
                    raw_data = json.loads(resp.read().decode('utf-8'))
                    break
        except urllib.error.HTTPError as e:
            if e.code == 404:
                continue
            continue
        except Exception:
            continue

    if not raw_data or not isinstance(raw_data, dict):
        result = {
            'found': False,
            'word': word,
            'error': f"No definition found for '{word}' on Wiktionary.",
            'cached': False
        }
        _wiktionary_cache.put(cache_key, result)
        return result

    # Parse and structure the definitions
    parsed_entries = []
    lang_keys = list(raw_data.keys())
    if preferred_lang and preferred_lang in lang_keys:
        lang_keys.remove(preferred_lang)
        lang_keys.insert(0, preferred_lang)

    for lang_code in lang_keys:
        entries = raw_data[lang_code]
        if not isinstance(entries, list):
            continue

        for item in entries:
            language_name = item.get('language') or lang_code.upper()
            part_of_speech = item.get('partOfSpeech', 'General')
            raw_definitions = item.get('definitions', [])

            cleaned_defs = []
            for d in raw_definitions:
                if isinstance(d, dict) and 'definition' in d:
                    cleaned = clean_definition_html(d['definition'])
                    if cleaned and cleaned not in cleaned_defs:
                        cleaned_defs.append(cleaned)

            if cleaned_defs:
                parsed_entries.append({
                    'language': language_name,
                    'lang_code': lang_code,
                    'part_of_speech': part_of_speech,
                    'definitions': cleaned_defs[:4]  # Top 4 most relevant definitions
                })

    if not parsed_entries:
        result = {
            'found': False,
            'word': word,
            'error': f"Definitions for '{word}' could not be parsed.",
            'cached': False
        }
        _wiktionary_cache.put(cache_key, result)
        return result

    result = {
        'found': True,
        'word': word,
        'entries': parsed_entries,
        'source': 'Wiktionary (Wikimedia REST API)',
        'wiktionary_url': f"https://en.wiktionary.org/wiki/{encoded_word}",
        'cached': False
    }

    _wiktionary_cache.put(cache_key, result)
    return result


# ---------------------------------------------------------------------------
# Strict Semantic Meaning Filters & Stopwords
# ---------------------------------------------------------------------------

DEFINITION_STOPWORDS = {
    'a', 'an', 'the', 'of', 'in', 'to', 'for', 'and', 'or', 'is', 'are', 'was', 'were',
    'with', 'as', 'by', 'on', 'at', 'from', 'that', 'this', 'it', 'etc', 'used', 'such',
    'especially', 'usually', 'typically', 'having', 'made', 'type', 'one', 'any', 'set',
    'inflection', 'singular', 'plural', 'present', 'indicative', 'subjunctive',
    'first-person', 'second-person', 'third-person', 'past', 'participle', 'noun', 'verb', 'adjective',
    'also', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'but',
    'not', 'can', 'could', 'may', 'might', 'must', 'shall', 'should', 'will', 'would',
    'mw-parser-output', 'object-usage-tag', 'deprecated', 'color', 'italic', 'font-style',
    'small', 'large', 'very', 'much', 'many', 'more', 'most', 'some', 'other', 'into',
    'out', 'up', 'down', 'about', 'over', 'than', 'them', 'their', 'there', 'what', 'which',
    'who', 'when', 'where', 'why', 'how', 'all', 'both', 'each', 'few', 'own', 'same',
    'so', 'too', 'just', 'now', 'form', 'person', 'tense', 'definite', 'indefinite',
    'sense', 'referring', 'pertaining', 'relating', 'consisting', 'containing', 'characterized',
    'you', 'your', 'yours', 'me', 'my', 'mine', 'we', 'us', 'our', 'ours', 'he', 'him', 'his',
    'she', 'her', 'hers', 'they', 'theirs',
    'day', 'days', 'night', 'morning', 'evening', 'time', 'times', 'life', 'year', 'years',
    'good', 'bad', 'top', 'bottom', 'side', 'page', 'said', 'say', 'saying', 'tell', 'ask',
    'well', 'way', 'ways', 'new', 'old', 'get', 'gets',
    'take', 'takes', 'make', 'makes', 'see', 'look', 'know', 'think', 'come', 'go', 'give',
    'someone', 'somebody', 'anyone', 'anybody', 'everyone', 'something', 'anything', 'nothing',
    'like', 'such', 'called', 'name', 'named', 'state', 'action', 'process', 'manner', 'quality',
    'order', 'part', 'piece', 'unit', 'kind', 'class', 'group', 'number', 'amount', 'degree',
    'word', 'words', 'test', 'tests', 'text', 'line', 'item', 'example', 'case', 'thing', 'things'
}

# Strict blocklist against informal slang, metaphors, animals applied to humans, and offensive terms
# that crowdsourced wiki pages often inappropriately cross-link.
DISALLOWED_METAPHOR_SLANG = {
    'cat', 'cats', 'dog', 'dogs', 'dawg', 'rooster', 'stud', 'bloke', 'boy', 'kid',
    'bird', 'birds', 'chick', 'doll', 'pig', 'pigs', 'shark', 'sharks', 'rat', 'rats',
    'snake', 'beast', 'tool', 'nut', 'clown', 'turkey', 'donkey', 'jackass', 'dude',
    'bro', 'bruh', 'broski', 'fella', 'guy', 'chap', 'cove', 'covey', 'gadgie', 'geezer',
    'nigga', 'nigger', 'bitch', 'whore', 'slut', 'bastard', 'asshole', 'fuck', 'shit'
}

SUPPORTED_LANG_NAMES = {
    'English', 'Spanish', 'Hindi', 'Bengali', 'Telugu', 'Marathi', 'Tamil', 'Urdu',
    'Gujarati', 'Kannada', 'Malayalam', 'Odia', 'Punjabi', 'Assamese', 'Sanskrit',
    'French', 'German', 'Portuguese', 'Arabic', 'Chinese'
}


def get_wiktionary_synonyms(word: str) -> list:
    """
    Fetches strict, high-confidence single-word synonyms directly from the main entry's
    {{syn|...}} or {{synonyms|...}} definitions on Wiktionary.
    
    NOTE: We explicitly DO NOT query Wiktionary 'Thesaurus:<word>' pages because they are
    crowdsourced dumps of street slang, insults, and metaphors (e.g. associating 'cat' or 'dog' with 'man')
    which pollute search results and corrupt semantic meaning.
    """
    word = (word or '').strip().lower()
    if not word or len(word) < 3:
        return []

    cache_key = f"__synonyms_clean_strict__::{word}"
    cached = _wiktionary_cache.get(cache_key)
    if cached is not None:
        return list(cached)

    synonyms = []
    encoded = urllib.parse.quote(word)
    headers = {
        'User-Agent': 'MultilingualRetriever/1.0 (Educational DSA Project; contact: student@project.local)'
    }

    url_page = f"https://en.wiktionary.org/w/api.php?action=parse&page={encoded}&prop=wikitext&format=json"
    try:
        req = urllib.request.Request(url_page, headers=headers)
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            wt = data.get('parse', {}).get('wikitext', {}).get('*', '')
            # Match explicit {{syn|en|word1|word2}} or {{synonyms|en|word1|word2}}
            for m in re.finditer(r'\{\{syn(?:onyms)?\|[a-z]{2,3}\|([^}]+)\}\}', wt):
                for piece in m.group(1).split('|'):
                    p = piece.split('=')[-1].strip().lower()
                    clean_p = re.sub(r'<[^>]+>', '', p).strip().lower()
                    if (
                        ' ' not in clean_p and
                        clean_p != word and
                        not clean_p.startswith('thesaurus:') and
                        len(clean_p) > 2 and
                        clean_p not in synonyms and
                        clean_p not in DEFINITION_STOPWORDS and
                        clean_p not in DISALLOWED_METAPHOR_SLANG
                    ):
                        synonyms.append(clean_p)
    except Exception:
        pass

    _wiktionary_cache.put(cache_key, synonyms[:8])
    return synonyms[:8]


SUPPORTED_LANG_CODES = {
    'en', 'es', 'fr', 'de', 'pt', 'ar', 'zh',
    'hi', 'bn', 'te', 'mr', 'ta', 'ur', 'gu', 'kn', 'ml', 'or', 'pa', 'as', 'sa'
}


def get_wiktionary_translations(word: str) -> list:
    """
    Extracts direct translation terms from Wiktionary's {{t|...}} or {{t+|...}}
    tables across the 20 supported languages (e.g. difficult -> मुश्किल, कठिन, difícil, difficile, schwierig).
    Uses O(1) LRU caching.
    """
    word = (word or '').strip().lower()
    if not word or len(word) < 2:
        return []

    cache_key = f"__translations_clean__::{word}"
    cached = _wiktionary_cache.get(cache_key)
    if cached is not None:
        return list(cached)

    translations = []
    encoded = urllib.parse.quote(word)
    headers = {
        'User-Agent': 'MultilingualRetriever/1.0 (Educational DSA Project; contact: student@project.local)'
    }

    url_page = f"https://en.wiktionary.org/w/api.php?action=parse&page={encoded}&prop=wikitext&format=json"
    try:
        req = urllib.request.Request(url_page, headers=headers)
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            wt = data.get('parse', {}).get('wikitext', {}).get('*', '')
            # Match standard translation templates: {{t|hi|मुश्किल}} or {{t+|es|difícil}}
            for m in re.finditer(r'\{\{t[+\-]?\|([a-z]{2,3})\|([^}|]+)', wt):
                lang_code = m.group(1).lower()
                term = m.group(2).strip()
                if lang_code in SUPPORTED_LANG_CODES:
                    clean_term = re.sub(r'<[^>]+>', '', term).strip().lower()
                    if (
                        clean_term and
                        clean_term != word and
                        clean_term not in translations and
                        clean_term not in DEFINITION_STOPWORDS and
                        clean_term not in DISALLOWED_METAPHOR_SLANG and
                        len(clean_term) > 1
                    ):
                        translations.append(clean_term)
    except Exception:
        pass

    _wiktionary_cache.put(cache_key, translations[:20])
    return translations[:20]


def extract_meaning_expansion(word: str, preferred_lang: str = None) -> dict:
    """
    Queries Wiktionary to extract the genuine semantic meaning concepts of a word:
    - Primary definition summary for user display.
    - Direct glosses (translation equivalents in foreign definitions, e.g., 'receta' -> 'recipe', 'agua' -> 'water').
    - Inflection roots (e.g. 'viajar' from 'inflection of viajar').
    - Strict, curated single-word synonyms (e.g. 'automobile' -> 'car').
    
    Excludes descriptive paragraph keywords, informal slang, and cross-category metaphors.
    Returns structured dictionary with word meaning and all expanded terms.
    """
    clean_word = (word or '').strip().lower()
    if not clean_word:
        return {'found': False, 'word': '', 'all_meaning_terms': [], 'summary_definition': ''}

    res = lookup_word(clean_word, preferred_lang=preferred_lang)
    if not res.get('found') or not res.get('entries'):
        return {
            'found': False,
            'word': clean_word,
            'all_meaning_terms': [],
            'summary_definition': '',
            'cached': res.get('cached', False)
        }

    entries = res['entries']

    # Sort entries to prioritize supported languages and substantive parts of speech
    def entry_priority(e):
        lang = e.get('language', '')
        pos = e.get('part_of_speech', '')
        defs = e.get('definitions', [])
        first_def = defs[0] if defs else ''
        return (
            preferred_lang and e.get('lang_code') == preferred_lang,
            lang in SUPPORTED_LANG_NAMES,
            pos in ('Noun', 'Verb', 'Adjective', 'Interjection'),
            not first_def.startswith('inflection of')
        )

    sorted_entries = sorted(entries, key=entry_priority, reverse=True)

    summary_def = ''
    direct_glosses = []
    inflection_roots = []

    from modules.tokenizer import tokenize

    for entry in sorted_entries:
        entry_lang = entry.get('language', '')
        if entry_lang not in SUPPORTED_LANG_NAMES:
            continue

        for d in entry.get('definitions', []):
            # Check for root word in inflection note
            root_match = re.search(r'inflection of ([^:\s,()]+)', d)
            if root_match:
                root = root_match.group(1).strip().lower()
                clean_root = re.sub(r'<[^>]+>', '', root).strip()
                if (
                    clean_root and
                    clean_root != clean_word and
                    clean_root not in inflection_roots and
                    clean_root not in DEFINITION_STOPWORDS and
                    clean_root not in DISALLOWED_METAPHOR_SLANG
                ):
                    inflection_roots.append(clean_root)

            # If this is purely a grammatical inflection line, skip setting as summary if we have better
            if d.startswith('inflection of') and summary_def:
                continue

            if not summary_def:
                summary_def = d

            # Extract direct leading gloss before punctuation / parentheses:
            # Foreign definitions typically start with 1-2 direct translation equivalents, e.g.:
            # "recipe (instructions for cooking food)" -> "recipe"
            # "water" -> "water"
            # "journey, trip" -> "journey", "trip"
            lead = re.split(r'[\(;:]', d)[0].strip()
            for part in re.split(r'[,/]', lead)[:2]:
                toks = tokenize(part)
                # Keep ONLY clean single headwords (never multi-word sentences)
                if len(toks) == 1:
                    tok = toks[0]
                    if (
                        tok not in DEFINITION_STOPWORDS and
                        tok not in DISALLOWED_METAPHOR_SLANG and
                        len(tok) > 2 and
                        tok != clean_word
                    ):
                        if tok not in direct_glosses:
                            direct_glosses.append(tok)

    # Fetch strict synonyms (strictly excludes Thesaurus slang/metaphors)
    strict_syns = get_wiktionary_synonyms(clean_word)

    # Fetch cross-lingual translations across the 20 supported languages
    translations = get_wiktionary_translations(clean_word)

    # Consolidate candidate meaning terms:
    combined = []
    for t in direct_glosses + inflection_roots + strict_syns + translations:
        t_clean = t.strip().lower()
        if (
            ' ' not in t_clean and
            t_clean not in DEFINITION_STOPWORDS and
            t_clean not in DISALLOWED_METAPHOR_SLANG and
            len(t_clean) > 1 and
            t_clean != clean_word
        ):
            if t_clean not in combined:
                combined.append(t_clean)

    return {
        'found': True,
        'word': clean_word,
        'summary_definition': summary_def,
        'direct_glosses': direct_glosses,
        'inflection_roots': inflection_roots,
        'thesaurus_synonyms': strict_syns[:6],
        'translations': translations[:15],
        'all_meaning_terms': combined,
        'wiktionary_url': res.get('wiktionary_url', f"https://en.wiktionary.org/wiki/{clean_word}"),
        'cached': res.get('cached', False)
    }
