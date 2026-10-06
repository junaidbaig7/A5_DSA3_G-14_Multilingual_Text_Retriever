# Synonyms Graph for Cross-Lingual Query Expansion
# Uses a simple Adjacency List (Hash Map of Sets) for BFS traversal
# Covers 20 languages: en, es, fr, de, pt, ar, zh + 13 Indian languages

from collections import deque

class SynonymGraph:
    def __init__(self):
        # Adjacency list: word -> set of synonyms  (Hash Map)
        self.adj = {}
        # List of defined clusters
        self.clusters = []

    def add_synonyms(self, words):
        """
        Creates bidirectional edges between all words in a synonym cluster.
        O(k^2) where k is the cluster size.
        """
        word_list = list(words)
        if word_list:
            self.clusters.append(word_list)

        for w1 in word_list:
            if w1 not in self.adj:
                self.adj[w1] = set()
            for w2 in word_list:
                if w1 != w2:
                    self.adj[w1].add(w2)

    def get_synonyms(self, word):
        """
        BFS traversal to find all connected synonyms across all languages.
        O(V + E) where V = vocabulary nodes, E = synonym edges.
        """
        if word not in self.adj:
            return []

        visited = {word}
        queue = deque([word])
        synonyms = []

        while queue:
            curr = queue.popleft()
            for neighbor in self.adj.get(curr, []):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)
                    synonyms.append(neighbor)

        return synonyms

    def get_cluster_with_steps(self, word):
        """
        Executes BFS and records detailed queue steps for interactive visualization.
        """
        if word not in self.adj:
            return {
                'found': False,
                'seed': word,
                'synonyms': [],
                'steps': [],
                'total_nodes': 0
            }

        visited = {word}
        queue = deque([word])
        synonyms = []
        steps = []
        step_idx = 1

        while queue:
            queue_snapshot = list(queue)
            curr = queue.popleft()
            new_discovered = []
            for neighbor in sorted(list(self.adj.get(curr, []))):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)
                    synonyms.append(neighbor)
                    new_discovered.append(neighbor)

            steps.append({
                'step': step_idx,
                'popped': curr,
                'queue_state': queue_snapshot,
                'discovered': new_discovered,
                'visited_total': len(visited)
            })
            step_idx += 1

        return {
            'found': True,
            'seed': word,
            'synonyms': synonyms,
            'steps': steps,
            'total_nodes': len(visited)
        }

    def get_all_cluster_heads(self):
        """Returns the representative head of each registered cluster."""
        heads = []
        seen = set()
        for cl in self.clusters:
            if cl and cl[0] not in seen:
                heads.append(cl[0])
                seen.add(cl[0])
        return sorted(heads)

    def get_graph_stats(self):
        total_edges = sum(len(n) for n in self.adj.values()) // 2
        return {
            'total_nodes': len(self.adj),
            'total_edges': total_edges,
            'total_clusters': len(self.clusters)
        }



# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------
synonym_graph = SynonymGraph()

# ===========================================================================
# Cross-lingual synonym clusters — all 20 languages
# ===========================================================================

# --- CHOCOLATE ---
synonym_graph.add_synonyms([
    'chocolate',                          # en
    'chocolat',                           # fr
    'schokolade',                         # de
    # es/pt share 'chocolate'
    'شوكولاتة',                           # ar
    '巧克力',                              # zh
    'चॉकलेट', 'चकलेट',                   # hi, mr, sa
    'চকলেট',                              # bn, as
    'చాక్లెట్',                           # te
    'சாக்லேட்',                           # ta
    'چاکلیٹ',                             # ur
    'ચોકલેટ',                             # gu
    'ಚಾಕೊಲೇಟ್',                          # kn
    'ചോക്കലേറ്റ്',                        # ml
    'ଚକୋଲେଟ',                             # or
    'ਚਾਕਲੇਟ',                             # pa
    'चाकलेट',                             # sa
])

