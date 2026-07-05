import os
import asyncio
import logging
import chromadb
from pathlib import Path
from honcho import Honcho
from core.tools.infrastructure.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- CONFIGURATION ---
CHROMA_HOST = settings.CHROMA_HOST
CHROMA_PORT = settings.CHROMA_PORT
PROJECT_NAME = settings.PROJECT_NAME

# By default, point Honcho SDK to the local docker instance we just configured
HONCHO_BASE_URL = os.getenv("HONCHO_BASE_URL", "http://127.0.0.1:8000")

def migrate_data():
    logger.info("📡 Connecting to ChromaDB...")
    try:
        from chromadb.config import Settings
        chroma_client = chromadb.HttpClient(
            host=CHROMA_HOST, 
            port=CHROMA_PORT,
            settings=Settings(
                chroma_api_impl="chromadb.api.fastapi.FastAPI"
            )
        )
        chroma_client.heartbeat()
        logger.info("✅ Connected to ChromaDB")
    except Exception as e:
        logger.error(f"❌ Failed to connect to ChromaDB: {e}")
        return

    logger.info(f"📡 Connecting to Honcho API at {HONCHO_BASE_URL}...")
    try:
        honcho_client = Honcho(base_url=HONCHO_BASE_URL)
        # We don't have a direct healthcheck method in the SDK, but initializing the client is synchronous
    except Exception as e:
        logger.error(f"❌ Failed to connect to Honcho: {e}")
        return

    # Create a Peer for the system or user
    peer_name = f"kenbun_system_{PROJECT_NAME}"
    logger.info(f"Creating Peer: {peer_name}")
    try:
        peer = honcho_client.peer(peer_name)
    except Exception as e:
        logger.error(f"❌ Failed to create Honcho Peer: {e}")
        return

    # Iterate over existing collections
    collections = chroma_client.list_collections()
    if not collections:
        logger.info("⚠️ No collections found in ChromaDB. Migration complete.")
        return

    for collection in collections:
        logger.info(f"📦 Processing Collection: {collection.name}")
        
        # Create a Session for this collection
        session_name = f"migration_{collection.name}"
        logger.info(f"Creating Session: {session_name}")
        session = honcho_client.session(session_name)
        
        # Retrieve all documents
        data = collection.get(include=['documents', 'metadatas'])
        documents = data.get('documents') or []
        metadatas = data.get('metadatas') or []
        
        if not documents:
            logger.info(f"  └─ Empty collection, skipping.")
            continue
            
        logger.info(f"  └─ Found {len(documents)} documents to migrate.")
        
        # We'll batch add messages to avoid overwhelming the system
        batch_size = 50
        messages_to_add = []
        
        for i, (doc, meta) in enumerate(zip(documents, metadatas)):
            # Add metadata as a JSON string to the message or pre-pend it
            msg_content = f"METADATA: {meta}\n\nCONTENT:\n{doc}"
            messages_to_add.append(peer.message(msg_content))
            
            if len(messages_to_add) >= batch_size:
                session.add_messages(messages_to_add)
                messages_to_add = []
                logger.info(f"  └─ Migrated batch up to index {i+1}")
                
        # Add any remaining messages
        if messages_to_add:
            session.add_messages(messages_to_add)
            logger.info(f"  └─ Migrated final batch")
            
    logger.info("🎉 Migration to Honcho complete!")
    logger.info("The Honcho deriver worker will now automatically process these messages in the background.")

if __name__ == "__main__":
    migrate_data()
