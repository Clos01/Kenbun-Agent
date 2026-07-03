import sys
import asyncio
sys.path.insert(0, '/Users/carlosrivas/Dev/Kenbun/core')

from tools.audit.supervisor_agent import _call_local_senior

def main():
    print("Testing Kenbun LLM Router with Legion LM Studio...")
    system_prompt = "You are a helpful assistant."
    user_message = "Respond with 'Yes, the Legion LM Studio is receiving messages from Kenbun!'"
    
    # _call_local_senior is a synchronous wrapper in supervisor_agent
    result, error = _call_local_senior(system_prompt, user_message)
    
    print("\n--- RESULTS ---")
    print(f"Error: {error}")
    print(f"Response: {result}")

if __name__ == "__main__":
    main()
