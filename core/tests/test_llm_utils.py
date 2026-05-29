import sys
# Standard absolute imports handled by PYTHONPATH or environment

from tools.utils.llm_utils import extract_json, clean_llm_response

def test_extract_json_markdown():
    text = "Here is the result: ```json\n{\"decision\": \"APPROVED\", \"confidence\": 0.9}\n``` Hope this helps!"
    result = extract_json(text)
    assert result == {"decision": "APPROVED", "confidence": 0.9}

def test_extract_json_generic_block():
    text = "Result: ```\n{\"status\": \"OK\"}\n```"
    result = extract_json(text)
    assert result == {"status": "OK"}

def test_extract_json_raw():
    text = "{\"key\": \"value\"}"
    result = extract_json(text)
    assert result == {"key": "value"}

def test_extract_json_with_filler():
    text = "The model says { \"verdict\": \"REJECTED\" } clearly."
    result = extract_json(text)
    assert result == {"verdict": "REJECTED"}

def test_extract_json_invalid():
    text = "This is not json { at all"
    result = extract_json(text)
    assert result is None

def test_clean_llm_response():
    text = "```\nClean this\n```"
    assert clean_llm_response(text) == "Clean this"

if __name__ == "__main__":
    test_extract_json_markdown()
    test_extract_json_generic_block()
    test_extract_json_raw()
    test_extract_json_with_filler()
    test_extract_json_invalid()
    test_clean_llm_response()
    print("✅ All llm_utils tests passed!")
