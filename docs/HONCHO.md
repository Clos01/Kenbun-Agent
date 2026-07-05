# 🐝 Honcho & PostgreSQL Memory Architecture (System 3)

The Kenbun Hivemind (System 3) historically used a local ChromaDB instance to store "Neural Signals" (code concepts, variables, logic). However, as the system grew, it encountered a latent "ghost bug": dual-write and dual-read drift between ChromaDB and Honcho memory layers.

## The Honcho Integration

To resolve this ghost bug, Kenbun has formally deprecated ChromaDB and shifted entirely to a unified PostgreSQL architecture managed by **Honcho**.

### Why Honcho?
Honcho provides structured, graph-based memory storage designed specifically for agentic swarms. It allows for:
1. **Namespaced Memory**: Isolating memory by user, agent, and session ID.
2. **Metadata Tagging**: Easy filtering based on `project_id`, `hash`, or `tags`.
3. **Single Source of Truth**: Eliminating the dual-write drift that plagued the old ChromaDB system.

### PostgreSQL Backend
The Honcho integration leverages `postgres_client.py` to route all memory storage (AST chunks, architectural concepts, and history logs) directly into PostgreSQL. The database runs within the local Docker network (or Proxmox) and ensures ACID compliance.

## Integration Details

When an agent needs context:
1. It queries the `knowledge_manager.py`.
2. The `knowledge_manager` constructs a filter based on the deterministic `project_id` and the current context requirements.
3. The query is dispatched to the Honcho client, which searches the PostgreSQL vectors and returns context chunks.
4. The agent can also *write* back to the memory using the same adapter, ensuring perfect state synchronization.

This architectural shift guarantees that all cognitive state is preserved seamlessly, preventing hallucination regressions caused by stale memory reads.
