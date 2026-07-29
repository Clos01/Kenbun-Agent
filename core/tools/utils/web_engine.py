import re
import os
import json
import logging
import asyncio
from typing import List, Dict, Any, Optional
import requests
from tools.infrastructure.config import settings

logger = logging.getLogger("web_engine")

def decrypt_value(val: Any) -> str:
    """Decrypt value if it is encrypted, otherwise return string representation."""
    if not val:
        return ""
    # Pydantic SecretStr compatibility
    if hasattr(val, "get_secret_value"):
        val_str = val.get_secret_value()
    else:
        val_str = str(val)
        
    if val_str.startswith("enc:v1:") or val_str.startswith("enc:"):
        return val_str.split(":", 2)[-1]
    return val_str

def ddgs_search(query: str, limit: int = 5) -> List[Dict[str, str]]:
    """Free DuckDuckGo scraping fallback without api keys."""
    results = []
    try:
        import html
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        url = f"https://html.duckduckgo.com/html/?q={requests.utils.quote(query)}"
        resp = requests.get(url, headers=headers, timeout=15)
        if resp.status_code == 200:
            body = resp.text
            # Result blocks are `<div class="result results_links results_links_deep
            # web-result ">`. The previous pattern looked for `result body`, which
            # matches nothing on the current markup -- so this returned [] on every
            # query while the caller still reported success. Sponsored blocks carry
            # `result--ad` in the same class attribute and are skipped.
            starts = [
                (m.start(), m.group(1))
                for m in re.finditer(r'<div class="(result results_links[^"]*)"', body)
            ]
            blocks = []
            for i, (pos, class_attr) in enumerate(starts):
                if "result--ad" in class_attr:
                    continue
                end = starts[i + 1][0] if i + 1 < len(starts) else len(body)
                blocks.append(body[pos:end])

            if not blocks:
                logger.warning(
                    "DuckDuckGo returned %d bytes but no parseable result blocks "
                    "-- the page layout likely changed, or the request was "
                    "challenged. Returning no results.", len(body)
                )

            # Match on the class attribute wherever it sits in the tag. The real
            # markup is `<a rel="nofollow" class="result__a" href="...">`, so the
            # old `<a class="result__a"` prefix match never fired even once the
            # blocks were split correctly.
            title_re = re.compile(
                r'<a\b([^>]*\bclass="[^"]*\bresult__a\b[^"]*"[^>]*)>(.*?)</a>', re.DOTALL)
            snippet_re = re.compile(
                r'<a\b[^>]*\bclass="[^"]*\bresult__snippet\b[^"]*"[^>]*>(.*?)</a>', re.DOTALL)

            for block in blocks[:limit]:
                title_match = title_re.search(block)
                snippet_match = snippet_re.search(block)
                if title_match:
                    href_match = re.search(r'href="([^"]+)"', title_match.group(1))
                    if not href_match:
                        continue
                    raw_url = href_match.group(1)
                    # Parse ddg redirects
                    if "uddg=" in raw_url:
                        redirect_match = re.search(r'uddg=([^&]+)', raw_url)
                        if redirect_match:
                            raw_url = requests.utils.unquote(redirect_match.group(1))
                    title = re.sub(r'<[^>]+>', '', title_match.group(2)).strip()
                    snippet = ""
                    if snippet_match:
                        snippet = re.sub(r'<[^>]+>', '', snippet_match.group(1)).strip()
                    results.append({
                        "title": html.unescape(title),
                        "url": raw_url,
                        "excerpt": html.unescape(snippet)
                    })
    except Exception as e:
        logger.debug(f"DuckDuckGo search fallback failed: {e}")
    return results

def raw_extract(url: str) -> str:
    """Fetch raw page and extract clean text fallback."""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        resp = requests.get(url, headers=headers, timeout=15)
        if resp.status_code == 200:
            text = resp.text
            text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r'<!--.*?-->', '', text, flags=re.DOTALL)
            text = re.sub(r'<[^>]+>', ' ', text)
            text = re.sub(r'\s+', ' ', text).strip()
            return text
    except Exception as e:
        return f"Failed to extract URL content: {e}"
    return ""

