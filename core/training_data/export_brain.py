from unsloth import FastLanguageModel
import torch

# --- CONFIGURATION ---
model_dir = "kenbun_model_v1"
export_name = "kenbun-llama3"

print(f"📦 Loading trained brain from {model_dir}...")
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name = model_dir,
    max_seq_length = 2048,
    load_in_4bit = True,
)

print(f"🚀 Exporting to GGUF (Quantization: Q4_K_M)...")
print("Note: This might take a few minutes as it merges the weights.")

model.save_pretrained_gguf(
    export_name, 
    tokenizer, 
    quantization_method = "q4_k_m"
)

print(f"✨ SUCCESS! Your model is ready at: {export_name}.Q4_K_M.gguf")
print("👉 You can now load this file into Ollama or LM Studio.")
