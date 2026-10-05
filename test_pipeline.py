import sys
import json

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

from app import app

client = app.test_client()

print("--- 1. Testing Homepage ---")
res = client.get('/')
assert res.status_code == 200
assert b'Meaning Search' in res.data
print("✓ Homepage OK")

print("\n--- 2. Testing Meaning Retrieval for 'receta' (Spanish for Recipe) ---")
res = client.get('/search?q=receta&lang=all&meaning=true')
assert res.status_code == 200
data = res.get_json()
print(f"Results returned: {len(data['results'])}")
if data.get('meaning_info'):
    print(f"Primary definitions: {data['meaning_info'].get('definitions')[:1]}")
    print(f"Extracted meaning terms: {data['meaning_info'].get('meaning_terms')}")
for r in data['results'][:3]:
    print(f"  * [{r['lang']}] {r['title']} (Score: {r['score']}) | Meaning: {r.get('matched_by_meaning')}")

print("\n--- 3. Testing Meaning Retrieval for 'automobile' (maps to car) ---")
res = client.get('/search?q=automobile&lang=all&meaning=true')
assert res.status_code == 200
data = res.get_json()
print(f"Results returned: {len(data['results'])}")
if data.get('meaning_info'):
    print(f"Extracted meaning terms: {data['meaning_info'].get('meaning_terms')}")
for r in data['results'][:3]:
    print(f"  * [{r['lang']}] {r['title']} (Score: {r['score']}) | Meaning: {r.get('matched_by_meaning')}")

print("\n--- 4. Testing Meaning Retrieval for 'agua' (Spanish for Water) ---")
res = client.get('/search?q=agua&lang=all&meaning=true')
assert res.status_code == 200
data = res.get_json()
print(f"Results returned: {len(data['results'])}")
if data.get('meaning_info'):
    print(f"Extracted meaning terms: {data['meaning_info'].get('meaning_terms')}")
for r in data['results'][:3]:
    print(f"  * [{r['lang']}] {r['title']} (Score: {r['score']}) | Meaning: {r.get('matched_by_meaning')}")

print("\n--- 5. Testing Meaning Retrieval for 'किताब' (Hindi for Book) ---")
res = client.get('/search?q=किताब&lang=all&meaning=true')
assert res.status_code == 200
data = res.get_json()
print(f"Results returned: {len(data['results'])}")
for r in data['results'][:3]:
    print(f"  * [{r['lang']}] {r['title']} (Score: {r['score']}) | Exact: {r.get('matched_by_exact')}")

print("\n--- 6. Testing /api/define endpoint ---")
res = client.get('/api/define/algorithm')
assert res.status_code == 200
data = res.get_json()
print(f"Found: {data.get('found')}, definitions count: {len(data.get('entries', []))}")
assert data.get('found') is True

print("\n--- 7. Testing Benchmark endpoint ---")
res = client.get('/api/run_benchmark')
assert res.status_code == 200
data = res.get_json()
print(f"Indexed latency: {data.get('indexed_latency_ms')} ms, Naive: {data.get('naive_latency_ms')} ms, Fuzzy acc: {data.get('fuzzy_accuracy_pct')}%")

print("\nALL VERIFICATIONS PASSED!")
