import os
from pypdf import PdfReader
from tools.memory.knowledge_manager import learn_concept

def ingest_pdf_to_hivemind(pdf_path: str, tech_key: str = "general") -> str:
    """
    Reads a PDF, extracts text by page, and saves each page as a 'Concept' in the Hivemind.
    This allows for semantic retrieval of technical documentation.
    """
    if not os.path.exists(pdf_path):
        return f"ERROR: PDF file not found at {pdf_path}"

    try:
        reader = PdfReader(pdf_path)
        total_pages = len(reader.pages)
        filename = os.path.basename(pdf_path)
        
        success_count = 0
        for i, page in enumerate(reader.pages):
            text = page.extract_text()
            if not text or len(text.strip()) < 50:
                continue
                
            title = f"Doc: {filename} - Page {i+1}"
            tags = f"pdf_ingestion, {tech_key}, {filename}"
            
            # Save to Hivemind as a 'tech_docs' category for better filtering
            res = learn_concept(title, text, tags, category="tech_docs")
            if "SUCCESS" in res:
                success_count += 1
                
        return f"SUCCESS: Ingested {success_count}/{total_pages} pages from '{filename}' into the Hivemind."
        
    except Exception as e:
        return f"ERROR: PDF Ingestion failed. {str(e)}"