# --- TRAVEL / TRIP ---
synonym_graph.add_synonyms([
    'travel', 'trip', 'backpacking',      # en
    'viaje', 'viajar',                    # es
    'voyage', 'voyager',                  # fr
    'reisen', 'rucksackreisen',           # de
    'viagem',                             # pt
    'سفر', 'التجوال',                     # ar
    '旅行', '穷游',                        # zh
    'यात्रा', 'ट्रैवल',                   # hi
    'ভ্রমণ',                              # bn
    'పర్యటన',                             # te
    'प्रवास',                             # mr
    'பயணம்',                              # ta
    'سفر',                                # ur
    'પ્રવાસ',                              # gu
    'ಪ್ರವಾಸ',                             # kn
    'യാത്ര',                              # ml
    'ଭ୍ରମଣ',                              # or
    'ਯਾਤਰਾ',                              # pa
    'ভ্ৰমণ',                              # as
    'यात्रा',                             # sa
])

# --- ARTIFICIAL INTELLIGENCE / AI ---
synonym_graph.add_synonyms([
    'ai', 'artificial', 'intelligence', 'machine', 'learning', # en
    'inteligencia', 'artificial',         # es
    'intelligence', 'artificielle',       # fr
    'künstliche', 'intelligenz',          # de
    'inteligência',                       # pt
    'الذكاء', 'الاصطناعي', 'التعلم',     # ar
    '人工智能', '机器学习',                # zh
    'एआई', 'कृत्रिम', 'बुद्धिमत्ता',    # hi
    'কৃত্রিম', 'বুদ্ধিমত্তা', 'এআই',    # bn
    'కృత్రిమ', 'మేధస్సు',               # te
    'कृत्रिम', 'बुद्धिमत्ता',           # mr (shares some with hi)
    'செயற்கை', 'நுண்ணறிவு',             # ta
    'مصنوعی', 'ذہانت',                   # ur
    'કૃત્રિમ',                           # gu
    'ಕೃತ್ರಿಮ', 'ಬುದ್ಧಿಮತ್ತೆ',           # kn
    'കൃത്രിമ', 'ബുദ്ധിമത്ത',           # ml
    'ଏଆଇ', 'ଯନ୍ତ୍ର',                    # or
    'ਆਰਟੀਫੀਸ਼ੀਅਲ', 'ਇੰਟੈਲੀਜੈਂਸ',        # pa
    'কৃত্ৰিম', 'বুদ্ধিমত্তা',            # as
])

# --- RECIPE / FOOD ---
synonym_graph.add_synonyms([
    'recipe', 'recipes', 'cook', 'cooking', 'baking', 'bake', # en
    'receta',                             # es
    'recette',                            # fr
    'rezept',                             # de
    'receita',                            # pt
    'وصفة',                               # ar
    '食谱',                                # zh
    'रेसिपी', 'विधि', 'रेसिपि',          # hi
    'রেসিপি', 'বেক',                     # bn
    'రెసిపీ',                             # te
    'रेसिपी',                            # mr
    'செய்முறை',                          # ta
    'ترکیب',                              # ur
    'રેસીપી',                             # gu
    'ರೆಸಿಪಿ',                            # kn
    'റെസിപ്പി',                          # ml
    'ରେସିପି',                             # or
    'ਵਿਧੀ',                              # pa
    'ৰেচিপি',                            # as
    'विधिः',                              # sa
])

# --- SMARTPHONE / GADGET / TECH ---
synonym_graph.add_synonyms([
    'smartphone', 'smartphones', 'smartwatch', 'smartwatches', 'gadget', 'gadgets', 'mobile', # en
    'teléfonos', 'inteligentes',          # es
    'smartphones', 'montres',             # fr
    'smartphones', 'smartwatches',        # de/pt share
    'هاتف', 'ذكي', 'الهواتف',           # ar
    '智能手机', '智能手表',               # zh
    'स्मार्टफोन', 'गैजेट्स',            # hi
    'স্মার্টফোন', 'গ্যাজেট',            # bn
    'స్మార్ట్‌ఫోన్', 'గ్యాడ్జెట్స్',    # te
    'स्मार्टफोन', 'गॅजेट्स',            # mr
    'ஸ்மார்ட்போன்', 'கேஜெட்கள்',        # ta
    'اسمارٹ', 'فون', 'گیجٹس',           # ur
    'સ્માર્ટફોન', 'ગેજેટ્સ',            # gu
    'ಸ್ಮಾರ್ಟ್‌ಫೋನ್', 'ಗ್ಯಾಜೆಟ್',        # kn
    'സ്മാർട്ട്ഫോൺ', 'ഗ്യാഡ്ജെറ്റ്',    # ml
    'ସ୍ମାର୍ଟଫୋନ',                        # or
    'ਸਮਾਰਟਫੋਨ',                          # pa
    'স্মাৰ্টফোন',                        # as
])

