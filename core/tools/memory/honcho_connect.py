import os
import logging
from honcho import Honcho
from tools.infrastructure.config import settings

logger = logging.getLogger(__name__)

HONCHO_BASE_URL = os.getenv("HONCHO_BASE_URL", "http://127.0.0.1:8000")
_HONCHO_CLIENT = None

def get_honcho_client():
    global _HONCHO_CLIENT
    if _HONCHO_CLIENT is None:
        try:
            logger.info(f"📡 Connecting to Honcho at {HONCHO_BASE_URL}...")
            _HONCHO_CLIENT = Honcho(base_url=HONCHO_BASE_URL)
        except Exception as e:
            logger.error(f"❌ Failed to connect to Honcho: {e}")
    return _HONCHO_CLIENT

def add_memory(content: str, category: str = "concepts"):
    """
    Sends a message to Honcho so it can reason over the information
    and store it in the peer's representation.
    """
    client = get_honcho_client()
    if not client: return
    
    session = client.session(category)
    peer_name = f"system_{settings.PROJECT_NAME}"
    peer = client.peer(peer_name)
    
    try:
        session.add_messages([peer.message(content)])
        logger.debug("✅ [HONCHO] Added memory successfully.")
    except Exception as e:
        logger.warning(f"⚠️ [HONCHO] Failed to add memory: {e}")

def retrieve_memory(query_text: str, n_results: int = 5, category: str = "concepts"):
    """
    Performs a semantic search against Honcho's reasoned representations.
    """
    client = get_honcho_client()
    if not client: 
        return []
        
    session = client.session(category)
    peer_name = f"system_{settings.PROJECT_NAME}"
    
    try:
        conclusions = session.representation(
            peer_name,
            search_query=query_text,
            search_top_k=n_results
        )
        
        # In Honcho, representation returns a list of conclusion objects or strings
        # We'll map them back to a simple string list
        results = []
        for c in conclusions:
            if hasattr(c, 'content'):
                results.append(c.content)
            elif isinstance(c, dict) and 'content' in c:
                results.append(c['content'])
            else:
                results.append(str(c))
                
        return results
    except Exception as e:
        logger.error(f"⚠️ [HONCHO] Query failed: {e}")
        return []

# --- ADAPTERS FOR BACKWARDS COMPATIBILITY ---
import uuid

def upsert_embedding(id: str, document: str, metadata: dict, collection_name: str = None):
    """Adapter to map ChromaDB's upsert to Honcho's add_memory."""
    category = metadata.get("category", "concepts")
    content = f"METADATA: {metadata}\n\nCONTENT:\n{document}"
    add_memory(content, category=category)

def query_embeddings(query_text: str, n_results: int = 5, category: str = "concepts", filter_project: str = None, where: dict = None):
    """Adapter to map ChromaDB's query to Honcho's retrieve_memory."""
    results = retrieve_memory(query_text, n_results=n_results, category=category)
    
    return {
        "ids": [[str(uuid.uuid4()) for _ in results]] if results else [[]],
        "documents": [results] if results else [[]],
        "metadatas": [[{"source": "honcho"}] * len(results)] if results else [[]]
    }

class DummyCollection:
    def __init__(self, name):
        self.name = name
    def add(self, ids, documents, metadatas=None):
        for doc, meta in zip(documents, metadatas or [{}] * len(documents)):
            upsert_embedding(id=str(uuid.uuid4()), document=doc, metadata=meta)
    def query(self, query_texts, n_results=5, where=None):
        return query_embeddings(query_texts[0], n_results=n_results)

def get_project_collection(name: str):
    return DummyCollection(name)

