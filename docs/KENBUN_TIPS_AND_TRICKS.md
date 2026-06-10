# 🌸 Kenbun-Agent: Tips & Tricks

Welcome to the Kenbun-Agent tips and tricks guide! These advanced patterns will help you harness the full potential of your cognitive sovereign workspace.

## 🧠 1. Smart Model Routing in Termchat
Kenbun features a **Bayesian Edge Router** that dynamically selects the best model. You can override it mid-conversation using tags in `kenbun chat`:
* **`@local`** — Forces the prompt to use your fastest local model (e.g., `gemma4:12b` or `deepseek-r1:8b`). Great for simple syntax parsing or avoiding API costs.
* **`@gemma` / `@deepseek`** — Overrides the router to explicitly use a specific local model.
* **Default behavior** — Automatically routes to the cloud provider (like Gemini) for complex, token-heavy tasks.

## 🛠️ 2. Zero-Config Custom Tools
You don't need to touch database tables or configuration files to add new capabilities to Kenbun:
1. Drop a new Python script inside any `core/tools/` subdirectory.
2. Decorate your function with `@sovereign_tool(name="tool_name", category="custom")`.
3. Kenbun's **Dynamic AST Harvester** will automatically parse and register the tool globally on its next run!

## ⚡ 3. Global CLI Shortcuts
Once installed, use the global `kenbun` command for instant operations without navigating to the project directory:
* **`kenbun chat`** — Instantly boot the Cognitive Agent Shell (Termchat).
* **`kenbun mcp`** — Automatically register Kenbun's tools with IDEs like Claude Desktop or Cursor via the Model Context Protocol.
* **`kenbun start` / `kenbun stop`** — Spin up or tear down the Docker Swarm Compose microservices in the background.

## ⌨️ 4. Tactile Navigation for SSH
If you are deploying Kenbun on a headless server or VM over SSH, network latency might break arrow key navigation in the interactive wizard.
* **Fallback:** Use **`w`** / **`k`** (Up) and **`s`** / **`j`** (Down) to navigate the menus safely.

## 🧹 5. Instant Stack Cleanup
Running out of disk space from large LLM Docker images or persistent volumes? 
* Open the `kenbun` wizard and select **Option 6: `🧹 Clean/Reset Swarm Stack`**. 
* You can choose a **Light Clean** (keeps base images) or a **Deep Purge** (recovers maximum host storage by destroying all cached LLM layers).

## 🎨 6. UI/UX Design Grounding
When building frontends, you can manually ask the agent to query the internal UI-UX database:
* Type `/search <query>` in Termchat to ground your session with specific HSL palettes, modern typography tokens, or layout designs before asking the agent to generate code.

## 🛡️ 7. The System 2 Audit Rule
Kenbun operates on a multi-tiered safety architecture. If you're using Kenbun to generate critical code:
* **Never commit blindly:** Always run `consult_supervisor(user_proposal, code_snippet)` to invoke the cognitive auditing layer (System 2). It checks for SQL injections, AST regressions, and architectural debt before merging.

## 🏎️ 8. Maximize Local GPU Performance (Linux)
If you are running on an Ubuntu/Linux machine with an NVIDIA GPU:
* Ensure you run `sudo ./scripts/setup_nvidia_gpu.sh` to install the NVIDIA Container Toolkit.
* If manually launching via Docker, append the GPU compose file to accelerate Ollama 10x:
  `docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d --build`
* Verify it's working by monitoring `watch -n 1 nvidia-smi`.

## 🌐 9. Decoupled Vector Database
Kenbun uses ChromaDB for AST Code Indexing. You can share one massive ChromaDB instance across multiple local developers or agents:
* Edit your `.env` and change `CHROMA_HOST` and `CHROMA_PORT` to point to your remote ChromaDB server instead of `localhost`.

## 🔍 10. Built-In System Telemetry
Typing `/system` in the Termchat instantly prints a secure audit of your active configuration, memory bindings, and current LLM provider—without leaking your raw API keys.
