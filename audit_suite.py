import sys, json, io, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, '.')
from app import app
client = app.test_client()

audit_results = []

def run_test(category, query, expected_concept, unacceptable_concepts=None, min_results=0, expect_typo_correction=None):
    start = time.time()
    res = client.get(f'/search?q={query}&meaning=0').get_json() # test core index + synonym + fuzzy
    latency = round((time.time() - start) * 1000, 1)
    
    corrected = res.get('corrected_query')
    results = res.get('results', [])
    
    matched_titles = [r['title'].lower() for r in results]
    matched_snippets = [r['snippet'].lower() for r in results]
    all_matched_text = ' '.join(matched_titles + matched_snippets)
    
    passed = True
    issues = []
    
    # 1. Typo correction check
    if expect_typo_correction is not None:
        if expect_typo_correction is False and corrected is not None:
            passed = False
            issues.append(f"Unexpected typo: '{query}' -> '{corrected}'")
        elif expect_typo_correction is not False and corrected != expect_typo_correction:
            passed = False
            issues.append(f"Expected typo '{expect_typo_correction}', got '{corrected}'")
            
    # 2. Unacceptable concept leakage check
    if unacceptable_concepts:
        for bad in unacceptable_concepts:
            for r in results:
                by_syn = [s.lower() for s in r.get('matched_by_synonym', [])]
                by_mean = [m.lower() for m in r.get('matched_by_meaning', [])]
                if bad.lower() in by_syn or bad.lower() in by_mean:
                    passed = False
                    issues.append(f"Semantic leakage! Result doc '{r['id']}' matched unwanted concept '{bad}'")
                    
    # 3. Expected concept match check
    if expected_concept and results and expected_concept != 'none':
        concept_found = any(expected_concept.lower() in t for t in matched_titles) or \
                        any(expected_concept.lower() in s for s in matched_snippets)
        if not concept_found and expected_concept in ('vehicle', 'car'):
            concept_found = any(k in all_matched_text for k in ['car', 'coche', 'कार', 'drive', 'conducir', 'चलाएं'])
        if not concept_found and expected_concept in ('dog', 'cat', 'pet'):
            concept_found = any(k in all_matched_text for k in ['pet', 'dog', 'cat', 'perro', 'gato', 'कुत्ते', 'बिल्ली', 'पालतू'])
        if not concept_found and expected_concept == 'man':
            concept_found = any(k in all_matched_text for k in ['man', 'men', 'masculina', 'पुरुष', 'पुरुषों'])
            
        if not concept_found:
            issues.append(f"Expected concept '{expected_concept}' not in top results")
            passed = False
            
    if min_results > 0 and len(results) < min_results:
        passed = False
        issues.append(f"Expected >= {min_results} results, got {len(results)}")
        
    status = '✓ PASS' if passed else '✗ FAIL'
    print(f"[{status}] {category:<16} | Query: '{query:<12}' | Results: {len(results):<2} | {latency}ms | Issues: {issues}", flush=True)
    
    audit_results.append({
        'category': category,
        'query': query,
        'passed': passed,
        'issues': issues
    })

print("="*80, flush=True)
print("STARTING COMPREHENSIVE SEMANTIC & DSA AUDIT", flush=True)
print("="*80, flush=True)

# 1. Transport & Vehicles (van, car, vehicle, coche, etc.)
run_test('Transport', 'van', 'vehicle', ['cat', 'dog', 'man'], min_results=1, expect_typo_correction=False)
run_test('Transport', 'car', 'vehicle', ['cat', 'dog', 'man'], min_results=1, expect_typo_correction=False)
run_test('Transport', 'vehicle', 'vehicle', ['cat', 'dog', 'man'], min_results=1, expect_typo_correction=False)
run_test('Transport', 'coche', 'vehicle', ['cat', 'dog', 'man'], min_results=1, expect_typo_correction=False)
run_test('Transport', 'गाड़ी', 'vehicle', ['cat', 'dog', 'man'], min_results=1, expect_typo_correction=False)

# 2. Animals (cat, dog, perro, gato, etc.)
run_test('Animals', 'cat', 'cat', ['car', 'van', 'man'], min_results=1, expect_typo_correction=False)
run_test('Animals', 'dog', 'dog', ['car', 'van', 'man'], min_results=1, expect_typo_correction=False)
run_test('Animals', 'pet', 'pet', ['car', 'van', 'man'], min_results=1, expect_typo_correction=False)
run_test('Animals', 'perro', 'dog', ['car', 'van', 'man'], min_results=1, expect_typo_correction=False)
run_test('Animals', 'gato', 'cat', ['car', 'van', 'man'], min_results=1, expect_typo_correction=False)
run_test('Animals', 'बिल्ली', 'cat', ['car', 'van', 'man'], min_results=1, expect_typo_correction=False)
run_test('Animals', 'कुत्ता', 'dog', ['car', 'van', 'man'], min_results=1, expect_typo_correction=False)

