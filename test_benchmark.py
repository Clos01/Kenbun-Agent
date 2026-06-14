import asyncio
from core.tools.audit.supervisor_agent import run_supervisor_audit
from core.tools.infrastructure.config import get_settings

async def run_benchmark():
    settings = get_settings()
    print(f"DEBUG: Using model -> {settings.PRIMARY_LLM_MODEL}")
    
    proposal = "Please review this Next.js page component for SEO and performance compliance."
    code = '''import { redirect } from "next/navigation";
export default function Page() {
    redirect("/new-page"); // Uses default redirect
}'''
    
    print("Running audit...")
    result = await run_supervisor_audit(proposal, code_snippet=code)
    print("AUDIT RESULT:")
    print(result)

if __name__ == "__main__":
    asyncio.run(run_benchmark())
