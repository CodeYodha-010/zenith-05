import re
from rank_bm25 import BM25Okapi


class BM25SearchService:
    def __init__(self):
        self.indexes = {}
        self.sections_store = {}
        self.doc_metadata = {}
    
    def build_index(self, doc_id, sections):
        tokenized = [self._tokenize(s["text"]) for s in sections]
        
        if doc_id not in self.indexes:
            self.indexes[doc_id] = BM25Okapi(tokenized)
        else:
            self.indexes[doc_id] = BM25Okapi(tokenized)
        
        self.sections_store[doc_id] = sections
        
        self.doc_metadata[doc_id] = {
            "total_sections": len(sections),
            "keywords": self._extract_keywords(sections)
        }
    
    def _extract_keywords(self, sections):
        all_text = " ".join([s.get("text", "") for s in sections])
        words = re.findall(r'\b[a-zA-Z]{4,}\b', all_text.lower())
        
        word_freq = {}
        for word in words:
            word_freq[word] = word_freq.get(word, 0) + 1
        
        sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
        return [w[0] for w in sorted_words[:50]]
    
    def search(self, doc_id, query, top_k=3):
        if doc_id not in self.indexes:
            return []
        
        tokens = self._tokenize(query)
        scores = self.indexes[doc_id].get_scores(tokens)
        
        query_keywords = set(self._tokenize(query))
        
        boosted_scores = []
        for i, score in enumerate(scores):
            section = self.sections_store[doc_id][i]
            section_text = section.get("text", "").lower()
            
            boost = 0
            for keyword in query_keywords:
                if keyword in section_text:
                    boost += 0.5
            
            boosted_scores.append(score + boost)
        
        top_indices = sorted(
            range(len(boosted_scores)), 
            key=lambda i: boosted_scores[i], 
            reverse=True
        )[:top_k]
        
        return [self.sections_store[doc_id][i] for i in top_indices if i < len(self.sections_store[doc_id])]
    
    def search_all(self, all_sections, query, top_k=5):
        if not all_sections:
            return []
        
        tokenized = [self._tokenize(s["text"]) for s in all_sections]
        bm25 = BM25Okapi(tokenized)
        
        tokens = self._tokenize(query)
        scores = bm25.get_scores(tokens)
        
        query_keywords = set(self._tokenize(query))
        
        boosted_scores = []
        for i, score in enumerate(scores):
            section = all_sections[i]
            section_text = section.get("text", "").lower()
            
            boost = 0
            for keyword in query_keywords:
                if keyword in section_text:
                    boost += 0.5
            
            boosted_scores.append(score + boost)
        
        top_indices = sorted(
            range(len(boosted_scores)), 
            key=lambda i: boosted_scores[i], 
            reverse=True
        )[:top_k]
        
        return [all_sections[i] for i in top_indices if i < len(all_sections)]
    
    def _tokenize(self, text):
        return re.findall(r'\w+', text.lower())
    
    def get_doc_keywords(self, doc_id):
        return self.doc_metadata.get(doc_id, {}).get("keywords", [])
