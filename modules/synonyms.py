# Synonyms Graph for Cross-Lingual Query Expansion
# Uses a simple Adjacency List for graph traversal to find equivalent words in other languages

class SynonymGraph:
    def __init__(self):
        self.adj = {}
        
    def add_synonyms(self, words):
        """
        Creates bidirectional edges between all words in the cluster.
        """
        for w1 in words:
            if w1 not in self.adj:
                self.adj[w1] = set()
            for w2 in words:
                if w1 != w2:
                    self.adj[w1].add(w2)
                    
    def get_synonyms(self, word):
        """
        BFS traversal to find all connected synonyms.
        """
        if word not in self.adj:
            return []
            
        visited = set([word])
        queue = [word]
        synonyms = []
        
        while queue:
            curr = queue.pop(0)
            for neighbor in self.adj.get(curr, []):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)
                    synonyms.append(neighbor)
                    
        return synonyms

# Global singleton for the application
synonym_graph = SynonymGraph()

# Build the cross-lingual synonym clusters
synonym_graph.add_synonyms(['pen', 'bolígrafo', 'पेन'])
synonym_graph.add_synonyms(['book', 'books', 'libro', 'libros', 'किताब', 'किताबें'])
synonym_graph.add_synonyms(['dog', 'dogs', 'perro', 'perros', 'कुत्ता', 'कुत्ते'])
synonym_graph.add_synonyms(['cat', 'cats', 'gato', 'gatos', 'बिल्ली', 'बिल्लियां'])
synonym_graph.add_synonyms(['pet', 'pets', 'mascota', 'mascotas', 'पालतू'])
synonym_graph.add_synonyms(['water', 'agua', 'पानी'])
synonym_graph.add_synonyms(['car', 'cars', 'coche', 'coches', 'कार'])
synonym_graph.add_synonyms(['room', 'rooms', 'habitación', 'habitaciones', 'कमरा', 'कमरे'])
synonym_graph.add_synonyms(['house', 'home', 'hogar', 'casa', 'घर'])
synonym_graph.add_synonyms(['clean', 'cleaning', 'limpieza', 'सफाई'])
synonym_graph.add_synonyms(['red', 'rojo', 'roja', 'लाल'])
synonym_graph.add_synonyms(['blue', 'azul', 'azules', 'नीला', 'नीले', 'नीली'])
synonym_graph.add_synonyms(['white', 'blanca', 'blanco', 'सफेद'])
synonym_graph.add_synonyms(['black', 'negro', 'negra', 'काला', 'काले', 'काली'])
synonym_graph.add_synonyms(['shoe', 'shoes', 'zapato', 'zapatos', 'जूता', 'जूते'])
synonym_graph.add_synonyms(['jacket', 'chaqueta', 'जैकेट'])
synonym_graph.add_synonyms(['coffee', 'café', 'कॉफी'])
synonym_graph.add_synonyms(['window', 'windows', 'ventana', 'ventanas', 'खिड़कियों', 'खिड़की'])
synonym_graph.add_synonyms(['chocolate', 'चॉकलेट'])
synonym_graph.add_synonyms(['cheap', 'budget', 'barato', 'सस्ता', 'सस्ती'])
synonym_graph.add_synonyms(['ai', 'artificial', 'inteligencia', 'कृत्रिम', 'बुद्धिमत्ता'])
synonym_graph.add_synonyms(['pasta', 'italian', 'italiana', 'इटालियन'])
synonym_graph.add_synonyms(['smartwatches', 'smartphones', 'teléfonos', 'inteligentes', 'स्मार्टफोन', 'गैजेट्स'])
synonym_graph.add_synonyms(['travel', 'trip', 'viaje', 'viajar', 'यात्रा', 'ट्रैवल'])
