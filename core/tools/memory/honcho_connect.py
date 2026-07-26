import os
import logging
import uuid
from honcho import Honcho
from tools.infrastructure.config import settings

logger = logging.getLogger(__name__)

HONCHO_BASE_URL = os.getenv("HONCHO_BASE_URL", "http://127.0.0.1:8000")
_HONCHO_CLIENT = None
_CHROMA_CLIENT = None

# The system self-model peer vs. the human user peer. Previously everything was
# attributed to the system peer, so Honcho never built a model of the user. The
# user peer lets the deriver learn Carlos's preferences/decisions over time.
def _system_peer() -> str:
    return f"system_{settings.PROJECT_NAME}"

USER_PEER = os.getenv("KENBUN_USER_PEER", "carlos")

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

def add_memory(content: str, category: str = "concepts", peer_name: str = None):
    """
    Sends a message to Honcho so it can reason over the information
    and store it in the peer's representation.

    peer_name defaults to the system self-model peer. Pass USER_PEER (or use
    add_user_memory) to attribute the message to the human user instead, so the
    deriver builds a model of the user's preferences.
    """
    client = get_honcho_client()
    if not client:
        return

    session = client.session(category)
    peer_name = peer_name or _system_peer()
    peer = client.peer(peer_name)

    try:
        session.add_messages([peer.message(content)])
        logger.debug(f"✅ [HONCHO] Added memory for peer '{peer_name}'.")
    except Exception as e:
        logger.warning(f"⚠️ [HONCHO] Failed to add memory: {e}")

def add_user_memory(content: str, category: str = "preferences"):
    """Attribute a message/decision to the human user peer so Honcho personalizes over time."""
    return add_memory(content, category=category, peer_name=USER_PEER)

def retrieve_memory(query_text: str, n_results: int = 5, category: str = "concepts", peer_name: str = None):
    """
    Performs a semantic search against Honcho's reasoned representations.
    peer_name defaults to the system peer; pass USER_PEER for the user's model.
    """
    client = get_honcho_client()
    if not client:
        return []

    session = client.session(category)
    peer_name = peer_name or _system_peer()

    try:
        conclusions = session.representation(
            peer_name,
            search_query=query_text,
            search_top_k=n_results
        )

        # SDK v2 returns the representation as one formatted string; iterating
        # it would yield single characters.
        if isinstance(conclusions, str):
            return [conclusions] if conclusions.strip() else []

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

def retrieve_user_memory(query_text: str, n_results: int = 5, category: str = "preferences"):
    """Retrieve the human user's reasoned representation (preferences/decisions)."""
    return retrieve_memory(query_text, n_results=n_results, category=category, peer_name=USER_PEER)

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
            # Fall back to Honcho if Chroma has no matching documents for this query
            if res.get("documents") and res["documents"][0]:
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
