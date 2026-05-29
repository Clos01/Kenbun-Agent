import asyncio
from tools.strategy.strategy_manager import governor
from tools.strategy.hme_router import hme_router

async def test_bayesian_pivot():
    print("🧪 Testing Bayesian-HME Pivot Logic...")
    
    task = "Fix the background color of the login button"
    
    # 1. Healthy State
    governor.update_intelligence("local-ollama", "ui", True)
    governor.update_intelligence("local-ollama", "ui", True)
    route_healthy = hme_router.route_task(task)
    print(f"Healthy State Route: {route_healthy['worker']}")

    # 2. Unstable State (Simulate failures)
    print("📉 Simulating tool instability (Multiple failures)...")
    for _ in range(10):
        governor.update_intelligence("local-ollama", "ui", False)
    
    conf = governor.get_tool_confidence("local-ollama")
    print(f"Local Worker Confidence: {conf:.2%}")
    
    route_unstable = hme_router.route_task(task)
    print(f"Unstable State Route: {route_unstable['worker']}")

    if route_unstable['worker'] != route_healthy['worker']:
        print("✅ SUCCESS: HME successfully pivoted to a more stable expert.")
    else:
        print("❌ FAILURE: HME did not pivot despite tool instability.")

if __name__ == "__main__":
    asyncio.run(test_bayesian_pivot())
