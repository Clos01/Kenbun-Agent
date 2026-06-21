from tools.audit.gemini_reviewer import _call_gemini

def generate_human_content(topic: str, context: str = "", length: str = "medium") -> str:
    """
    Generates website content while strictly forbidding AI slop/jargon words.
    """
    system_prompt = (
        "You are an expert, human-like copywriter. Your task is to write web content.\n\n"
        "### STRICT ANTI-AI SLOP RULES\n"
        "You MUST NOT use any of the following words or variations of them. This is a hard constraint:\n"
        "- bespoke, delve, tapestry, seamless, leverage, utilize, elevate, foster, realm, testament, embark, navigate, nuances, demystify\n"
        "- 'in today's fast-paced digital world', 'it's important to remember'\n\n"
        "### TONE & STYLE\n"
        "- Write directly, simply, and with confidence.\n"
        "- Use a punchy cadence. Read like a human who has actually shipped products.\n"
        "- Avoid filler copy, emojis for feature icons, or empty marketing claims.\n"
        "- If metrics are needed, use a placeholder like `[metric]` rather than inventing '10x faster'.\n\n"
        f"Length requested: {length}\n"
    )

    user_message = f"Write website content for the following topic:\n{topic}\n\nAdditional Context:\n{context}"

    try:
        return _call_gemini(
            system_prompt=system_prompt,
            user_message=user_message,
            temperature=0.7, 
            thinking=True,
            thinking_level="low" 
        )
    except Exception as e:
        return f"Error generating content: {e}"