# --- TECHNOLOGY ---
synonym_graph.add_synonyms([
    'technology', 'tech', 'technological', # en
    'tecnología', 'tecnológicas',         # es
    'technologie',                        # fr
    'technologie', 'technologietrends',   # de
    'tecnologia',                         # pt
    'التكنولوجيا', 'تكنولوجيا',         # ar
    '技术', '科技',                        # zh
    'तकनीक', 'तकनीकी', 'प्रौद्योगिकी', # hi
    'প্রযুক্তি',                          # bn
    'సాంకేతికత', 'టెక్నాలజీ',           # te
    'तंत्रज्ञान',                        # mr
    'தொழில்நுட்பம்',                    # ta
    'ٹیکنالوجی',                         # ur
    'ટેક્નોલોજી', 'ટેકનોલોજી',           # gu
    'ತಂತ್ರಜ್ಞಾನ',                        # kn
    'സാങ്കേതിക', 'ടെക്',               # ml
    'ପ୍ରଯୁକ୍ତି',                          # or
    'ਤਕਨਾਲੋਜੀ',                          # pa
    'প্ৰযুক্তি',                          # as
    'प्रौद्योगिकी',                       # sa
])

# --- BUDGET / CHEAP / AFFORDABLE ---
synonym_graph.add_synonyms([
    'cheap', 'budget', 'affordable', 'inexpensive', # en
    'barato', 'barata',                   # es
    'pas', 'cher',                        # fr
    'günstig', 'preiswert',              # de
    'barato', 'barata',                   # pt
    'رخيص', 'رخيصة', 'ميزانية',         # ar
    '便宜', '穷',                          # zh
    'सस्ता', 'सस्ती', 'बजट',            # hi
    'সস্তা', 'বাজেট',                    # bn
    'చవకైన',                             # te
    'स्वस्त', 'बजेट',                   # mr
    'மலிவு', 'பட்ஜெட்',                 # ta
    'سستا', 'بجٹ',                       # ur
    'સસ્તી', 'બજેટ',                     # gu
    'ಅಗ್ಗದ', 'ಬಜೆಟ್',                  # kn
    'ചെലവ്', 'ബജറ്റ്',                 # ml
    'ସ୍ୱଳ୍ପ',                            # or
    'ਸਸਤੇ', 'ਬਜਟ',                      # pa
    'সস্তা',                              # as
])

# --- BOOK ---
synonym_graph.add_synonyms([
    'book', 'books',                      # en
    'libro', 'libros',                    # es
    'livre', 'livres',                    # fr
    'buch', 'bücher',                     # de
    'livro',                              # pt
    'كتاب', 'كتب',                       # ar
    '书', '图书',                          # zh
    'किताब', 'किताबें',                  # hi
    'বই', 'কিতাব',                       # bn
    'పుస్తకం',                           # te
    'पुस्तक',                            # mr
    'புத்தகம்',                           # ta
    'کتاب',                               # ur
    'પુસ્તક',                             # gu
    'ಪುಸ್ತಕ',                            # kn
    'പുസ്തകം',                            # ml
    'ପୁସ୍ତକ',                             # or
    'ਕਿਤਾਬ',                              # pa
    'কিতাপ',                              # as
])

# --- COFFEE ---
synonym_graph.add_synonyms([
    'coffee',                             # en
    'café',                               # es/fr
    'kaffee',                             # de
    'café',                               # pt
    'قهوة',                               # ar
    '咖啡',                                # zh
    'कॉफी',                              # hi
    'কফি', 'কফ্ফি',                     # bn
    'కాఫీ',                              # te
    'कॉफी',                              # mr
    'காபி',                               # ta
    'کافی',                               # ur
    'કૉફી',                              # gu
    'ಕಾಫಿ',                              # kn
    'കോഫി',                              # ml
    'ଚା',                                 # or
    'ਕੌਫੀ',                              # pa
    'কফি',                                # as
])

