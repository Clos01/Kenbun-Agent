# Kenbun-Agent MCP Integration Guide

Kenbun-Agent operates as a native Model Context Protocol (MCP) server. This allows state-of-the-art AI developer IDEs and desktop assistants to connect directly to your Sovereign Swarm's System 3 (ChromaDB) and System 5 (AST Harvester) tools. 

Instead of blowing up expensive context windows by dragging your entire codebase into your IDE, you can let your IDE query the Kenbun MCP server, which will retrieve precisely the shadowed AST topology you need.

---

## 1. Google Antigravity Integration

Antigravity natively supports connecting to local or remote Dockerized MCP servers over HTTP/SSE. 

1. Ensure Kenbun-Agent is running (`docker compose up -d`).
2. Open your Antigravity Settings or the MCP Configuration Panel.
3. Add a new **MCP SSE Server**:
   * **Name**: `kenbun-agent`
   * **Endpoint URL**: `http://localhost:8001/sse`
4. The Antigravity Swarm will immediately inherit Kenbun's custom tools (e.g., AST semantic search, vulnerability audits).

---

## 2. Cursor (Codex) Integration

Cursor IDE allows you to add custom MCP servers directly from the Cursor settings menu.

1. Open Cursor Settings.
2. Navigate to **Features > MCP**.
3. Click **+ Add new MCP server**.
4. Set the **Type** to `sse` (Server-Sent Events).
5. Set the **Name** to `Kenbun`.
6. Set the **URL** to `http://localhost:8001/sse`.

Cursor will ping the FastMCP API and dynamically populate the `@Kenbun` context mention in your composer!

---

## 3. Claude Desktop Integration

Claude Desktop relies on standard IO (`stdio`) communication for MCPs. Because Kenbun runs inside an isolated Docker container (`portable_fastmcp`), you can route the stdio streams directly into the Docker shell.

1. Open your Claude Desktop configuration file:
   * **Mac:** `~/Library/Application Support/Claude/claude_desktop_config.json`
   * **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

2. Add the Kenbun integration node:

#### Option A: Dockerized Stdio MCP (For Docker Swarm users)
```json
{
  "mcpServers": {
    "kenbun": {
      "command": "docker",
      "args": [
        "exec",
        "-i",
        "portable_fastmcp",
        "python",
        "-m",
        "tools.infrastructure.server"
      ]
    }
  }
}
```

#### Option B: Standalone Native Stdio MCP (For virtualenv users)
```json
{
  "mcpServers": {
    "kenbun": {
      "command": "/absolute/path/to/kenbun-agent/venv/bin/python",
      "args": [
        "-m",
        "tools.infrastructure.server"
      ],
      "env": {
        "PYTHONPATH": "/absolute/path/to/kenbun-agent/core"
      }
    }
  }
}
```

3. Restart Claude Desktop. You will now see the Kenbun logo next to your tool pin!

---

## Architecture & Security Note

When an external IDE connects via MCP:
- The IDE **never** evaluates or executes arbitrary Python code directly. 
- All logic is passed through the Kenbun System 1 (Jail) and evaluated via recursive AST Math execution.
- If the IDE requests a sensitive AST chunk, Kenbun's Sovereign Cryptography module enforces clearance before releasing the code graph to the IDE context.