# 3. Humans & Fashion (man, men, fashion, पुरुष)
run_test('Human/Fashion', 'man', 'man', ['cat', 'dog', 'van'], min_results=1, expect_typo_correction=False)
run_test('Human/Fashion', 'men', 'man', ['cat', 'dog', 'van'], min_results=1, expect_typo_correction=False)
run_test('Human/Fashion', 'fashion', 'fashion', ['cat', 'dog', 'van'], min_results=1, expect_typo_correction=False)
run_test('Human/Fashion', 'पुरुषों', 'man', ['cat', 'dog', 'van'], min_results=1, expect_typo_correction=False)

# 4. Short 3-letter Confusable Words (MUST NEVER falsely typo-correct!)
run_test('Collision-Safety', 'can', 'none', expect_typo_correction=False)
run_test('Collision-Safety', 'pan', 'none', expect_typo_correction=False)
run_test('Collision-Safety', 'cap', 'none', expect_typo_correction=False)
run_test('Collision-Safety', 'hat', 'none', expect_typo_correction=False)
run_test('Collision-Safety', 'rat', 'none', expect_typo_correction=False)
run_test('Collision-Safety', 'bat', 'none', expect_typo_correction=False)
run_test('Collision-Safety', 'dot', 'none', expect_typo_correction=False)
run_test('Collision-Safety', 'fog', 'none', expect_typo_correction=False)
run_test('Collision-Safety', 'log', 'none', expect_typo_correction=False)
run_test('Collision-Safety', 'pin', 'none', expect_typo_correction=False)
run_test('Collision-Safety', 'run', 'none', expect_typo_correction=False)

# 5. Food & Coffee
run_test('Food', 'chocolate', 'chocolate', ['dog', 'cat', 'car', 'man'], min_results=1, expect_typo_correction=False)
run_test('Food', 'recipe', 'recipe', ['dog', 'cat', 'car', 'man'], min_results=1, expect_typo_correction=False)
run_test('Food', 'coffee', 'coffee', ['dog', 'cat', 'car', 'man'], min_results=1, expect_typo_correction=False)
run_test('Food', 'चॉकलेट', 'chocolate', ['dog', 'cat', 'car', 'man'], min_results=1, expect_typo_correction=False)
run_test('Food', 'কফি', 'coffee', ['dog', 'cat', 'car', 'man'], min_results=1, expect_typo_correction=False)

# 6. Technology & AI
run_test('Tech', 'ai', 'ai', ['dog', 'cat', 'chocolate'], min_results=1, expect_typo_correction=False)
run_test('Tech', 'technology', 'technology', ['dog', 'cat', 'chocolate'], min_results=1, expect_typo_correction=False)
run_test('Tech', 'smartphone', 'smartphone', ['dog', 'cat', 'chocolate'], min_results=1, expect_typo_correction=False)
run_test('Tech', 'स्मार्टफोन', 'smartphone', ['dog', 'cat', 'chocolate'], min_results=1, expect_typo_correction=False)

# 7. Travel & Cities
run_test('Travel', 'travel', 'travel', ['cat', 'dog', 'chocolate'], min_results=1, expect_typo_correction=False)
run_test('Travel', 'paris', 'paris', ['cat', 'dog', 'chocolate'], min_results=1, expect_typo_correction=False)
run_test('Travel', 'japan', 'japan', ['cat', 'dog', 'chocolate'], min_results=1, expect_typo_correction=False)
run_test('Travel', 'यात्रा', 'travel', ['cat', 'dog', 'chocolate'], min_results=1, expect_typo_correction=False)

# 8. Legitimate Typos (MUST correct!)
run_test('Typo-Resolution', 'receipe', 'recipe', expect_typo_correction='recipe')
run_test('Typo-Resolution', 'tecnolojia', 'technology', min_results=1) # Deliberate typo 'j' -> resolves to tecnologia/tecnología
run_test('Typo-Resolution', 'machne', 'machine', expect_typo_correction='machine')
run_test('Typo-Resolution', 'paela', 'paella', expect_typo_correction='paella')
run_test('Typo-Resolution', 'choclate', 'chocolate', expect_typo_correction='chocolate')


# 9. Out-of-Vocabulary Random Words
run_test('OOV-Random', 'elephant', 'none', expect_typo_correction=False)
run_test('OOV-Random', 'galaxy', 'none', expect_typo_correction=False)
run_test('OOV-Random', 'cryptocurrency', 'none', expect_typo_correction=False)
run_test('OOV-Random', 'banana', 'none', expect_typo_correction=False)

# Summary
total = len(audit_results)
passed_count = sum(1 for r in audit_results if r['passed'])
failed_count = total - passed_count

print("="*80, flush=True)
print(f"AUDIT SUMMARY: {passed_count}/{total} PASSED ({round(passed_count/total*100, 1)}%)", flush=True)
if failed_count == 0:
    print("ALL SEMANTIC & DSA INVARIANTS VERIFIED SUCCESSFULLY!", flush=True)
else:
    print(f"{failed_count} ISSUES DETECTED!", flush=True)
print("="*80, flush=True)
