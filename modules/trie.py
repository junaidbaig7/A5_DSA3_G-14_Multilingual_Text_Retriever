class TrieNode:
    def __init__(self):
        self.children = {}
        self.is_end_of_word = False

class Trie:
    def __init__(self):
        self.root = TrieNode()

    def insert(self, word):
        """
        O(L) time complexity where L is the length of the word.
        """
        node = self.root
        for char in word:
            if char not in node.children:
                node.children[char] = TrieNode()
            node = node.children[char]
        node.is_end_of_word = True

    def search(self, word):
        """
        O(L) time complexity where L is the length of the word.
        """
        node = self.root
        for char in word:
            if char not in node.children:
                return False
            node = node.children[char]
        return node.is_end_of_word

    def get_words_with_prefix(self, prefix, limit=50):
        """
        Finds all words starting with prefix.
        Time Complexity: O(L + K) where L = len(prefix), K = nodes in subtree.
        Returns: (matching_words, nodes_visited)
        """
        node = self.root
        nodes_visited = 1
        for char in prefix:
            if char not in node.children:
                return [], nodes_visited
            node = node.children[char]
            nodes_visited += 1

        matches = []
        def _dfs(curr, current_word):
            nonlocal nodes_visited
            if len(matches) >= limit:
                return
            if curr.is_end_of_word:
                matches.append(current_word)
            for ch, child in sorted(curr.children.items()):
                nodes_visited += 1
                _dfs(child, current_word + ch)
                if len(matches) >= limit:
                    break

        _dfs(node, prefix)
        return matches, nodes_visited

    def count_nodes(self):
        """Total number of nodes in the Trie."""
        count = 0
        def _count(curr):
            nonlocal count
            count += 1
            for child in curr.children.values():
                _count(child)
        _count(self.root)
        return count

    def get_depth(self):
        """Maximum depth of the Trie."""
        def _depth(curr):
            if not curr.children:
                return 0
            return 1 + max(_depth(child) for child in curr.children.values())
        return _depth(self.root)

    def get_stats(self):
        return {
            'total_nodes': self.count_nodes(),
            'max_depth': self.get_depth()
        }

    def get_tree_structure(self, prefix="", max_depth=3, max_branches=5):
        """
        Extracts a JSON-serializable hierarchical tree starting from prefix
        for UI visualization.
        """
        node = self.root
        for char in prefix:
            if char not in node.children:
                return None
            node = node.children[char]

        def _build_node(char_val, curr, depth):
            item = {
                'char': char_val,
                'is_end': curr.is_end_of_word,
                'children': []
            }
            if depth >= max_depth:
                item['has_more'] = len(curr.children) > 0
                return item

            sorted_children = sorted(curr.children.items())[:max_branches]
            for ch, child in sorted_children:
                item['children'].append(_build_node(ch, child, depth + 1))
            if len(curr.children) > max_branches:
                item['truncated'] = len(curr.children) - max_branches
            return item

        return _build_node(prefix[-1] if prefix else 'root', node, 0)

