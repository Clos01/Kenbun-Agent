import os
import base64
from tools.registry import sovereign_tool
from tools.infrastructure.config import settings
from tools.utils.vision_helper import is_vision_capable_model, describe_image_with_aux

@sovereign_tool(name="vision_analyze", category="Sensory")
async def vision_analyze(image_path: str, prompt: str = "Describe this image in detail.") -> dict:
    """
    Analyze an image file and return either a native multimodal object or a textual description.
    
    If the active primary model is vision-capable, this returns a multimodal data structure.
    If the active primary model is text-only, this routes the image through the auxiliary
    vision describer and returns a text summary of the image content.
    
    Args:
        image_path: The absolute path to the image file to analyze.
        prompt: Question or instruction to guide the vision analysis.
    """
    if not os.path.exists(image_path):
        return {"success": False, "error": f"Image file not found at path: {image_path}"}
        
    try:
        with open(image_path, "rb") as f:
            image_bytes = f.read()
    except Exception as e:
        return {"success": False, "error": f"Failed to read image file: {e}"}

    # Fetch active model and URL from settings
    active_model = settings.PRIMARY_LLM_MODEL or "qwen2.5:1.5b"
    active_url = settings.PRIMARY_LLM_URL or "http://localhost:11434/v1"
    
    is_vision = is_vision_capable_model(active_model, active_url)
    
    # We also check if the provider is likely to support multimodal tool results.
    # Stacks that support multimodal inside tool results: Anthropic, OpenAI, Azure, Gemini 3.x
    url_lower = active_url.lower()
    supports_multimodal_results = any(
        kw in url_lower for kw in ["api.openai.com", "api.anthropic.com", "googleapis.com", "generativelanguage"]
    )
    
    if is_vision and supports_multimodal_results:
        # Return raw image pixels as a multimodal tool-result envelope
        ext = os.path.splitext(image_path)[1].lower().replace(".", "")
        if ext not in ["png", "jpeg", "jpg", "webp", "gif"]:
            ext = "png"
        mime_type = f"image/{ext}"
        if mime_type == "image/jpg":
            mime_type = "image/jpeg"
            
        b64_data = base64.b64encode(image_bytes).decode("utf-8")
        return {
            "success": True,
            "format": "multimodal",
            "data": {
                "type": "image_url",
                "image_url": {
                    "url": f"data:{mime_type};base64,{b64_data}"
                }
            }
        }
    else:
        # Fall back to text description
        description = describe_image_with_aux(image_bytes, prompt)
        return {
            "success": True,
            "format": "text",
            "data": description
        }
