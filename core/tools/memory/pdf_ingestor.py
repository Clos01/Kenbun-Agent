import os
from pypdf import PdfReader
from tools.memory.knowledge_manager import learn_concept

def ingest_pdf_to_hivemind(pdf_path: str, tech_key: str = "general") -> str:
    """
    Reads a PDF, extracts text by page, and saves each page as a 'Concept' in the Hivemind.
    This allows for semantic retrieval of technical documentation.
    """
    from tools.infrastructure.config import settings
    from pathlib import Path
    
    # Path Traversal Guardrail
    try:
        resolved_path = Path(pdf_path).resolve()
        project_root = settings.PROJECT_ROOT.resolve()
        if not resolved_path.is_relative_to(project_root):
            return "ERROR: Security Sentinel blocked access to a PDF outside the authorized workspace."
        if not resolved_path.exists():
            return f"ERROR: PDF file not found at {pdf_path}"
    except Exception as e:
        return f"ERROR: Path resolution failed. {e}"

    try:
        # strict=True disables lenient parsing and reduces XXE surface area
        reader = PdfReader(str(resolved_path), strict=True)
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
