from tools.registry import sovereign_tool
from tools.utils.web_engine import WebSearchEngine, WebExtractEngine

@sovereign_tool(name="web_search", category="Sensory")
def web_search(query: str, limit: int = 5) -> dict:
    """
    Search the web for ranked results.
    
    Args:
        query: The search term or query.
        limit: Max results count.
    """
    engine = WebSearchEngine()
    return engine.search(query, limit)

@sovereign_tool(name="web_extract", category="Sensory")
def web_extract(urls: list[str]) -> dict:
    """
    Extract readable content from one or more URLs.
    
    Args:
        urls: List of source URLs to extract content from.
    """
    engine = WebExtractEngine()
    return engine.extract(urls)
