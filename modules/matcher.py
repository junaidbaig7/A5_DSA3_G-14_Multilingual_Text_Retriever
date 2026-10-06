def edit_distance(word1, word2):
    """
    O(m * n) time complexity, where m and n are the lengths of the two words.
    Uses Dynamic Programming to compute Levenshtein distance.
    """
    m = len(word1)
    n = len(word2)
    dp = [[0] * (n + 1) for _ in range(m + 1)]

    for i in range(m + 1):
        dp[i][0] = i
    for j in range(n + 1):
        dp[0][j] = j

    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if word1[i - 1] == word2[j - 1]:
                cost = 0
            else:
                cost = 1
            dp[i][j] = min(dp[i - 1][j] + 1,          # Deletion
                           dp[i][j - 1] + 1,          # Insertion
                           dp[i - 1][j - 1] + cost)   # Substitution
    return dp[m][n]


def get_max_allowed_distance(word: str) -> int:
    """
    Computes the maximum permissible edit distance based on word length.
    Prevents short words (<= 3 chars like 'van', 'man', 'cat', 'car', 'dog', 'pen')
    from mutating into completely different words!
    
    Rule:
    - len <= 3: 0 edits (exact match only; 1-letter change completely changes word meaning!)
    - len 4..5: max 1 edit (e.g. 'paela' -> 'paella', 'cooke' -> 'cookie')
    - len >= 6: max 2 edits (e.g. 'receipe' -> 'recipe', 'tecnologia' -> 'tecnología')
    """
    length = len(word.strip())
    if length <= 3:
        return 0
    elif length <= 5:
        return 1
    else:
        return 2


def find_closest_word(word, vocabulary_words, max_distance=None):
    """
    O(V * m * n) time complexity where V is vocabulary size, 
    m is length of the query word, and n is average vocabulary word length.
    Uses length-based adaptive distance thresholds to prevent false positives on short words.
    """
    allowed_by_len = get_max_allowed_distance(word)
    if max_distance is None:
        effective_max = allowed_by_len
    else:
        effective_max = min(max_distance, allowed_by_len)

    if effective_max <= 0:
        return None

    best_word = None
    min_dist = float('inf')
    
    for vocab_word in vocabulary_words:
        # Optimization: if length difference is greater than effective_max, skip
        if abs(len(word) - len(vocab_word)) > effective_max:
            continue
            
        dist = edit_distance(word, vocab_word)
        if dist <= effective_max and dist < min_dist:
            min_dist = dist
            best_word = vocab_word
            
    return best_word


def get_dp_matrix_details(word1, word2):
    """
    Computes the full 2D Levenshtein Dynamic Programming table and
    reconstructs the optimal edit path and operation sequence.
    Time Complexity: O(m * n)
    Space Complexity: O(m * n)
    """
    m = len(word1)
    n = len(word2)
    dp = [[0] * (n + 1) for _ in range(m + 1)]

    for i in range(m + 1):
        dp[i][0] = i
    for j in range(n + 1):
        dp[0][j] = j

    for i in range(1, m + 1):
        for j in range(1, n + 1):
            cost = 0 if word1[i - 1] == word2[j - 1] else 1
            dp[i][j] = min(dp[i - 1][j] + 1,          # Deletion
                           dp[i][j - 1] + 1,          # Insertion
                           dp[i - 1][j - 1] + cost)   # Substitution

    # Backtrack optimal alignment path from (m, n) down to (0, 0)
    i, j = m, n
    path = [[i, j]]
    operations = []
    while i > 0 or j > 0:
        curr = dp[i][j]
        cost = 0 if (i > 0 and j > 0 and word1[i - 1] == word2[j - 1]) else 1

        if i > 0 and j > 0 and curr == dp[i - 1][j - 1] + cost:
            op_name = "match" if cost == 0 else "substitute"
            operations.append({
                "op": op_name,
                "cost": cost,
                "char1": word1[i - 1],
                "char2": word2[j - 1],
                "from": [i - 1, j - 1],
                "to": [i, j]
            })
            i -= 1
            j -= 1
        elif i > 0 and curr == dp[i - 1][j] + 1:
            operations.append({
                "op": "delete",
                "cost": 1,
                "char1": word1[i - 1],
                "char2": None,
                "from": [i - 1, j],
                "to": [i, j]
            })
            i -= 1
        else:
            operations.append({
                "op": "insert",
                "cost": 1,
                "char1": None,
                "char2": word2[j - 1] if j > 0 else '',
                "from": [i, j - 1],
                "to": [i, j]
            })
            j -= 1
        path.append([i, j])

    path.reverse()
    operations.reverse()

    return {
        "word1": word1,
        "word2": word2,
        "word1_chars": list(word1),
        "word2_chars": list(word2),
        "matrix": dp,
        "distance": dp[m][n],
        "path": path,
        "operations": operations
    }
