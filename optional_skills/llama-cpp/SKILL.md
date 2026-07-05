---
kenbun:
  mode: document
  fidelity: high
  tech_stack: [python, c++, llama.cpp, bash]
  discovery_required: false
---

# llama.cpp + GGUF

Use this skill for local GGUF inference, quantization selection, or Hugging Face repository discovery for `llama.cpp`.

---

## When to Use
- Run local LLMs on CPU, Apple Silicon, CUDA, ROCm, or Intel GPUs.
- Find the correct GGUF for a specific Hugging Face repository.
- Build a `llama-server` or `llama-cli` command from the Hugging Face Hub.
- Search the Hugging Face Hub for models that already support `llama.cpp`.
- Enumerate available `.gguf` files and sizes for a repository.
- Decide between Q4/Q5/Q6/IQ variants based on the user's RAM or VRAM constraints.

---

## Model Discovery Workflow
*Prefer URL-based workflows before asking for HF, Python, or custom scripts.*

### 1. Search for Candidate Repositories on the Hub
- Base URL: `https://huggingface.co/models?apps=llama.cpp&sort=trending`
- Add `search=<term>` for a specific model family.
- Add `num_parameters=min:0,max:24B` or similar parameter filters when the user has hardware size constraints.

### 2. Open the Repository with local-app view
- Open `https://huggingface.co/<repo>?local-app=llama.cpp`.
- Treat the `local-app` snippet as the source of truth when visible:
  - Copy the exact `llama-server` or `llama-cli` command.
  - Report the recommended quantization exactly as Hugging Face shows it.
- Read the same URL as page text/HTML and extract the section under *Hardware compatibility*:
  - Prefer its exact quantization labels and sizes over generic tables.
  - Keep repo-specific labels such as `UD-Q4_K_M` or `IQ4_NL_XL`.
  - If that section is not visible, fall back to the tree API plus generic quantization guidance.

### 3. Query the Hugging Face Tree API to Confirm What Exists
- Request: `https://huggingface.co/api/models/<repo>/tree/main?recursive=true`
- Keep entries where `type` is `file` and `path` ends with `.gguf`.
- Use the `path` and `size` fields as the source of truth for filenames and byte sizes.
- Separate quantized checkpoints from `mmproj-*.gguf` projector files and BF16/shard files.
- Use `https://huggingface.co/<repo>/tree/main` only as a human fallback.

### 4. Reconstruct Command
- If the `local-app` snippet is not text-visible, reconstruct the command from the repo plus the chosen quantization:
  - **Shorthand:** `llama-server -hf <repo>:<QUANT>`
  - **Exact File:** `llama-server --hf-repo <repo> --hf-file <filename.gguf>`
- Only suggest converting from Transformers weights if the repository does not already expose GGUF files.

---

## Quick Start

### Install llama.cpp
- **macOS / Linux:**
  ```bash
  brew install llama.cpp
  ```
- **Windows:**
  ```bash
  winget install llama.cpp
  ```
- **From Source:**
  ```bash
  git clone https://github.com/ggml-org/llama.cpp
  cd llama.cpp
  cmake -B build
  cmake --build build --config Release
  ```

### Run Directly from Hugging Face Hub
```bash
llama-cli -hf bartowski/Llama-3.2-3B-Instruct-GGUF:Q8_0

# Start OpenAI-compatible server
llama-server -hf bartowski/Llama-3.2-3B-Instruct-GGUF:Q8_0
```

### Run Exact GGUF File from the Hub
Use this when the tree API shows custom file naming or the exact HF snippet is missing:
```bash
llama-server \
    --hf-repo microsoft/Phi-3-mini-4k-instruct-gguf \
    --hf-file Phi-3-mini-4k-instruct-q4.gguf \
    -c 4096
```

### OpenAI-Compatible Server Check
```bash
curl http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user", "content": "Write a limerick about Python exceptions"}
    ]
  }'
```

---

## Python Bindings (llama-cpp-python)
```bash
# Basic CPU/generic install
pip install llama-cpp-python

# GPU acceleration (CUDA)
CMAKE_ARGS="-DGGML_CUDA=on" pip install llama-cpp-python --force-reinstall --no-cache-dir

# GPU acceleration (Apple Silicon / Metal)
CMAKE_ARGS="-DGGML_METAL=on" pip install llama-cpp-python --force-reinstall --no-cache-dir
```

### Basic Generation
```python
from llama_cpp import Llama

llm = Llama(
    model_path="./model-q4_k_m.gguf",
    n_ctx=4096,
    n_gpu_layers=35,     # 0 for CPU, 99 to offload all layers to GPU
    n_threads=8,
)

out = llm("What is machine learning?", max_tokens=256, temperature=0.7)
print(out["choices"][0]["text"])
```

### Chat Completion + Streaming
```python
from llama_cpp import Llama

llm = Llama(
    model_path="./model-q4_k_m.gguf",
    n_ctx=4096,
    n_gpu_layers=35,
    chat_format="llama-3",   # or "chatml", "mistral", etc.
)

resp = llm.create_chat_completion(
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "What is Python?"},
    ],
    max_tokens=256,
)
print(resp["choices"][0]["message"]["content"])

# Streaming response
for chunk in llm("Explain quantum computing:", max_tokens=256, stream=True):
    print(chunk["choices"][0]["text"], end="", flush=True)
```

### Embeddings
```python
from llama_cpp import Llama

llm = Llama(model_path="./model-q4_k_m.gguf", embedding=True, n_gpu_layers=35)
vec = llm.embed("This is a test sentence.")
print(f"Embedding dimension: {len(vec)}")
```

### Direct-from-Hub pre-trained model loading
```python
from llama_cpp import Llama

llm = Llama.from_pretrained(
    repo_id="bartowski/Llama-3.2-3B-Instruct-GGUF",
    filename="*Q4_K_M.gguf",
    n_gpu_layers=35,
)
```

---

## Choosing a Quantization (Quant)
*Use the Hub page recommendations first, and generic heuristics second.*
- Prefer the exact quant marked as compatible for the user's hardware profile on the HF model page.
- **General chat/reasoning:** Start with `Q4_K_M`.
- **Coding or technical workflows:** Prefer `Q5_K_M` or `Q6_K` if memory allows.
- **Tight memory/RAM constraints:** Consider `Q3_K_M`, `IQ` variants, or `Q2` variants only if the user prioritizes fitting the model over quality.
- **Multimodal models:** Mention the `mmproj-*.gguf` multimodal projector separately. The projector is not the main model file.
- Do not normalize repo-native labels (e.g., if the page specifies `UD-Q4_K_M`, report `UD-Q4_K_M`).

---

## Output Format
When answering discovery requests, prefer a compact structured result:

```markdown
Repo: <repo>
Recommended quant from HF: <label> (<size>)
llama-server: <command>
Other GGUFs:
- <filename> - <size>
- <filename> - <size>
Source URLs:
- <local-app URL>
- <tree API URL>
```