class ContentCompressor:
    """Tiered Content Compression: Summarizes web_extract content depending on size."""
    
    def __init__(self):
        self.llm_url = settings.PRIMARY_LLM_URL or "http://localhost:11434/v1"
        self.llm_model = settings.PRIMARY_LLM_MODEL or "qwen2.5:1.5b"
        
        # Override with auxiliary web_extract settings if configured
        if settings.AUXILIARY_WEB_EXTRACT_PROVIDER != "auto":
            # If using specific provider, resolve it. For standard local dev, we default to primary.
            pass
        if settings.AUXILIARY_WEB_EXTRACT_MODEL:
            self.llm_model = settings.AUXILIARY_WEB_EXTRACT_MODEL

    def _call_llm(self, system_prompt: str, user_content: str) -> str:
        """Call the auxiliary LLM synchronously."""
        headers = {"Content-Type": "application/json"}
        env = os.environ
        is_gemini_route = "gemini" in self.llm_url.lower() or "googleapis" in self.llm_url.lower()
        
        # Get Decrypted API Keys
        if "GEMINI_API_KEY" in env and is_gemini_route:
            headers["Authorization"] = f"Bearer {decrypt_value(env['GEMINI_API_KEY'])}"
        elif "OPENAI_API_KEY" in env and "openai" in self.llm_url.lower():
            headers["Authorization"] = f"Bearer {decrypt_value(env['OPENAI_API_KEY'])}"
        elif "DEEPSEEK_API_KEY" in env and "deepseek" in self.llm_url.lower():
            headers["Authorization"] = f"Bearer {decrypt_value(env['DEEPSEEK_API_KEY'])}"
            
        payload = {
            "model": self.llm_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            "temperature": 0.1
        }
        
        try:
            resp = requests.post(f"{self.llm_url}/chat/completions", json=payload, headers=headers, timeout=settings.AUXILIARY_WEB_EXTRACT_TIMEOUT)
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
        except Exception as e:
            logger.error(f"Auxiliary LLM compression call failed: {e}")
            return ""

    async def compress(self, text: str) -> str:
        """Run compression loop based on character size tiers."""
        size = len(text)
        
        # Tier 1: Under 5,000 characters -> return as-is
        if size < 5000:
            return text
            
        # Tier 4: Over 2,000,000 characters -> Refuse
        if size > 2000000:
            return "[Error: Content exceeds 2,000,000 characters. Please choose a more focused source URL.]"

        system_prompt = (
            "You are a web content summarization agent. Compress the provided web page text. "
            "Preserve code blocks, quotes, and key facts. Keep formatting clean. Output must not exceed 5000 characters."
        )

        # Tier 2: 5,000 to 500,000 characters -> Single-pass summary
        if size <= 500000:
            loop = asyncio.get_event_loop()
            summary = await loop.run_in_executor(None, self._call_llm, system_prompt, text)
            return summary if summary else text[:5000]

        # Tier 3: 500,000 to 2,000,000 characters -> Chunked parallel summary
        # Split into 100k chunks
        chunk_size = 100000
        chunks = [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]
        
        loop = asyncio.get_event_loop()
        tasks = []
        for chunk in chunks:
            tasks.append(loop.run_in_executor(None, self._call_llm, "Summarize this segment of a long web page. Keep key facts.", chunk))
            
        chunk_summaries = await asyncio.gather(*tasks)
        combined_summaries = "\n\n".join([s for s in chunk_summaries if s])
        
        # Synthesize final summary
        final_summary = await loop.run_in_executor(
            None,
            self._call_llm,
            system_prompt,
            f"Synthesize a final unified summary from these segment summaries:\n\n{combined_summaries}"
        )
        return final_summary if final_summary else text[:5000]


