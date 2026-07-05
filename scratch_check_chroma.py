import asyncio
from core.tools.memory.honcho_connect import get_project_collection

collection = get_project_collection("code")
if collection:
    count = collection.count()
    print(f"Collection count: {count}")
    
    results = collection.get(limit=5)
    print(f"Results metadatas length: {len(results.get('metadatas', [])) if results else 'None'}")
else:
    print("Collection is None")
