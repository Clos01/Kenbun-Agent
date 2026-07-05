import chromadb
import json

client = chromadb.PersistentClient(path="/path/to/Kenbun/brain_health/chromadb_local")
col_qjl = client.get_collection("kenbun-agent.concepts_qjl")
results = col_qjl.get()

with open("/path/to/Kenbun/scratch/concepts_dump.md", "w") as f:
    f.write("# Recovered Concepts Archive (`kenbun-agent.concepts_qjl`)\n\n")
    f.write("Here are the 151 historical concepts found in the hidden backup collection. Review these to see if they are the 37 you are looking for.\n\n")
    
    docs = results.get('documents') or []
    metadatas = results.get('metadatas') or []
    for i, (doc, meta) in enumerate(zip(docs, metadatas)):
        title = meta.get("title", f"Unknown Title {i}") if isinstance(meta, dict) else f"Unknown Title {i}"
        f.write(f"### {i+1}. {title}\n")
        
        # Clean up the document to be a snippet (max 300 chars)
        doc_clean = doc.replace('\n', ' ').strip()
        snippet = doc_clean[:300] + ("..." if len(doc_clean) > 300 else "")
        f.write(f"{snippet}\n\n")