# --- PEN ---
synonym_graph.add_synonyms([
    'pen', 'pens',                        # en
    'bolígrafo', 'boligrafo', 'bolígrafos', 'boligrafos', 'pluma', 'plumas', # es
    'stylo', 'stylos', 'plume', 'plumes', # fr
    'stift', 'stifte', 'kugelschreiber',  # de
    'caneta', 'canetas',                  # pt
    'قلم',                                # ar
    '钢笔', '笔',                          # zh
    'पेन',                               # hi
    'পেন', 'কলম',                        # bn
    'పెన్',                              # te
    'पेन', 'लेखणी',                     # mr
    'பேனா',                              # ta
    'قلم',                                # ur
    'પેન',                               # gu
    'ಪೆನ್',                              # kn
    'പേന',                               # ml
    'ଲେଖଣୀ',                             # or
    'ਕਲਮ',                               # pa
    'কলম',                               # as
    'लेखनी',                             # sa
])

# --- DOG ---
synonym_graph.add_synonyms([
    'dog', 'dogs',                        # en
    'perro', 'perros',                    # es
    'chien',                              # fr
    'hund',                               # de
    'cão',                                # pt
    'كلب',                                # ar
    '狗',                                  # zh
    'कुत्ता', 'कुत्ते',                  # hi
    'কুকুর',                              # bn
    'కుక్క',                             # te
    'कुत्रा',                            # mr
    'நாய்',                               # ta
    'کتا',                                # ur
    'કૂતરો',                             # gu
    'ನಾಯಿ',                              # kn
    'നായ',                               # ml
    'କୁକୁର',                              # or
    'ਕੁੱਤਾ',                             # pa
    'কুকুৰ',                              # as
])

# --- CAT ---
synonym_graph.add_synonyms([
    'cat', 'cats',                        # en
    'gato', 'gatos',                      # es
    'chat',                               # fr
    'katze',                              # de
    'gato',                               # pt
    'قطة',                                # ar
    '猫',                                  # zh
    'बिल्ली', 'बिल्लियां',               # hi
    'বিড়াল',                            # bn
    'పిల్లి',                            # te
    'मांजर',                             # mr
    'பூனை',                              # ta
    'بلی',                                # ur
    'બિલ્લી',                            # gu
    'ಬೆಕ್ಕು',                            # kn
    'പൂച്ച',                             # ml
    'ବିଲେଇ',                              # or
    'ਬਿੱਲੀ',                              # pa
    'মেকুৰী',                             # as
])

# --- HOUSE / HOME ---
synonym_graph.add_synonyms([
    'house', 'home',                      # en
    'casa', 'hogar',                      # es
    'maison',                             # fr
    'haus',                               # de
    'casa',                               # pt
    'منزل', 'بيت',                       # ar
    '家', '房子',                          # zh
    'घर',                                # hi, sa (same word)
    'বাড়ি', 'ঘর',                       # bn
    'ఇల్లు',                             # te
    'घर',                                # mr (same)
    'வீடு',                               # ta
    'گھر',                                # ur
    'ઘર',                                 # gu
    'ಮನೆ',                               # kn
    'വീട്',                              # ml
    'ଘର',                                 # or
    'ਘਰ',                                # pa
    'ঘৰ',                                 # as
])

# --- WATER ---
synonym_graph.add_synonyms([
    'water',                              # en
    'agua',                               # es/pt
    'eau',                                # fr
    'wasser',                             # de
    'ماء',                                # ar
    '水',                                  # zh
    'पानी',                              # hi
    'পানি', 'জল',                        # bn
    'నీళ్ళు',                            # te
    'पाणी',                              # mr
    'தண்ணீர்',                            # ta
    'پانی',                               # ur
    'પાણી',                              # gu
    'ನೀರು',                              # kn
    'വെള്ളം',                            # ml
    'ଜଳ',                                 # or
    'ਪਾਣੀ',                              # pa
    'পানী',                               # as
])

