---
kenbun:
  mode: document
  fidelity: high
  tech_stack: [python, bash, vllm, torch]
  discovery_required: false
---

# vLLM - High-Performance LLM Serving

Deploy production LLM APIs, optimize inference latency/throughput, and serve large models efficiently with limited GPU memory. vLLM supports OpenAI-compatible endpoints, quantization (AWQ/GPTQ/FP8), prefix caching, and tensor parallelism.

---

## When to Use
- Deploying production-grade LLM APIs (100+ requests/second).
- Serving OpenAI-compatible API endpoints locally or in the cloud.
- Scaling inference using multiple GPUs with Tensor Parallelism.
- Serving quantized models (AWQ, GPTQ, FP8) to fit within reduced VRAM budgets.
- Decreasing Time-to-First-Token (TTFT) and increasing total output throughput.

---

## Quick Start
vLLM achieves up to 24× higher throughput than standard Hugging Face Transformers through PagedAttention (block-based KV cache) and continuous batching.

### Installation
```bash
pip install vllm
```

### Basic Offline Inference
```python
from vllm import LLM, SamplingParams

# Load the model
llm = LLM(model="meta-llama/Llama-3-8B-Instruct")
sampling = SamplingParams(temperature=0.7, max_tokens=256)

# Generate response
outputs = llm.generate(["Explain quantum computing"], sampling)
print(outputs[0].outputs[0].text)
```

### Start an OpenAI-Compatible API Server
```bash
vllm serve meta-llama/Llama-3-8B-Instruct
```

#### Query Server with OpenAI SDK
```python
from openai import OpenAI

client = OpenAI(base_url='http://localhost:8000/v1', api_key='EMPTY')
response = client.chat.completions.create(
    model='meta-llama/Llama-3-8B-Instruct',
    messages=[{'role': 'user', 'content': 'Hello!'}]
)
print(response.choices[0].message.content)
```

---

## Common Workflows

### Workflow 1: Production API Deployment

#### Step 1: Configure Server Settings
Choose a configuration template based on model size and hardware:
```bash
# 7B-13B models on a single GPU
vllm serve meta-llama/Llama-3-8B-Instruct \
  --gpu-memory-utilization 0.9 \
  --max-model-len 8192 \
  --port 8000

# 30B-70B models with 4-way tensor parallelism and AWQ quantization
vllm serve meta-llama/Llama-2-70b-hf \
  --tensor-parallel-size 4 \
  --gpu-memory-utilization 0.9 \
  --quantization awq \
  --port 8000

# Production configuration with prefix caching and Prometheus metrics enabled
vllm serve meta-llama/Llama-3-8B-Instruct \
  --gpu-memory-utilization 0.9 \
  --enable-prefix-caching \
  --enable-metrics \
  --metrics-port 9090 \
  --port 8000 \
  --host 0.0.0.0
```

#### Step 2: Test with Limited Traffic
Conduct a load test to verify performance:
```bash
# Install load tester
pip install locust

# Create a test script (locust -f test_load.py --host http://localhost:8000)
# Verify TTFT < 500ms and throughput meets expectations
```

#### Step 3: Enable Monitoring
Expose metrics via port `9090`:
```bash
curl http://localhost:9090/metrics | grep vllm
```
Key metrics to track:
- `vllm:time_to_first_token_seconds` - Time to first token latency.
- `vllm:num_requests_running` - Number of concurrent active requests.
- `vllm:gpu_cache_usage_perc` - KV cache allocation percentage.

#### Step 4: Deploy to Production
Run vLLM using a production Docker container:
```bash
docker run --gpus all -p 8000:8000 \
  vllm/vllm-openai:latest \
  --model meta-llama/Llama-3-8B-Instruct \
  --gpu-memory-utilization 0.9 \
  --enable-prefix-caching
```

#### Step 5: Verify Performance Metrics
- Time-to-First-Token (TTFT) is below 500ms for standard prompt lengths.
- Request throughput aligns with hardware ceilings.
- No Out of Memory (OOM) errors in logs.

