import chromadb
import sys
import json

CHROMA_HOST = '127.0.0.1'
CHROMA_PORT = 8000

print(f"Connecting to Chroma at {CHROMA_HOST}:{CHROMA_PORT}...\n")

try:
    client = chromadb.HttpClient(host=CHROMA_HOST, port=CHROMA_PORT)
    collections = client.list_collections()
except Exception as e:
    print(f"Failed to connect: {e}")
    sys.exit(1)

if not collections:
    print("Database is empty (no collections found).")
    sys.exit(0)

print("--- COLLECTIONS SUMMARY ---")
for c in collections:
    try:
        print(f"✅ {c.name}: {c.count()} documents")
    except Exception as e:
        print(f"❌ {c.name}: Error fetching count ({e})")

print("\n--- SAMPLE DATA ---")
for c in collections:
    if c.count() > 0:
        print(f"\nPeek into '{c.name}':")
        data = c.peek(1)
        doc = data['documents'][0][:200] + "..." if data['documents'] and data['documents'][0] else "[No text content]"
        meta = json.dumps(data['metadatas'][0], indent=2) if data['metadatas'] and data['metadatas'][0] else "{}"
        
        print(f"  Document Snippet: {doc}")
        print(f"  Metadata: {meta}")
        # Only show a sample for the first non-empty collection to keep output clean
        break
