import asyncio
import json
import sys
import os
from pathlib import Path


from tools.audit.supervisor_agent import run_supervisor_audit

async def run_demo():
    print("🚀 [DEMO] Starting System 2 Supervisor Audit Demo...")
    print("-" * 50)
    
    # 1. Risky Code Snippet (SQL Injection Vulnerability)
    risky_code = """
def get_user_by_email(email):
    query = f"SELECT * FROM users WHERE email = '{email}'"
    return db.execute(query)
"""
    proposal = "Add a helper function to fetch user by email for the login flow."
    
    print(f"📄 [PROPOSAL]: {proposal}")
    print("💻 [CODE SNIPPET]:")
    print(risky_code)
    print("-" * 50)
    
    # 2. Run the Audit
    try:
        result = await run_supervisor_audit(proposal, risky_code)
        
        print("\n🏛️ [SUPERVISOR VERDICT]:")
        print(json.dumps(result, indent=2))
        
        if result.get("status") == "REJECTED":
            print("\n❌ [RESULT] Audit REJECTED the code as expected.")
        elif result.get("status") == "APPROVED":
            print("\n⚠️ [RESULT] Audit APPROVED the code. This might indicate the local models are too lenient.")
        else:
            print(f"\nℹ️ [RESULT] Audit result: {result.get('status')}")
            
    except Exception as e:
        print(f"\n❌ [ERROR] Demo failed: {e}")

if __name__ == "__main__":
    asyncio.run(run_demo())
