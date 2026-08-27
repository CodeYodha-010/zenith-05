import fitz
from pathlib import Path


def extract_text_from_pdf(pdf_path):
    try:
        doc = fitz.open(pdf_path)
        full_text = ""
        
        for page in doc:
            text = page.get_text()
            full_text += f"\n\n[Page {page.number + 1}]\n{text}"
        
        doc.close()
        
        is_scanned = len(full_text.strip()) < 100
        
        return full_text.strip(), is_scanned
    
    except Exception as e:
        raise Exception(f"PDF extraction failed: {str(e)}")


def extract_sections_from_pdf(pdf_path):
    try:
        doc = fitz.open(pdf_path)
        sections = []
        
        for page in doc:
            text = page.get_text()
            if text.strip():
                sections.append({
                    "page": page.number + 1,
                    "text": text.strip(),
                    "heading": f"Page {page.number + 1}"
                })
        
        doc.close()
        return sections
    
    except Exception as e:
        raise Exception(f"Section extraction failed: {str(e)}")


def get_pdf_page_count(pdf_path):
    try:
        doc = fitz.open(pdf_path)
        count = len(doc)
        doc.close()
        return count
    except:
        return 0
