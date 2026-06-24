---
kenbun:
  mode: document
  fidelity: high
  tech_stack: [python, bash, transformers, vllm]
  discovery_required: false
---

# lm-evaluation-harness (LLM Benchmarking)

Evaluate LLMs across 60+ academic benchmarks (e.g., MMLU, HumanEval, GSM8K, TruthfulQA, HellaSwag). Use this skill when benchmarking model quality, comparing models, reporting academic results, or tracking training progress. 

---

## Prerequisites
- PyTorch-compatible environment with GPU (CUDA 11.8+) or CPU (very slow).
- VRAM requirements for FP16 evaluation:
  - **7B model:** ~16GB (or 8GB quantized in 8-bit).
  - **13B model:** ~28GB (or 14GB quantized in 8-bit).
  - **70B model:** Requires multi-GPU or heavy quantization.

---

## Quick Start

### Installation
```bash
pip install lm-eval
```

### Basic Evaluation
```bash
# Evaluate HuggingFace model on MMLU, GSM8K, and HellaSwag
lm_eval --model hf \
  --model_args pretrained=meta-llama/Llama-2-7b-hf \
  --tasks mmlu,gsm8k,hellaswag \
  --device cuda:0 \
  --batch_size 8
```

### List Available Tasks
```bash
lm_eval --tasks list
```

---

## Common Workflows

### Workflow 1: Standard Benchmark Evaluation

#### Step 1: Choose Benchmark Suite
- **Core Reasoning:** `mmlu` (57 subjects), `gsm8k` (grade school math), `hellaswag` (commonsense), `truthfulqa` (factuality), `arc_challenge` (science).
- **Code:** `humaneval` (Python code generation), `mbpp` (basic Python programming).
- **Standard release suite recommendation:** `--tasks mmlu,gsm8k,hellaswag,truthfulqa,arc_challenge`.

#### Step 2: Configure Model
- **Standard Hugging Face model:**
  ```bash
  lm_eval --model hf \
    --model_args pretrained=meta-llama/Llama-2-7b-hf,dtype=bfloat16 \
    --tasks mmlu \
    --device cuda:0 \
    --batch_size auto
  ```
- **Quantized (4-bit/8-bit):**
  ```bash
  lm_eval --model hf \
    --model_args pretrained=meta-llama/Llama-2-7b-hf,load_in_4bit=True \
    --tasks mmlu \
    --device cuda:0
  ```
- **Custom Local Checkpoint:**
  ```bash
  lm_eval --model hf \
    --model_args pretrained=/path/to/my-model,tokenizer=/path/to/tokenizer \
    --tasks mmlu \
    --device cuda:0
  ```

#### Step 3: Run Evaluation
```bash
# 5-shot evaluation with log samples output
lm_eval --model hf \
  --model_args pretrained=meta-llama/Llama-2-7b-hf \
  --tasks mmlu \
  --num_fewshot 5 \
  --batch_size 8 \
  --output_path results/ \
  --log_samples
```

#### Step 4: Analyze Results
Check the JSON file in `results/` for accuracy scores:
```json
{
  "results": {
    "mmlu": {
      "acc": 0.459,
      "acc_stderr": 0.004
    },
    "gsm8k": {
      "exact_match": 0.142,
      "exact_match_stderr": 0.006
    }
  }
}
```

---

### Workflow 2: Track Training Progress
Evaluate checkpoints periodically during training loop.

#### Step 1: Periodic Evaluation Script
```bash
#!/bin/bash
# eval_checkpoint.sh
CHECKPOINT_DIR=$1
STEP=$2

lm_eval --model hf \
  --model_args pretrained=$CHECKPOINT_DIR/checkpoint-$STEP \
  --tasks gsm8k,hellaswag \
  --num_fewshot 0 \
  --batch_size 16 \
  --output_path results/step-$STEP.json
```

#### Step 2: Choose Quick Benchmarks
- **Fast:** HellaSwag (~10 mins on 1 GPU), GSM8K (~5 mins), PIQA (~2 mins).
- **Slow (avoid during training):** MMLU (~2 hours), HumanEval (requires execution environment).

#### Step 3: Automate Execution
Integrate training loop callbacks (or simple shell wrapper checks) that invoke the evaluation script on saved model checkpoints.

---

### Workflow 3: Compare Multiple Models

#### Step 1: Define Model List
Write model IDs to a text file (e.g., `models.txt`):
```
meta-llama/Llama-2-7b-hf
meta-llama/Llama-2-13b-hf
mistralai/Mistral-7B-v0.1
```

#### Step 2: Run Evaluation Loop
```bash
TASKS="mmlu,gsm8k,hellaswag"
while read -r model; do
    model_name=$(echo "$model" | sed 's/\//-/g')
    lm_eval --model hf \
      --model_args pretrained="$model",dtype=bfloat16 \
      --tasks $TASKS \
      --num_fewshot 5 \
      --batch_size auto \
      --output_path results/"$model_name".json
done < models.txt
```

#### Step 3: Aggregate Results
Aggregate the JSON files into a markdown table comparing primary metrics.

---

### Workflow 4: Evaluate with vLLM (Fast Inference)
Use vLLM backend for 5-10× faster evaluation compared to standard HuggingFace:

```bash
# Install vLLM
pip install vllm

# Run vLLM evaluation
lm_eval --model vllm \
  --model_args pretrained=meta-llama/Llama-2-7b-hf,tensor_parallel_size=2,dtype=auto \
  --tasks mmlu \
  --batch_size auto
```

---

## Troubleshooting

- **Evaluation is too slow:**
  - Switch to the `--model vllm` backend.
  - Reduce fewshot templates: `--num_fewshot 0` (instead of 5).
  - Target subsets: `--tasks mmlu_stem` (STEM subjects only).
- **Out of Memory (OOM) Errors:**
  - Force batch size to 1: `--batch_size 1` or use `--batch_size auto`.
  - Use quantization: `--model_args pretrained=model-name,load_in_8bit=True`.
  - CPU offload: `--model_args pretrained=model,device_map=auto,offload_folder=offload`.
- **HumanEval Code Execution Disabled:**
  - Make sure `human-eval` is installed: `pip install human-eval`.
  - Pass the explicit permission flag: `--allow_code_execution`.
