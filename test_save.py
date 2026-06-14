import gc
gc.collect(2)
gc.freeze()

import sys
import traceback
from core.tools.infrastructure.server import save_to_hivemind

title = "Next.js Production SEO & Performance Audit Protocols"
content = """When conducting a terminal-based SEO audit of a production Next.js app, always verify:

Redirect Enforcement: Use curl -I http://domain.com to verify a 308 Permanent Redirect is served to preserve SEO link equity. NEVER accept a 307 Temporary Redirect (which is the default Next.js redirect() behavior).
TTFB: Run curl -s -w '%{time_starttransfer}s' to ensure response times are under 200ms. Look for x-vercel-cache: HIT to confirm CDN Edge delivery.
Semantic Schemas: Ensure layout.tsx and specific page components contain JSON-LD Schema markup (e.g., LocalBusiness) for local SEO snippets."""
category = "performance-and-seo"
tags = "seo, performance, nextjs, curl, audit"

try:
    print("Ingesting user rule into Hivemind...")
    result = save_to_hivemind(title=title, content=content, tags=tags, category=category)
    print(f"Result: {result}")
except Exception as e:
    print("Caught an exception!")
    traceback.print_exc()
