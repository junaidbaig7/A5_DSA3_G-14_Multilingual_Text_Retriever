import urllib.request
import urllib.parse
import urllib.error
import json
import re
import html
import threading
import time
from collections import OrderedDict


class LRUCache:
    """
    Least Recently Used (LRU) Cache implementation using a Hash Map + Doubly Linked List logic
    (via collections.OrderedDict) to achieve O(1) get and O(1) put operations.
    Used to memoize Wiktionary API responses, minimizing latency and external HTTP overhead.
    A lock guards every operation because meaning links are resolved from worker threads.
    """
    def __init__(self, capacity: int = 256):
        self.capacity = capacity
        self.cache = OrderedDict()
        self.hits = 0
        self.misses = 0
        self._lock = threading.Lock()

    def get(self, key):
        with self._lock:
            if key not in self.cache:
                self.misses += 1
                return None
            # Move accessed key to end (most recently used)
            self.hits += 1
            self.cache.move_to_end(key)
            return self.cache[key]

    def put(self, key, value):
        with self._lock:
            if key in self.cache:
                self.cache.move_to_end(key)
            self.cache[key] = value
            if len(self.cache) > self.capacity:
                # Evict oldest / least recently used (first item)
                self.cache.popitem(last=False)

    def __contains__(self, key):
        with self._lock:
            return key in self.cache

    def size(self):
        with self._lock:
            return len(self.cache)

    def get_stats(self):
        with self._lock:
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


HTTP_HEADERS = {
    'User-Agent': 'MultilingualRetriever/1.0 (Educational DSA Project; contact: student@project.local)'
}


