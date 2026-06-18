import os
import logging
import uuid
from honcho import Honcho
from tools.infrastructure.config import settings

logger = logging.getLogger(__name__)

HONCHO_BASE_URL = os.getenv("HONCHO_BASE_URL", "http://127.0.0.1:8000")
_HONCHO_CLIENT = None
_CHROMA_CLIENT = None

def get_honcho_client():
    global _HONCHO_CLIENT
    # If Honcho base URL points to port 8000, it clashes with ChromaDB in local dev
    if "8000" in HONCHO_BASE_URL:
        return None
    if _HONCHO_CLIENT is None:
        try:
            logger.info(f"📡 Connecting to Honcho at {HONCHO_BASE_URL}...")
            _HONCHO_CLIENT = Honcho(base_url=HONCHO_BASE_URL)
        except Exception as e:
            logger.error(f"❌ Failed to connect to Honcho: {e}")
    return _HONCHO_CLIENT

def get_chroma_client():
    global _CHROMA_CLIENT
    if _CHROMA_CLIENT is None:
        try:
            import chromadb
            from chromadb.config import Settings
            logger.info(f"📡 Connecting to local ChromaDB at {settings.CHROMA_HOST}:{settings.CHROMA_PORT}...")
            _CHROMA_CLIENT = chromadb.HttpClient(
                host=settings.CHROMA_HOST,
                port=int(settings.CHROMA_PORT),
                settings=Settings(chroma_api_impl="chromadb.api.fastapi.FastAPI")
            )
            _CHROMA_CLIENT.heartbeat()
            logger.info("✅ Connected to ChromaDB successfully")
        except Exception as e:
            logger.error(f"❌ Failed to connect to ChromaDB client: {e}")
    return _CHROMA_CLIENT

def add_memory(content: str, category: str = "concepts"):
    """
    Sends a message to Honcho so it can reason over the information
    and store it in the peer's representation.
    """
    client = get_honcho_client()
    if not client:
        return
    
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
def upsert_embedding(id: str, document: str, metadata: dict, collection_name: str = None):
    """Adapter to map ChromaDB's upsert to Honcho's add_memory or local ChromaDB directly."""
    category = metadata.get("category", "concepts")
    chroma = get_chroma_client()
    if chroma:
        try:
            col_name = collection_name or category
            collection = chroma.get_or_create_collection(col_name)
            collection.upsert(ids=[id], documents=[document], metadatas=[metadata])
            return
        except Exception as e:
            logger.warning(f"⚠️ [CHROMA] Upsert failed: {e}. Falling back to Honcho.")
            
    content = f"METADATA: {metadata}\n\nCONTENT:\n{document}"
    add_memory(content, category=category)

def query_embeddings(query_text: str, n_results: int = 5, category: str = "concepts", filter_project: str = None, where: dict = None):
    """Adapter to map ChromaDB's query to Honcho's retrieve_memory or query local ChromaDB directly."""
    chroma = get_chroma_client()
    if chroma:
        try:
            collection = chroma.get_or_create_collection(category)
            res = collection.query(query_texts=[query_text], n_results=n_results)
            return {
                "ids": res.get("ids", [[]]),
                "documents": res.get("documents", [[]]),
                "metadatas": res.get("metadatas", [[]])
            }
        except Exception as e:
            logger.warning(f"⚠️ [CHROMA] Query failed: {e}. Falling back to Honcho.")

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
            upsert_embedding(id=str(uuid.uuid4()), document=doc, metadata=meta, collection_name=self.name)
            
    def upsert(self, ids, documents, metadatas=None):
        self.add(ids, documents, metadatas)
    def query(self, query_texts, n_results=5, where=None):
        return query_embeddings(query_texts[0], n_results=n_results, category=self.name)
    def count(self):
        chroma = get_chroma_client()
        if chroma:
            try:
                collection = chroma.get_or_create_collection(self.name)
                return collection.count()
            except Exception as e:
                logger.warning(f"⚠️ [CHROMA] Count failed: {e}")
        return 0

def get_project_collection(name: str):
    chroma = get_chroma_client()
    if chroma:
        try:
            return chroma.get_or_create_collection(name)
        except Exception as e:
            logger.warning(f"⚠️ [CHROMA] Failed to get/create collection {name}: {e}. Falling back to Dummy.")
    return DummyCollection(name)