# --- CLEAN / CLEANING ---
synonym_graph.add_synonyms([
    'clean', 'cleaning',                  # en
    'limpieza', 'limpiar',               # es
    'nettoyage',                          # fr
    'reinigung', 'sauber',               # de
    'limpeza',                            # pt
    'تنظيف',                              # ar
    '清洁', '打扫',                        # zh
    'सफाई', 'साफ',                       # hi
    'পরিষ্কার',                          # bn
    'శుభ్రత',                            # te
    'स्वच्छता',                          # mr
    'சுத்தம்',                            # ta
    'صفائی',                              # ur
    'સ્વચ્છ',                             # gu
    'ಶುಚಿ',                              # kn
    'വൃത്തി',                            # ml
    'ସଫା',                                # or
    'ਸਫ਼ਾਈ',                             # pa
    'পৰিষ্কাৰ',                           # as
])

# --- CAR / VEHICLE ---
synonym_graph.add_synonyms([
    'car', 'cars', 'van', 'vans', 'vehicle', 'vehicles', 'automobile', 'auto', # en
    'coche', 'coches', 'vehículo', 'furgoneta',   # es
    'voiture', 'véhicule', 'camionnette',         # fr
    'auto', 'fahrzeug', 'lieferwagen',            # de/pt
    'سيارة', 'مركبة',                              # ar
    '汽车', '车', '车辆',                           # zh
    'कार', 'गाड़ी', 'वाहन',                        # hi
    'গাড়ি', 'যানবাহন',                            # bn
    'కారు', 'వాహనం',                              # te
    'कार', 'गाडी', 'वाहन',                        # mr
    'கார்', 'வாகனம்',                             # ta
    'گاڑی', 'گاڑیاں',                              # ur
    'કાર', 'વાહન',                               # gu
    'ಕಾರ್', 'ವಾಹನ',                               # kn
    'കാർ', 'വാഹനം',                              # ml
    'ଗାଡ଼ି', 'ଯାନ',                                # or
    'ਕਾਰ', 'ਗੱਡੀ',                                # pa
    'গাড়ী', 'বাহন',                               # as
])


# --- PARIS ---
synonym_graph.add_synonyms([
    'paris',                              # en/fr/es/de/pt
    'باريس',                              # ar
    '巴黎',                                # zh
    'पेरिस', 'पैरिस',                   # hi
    'প্যারিস', 'পেরিস',                 # bn
    'ప్యారిస్',                          # te
    'पॅरिस',                             # mr
    'பாரிஸ்',                            # ta
    'پیرس',                               # ur
    'પેરિસ',                             # gu
    'ಪ್ಯಾರಿಸ್',                          # kn
    'പാരീസ്',                            # ml
    'ପ୍ୟାରିସ',                           # or
    'ਪੈਰਿਸ',                              # pa
    'পেৰিছ',                              # as
])

# --- JAPAN / TOKYO ---
synonym_graph.add_synonyms([
    'japan', 'tokyo', 'kyoto', 'sushi',  # en
    'japón',                              # es
    'japon',                              # fr
    'japan',                              # de/pt
    'اليابان', 'طوكيو',                  # ar
    '日本', '东京',                        # zh
    'जापान', 'टोक्यो',                  # hi
    'জাপান',                             # bn
    'జపాన్',                             # te
    'जपान',                              # mr
    'ஜப்பான்',                           # ta
    'جاپان',                              # ur
])

# --- FASHION ---
synonym_graph.add_synonyms([
    'fashion', 'style', 'wardrobe',      # en
    'moda',                               # es/pt
    'mode',                               # fr/de
    'موضة',                               # ar
    '时尚', '穿搭',                        # zh
    'फैशन',                              # hi
    'ফ্যাশন',                            # bn
    'ఫ్యాషన్',                           # te
    'फॅशन',                              # mr
    'ஃபேஷன்',                            # ta
    'فیشن',                               # ur
    'ફેશન',                              # gu
    'ಫ್ಯಾಷನ್',                           # kn
    'ഫാഷൻ',                              # ml
])

