import asyncio
import aiohttp
import json
import sys

def log(msg):
    print(msg)
    with open("scratch/model_test_output.log", "a") as f:
        f.write(msg + "\n")

async def test_model(model_id):
    url = "http://lg2025.tailbe4852.ts.net:11434/api/chat"
    payload = {
        "model": model_id,
        "messages": [
            {"role": "system", "content": "You are a test helper. Say 'OK' if you can read this."},
            {"role": "user", "content": "Hello"}
        ],
        "stream": False,
        "options": {"temperature": 0.1}
    }
    
    log(f"Testing model: {model_id}...")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=90) as response:
                log(f"[{model_id}] HTTP Status: {response.status}")
                if response.status == 200:
                    data = await response.json()
                    log(f"[{model_id}] Response content: {data['message']['content']}")
                else:
                    text = await response.text()
                    log(f"[{model_id}] Error body: {text}")
    except Exception as e:
        log(f"[{model_id}] Exception: {type(e).__name__}: {e}")

async def main():
    # Clear log
    with open("scratch/model_test_output.log", "w") as f:
        f.write("=== Direct Model Test Start ===\n")
        
    models = ["gemma2:latest", "llama3.2:latest", "phi3:latest"]
    await asyncio.gather(*(test_model(m) for m in models))

if __name__ == "__main__":
    asyncio.run(main())
