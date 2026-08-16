import os
from unittest.mock import patch, MagicMock
import pytest
from tools.utils.web_engine import WebSearchEngine, WebExtractEngine, ContentCompressor, ddgs_search, raw_extract
from tools.infrastructure.config import settings

@pytest.mark.asyncio
async def test_content_compressor_tier1():
    """Verifies that pages under 5,000 characters are returned as-is (no LLM call)."""
    compressor = ContentCompressor()
    text = "Short text content under 5000 characters."
    
    with patch.object(compressor, "_call_llm") as mock_call:
        res = await compressor.compress(text)
        assert res == text
        mock_call.assert_not_called()

@pytest.mark.asyncio
async def test_content_compressor_tier4():
    """Verifies that pages over 2,000,000 characters are immediately refused."""
    compressor = ContentCompressor()
    text = "A" * 2000001
    
    with patch.object(compressor, "_call_llm") as mock_call:
        res = await compressor.compress(text)
        assert "[Error: Content exceeds 2,000,000 characters" in res
        mock_call.assert_not_called()

@pytest.mark.asyncio
@patch("tools.utils.web_engine.ContentCompressor._call_llm")
async def test_content_compressor_tier2(mock_call):
    """Verifies that pages between 5,000 and 500,000 characters trigger a single-pass summary."""
    compressor = ContentCompressor()
    text = "A" * 10000
    mock_call.return_value = "Compressed single-pass output."
    
    res = await compressor.compress(text)
    assert res == "Compressed single-pass output."
    mock_call.assert_called_once()

@pytest.mark.asyncio
@patch("tools.utils.web_engine.ContentCompressor._call_llm")
async def test_content_compressor_tier3(mock_call):
    """Verifies that pages between 500,000 and 2,000,000 characters trigger chunked parallel summaries."""
    compressor = ContentCompressor()
    # 600,000 chars -> splits into 6 chunks of 100k
    text = "A" * 600000
    mock_call.side_effect = [
        "Chunk 1 summary",
        "Chunk 2 summary",
        "Chunk 3 summary",
        "Chunk 4 summary",
        "Chunk 5 summary",
        "Chunk 6 summary",
        "Unified final summary."
    ]
    
    res = await compressor.compress(text)
    assert res == "Unified final summary."
    # 6 chunk calls + 1 synthesize call = 7 calls
    assert mock_call.call_count == 7

def test_web_search_engine_auto_detection():
    """Verifies that backend detection respects settings priorities and environment variables."""
    engine = WebSearchEngine()
    
    # Standard fallback when no key is set
    with patch.dict(os.environ, {}, clear=True):
        with patch.object(settings, "WEB_SEARCH_BACKEND", None):
            with patch.object(settings, "WEB_BACKEND", "ddgs"):
                assert engine._detect_backend() == "ddgs"
                
    # Detect from settings.WEB_SEARCH_BACKEND
    with patch.object(settings, "WEB_SEARCH_BACKEND", "searxng"):
        assert engine._detect_backend() == "searxng"

    # Detect from settings.WEB_BACKEND
    with patch.object(settings, "WEB_SEARCH_BACKEND", None):
        with patch.object(settings, "WEB_BACKEND", "exa"):
            assert engine._detect_backend() == "exa"

    # Auto-detect from environment variable
    with patch.object(settings, "WEB_SEARCH_BACKEND", None):
        with patch.object(settings, "WEB_BACKEND", "ddgs"):
            with patch.dict(os.environ, {"TAVILY_API_KEY": "test-key"}):
                assert engine._detect_backend() == "tavily"

@patch("requests.post")
def test_web_search_engine_tavily(mock_post):
    """Verifies Tavily provider search payload and standardized response mapping."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "results": [
            {"title": "Result 1", "url": "https://example.com/1", "content": "Excerpt 1"}
        ]
    }
    mock_post.return_value = mock_resp
    
    with patch.dict(os.environ, {"TAVILY_API_KEY": "tvly-key"}):
        engine = WebSearchEngine()
        assert engine.backend == "tavily"
        
        res = engine.search("test query", limit=1)
        assert res["success"] is True
        assert len(res["data"]["web"]) == 1
        assert res["data"]["web"][0]["title"] == "Result 1"
        assert res["data"]["web"][0]["url"] == "https://example.com/1"
        assert res["data"]["web"][0]["excerpt"] == "Excerpt 1"

@patch("requests.post")
@patch("requests.get")
def test_web_extract_engine_firecrawl(mock_get, mock_post):
    """Verifies Firecrawl provider extraction and fallback to raw scraper."""
    # Scrape API response
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "data": {
            "markdown": "Scraped Markdown Content"
        }
    }
    mock_post.return_value = mock_resp
    
    with patch.dict(os.environ, {"FIRECRAWL_API_KEY": "fc-key"}):
        engine = WebExtractEngine()
        assert engine.backend == "firecrawl"
        
        res = engine.extract(["https://example.com/scrape"])
        assert res["success"] is True
        assert len(res["results"]) == 1
        assert res["results"][0]["url"] == "https://example.com/scrape"
        assert res["results"][0]["content"] == "Scraped Markdown Content"

@patch("requests.get")
def test_ddgs_search_scraping(mock_get):
    """Verifies the free DuckDuckGo HTML scraper parsing."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = """
    <div class="result body">
        <a class="result__a" href="https://example.com/target">Title of Result</a>
        <a class="result__snippet">This is the excerpt snippet.</a>
    </div>
    """
    mock_get.return_value = mock_resp
    
    results = ddgs_search("test query", limit=1)
    assert len(results) == 1
    assert results[0]["title"] == "Title of Result"
    assert results[0]["url"] == "https://example.com/target"
    assert results[0]["excerpt"] == "This is the excerpt snippet."

def test_raw_extract_cleans_html():
    """Verifies that raw extraction strips script tags, styles, and html markup."""
    html_content = """
    <html>
        <head>
            <style>body { color: red; }</style>
            <script>console.log("hello");</script>
        </head>
        <body>
            <!-- Comment -->
            <h1>Hello World</h1>
            <p>This is a <b>test</b>.</p>
        </body>
    </html>
    """
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = html_content
    
    with patch("requests.get", return_value=mock_resp):
        clean_text = raw_extract("https://example.com")
        assert "console.log" not in clean_text
        assert "body {" not in clean_text
        assert "Comment" not in clean_text
        assert "Hello World" in clean_text
        assert "This is a test" in clean_text
