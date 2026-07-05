import asyncio
from tools.strategy.hme_router import hme_router

async def test_integrity_chunking():
    print("🧪 Testing HME Integrity Layer (Truncation Prevention)...")
    
    # 1. Simple Task (Should be ATOMIC)
    simple_task = "Fix the background color of the login button"
    route_simple = hme_router.route_task(simple_task)
    print(f"Simple Task Integrity: {route_simple.get('integrity_flag')} (Volume: {route_simple.get('estimated_volume', 0)})")

    # 2. Massive Task (Should be CHUNKING_REQUIRED)
    massive_task = "Refactor the entire core orchestrator.py and the parallel_manager.py and implement a massive new dashboard telemetry system from scratch across 50 files"
    route_massive = hme_router.route_task(massive_task)
    print(f"Massive Task Integrity: {route_massive.get('integrity_flag')} (Volume: {route_massive.get('estimated_volume', 0)})")

    if route_massive.get('integrity_flag') == "CHUNKING_REQUIRED":
        print("✅ SUCCESS: HME successfully detected a potential truncation risk.")
    else:
        print("❌ FAILURE: HME failed to flag a massive task for chunking.")

if __name__ == "__main__":
    asyncio.run(test_integrity_chunking())
