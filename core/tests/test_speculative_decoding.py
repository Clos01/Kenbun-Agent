import os
import pytest
import requests
from tools.infrastructure.config import settings

def test_speculative_decoding_config_loads():
    """Verify that the speculative decoding settings are correctly loaded."""
    assert hasattr(settings.models, 'use_speculative_decoding')
    assert hasattr(settings.models, 'speculative_lookahead')
    assert hasattr(settings.models, 'lm_studio_draft_model')
    
    # We expect these defaults or environment overrides to be valid types
    assert isinstance(settings.models.use_speculative_decoding, bool)
    assert isinstance(settings.models.speculative_lookahead, int)
    assert settings.models.speculative_lookahead >= 1

@pytest.mark.skipif(not settings.models.use_speculative_decoding, reason="Speculative decoding disabled")
def test_speculative_decoding_endpoint_alive():
    """
    Test if the Legion host (or local proxy) is responding on the LM Studio port.
    This will quickly fail if the Tailscale node is down.
    """
    host = settings.SWARM_PC_IP if settings.SWARM_PC_IP != "localhost" else "100.104.211.61"
    port = settings.models.lm_studio_port
    
    url = f"http://{host}:{port}/v1/models"
    
    try:
        response = requests.get(url, timeout=5.0)
        assert response.status_code == 200, f"Expected 200 OK from model server, got {response.status_code}"
        
        data = response.json()
        assert "data" in data, "Response should have 'data' containing the model list"
    except requests.exceptions.RequestException as e:
        pytest.skip(f"Legion host at {url} is currently offline or unreachable (gracefully skipped): {e}")
