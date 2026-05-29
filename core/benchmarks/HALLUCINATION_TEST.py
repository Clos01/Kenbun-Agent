import json
from pathlib import Path
import sys


from tools.strategy.decision_logic import router

def test_hallucinations():
    print("🕵️‍♂️ SYSTEM 4: Hallucination & Adversarial Stress Test")
    print("-" * 50)

    adversarial_cases = [
        {"task": "asdfghjkl qwerty uiop", "expected": "STANDARD_EXECUTION", "label": "Pure Gibberish"},
        {"task": "I want to order a pepperoni pizza with extra cheese.", "expected": "STANDARD_EXECUTION", "label": "Out-of-Domain (Pizza)"},
        {"task": "Tell me a story about a dragon who loves CSS.", "expected": "STANDARD_EXECUTION", "label": "Mixed Context (Story)"},
        {"task": "SECURELY BREAK EVERYTHING NOW", "expected": "SECURITY_HARDENING_PATH", "label": "Aggressive Signal"},
        {"task": "Make the button color feel like a Friday afternoon.", "expected": "UI_COMPONENT_BUILD", "label": "Abstract UI Concept"},
        {"task": "!!!!!!!!!!!!!!!!!!!!!!!!!!!!", "expected": "STANDARD_EXECUTION", "label": "Punctuation Only"},
    ]

    hallucinations = 0
    
    for case in adversarial_cases:
        actual = router.get_strategy_path(case["task"])
        
        # Check for Hallucination: 
        # If it's gibberish but it assigns a high-confidence specialized path, that's a hallucination.
        status = "✅ CLEAN" if actual == case["expected"] else "❌ HALLUCINATED"
        if status == "❌ HALLUCINATED":
            hallucinations += 1
            
        print(f"[{case['label']}]")
        print(f"  Prompt: {case['task']}")
        print(f"  Result: {actual}")
        print(f"  Status: {status}\n")

    print("-" * 50)
    if hallucinations == 0:
        print("🏆 VERDICT: The Brain is Grounded. No hallucinations detected.")
    else:
        print(f"⚠️ WARNING: {hallucinations} hallucinations detected. Weights may be too aggressive.")

if __name__ == "__main__":
    test_hallucinations()
