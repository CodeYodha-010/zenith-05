import re
from rank_bm25 import BM25Okapi


class PageIndexTreeBuilder:
    def __init__(self, llm_service=None):
        self.llm = llm_service
        self.max_depth = 2
        self.min_chunk_size = 500
        self.use_summaries = False
    
    def build_tree(self, sections, depth=0):
        if depth >= self.max_depth or len(sections) < 2:
            combined_text = "\n\n".join([s["text"] for s in sections])
            return {
                "summary": self._get_summary(combined_text) if self.use_summaries else "",
                "content": combined_text,
                "pages": list(set([s["page"] for s in sections])),
                "is_leaf": True
            }
        
        children = []
        group_size = max(2, len(sections) // 3)
        
        for i in range(0, len(sections), group_size):
            group = sections[i:i + group_size]
            child_tree = self.build_tree(group, depth + 1)
            children.append(child_tree)
        
        combined_text = "\n\n".join([s["text"] for s in sections])
        
        return {
            "summary": self._get_summary(combined_text) if self.use_summaries else "",
            "children": children,
            "pages": list(set([s["page"] for s in sections])),
            "is_leaf": False
        }
    
    def build_from_sections(self, sections):
        all_text = "\n\n".join([s["text"] for s in sections])
        
        if self.use_summaries:
            doc_summary = self._get_summary(all_text, max_length=300)
        else:
            doc_summary = all_text[:500] + "..." if len(all_text) > 500 else all_text
        
        tree = {
            "summary": doc_summary,
            "title": "Document Index",
            "children": self.build_tree(sections, depth=1).get("children", []),
            "is_leaf": False
        }
        
        return tree
    
    def _get_summary(self, text, max_length=200):
        if self.llm:
            try:
                return self.llm.summarize(text, max_length)
            except:
                pass
        
        words = text.split()[:50]
        return " ".join(words) + "..." if len(text.split()) > 50 else text
    
    def choose_branch(self, query, branches):
        branch_texts = [b.get("content", b.get("summary", "")) for b in branches]
        
        if not any(branch_texts):
            return 0
        
        bm25 = BM25Okapi([self._tokenize(t) for t in branch_texts])
        scores = bm25.get_scores(self._tokenize(query))
        
        return scores.argmax() if len(scores) > 0 else 0
    
    def _tokenize(self, text):
        return re.findall(r'\w+', text.lower())