# --- FOOD / EAT ---
synonym_graph.add_synonyms([
    'food', 'eat', 'eating', 'dish',     # en
    'comida', 'comer',                   # es
    'nourriture', 'manger',              # fr
    'essen', 'gericht',                  # de
    'comida',                             # pt
    'طعام', 'أكل',                       # ar
    '食物', '吃',                          # zh
    'खाना', 'भोजन',                      # hi
    'খাবার', 'খাওয়া',                  # bn
    'తినడం', 'ఆహారం',                  # te
    'अन्न', 'खाणे',                     # mr
    'உணவு', 'சாப்பிட',                  # ta
    'کھانا',                              # ur
    'ખાવું', 'ખોરાક',                   # gu
    'ಊಟ', 'ತಿನ್ನು',                     # kn
    'ഭക്ഷണം', 'കഴിക്കൽ',              # ml
    'ଖାଦ୍ୟ',                              # or
    'ਖਾਣਾ',                              # pa
    'খোৱা',                               # as
])

# --- HOSTEL ---
synonym_graph.add_synonyms([
    'hostel', 'hostels',                  # en
    'albergue', 'hostel',                # es
    'auberge',                            # fr
    'hostel', 'herberge',                # de
    'albergue', 'hostel',               # pt
    'نزل', 'فندق',                       # ar
    '旅馆', '青年旅馆',                    # zh
    'हॉस्टेल',                           # hi
    'হোস্টেল',                          # bn
    'హోస్టల్',                          # te
    'होस्टेल',                           # mr
    'ஹோஸ்டல்',                           # ta
    'ہوسٹل',                              # ur
    'હૉસ્ટેલ',                           # gu
    'ಹೋಸ್ಟೆಲ್',                         # kn
    'ഹോസ്റ്റൽ',                          # ml
    'ହୋଷ୍ଟେଲ',                           # or
    'ਹੋਸਟਲ',                              # pa
    'হোষ্টেল',                            # as
])

# --- GREETINGS / HELLO ---
synonym_graph.add_synonyms([
    'hello', 'hi', 'hey', 'greetings', 'greeting',  # en
    'hola',                                         # es
    'bonjour', 'salut',                             # fr
    'hallo',                                        # de
    'olá', 'ola', 'oi',                             # pt
    'مرحبا', 'أهلا',                                 # ar
    '你好',                                         # zh
    'नमस्ते', 'नमस्कार',                            # hi
    'নমস্কার', 'হ্যালো',                             # bn
    'నమస్కారం', 'హలో',                              # te
    'नमस्कार', 'हॅलो',                              # mr
    'வணக்கம்', 'ஹலோ',                               # ta
    'سلام', 'ہیلو',                                 # ur
    'નમસ્તે', 'નમસ્કાર',                            # gu
    'ನಮಸ್ಕಾರ', 'ಹಲೋ',                               # kn
    'നമസ്കാരം', 'ഹലോ',                              # ml
    'ନମସ୍କାର',                                      # or
    'ਸਤਿ ਸ੍ਰੀ ਅਕਾਲ', 'ਹੈਲੋ',                        # pa
    'নমস্কাৰ',                                      # as
    'नमस्ते', 'नमस्कारः',                           # sa
])

# --- MAN / MEN ---
synonym_graph.add_synonyms([
    'man', 'men', 'male', 'gentleman',               # en
    'hombre', 'hombres', 'masculina',                # es
    'homme', 'hommes',                               # fr
    'mann', 'männer',                                # de
    'homem', 'homens',                               # pt
    'رجل', 'رجال',                                   # ar
    '男人', '男士',                                   # zh
    'पुरुष', 'पुरुषों', 'आदमी',                      # hi
    'পুরুষ', 'মানুষ',                                # bn
    'పురుషుడు', 'పురుషులు',                          # te
    'पुरुष', 'माणूस',                                # mr
    'ஆண்', 'மனிதன்',                                 # ta
    'مرد', 'آدمی',                                   # ur
    'પુરુષ', 'માણસ',                                 # gu
    'ಪುರುಷ', 'ಮನುಷ್ಯ',                               # kn
    'പുരുഷൻ',                                       # ml
    'ପୁରୁଷ',                                         # or
    'ਪੁਰਖ', 'ਆਦਮੀ',                                  # pa
    'পুৰুষ',                                         # as
    'पुरुषः',                                        # sa
])