class WebSearchEngine:
    def __init__(self):
        self.backend = self._detect_backend()

    def _detect_backend(self) -> str:
        # 1. Explicit Search Backend
        if settings.WEB_SEARCH_BACKEND:
            return settings.WEB_SEARCH_BACKEND
            
        # 2. General Backend
        if settings.WEB_BACKEND and settings.WEB_BACKEND != "ddgs":
            return settings.WEB_BACKEND
            
        # 3. Auto-detect from environment
        env = os.environ
        if env.get("FIRECRAWL_API_KEY") or env.get("FIRECRAWL_API_URL"):
            return "firecrawl"
        if env.get("PARALLEL_API_KEY"):
            return "parallel"
        if env.get("TAVILY_API_KEY"):
            return "tavily"
        if env.get("EXA_API_KEY"):
            return "exa"
        if env.get("SEARXNG_URL"):
            return "searxng"
        if env.get("BRAVE_SEARCH_API_KEY"):
            return "brave"
            
        return "ddgs"

    def search(self, query: str, limit: int = 5) -> Dict[str, Any]:
        """Routes search queries to the resolved backend provider."""
        results = []
        
        try:
            if self.backend == "firecrawl":
                key = decrypt_value(settings.FIRECRAWL_API_KEY or os.environ.get("FIRECRAWL_API_KEY"))
                url = settings.FIRECRAWL_API_URL or os.environ.get("FIRECRAWL_API_URL") or "https://api.firecrawl.dev"
                headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
                payload = {"query": query, "limit": limit}
                resp = requests.post(f"{url}/v1/search", json=payload, headers=headers, timeout=15)
                if resp.status_code == 200:
                    for item in resp.json().get("data", []):
                        results.append({"title": item.get("title"), "url": item.get("url"), "excerpt": item.get("description")})
            
            elif self.backend == "searxng":
                base_url = settings.SEARXNG_URL or os.environ.get("SEARXNG_URL") or "http://localhost:8888"
                resp = requests.get(f"{base_url}/search?q={requests.utils.quote(query)}&format=json", timeout=15)
                if resp.status_code == 200:
                    for item in resp.json().get("results", []):
                        results.append({"title": item.get("title"), "url": item.get("url"), "excerpt": item.get("content")})
                        
            elif self.backend == "brave":
                key = decrypt_value(settings.BRAVE_SEARCH_API_KEY or os.environ.get("BRAVE_SEARCH_API_KEY"))
                headers = {"X-Subscription-Token": key, "Accept": "application/json"}
                resp = requests.get(f"https://api.search.brave.com/res/v1/web/search?q={requests.utils.quote(query)}&count={limit}", headers=headers, timeout=15)
                if resp.status_code == 200:
                    for item in resp.json().get("web", {}).get("results", []):
                        results.append({"title": item.get("title"), "url": item.get("url"), "excerpt": item.get("description")})
                        
            elif self.backend == "tavily":
                key = decrypt_value(settings.TAVILY_API_KEY or os.environ.get("TAVILY_API_KEY"))
                payload = {"query": query, "max_results": limit, "api_key": key}
                resp = requests.post("https://api.tavily.com/search", json=payload, timeout=15)
                if resp.status_code == 200:
                    for item in resp.json().get("results", []):
                        results.append({"title": item.get("title"), "url": item.get("url"), "excerpt": item.get("content")})
                        
            elif self.backend == "exa":
                key = decrypt_value(settings.EXA_API_KEY or os.environ.get("EXA_API_KEY"))
                headers = {"x-api-key": key, "Content-Type": "application/json"}
                payload = {"query": query, "numResults": limit}
                resp = requests.post("https://api.exa.ai/search", json=payload, headers=headers, timeout=15)
                if resp.status_code == 200:
                    for item in resp.json().get("results", []):
                        results.append({"title": item.get("title"), "url": item.get("url"), "excerpt": item.get("text")})
                        
            elif self.backend == "parallel":
                key = decrypt_value(settings.PARALLEL_API_KEY or os.environ.get("PARALLEL_API_KEY"))
                headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
                payload = {"query": query, "limit": limit}
                resp = requests.post("https://api.parallel.ai/v1/search", json=payload, headers=headers, timeout=15)
                if resp.status_code == 200:
                    for item in resp.json().get("results", []):
                        results.append({"title": item.get("title"), "url": item.get("url"), "excerpt": item.get("snippet")})
                        
            elif self.backend == "xai":
                # Grok web_search integration
                key = decrypt_value(settings.XAI_API_KEY or os.environ.get("XAI_API_KEY"))
                headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
                payload = {
                    "model": "grok-build-0.1",
                    "messages": [{"role": "user", "content": f"Search the web for: {query}"}],
                    "web_search": True
                }
                resp = requests.post("https://api.x.ai/v1/chat/completions", json=payload, headers=headers, timeout=90)
                if resp.status_code == 200:
                    # Parse Grok search annotations
                    search_results = resp.json().get("web_search_results", [])
                    for item in search_results[:limit]:
                        results.append({"title": item.get("title"), "url": item.get("url"), "excerpt": item.get("snippet")})

        except Exception as e:
            logger.error(f"Search provider '{self.backend}' failed: {e}")

        # Fallback to DDGS scraping if results are empty
        if not results:
            results = ddgs_search(query, limit)

        return {
            "success": True,
            "data": {
                "web": results
            }
        }