def _http_get_json(url: str, timeout: float, attempts: int = 2):
    """
    Returns (status, data) where status is:
      'ok'      - HTTP 200 with a JSON body
      'missing' - a definitive 404 (the page does not exist)
      'error'   - anything transient (timeout, DNS failure, 5xx, bad JSON) that survived a retry
    Callers must NOT cache an 'error' as "word not found": the next lookup should retry.
    """
    for attempt in range(attempts):
        try:
            req = urllib.request.Request(url, headers=HTTP_HEADERS)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return 'ok', json.loads(resp.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return 'missing', None
            if e.code in (429, 503) and attempt + 1 < attempts:
                # Rate limited: honour Retry-After (capped) before the retry
                try:
                    time.sleep(min(float(e.headers.get('Retry-After', 1)), 2.0))
                except (TypeError, ValueError):
                    time.sleep(1.0)
        except Exception:
            pass
    return 'error', None


def _title_variants(word: str) -> list:
    """
    Wiktionary page titles are case-sensitive, while our tokenizer lower-cases everything.
    German nouns ('Apfel') and other capitalised headwords therefore only resolve via the
    capitalised variant, which is tried second.
    """
    variants = [word]
    if word[:1].islower():
        variants.append(word[:1].upper() + word[1:])
    return variants


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


def _fetch_definitions(word: str, preferred_lang: str = None):
    """
    Fetches REST definitions for the lower-case title and, when needed, the capitalised one.
    Returns (entries_by_language_code | None, page_title, transient_failure).

    The capitalised title is tried when the lower-case page only holds languages we do not support
    (the lower-case 'apfel' page is Middle High German; German 'Apfel' lives under the capital), or
    when the caller works in German, where every noun is capitalised ('Bank' != 'bank').
    A transient error aborts instead of falling through: silently answering from a different
    title ('Automobile' = German plural) would be wrong, and must not be cached.
    """
    merged = {}
    page_title = word
    for title in _title_variants(word):
        encoded_title = urllib.parse.quote(title)
        urls = [f"https://en.wiktionary.org/api/rest_v1/page/definition/{encoded_title}"]
        # Optional fallback to specific language edition if distinct from 'en'
        if preferred_lang and preferred_lang not in ('en', 'all'):
            urls.append(f"https://{preferred_lang}.wiktionary.org/api/rest_v1/page/definition/{encoded_title}")

        hit, errored = None, False
        for url in urls:
            status, data = _http_get_json(url, timeout=4)
            if status == 'ok' and isinstance(data, dict) and data:
                hit = data
                break
            errored = errored or status == 'error'

        if hit is None:
            if errored:
                return (merged or None), page_title, True
            continue    # definitive miss: try the next title variant

        had_supported = any(code in SUPPORTED_LANG_CODES for code in merged)
        for code, entries in hit.items():
            merged.setdefault(code, entries)
        if not had_supported and any(code in SUPPORTED_LANG_CODES for code in hit):
            page_title = title
        if any(code in SUPPORTED_LANG_CODES for code in hit) and preferred_lang != 'de':
            break

    return (merged or None), page_title, False


def lookup_word(word: str, preferred_lang: str = None) -> dict:
    """
    Fetches word definitions from the official Wiktionary REST API.

    1. Checks the LRU cache (O(1)).
    2. Queries https://en.wiktionary.org/api/rest_v1/page/definition/{word} which
       catalogs definitions in English, Spanish, Hindi, French, and hundreds of other languages.
       A capitalised title is tried when the lower-case one is missing (German nouns).
    3. If missing and a specific preferred_lang is provided, falls back to
       https://{preferred_lang}.wiktionary.org/api/rest_v1/page/definition/{word}.
    4. Cleans HTML tags into formatted plain text definitions.
    5. Saves result in LRU Cache - but never a failure caused by a timeout / network error.
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

    raw_data, page_title, transient_failure = _fetch_definitions(word, preferred_lang)

    if not raw_data:
        result = {
            'found': False,
            'word': word,
            'error': f"No definition found for '{word}' on Wiktionary.",
            'transient': transient_failure,
            'cached': False
        }
        if not transient_failure:
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
            'transient': False,
            'cached': False
        }
        _wiktionary_cache.put(cache_key, result)
        return result

    result = {
        'found': True,
        'word': word,
        'page_title': page_title,
        'entries': parsed_entries,
        'source': 'Wiktionary (Wikimedia REST API)',
        'wiktionary_url': f"https://en.wiktionary.org/wiki/{urllib.parse.quote(page_title)}",
        'transient': transient_failure,
        'cached': False
    }

    if not transient_failure:
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

SUPPORTED_LANG_CODES = {
    'en', 'es', 'fr', 'de', 'pt', 'ar', 'zh',
    'hi', 'bn', 'te', 'mr', 'ta', 'ur', 'gu', 'kn', 'ml', 'or', 'pa', 'as', 'sa'
}

# Translations listed per language are kept in page order (primary senses come first) up to this cap,
# so a rarely-used variant never outweighs the main equivalent.
MAX_TRANSLATIONS_PER_LANG = 3

# Only the first senses of a foreign headword are mined for direct glosses.
MAX_GLOSSED_SENSES = 2

# Words that only describe the *grammar* of a form: a definition built purely from them, followed by
# "of <word>", marks an inflected form ("plural of kitten", "inflection of viajar: ...").
GRAMMAR_WORDS = {
    'inflection', 'plural', 'singular', 'dual', 'participle', 'gerund', 'infinitive',
    'feminine', 'masculine', 'neuter', 'comparative', 'superlative',
    'genitive', 'dative', 'accusative', 'nominative', 'vocative', 'ablative', 'locative', 'instrumental',
    'past', 'present', 'future', 'tense', 'simple', 'perfect', 'imperfect', 'preterite',
    'indicative', 'subjunctive', 'imperative', 'conditional', 'active', 'passive', 'reflexive',
    'person', 'first', 'second', 'third', 'first-person', 'second-person', 'third-person',
    'form', 'forms', 'case', 'alternative', 'spelling', 'obsolete', 'archaic', 'dated', 'nonstandard',
    'misspelling', 'informal', 'formal', 'polite', 'standard', 'and', 'or',
    'definite', 'indefinite', 'attributive', 'predicative', 'strong', 'weak', 'mixed',
    'singulative', 'collective'
}

_OF_PATTERN = re.compile(r'^(.*?)\s+of\s+([^\s:;,()]+)', re.DOTALL)
_SYN_TEMPLATE = re.compile(r'\{\{syn(?:onyms)?\|([a-z\-]{2,8})\|([^}]+)\}\}')
# {{t|..}} {{t+|..}} and the tooltip variants {{tt|..}} {{tt+|..}} {{t-check|..}} {{t+check|..}}
_TRANS_TEMPLATE = re.compile(r'\{\{tt?(?:\+|-check|\+check|-simple)?\|([a-z\-]{2,8})\|([^}|]+)')
_MARKUP = re.compile(r'<[^>]+>|\[\[|\]\]')
_ARABIC_MARKS = re.compile('[ـً-ٰٟ]')


def normalize_link_term(raw: str) -> str:
    """
    Normalises a term scraped from Wiktionary so it can equal a tokenizer token:
    strips wiki/HTML markup, lower-cases, and drops Arabic vowel marks (tashkeel) that
    dictionaries add but running text almost never contains.
    """
    text = html.unescape(_MARKUP.sub('', raw or ''))
    return _ARABIC_MARKS.sub('', text.strip().lower()).strip()


def _is_cjk(text: str) -> bool:
    return any('一' <= c <= '鿿' for c in text)


def _acceptable_term(term: str, word: str) -> bool:
    """Single-token, non-stopword, non-slang candidates that differ from the headword itself."""
    return bool(
        term and
        ' ' not in term and
        ':' not in term and
        '{' not in term and
        term != word and
        (len(term) > 1 or _is_cjk(term)) and
        term not in DEFINITION_STOPWORDS and
        term not in DISALLOWED_METAPHOR_SLANG
    )


def parse_inflection_root(definition: str):
    """
    Returns the lemma if a definition only says "<grammatical description> of <lemma>", else None.
    'plural of kitten' -> 'kitten'; 'inflection of viajar: ...' -> 'viajar';
    'ellipsis of jardín delantero' -> None (not purely grammatical).
    """
    m = _OF_PATTERN.match((definition or '').strip())
    if not m:
        return None
    prefix_words = re.findall(r"[a-z]+(?:-[a-z]+)*", m.group(1).lower())
    if not prefix_words or any(w not in GRAMMAR_WORDS for w in prefix_words):
        return None
    return normalize_link_term(m.group(2)) or None


def _language_section(wikitext: str, language_name: str) -> str:
    """Returns the body of one '==Language==' section of a Wiktionary page ('' if absent)."""
    start = re.search(rf'(?m)^==\s*{re.escape(language_name)}\s*==\s*$', wikitext)
    if not start:
        return ''
    body = wikitext[start.end():]
    nxt = re.search(r'(?m)^==[^=].*==\s*$', body)
    return body[:nxt.start()] if nxt else body


def _fetch_wikitext(title: str):
    """Returns (status, wikitext) with the same 'ok' / 'missing' / 'error' status as _http_get_json."""
    url = (f"https://en.wiktionary.org/w/api.php?action=parse&page={urllib.parse.quote(title)}"
           f"&prop=wikitext&format=json&redirects=1")
    status, data = _http_get_json(url, timeout=5)
    if status != 'ok':
        return status, ''
    if 'error' in data:        # MediaWiki answers HTTP 200 + {"error": {"code": "missingtitle"}}
        return 'missing', ''
    return 'ok', data.get('parse', {}).get('wikitext', {}).get('*', '')


def _extract_wikitext_links(wikitext: str, section_lang, word: str) -> dict:
    synonyms = []
    syn_codes = {section_lang} if section_lang else SUPPORTED_LANG_CODES
    for m in _SYN_TEMPLATE.finditer(wikitext):
        if m.group(1) not in syn_codes:
            continue
        for piece in m.group(2).split('|'):
            # Named parameters (q1=archaic, t2=..., tr=...) are annotations, not synonyms.
            if '=' in piece:
                continue
            term = normalize_link_term(piece)
            if _acceptable_term(term, word) and len(term) > 2 and term not in synonyms:
                synonyms.append(term)

    translations = []
    # Translation tables only exist in the English section, and only describe an English headword.
    if section_lang in (None, 'en'):
        per_lang = {}
        for m in _TRANS_TEMPLATE.finditer(_language_section(wikitext, 'English')):
            code = m.group(1)
            if code not in SUPPORTED_LANG_CODES:
                continue
            term = normalize_link_term(m.group(2))
            if (_acceptable_term(term, word) and term not in translations
                    and per_lang.get(code, 0) < MAX_TRANSLATIONS_PER_LANG):
                translations.append(term)
                per_lang[code] = per_lang.get(code, 0) + 1

    return {'synonyms': synonyms[:8], 'translations': translations}


def get_wikitext_links(word: str, section_lang: str = None, page_title: str = None) -> dict:
    """
    One Wiktionary wikitext fetch yields both strict {{syn}} synonyms and {{t}}/{{tt}} translations
    (they used to be two identical HTTP requests). Cached in the O(1) LRU unless the fetch failed
    transiently, in which case 'complete' is False and the next call retries.
    """
    word = (word or '').strip().lower()
    if not word or len(word) < 2:
        return {'synonyms': [], 'translations': [], 'complete': True}

    cache_key = f"__wikilinks__::{section_lang or 'any'}::{page_title or word}"
    cached = _wiktionary_cache.get(cache_key)
    if cached is not None:
        return dict(cached)

    wikitext, complete = '', True
    for title in ([page_title] if page_title else _title_variants(word)):
        status, text = _fetch_wikitext(title)
        if status == 'ok':
            wikitext = text
            break
        if status == 'error':       # never fall through to another title after a failure
            complete = False
            break

    links = _extract_wikitext_links(wikitext, section_lang, word)
    links['complete'] = complete
    if complete:
        _wiktionary_cache.put(cache_key, links)
    return dict(links)


def get_wiktionary_synonyms(word: str) -> list:
    """
    Strict, high-confidence single-word synonyms from the main entry's {{syn|...}} templates.

    NOTE: We explicitly DO NOT query Wiktionary 'Thesaurus:<word>' pages because they are
    crowdsourced dumps of street slang, insults, and metaphors (e.g. associating 'cat' or 'dog' with 'man')
    which pollute search results and corrupt semantic meaning.
    """
    if len((word or '').strip()) < 3:
        return []
    return get_wikitext_links(word)['synonyms']


def get_wiktionary_translations(word: str) -> list:
    """
    Direct translation terms from Wiktionary's {{t|...}} / {{tt|...}} tables across the 20 supported
    languages (e.g. difficult -> मुश्किल, कठिन, difícil, difficile, schwierig). Uses O(1) LRU caching.
    """
    return get_wikitext_links(word)['translations'][:60]


def extract_meaning_expansion(word: str, preferred_lang: str = None) -> dict:
    """
    Queries Wiktionary to extract the genuine semantic meaning concepts of a word:
    - Primary definition summary for user display.
    - Direct glosses (translation equivalents in foreign definitions, e.g., 'receta' -> 'recipe', 'agua' -> 'water').
    - Inflection roots (e.g. 'viajar' from 'inflection of viajar', 'kitten' from 'plural of kitten').
    - Strict, curated single-word synonyms (e.g. 'automobile' -> 'car').
    - Translations from the English entry's translation table.

    When preferred_lang is given and the word has an entry in that language, only that language's
    entries are used (so Spanish 'pan' = bread is not mixed with English 'pan' = cookware).

    Excludes descriptive paragraph keywords, informal slang, and cross-category metaphors.
    Returns a structured dictionary; 'links' is the machine-readable result: (term, cost, hub) triples where
    cost 0 means "same word, different inflection" and cost 1 means "same meaning". `hub` says which side is
    the English headword that other languages hang off: 'other' (a foreign word glossed as `term`), 'self'
    (`term` is a translation listed under this word) or None (peers: inflections, synonyms).
    """
    clean_word = (word or '').strip().lower()
    if not clean_word:
        return {'found': False, 'word': '', 'all_meaning_terms': [], 'summary_definition': '',
                'links': [], 'complete': True}

    res = lookup_word(clean_word, preferred_lang=preferred_lang)
    if not res.get('found') or not res.get('entries'):
        return {
            'found': False,
            'word': clean_word,
            'all_meaning_terms': [],
            'summary_definition': '',
            'links': [],
            'complete': not res.get('transient', False),
            'cached': res.get('cached', False)
        }

    supported_entries = [e for e in res['entries'] if e.get('language') in SUPPORTED_LANG_NAMES]
    same_language = [e for e in supported_entries if preferred_lang and e.get('lang_code') == preferred_lang]
    entries = same_language or supported_entries
    section_lang = preferred_lang if same_language else None

    # Prioritise substantive parts of speech and real definitions over bare inflection lines
    def entry_priority(e):
        pos = e.get('part_of_speech', '')
        defs = e.get('definitions', [])
        first_def = defs[0] if defs else ''
        return (
            pos in ('Noun', 'Verb', 'Adjective', 'Interjection'),
            parse_inflection_root(first_def) is None
        )

    sorted_entries = sorted(entries, key=entry_priority, reverse=True)

    summary_def = ''
    inflection_summary = ''
    direct_glosses = []
    inflection_roots = []
    has_lemma_definition = False

    from modules.tokenizer import tokenize

    for entry in sorted_entries:
        is_english = entry.get('lang_code') == 'en'

        for sense_index, d in enumerate(entry.get('definitions', [])):
            root = parse_inflection_root(d)
            if root:
                if not inflection_summary:
                    inflection_summary = d
                if _acceptable_term(root, clean_word) and root not in inflection_roots:
                    inflection_roots.append(root)
                continue

            has_lemma_definition = True
            if not summary_def:
                summary_def = d

            # English definitions are prose ("Common, ordinary, domesticated."), not translation
            # equivalents, so only foreign-language entries yield direct glosses. Senses are listed by
            # prominence, so rare/slang later senses (German 'Apfel' #3 = "breasts") are not glossed.
            if is_english or sense_index >= MAX_GLOSSED_SENSES:
                continue

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
                    if _acceptable_term(tok, clean_word) and len(tok) > 2 and tok not in direct_glosses:
                        direct_glosses.append(tok)

    # A headword with a meaning of its own (French 'pomme' = apple, also a verb form of 'pommer')
    # is not an inflection; only words that are *purely* inflected forms point at a lemma.
    if has_lemma_definition:
        inflection_roots = []
    summary_def = summary_def or inflection_summary

    wiki = get_wikitext_links(clean_word, section_lang=section_lang, page_title=res.get('page_title'))
    strict_syns = wiki['synonyms']
    translations = wiki['translations']

    # Consolidate candidate meaning terms with their link cost and hub side (first source wins per term)
    links = []
    seen = set()
    for terms, cost, hub in ((inflection_roots, 0, None), (direct_glosses, 1, 'other'),
                             (strict_syns, 1, None), (translations, 1, 'self')):
        for t in terms:
            t_clean = normalize_link_term(t)
            if _acceptable_term(t_clean, clean_word) and t_clean not in seen:
                seen.add(t_clean)
                links.append((t_clean, cost, hub))

    return {
        'found': True,
        'word': clean_word,
        'summary_definition': summary_def,
        'direct_glosses': direct_glosses,
        'inflection_roots': inflection_roots,
        'thesaurus_synonyms': strict_syns[:6],
        'translations': translations[:15],
        'all_meaning_terms': [t for t, _cost, _hub in links],
        'links': links,
        'complete': wiki['complete'] and not res.get('transient', False),
        'wiktionary_url': res.get('wiktionary_url', f"https://en.wiktionary.org/wiki/{clean_word}"),
        'cached': res.get('cached', False)
    }
