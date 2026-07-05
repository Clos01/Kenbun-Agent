from typing import Optional
from tools.registry import sovereign_tool
from tools.utils.browser_engine import BrowserEngine

@sovereign_tool(name="browser_navigate", category="Sensory")
def browser_navigate(url: str) -> dict:
    """
    Navigate the browser to the specified URL. Must be called before any other browser tool.
    
    Args:
        url: The web URL to navigate to.
    """
    engine = BrowserEngine()
    return engine.navigate(url)

@sovereign_tool(name="browser_snapshot", category="Sensory")
def browser_snapshot(full: bool = False) -> dict:
    """
    Get a text-based snapshot of the current page's accessibility tree.
    Returns interactive elements with ref IDs like @e1, @e2 for use with click/type.
    
    Args:
        full: If True, returns full page tree. If False (default), returns interactive elements only.
    """
    engine = BrowserEngine()
    return engine.snapshot(full=full)

@sovereign_tool(name="browser_click", category="Sensory")
def browser_click(ref: str) -> dict:
    """
    Click an element on the page using its ref ID from the snapshot.
    
    Args:
        ref: The element reference identifier (e.g. "@e1" or "e1").
    """
    engine = BrowserEngine()
    # Normalize ref string
    ref_norm = ref.lstrip("@")
    return engine.click(ref_norm)

@sovereign_tool(name="browser_type", category="Sensory")
def browser_type(ref: str, text: str) -> dict:
    """
    Type text into an input field using its ref ID from the snapshot. Clears the field first.
    
    Args:
        ref: The element reference identifier (e.g. "@e1" or "e1").
        text: The string to type into the element.
    """
    engine = BrowserEngine()
    ref_norm = ref.lstrip("@")
    return engine.type(ref_norm, text)

@sovereign_tool(name="browser_scroll", category="Sensory")
def browser_scroll(direction: str) -> dict:
    """
    Scroll the page in the specified direction.
    
    Args:
        direction: Direction to scroll ('up', 'down', 'left', 'right').
    """
    engine = BrowserEngine()
    return engine.scroll(direction)

@sovereign_tool(name="browser_press", category="Sensory")
def browser_press(key: str) -> dict:
    """
    Press a keyboard key on the active element.
    
    Args:
        key: The key name (e.g. 'Enter', 'Tab', 'Escape', 'ArrowDown').
    """
    engine = BrowserEngine()
    return engine.press(key)

@sovereign_tool(name="browser_back", category="Sensory")
def browser_back() -> dict:
    """
    Navigate back to the previous page in the browser history.
    """
    engine = BrowserEngine()
    return engine.back()

@sovereign_tool(name="browser_get_images", category="Sensory")
def browser_get_images() -> dict:
    """
    List all images on the current page with their URLs and alt text.
    """
    engine = BrowserEngine()
    return engine.get_images()

@sovereign_tool(name="browser_vision", category="Sensory")
def browser_vision(prompt: str) -> dict:
    """
    Take a screenshot of the current page and perform vision AI analysis on it.
    Useful for CAPTCHAs, complex layouts, or visual verifications.
    
    Args:
        prompt: Prompt or question to guide the visual analysis.
    """
    engine = BrowserEngine()
    return engine.vision(prompt)

@sovereign_tool(name="browser_console", category="Sensory")
def browser_console(expression: Optional[str] = None, clear: bool = False) -> dict:
    """
    Get console logs or evaluate JavaScript expressions.
    
    Args:
        expression: Optional JavaScript expression to evaluate. If omitted, returns page logs.
        clear: If True, clears the log buffer after reading.
    """
    engine = BrowserEngine()
    return engine.console(expression=expression, clear=clear)

@sovereign_tool(name="browser_cdp", category="Sensory")
def browser_cdp(method: str, params: Optional[dict] = None, target_id: Optional[str] = None, frame_id: Optional[str] = None) -> dict:
    """
    Execute a raw Chrome DevTools Protocol method.
    
    Args:
        method: The CDP method to execute (e.g. 'Target.getTargets', 'Page.captureScreenshot').
        params: Optional parameters for the method.
        target_id: Optional target identifier to direct the call.
        frame_id: Optional frame identifier for iframe-scoped execution.
    """
    engine = BrowserEngine()
    return engine.cdp(method=method, params=params, target_id=target_id, frame_id=frame_id)

@sovereign_tool(name="browser_dialog", category="Sensory")
def browser_dialog(action: str, prompt_text: Optional[str] = None) -> dict:
    """
    Respond to a pending JavaScript dialog (alert, confirm, prompt).
    
    Args:
        action: Response action ('accept' or 'dismiss').
        prompt_text: Optional text response for prompt dialogs.
    """
    engine = BrowserEngine()
    return engine.dialog(action=action, prompt_text=prompt_text)
