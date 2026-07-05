"""Unit tests for detect_model_tier — numeric parameter-count parsing.

Tier routing matters: 'nano' models go through the decoupled
planner-executor anti-hallucination pipeline. A missed nano tag means a
small model is asked to emit tool calls directly, which is exactly the
failure mode the pipeline exists to prevent.
"""
import pytest

from core.tools.infrastructure.ai_gateway import detect_model_tier

LOCAL_URL = "http://ollama_server:11434/v1"


@pytest.mark.parametrize("model", [
    # Sizes the old string patterns covered
    "gemma-4:1b",
    "deepseek-r1:1.5b",
    "qwen2.5:0.5b",
    "gemma2:2b",
    # Sizes the old patterns MISSED (the bug)
    "qwen3:1.7b",
    "qwen3:0.6b",
    "llama3.2:3b",
    "gemma2:2b-instruct-q4_K_M",
    # Million-scale tags
    "gemma3:270m",
    # Named nano models without a size tag
    "phi3:mini",
    "tinyllama",
])
def test_nano_models(model):
    assert detect_model_tier(model, LOCAL_URL) == "nano", model


@pytest.mark.parametrize("model", [
    "gemma4:12b",
    "gemma3:9b",
    "mistral:7b",
    "llama3.1:8b-instruct-q4_K_M",
    "qwen3:4b",
    "mixtral:8x7b",
    # No size info in the tag -> assume standard
    "codellama:latest",
    "some-custom-model",
])
def test_standard_models(model):
    assert detect_model_tier(model, LOCAL_URL) == "standard", model


@pytest.mark.parametrize("url", [
    "https://api.openai.com/v1",
    "https://api.anthropic.com/v1",
    "https://generativelanguage.googleapis.com/v1beta/openai",
    "https://api.deepseek.com/v1",
])
def test_cloud_urls_win_regardless_of_model(url):
    # Even a nano-sized tag is 'cloud' when served by a cloud endpoint
    assert detect_model_tier("gemma2:2b", url) == "cloud"


def test_quant_suffix_not_mistaken_for_size():
    # 'q4_K_M' must not parse as 4B; the real size is 1.5b -> nano
    assert detect_model_tier("deepseek-r1:1.5b-qwen-distill-q4_K_M", LOCAL_URL) == "nano"
