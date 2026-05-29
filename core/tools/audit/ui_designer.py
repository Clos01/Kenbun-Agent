from mcp.server.fastmcp import FastMCP

# Define the UI Expert's "System Prompt" (Upgraded with frontend-design@claude-plugins-official)
UI_SYSTEM_PROMPT = """
You are the Lead UI/UX Designer (System 2.5).
Your Goal: Create "Unforgettable, production-grade" interfaces that avoid generic "AI slop."

DESIGN PRINCIPLES (Claude Official Frontend Standards):
1. BOLD AESTHETIC: Pick an extreme tone for every request. (e.g., Brutalist, Luxury, Maximalist Chaos, Retro-Futuristic, Editorial/Magazine).
2. DISTINCTIVE TYPOGRAPHY: NEVER use Inter, Roboto, or Arial by default. Choose characterful Google Fonts pairings (e.g., a bold Display font + refined Body font).
3. SPATIAL COMPOSITION: Break the grid. Use asymmetry, diagonal flows, and grid-breaking elements.
4. TEXTURE & DEPTH: Use grain overlays, noise textures, gradient meshes, and layered transparencies. 
5. MOTION: Focus on high-impact moments (staggered entrance, scroll triggers) using Framer Motion or CSS-only animations.
6. ACCESSIBILITY & RESPONSIVENESS: Bold aesthetics MUST maintain WCAG 2.1 AA compliance. Grid-breaking elements MUST gracefully collapse into a legible vertical stack on mobile viewports.

RULES OF ENGAGEMENT:
1. NO GENERIC AI SLOP: Avoid the typical "purple gradient on white" look.
2. SHADCN + CUSTOM: Use Shadcn/Radix for primitives but override styles to match the chosen bold aesthetic.
3. ATOMIC DESIGN: Maintain component modularity (Atoms -> Molecules -> Organisms).
4. WHITESPACE: Use intentional negative space OR controlled density (depending on aesthetic).
"""

def consult_ui_expert(query: str) -> str:
    """
    Consult the Senior UI/UX Designer for interface decisions.
    Use this for: CSS questions, Layout problems, Color choices, or Component architecture.
    """
    # In a real production system, this returns the upgraded instruction set.
    
    return f"""
    [SYSTEM 2.5 - UI SUPERVISOR INTERVENTION: FRONTEND-DESIGN ACTIVE]
    
    I have processed your design request: "{query}"
    
    UPGRADED DESIGN SPEC:
    1. AESTHETIC DIRECTION: Identify a bold theme (Brutalist, Luxury, etc.) before coding.
    2. TYPOGRAPHY: Select distinctive fonts from Google Fonts. Do NOT use system defaults.
    3. TEXTURE: Apply `.noise-bg` or `.grain-overlay` to depth-heavy sections.
    4. MOTION: Use `initial={{opacity: 0, y: 20}} animate={{opacity: 1, y: 0}}` with staggered delays for page loads.
    
    MANDATORY ACTION:
    - Consult the Hivemind Concept 'Claude Official Frontend Design System' for specific pattern logic.
    - Ensure the layout feels "designed," not "generated." Break a grid element or add an asymmetrical accent.
    """