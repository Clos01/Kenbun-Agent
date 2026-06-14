import os
import sys

# Ensure core is in path
sys.path.append(os.path.join(os.path.dirname(__file__), 'core'))

from tools.infrastructure.server import ingest_url_to_hivemind

url = "https://en.wikipedia.org/wiki/Vector_quantization"
print(f"Testing URL ingestion for: {url}")

result = ingest_url_to_hivemind(url, title="Vector Quantization Wiki", tags="test,wiki,vq")
print(f"Result:\n{result}")