class WebExtractEngine:
    def __init__(self):
        self.backend = self._detect_backend()

    def _detect_backend(self) -> str:
        # 1. Explicit Extract Backend
        if settings.WEB_EXTRACT_BACKEND:
            return settings.WEB_EXTRACT_BACKEND
            
        # 2. General Backend
        if settings.WEB_BACKEND and settings.WEB_BACKEND != "ddgs":
            return settings.WEB_BACKEND
            
        # 3. Auto-detect from environment
        env = os.environ
        if env.get("FIRECRAWL_API_KEY") or env.get("FIRECRAWL_API_URL"):
            return "firecrawl"
        if env.get("TAVILY_API_KEY"):
            return "tavily"
        if env.get("EXA_API_KEY"):
            return "exa"
        if env.get("PARALLEL_API_KEY"):
            return "parallel"
            
        return "raw"

    def extract(self, urls: List[str]) -> Dict[str, Any]:
        """Routes URLs extraction to the resolved backend provider."""
        extracted_results = []
        compressor = ContentCompressor()

        # Handle multiple URLs concurrently or sequentially
        for url in urls:
            content = ""
            try:
                if self.backend == "firecrawl":
                    key = decrypt_value(settings.FIRECRAWL_API_KEY or os.environ.get("FIRECRAWL_API_KEY"))
                    api_url = settings.FIRECRAWL_API_URL or os.environ.get("FIRECRAWL_API_URL") or "https://api.firecrawl.dev"
                    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
                    payload = {"url": url}
                    resp = requests.post(f"{api_url}/v1/scrape", json=payload, headers=headers, timeout=15)
                    if resp.status_code == 200:
                        content = resp.json().get("data", {}).get("markdown", "")
                        
                elif self.backend == "tavily":
                    key = decrypt_value(settings.TAVILY_API_KEY or os.environ.get("TAVILY_API_KEY"))
                    payload = {"urls": [url], "api_key": key}
                    resp = requests.post("https://api.tavily.com/scrape", json=payload, timeout=15)
                    if resp.status_code == 200:
                        content = resp.json().get("results", [{}])[0].get("content", "")
                        
                elif self.backend == "exa":
                    key = decrypt_value(settings.EXA_API_KEY or os.environ.get("EXA_API_KEY"))
                    headers = {"x-api-key": key, "Content-Type": "application/json"}
                    payload = {"ids": [url]}
                    resp = requests.post("https://api.exa.ai/contents", json=payload, headers=headers, timeout=15)
                    if resp.status_code == 200:
                        content = resp.json().get("results", [{}])[0].get("text", "")
                        
                elif self.backend == "parallel":
                    key = decrypt_value(settings.PARALLEL_API_KEY or os.environ.get("PARALLEL_API_KEY"))
                    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
                    payload = {"url": url}
                    resp = requests.post("https://api.parallel.ai/v1/extract", json=payload, headers=headers, timeout=15)
                    if resp.status_code == 200:
                        content = resp.json().get("content", "")
            except Exception as e:
                logger.error(f"Extract provider '{self.backend}' failed for {url}: {e}")

            # Fallback to Raw Extract Scraper
            if not content.strip():
                content = raw_extract(url)

            # Apply Tiered Content Compression
            compressed_content = asyncio.run(compressor.compress(content))
            
            extracted_results.append({
                "url": url,
                "content": compressed_content
            })

        return {
            "success": True,
            "results": extracted_results
        }
