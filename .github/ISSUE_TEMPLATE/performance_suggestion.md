---
name: Performance / Memory Suggestion
about: Suggest optimizations for RAM usage, GC latencies, CPU core efficiencies, or vector search speeds.
title: 'perf: [Short Description]'
labels: performance
assignees: ''
---

## ⚡ Performance / Memory Bottleneck
Describe the specific bottleneck or memory leak you have encountered.

## 📊 Metrics & Evidence
Please share any specific benchmark results, memory profiles, or telemetry evidence (e.g., CPython heap size, gc traces, search response times in milliseconds):
```text
[Paste profiling logs, metrics, or telemetry graphs here]
```

## 🛠️ Proposed Optimization
What specific adjustments do you suggest to optimize performance?
*   [ ] **CPython GC Tuning:** Tweaking generation thresholds or module freezing (`gc.freeze()`).
*   [ ] **Vector Store / ChromaDB:** HNSW clustering parameters or memory index compaction.
*   [ ] **Buffer Protocol / Zero-Copy:** Utilizing `memoryview` or `Span`-like constructs to avoid allocations.
*   [ ] **Model Quantization:** Transitioning model parameter formats (e.g., GGUF quant parameters).
*   [ ] **Other:** (Please describe below)

## 💻 Running Host Topology
Please specify your hardware details so we can understand the execution constraints:
*   **Host Environment:** (e.g. Lenovo ThinkStation P330 SFF, Proxmox VE VM)
*   **Resources:** (e.g., 6 CPU cores, 24GB RAM)
*   **Model Config:** (e.g., Llama 3.2 3B via Ollama CPU, Nomix-Embed-Text)