# --- PET / PETS ---
synonym_graph.add_synonyms([
    'pet', 'pets',                                   # en
    'mascota', 'mascotas',                           # es
    'animal', 'animaux',                             # fr
    'haustier', 'haustiere',                         # de
    'mascote', 'mascotes',                           # pt
    'حيوان', 'أليف',                                 # ar
    '宠物',                                          # zh
    'पालतू',                                         # hi
    'পোষা',                                          # bn
    'పెంపుడు',                                       # te
    'पाळीव',                                         # mr
    'செல்லப்பிராணி',                                 # ta
    'پالتو',                                         # ur
    'પાલતુ',                                         # gu
    'ಸಾಕುಪ್ರಾಣಿ',                                   # kn
    'വളർത്തുമൃഗം',                                   # ml
    'ਪਾਲਤੂ',                                         # pa
    'পোহনীয়া',                                       # as
])

# --- DIFFICULT / HARD / COMPLICATED ---
synonym_graph.add_synonyms([
    'difficult', 'hard', 'tough', 'complicated',     # en
    'difícil', 'dificil', 'complejo',                # es
    'difficile', 'compliqué',                        # fr
    'schwierig', 'schwer',                           # de
    'difícil', 'dificil',                            # pt
    'صعب', 'معقد',                                   # ar
    '困难', '难',                                    # zh
    'मुश्किल', 'कठिन',                               # hi
    'কঠিন', 'মুশকিল',                                # bn
    'కష్టమైన', 'కష్టం',                              # te
    'कठीण', 'अवघड',                                  # mr
    'கடினம்', 'கடினமான',                             # ta
    'مشکل', 'کٹھن',                                  # ur
    'મુશ્કેલ', 'કઠિન',                               # gu
    'ಕಷ್ಟ', 'ಕಠಿಣ',                                  # kn
    'ബുദ്ധിമുട്ടുള്ള', 'പ്രയാസമുള്ള',                 # ml
    'କଠିନ', 'ମୁସ୍କିଲ',                               # or
    'ਔਖਾ', 'ਮੁਸ਼ਕਿਲ',                                 # pa
    'কঠিন', 'টান',                                   # as
    'कठिनम्', 'दुरूहम्',                             # sa
])

# --- EASY / SIMPLE ---
synonym_graph.add_synonyms([
    'easy', 'simple',                                # en
    'fácil', 'facil', 'sencillo',                    # es
    'facile', 'simple',                              # fr
    'einfach', 'leicht',                             # de
    'fácil', 'facil', 'simples',                     # pt
    'سهل', 'بسيط',                                   # ar
    '容易', '简单',                                   # zh
    'आसान', 'सरल',                                   # hi
    'সহজ', 'সরল',                                    # bn
    'సులభం', 'సులువు',                               # te
    'सोपे', 'सरळ',                                   # mr
    'எளிதான', 'சுலபமான',                             # ta
    'آسان', 'سہل',                                   # ur
    'સરળ', 'સહેલું',                                 # gu
    'ಸುಲಭ', 'ಸರಳ',                                   # kn
    'ലളിതമായ', 'എളുപ്പമുള്ള',                         # ml
    'ସହଜ', 'ସରଳ',                                    # or
    'ਸੌਖਾ', 'ਸਰਲ',                                   # pa
    'সহজ', 'সৰল',                                    # as
    'सरलम्', 'सुकरम्',                               # sa
])

# --- STORY / TALE ---
synonym_graph.add_synonyms([
    'story', 'tale', 'narrative',                    # en
    'cuento', 'historia', 'relato',                  # es
    'histoire', 'conte',                             # fr
    'geschichte', 'erzählung',                       # de
    'história', 'conto',                             # pt
    'قصة', 'رواية',                                  # ar
    '故事', '童话',                                   # zh
    'कहानी', 'कथा', 'किस्सा',                        # hi
    'গল্প', 'কাহিনী',                                 # bn
    'కథ', 'గాథ',                                     # te
    'गोष्ट', 'कथा',                                  # mr
    'கதை', 'சிறுகதை',                                # ta
    'کہانی', 'قصہ',                                  # ur
    'વાર્તા', 'કથા',                                 # gu
    'ಕಥೆ', 'ಗಾಥೆ',                                   # kn
    'കഥ', 'ചരിത്രം',                                 # ml
    'ଗଳ୍ପ', 'କାହାଣୀ',                                 # or
    'ਕਹਾਣੀ', 'ਗਾਥਾ',                                 # pa
    'কাহিনী', 'সাধুকথা',                              # as
    'कथा', 'आख्यायिका',                              # sa
])

