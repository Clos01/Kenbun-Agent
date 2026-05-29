from unsloth import FastLanguageModel, is_bfloat16_supported
import torch
from trl import SFTTrainer
from transformers import TrainingArguments
from datasets import load_dataset
import os

# --- CONFIGURATION ---
model_name = "unsloth/llama-3-8b-bnb-4bit"
dataset_path = "kenbun_dataset.jsonl"
output_dir = "kenbun_model_v1"

# 1. Load Model & Tokenizer
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name = model_name,
    max_seq_length = 1024,
    load_in_4bit = True,
)

# 2. Add LoRA
model = FastLanguageModel.get_peft_model(
    model,
    r = 16,
    target_modules = ["q_proj", "k_proj", "v_proj", "o_proj",
                      "gate_proj", "up_proj", "down_proj",],
    lora_alpha = 32,
    lora_dropout = 0,
    bias = "none",
    use_gradient_checkpointing = "unsloth",
    random_state = 3407,
)

# 3. Load & Format Dataset
dataset = load_dataset("json", data_files=dataset_path, split="train")

# Standard Llama 3 Template
from unsloth.chat_templates import get_chat_template
tokenizer = get_chat_template(
    tokenizer,
    chat_template = "llama-3",
    mapping = {"role" : "role", "content" : "content", "user" : "user", "assistant" : "assistant"},
)

def formatting_prompts_func(examples):
    messages = examples["messages"]
    texts = [tokenizer.apply_chat_template(convo, tokenize=False, add_generation_prompt=False) for convo in messages]
    return { "text" : texts }

dataset = dataset.map(formatting_prompts_func, batched = True,)

# 4. Training
trainer = SFTTrainer(
    model = model,
    tokenizer = tokenizer,
    train_dataset = dataset,
    dataset_text_field = "text",
    max_seq_length = 1024, # Clip length to save memory
    args = TrainingArguments(
        per_device_train_batch_size = 1,
        gradient_accumulation_steps = 4,
        warmup_steps = 2,
        max_steps = 15,
        learning_rate = 5e-5,
        fp16 = not is_bfloat16_supported(),
        bf16 = is_bfloat16_supported(),
        logging_steps = 1,
        optim = "adamw_8bit",
        seed = 3407,
        output_dir = "outputs",
        save_total_limit = 1,
    ),
)

print("🚀 Baking the Bulletproof Brain...")
trainer.train()

# 5. Save
model.save_pretrained(output_dir)
tokenizer.save_pretrained(output_dir)
print("✅ Success!")
