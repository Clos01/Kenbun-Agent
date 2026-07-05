import os
import re
import time
import requests
import json

from core.tools.infrastructure.config import settings
base_url = f"{settings.PRIMARY_LLM_URL}/chat/completions" if settings.PRIMARY_LLM_URL else "http://localhost:2065/v1/chat/completions"
model = "google/gemma-4-26b-a4b"

chinese_re = re.compile(r"[\u4e00-\u9fff]")

def translate_content(content):
    prompt = "You are a professional technical translator. Translate the following file content from Chinese to English. Preserve all markdown formatting, code blocks, HTML tags, frontmatter, and file structure exactly as is. Only translate the human-readable text. Do not add any conversational filler or markdown code blocks around your output if the input didn't have them. Content:\n\n" + content
    
    payload = {
        "model": model,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.1
    }
    
    try:
        response = requests.post(base_url, json=payload, headers={"Content-Type": "application/json"}, timeout=300)
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"API Error: {e}")
        return None

found_files = []
for root, _, files in os.walk(os.path.dirname(os.path.abspath(__file__))):
    if ".git" in root or ".venv" in root or "node_modules" in root or "__pycache__" in root:
        continue
    for file in files:
        if file.endswith((".py", ".md", ".html", ".js", ".ts", ".json", ".sh")):
            path = os.path.join(root, file)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                    if chinese_re.search(content):
                        found_files.append(path)
            except Exception:
                pass

print(f"Found {len(found_files)} files containing Chinese characters.")

for i, file_path in enumerate(found_files):
    print(f"[{i+1}/{len(found_files)}] Translating {file_path}...")
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        translated = translate_content(content)
        
        if translated:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(translated)
            print(f"✓ Translated {file_path}")
        else:
            print(f"✗ Failed to translate {file_path} (Empty response)")
            
    except Exception as e:
        print(f"✗ Failed to translate {file_path}: {e}")

print("Translation complete!")