# --- SUCCESS / VICTORY ---
synonym_graph.add_synonyms([
    'success', 'victory', 'achievement',             # en
    'éxito', 'exito', 'victoria',                    # es
    'succès', 'victoire',                            # fr
    'erfolg', 'sieg',                                # de
    'sucesso', 'vitória',                            # pt
    'نجاح', 'فوز',                                   # ar
    '成功', '胜利',                                   # zh
    'सफलता', 'कामयाबी', 'विजय',                      # hi
    'সফলতা', 'সাফল্য', 'বিজয়',                      # bn
    'విజయం', 'సఫలత',                                 # te
    'यश', 'सफलता',                                   # mr
    'வெற்றி', 'சாதிப்பு',                            # ta
    'کامیابی', 'فتح',                                 # ur
    'સફળતા', 'વિજય',                                 # gu
    'ಯಶಸ್ಸು', 'ವಿಜಯ',                                # kn
    'വിജയം', 'വിജയശ്രീ',                             # ml
    'ସଫଳତା', 'ବିଜୟ',                                 # or
    'ਸਫਲਤਾ', 'ਜਿੱਤ',                                 # pa
    'সাফল্য', 'বিজয়',                                 # as
    'सफलता', 'विजयः',                                # sa
])

# --- STUDENT / LEARNER ---
synonym_graph.add_synonyms([
    'student', 'pupil', 'learner',                   # en
    'estudiante', 'alumno',                          # es
    'étudiant', 'élève',                             # fr
    'schüler', 'student',                            # de
    'estudante', 'aluno',                            # pt
    'طالب', 'تلميذ',                                 # ar
    '学生', '学员',                                   # zh
    'छात्र', 'विद्यार्थी', 'शिष्य',                 # hi
    'ছাত্র', 'শিক্ষার্থী',                            # bn
    'విద్యార్థి', 'శిష్యుడు',                         # te
    'विद्यार्थी', 'छात्र',                           # mr
    'மாணவர்', 'மாணவன்',                              # ta
    'طالب', 'شاگرد',                                 # ur
    'વિદ્યાર્થી', 'શિષ્ય',                           # gu
    'ವಿದ್ಯಾರ್ಥಿ', 'ಶಿಷ್ಯ',                           # kn
    'വിദ്യാർത്ഥി', 'ശിഷ്യൻ',                         # ml
    'ଛାତ୍ର', 'ବିଦ୍ୟାର୍ଥୀ',                            # or
    'ਵਿਦਿਆਰਥੀ', 'ਚੇਲਾ',                              # pa
    'ছাত্ৰ', 'শিক্ষাৰ্থী',                            # as
    'छात्रः', 'विद्यार्थी',                          # sa
])

# --- TEACHER / MENTOR ---
synonym_graph.add_synonyms([
    'teacher', 'mentor', 'instructor', 'educator',   # en
    'profesor', 'maestro', 'mentor',                 # es
    'professeur', 'enseignant',                      # fr
    'lehrer', 'dozent',                              # de
    'professor', 'mestre',                           # pt
    'معلم', 'أستاذ',                                 # ar
    '老师', '教师',                                   # zh
    'शिक्षक', 'अध्यापक', 'गुरु',                     # hi
    'শিক্ষক', 'গুরু',                                # bn
    'గురువు', 'ఉపాధ్యాయుడు',                         # te
    'शिक्षक', 'गुरुजी',                              # mr
    'ஆசிரியர்', 'குரு',                               # ta
    'استاد', 'معلم',                                 # ur
    'શિક્ષક', 'ગુરુ',                                 # gu
    'ಶಿಕ್ಷಕ', 'ಗುರು',                                # kn
    'അധ്യാപകൻ', 'ഗുരു',                              # ml
    'ଶିକ୍ଷକ', 'ଗୁରୁ',                                # or
    'ਅਧਿਆਪਕ', 'ਗੁਰੂ',                                # pa
    'শিক্ষক', 'গুৰু',                                # as
    'गुरुः', 'उपाध्यायः',                            # sa
])