---

### Workflow 2: Offline Batch Inference
Efficiently process massive datasets offline without spinning up a live HTTP server.

#### Step 1: Load Input Data
```python
prompts = []
with open("prompts.txt") as f:
    prompts = [line.strip() for line in f]
print(f"Loaded {len(prompts)} prompts")
```

#### Step 2: Configure LLM Engine
```python
from vllm import LLM, SamplingParams

llm = LLM(
    model="meta-llama/Llama-3-8B-Instruct",
    tensor_parallel_size=2,  # Span across 2 GPUs
    gpu_memory_utilization=0.9,
    max_model_len=4096
)

sampling = SamplingParams(
    temperature=0.7,
    top_p=0.95,
    max_tokens=512,
    stop=["</s>", "\n\n"]
)
```

#### Step 3: Run Batch Inference
vLLM will auto-batch inputs internally:
```python
outputs = llm.generate(prompts, sampling)
```

#### Step 4: Save Outputs
```python
import json

results = []
for output in outputs:
    results.append({
        "prompt": output.prompt,
        "generated": output.outputs[0].text,
        "tokens": len(output.outputs[0].token_ids)
    })

with open("results.jsonl", "w") as f:
    for r in results:
        f.write(json.dumps(r) + "\n")
```

---

### Workflow 3: Quantized Model Serving
Reduce VRAM requirements to host larger models on smaller GPUs.

#### Step 1: Select Quantization Method
- **AWQ:** Recommended for 70B+ models; preserves accuracy.
- **GPTQ:** High compatibility, fast generation speed.
- **FP8:** High-throughput serving on modern architectures (e.g., Hopper GPUs).

#### Step 2: Find Pre-quantized Hub Repository
Search Hugging Face for AWQ/GPTQ releases of your target model (e.g., `TheBloke/Llama-2-70B-AWQ`).

#### Step 3: Launch Server
```bash
# Serves a 70B AWQ model within ~40GB VRAM
vllm serve TheBloke/Llama-2-70B-AWQ \
  --quantization awq \
  --tensor-parallel-size 1 \
  --gpu-memory-utilization 0.95
```

---

## When to Use vs. Alternatives

| Aspect | vLLM | llama.cpp | TensorRT-LLM |
| :--- | :--- | :--- | :--- |
| **Use Case** | Multi-user High-Throughput APIs | Local CPU/Edge inference | Max Nvidia-specific performance |
| **Setup** | Moderate (Python/pip/Docker) | Easy (Binary/brew/C++) | Complex (Compilation/Nvidia tools) |
| **Format** | Hugging Face weights/AWQ/GPTQ | GGUF | TensorRT Engine |
| **Hosting** | Dedicated GPU servers | Laptops, CPU servers | Enterprise scale on Nvidia hardware |

---

## Troubleshooting

- **Out of Memory (OOM) during initialization:**
  - Reduce memory allocation: `--gpu-memory-utilization 0.7`.
  - Limit max context length: `--max-model-len 4096`.
  - Switch to a quantized variant: `--quantization awq`.
- **High Time-to-First-Token (TTFT):**
  - Enable prefix caching for repetitive prompts: `--enable-prefix-caching`.
  - Enable chunked prefill: `--enable-chunked-prefill`.
- **Model not found / loading issues:**
  - Ensure `--trust-remote-code` is supplied if loading custom model scripts.
- **Low throughput performance:**
  - Increase concurrent sequences: `--max-num-seqs 512`.
  - Verify GPU parallelism is configured to power-of-two increments (e.g. `--tensor-parallel-size 2` or `4`, not `3`).
  - Introduce draft models for speculative decoding: `--speculative-model DRAFT_MODEL`.

---

## Hardware Requirements

- **7B-13B models:** 1x A10 (24GB VRAM) or A100 (40GB VRAM).
- **30B-40B models:** 2x A100 (40GB VRAM) via Tensor Parallelism.
- **70B+ models:** 4x A100 (40GB VRAM) or 2x A100 (80GB VRAM).
