from typing import Optional, List
from tools.registry import sovereign_tool
from tools.utils.computer_use_engine import ComputerUseEngine

@sovereign_tool(name="computer_use", category="Sensory")
async def computer_use(
    action: str,
    mode: Optional[str] = None,
    app: Optional[str] = None,
    element: Optional[int] = None,
    text: Optional[str] = None,
    keys: Optional[str] = None,
    coordinate: Optional[List[int]] = None,
    duration: Optional[int] = None,
    button: Optional[str] = None
) -> dict:
    """
    Drive desktop OS interactions in the background (capturing screenshots/AX tree, clicking, typing, scrolling, key presses).
    
    Args:
        action: The computer interaction type ('capture', 'click', 'dblclick', 'type', 'key', 'hover', 'drag', 'scroll', 'focus_app').
        mode: The capture inspection mode ('som' for labeled screenshot, 'ax' for accessibility-tree only).
        app: Application name to target or focus.
        element: Numbered element index reference to interact with (from accessibility tree/SOM screenshot).
        text: Character string to type.
        keys: Key combinations to press (e.g. 'Return', 'Control+c').
        coordinate: Coordinate point [x, y] to interact with directly.
        duration: Drag/hold duration in milliseconds.
        button: Mouse button ('left', 'right', 'middle').
    """
    engine = ComputerUseEngine()
    kwargs = {}
    if mode is not None:
        kwargs["mode"] = mode
    if app is not None:
        kwargs["app"] = app
    if element is not None:
        kwargs["element"] = element
    if text is not None:
        kwargs["text"] = text
    if keys is not None:
        kwargs["keys"] = keys
    if coordinate is not None:
        kwargs["coordinate"] = coordinate
    if duration is not None:
        kwargs["duration"] = duration
    if button is not None:
        kwargs["button"] = button

    return await engine.execute(action, **kwargs)
