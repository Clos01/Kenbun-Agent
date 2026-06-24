import os
import io
import logging
from typing import Optional
from tools.infrastructure.config import settings
from tools.utils.secret_manager import decrypt_value

logger = logging.getLogger(__name__)

def is_vision_capable_model(model_name: str, base_url: str) -> bool:
    """
    Returns True if the active model supports multimodal vision inputs natively.
    """
    model_lower = model_name.lower()
    base_lower = base_url.lower()
    
    # Standard vision keywords
    vision_keywords = [
        "vision", "gpt-4o", "gpt-4v", "gemini", "claude-3",
        "-vl", "vl-", "qwen-vl", "mimo-vl", "llava", "internvl",
        "pixtral", "llama-3.2-11b-vision", "llama-3.2-90b-vision"
    ]
    
    # Check model name
    if any(keyword in model_lower for keyword in vision_keywords):
        return True
        
    # Check Google Gemini API endpoints
    if "googleapis.com" in base_lower or "generativelanguage" in base_lower:
        return True
        
    return False

def describe_image_with_aux(image_bytes: bytes, prompt: str = "Describe this image in detail.") -> str:
    """
    Invokes the auxiliary vision model (usually Gemini) to describe the image.
    Provides robust simulated fallbacks if API keys/dependencies are missing.
    """
    # Try using Google GenAI SDK if configured
    raw_key = None
    if settings.GEMINI_API_KEY:
        raw_key = settings.GEMINI_API_KEY.get_secret_value()
    if not raw_key:
        raw_key = os.environ.get("GEMINI_API_KEY")

    provider = settings.AUXILIARY_VISION_PROVIDER.lower()
    
    if (provider == "google" or provider == "auto") and raw_key:
        try:
            from google import genai
            import PIL.Image
            
            api_key = decrypt_value(raw_key)
            client = genai.Client(api_key=api_key)
            img = PIL.Image.open(io.BytesIO(image_bytes))
            
            # Resolve model name
            model_name = settings.AUXILIARY_VISION_MODEL or settings.models.gemini_model or "gemini-3-flash-preview"
            
            logger.info(f"Invoking auxiliary vision model '{model_name}' for description...")
            response = client.models.generate_content(
                model=model_name,
                contents=[img, prompt]
            )
            if response and response.text:
                return response.text
        except Exception as e:
            logger.warning(f"Auxiliary Google GenAI vision API failed: {e}")

    # Fallback to simulated description
    logger.info("Using simulated fallback description for image.")
    return f"[Vision Analysis Fallback] Simulated description of image (bytes: {len(image_bytes)}) for prompt: '{prompt}'"
