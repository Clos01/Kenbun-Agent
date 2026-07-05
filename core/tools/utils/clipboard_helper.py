import os
import sys
import subprocess
import tempfile
import base64
import logging
from typing import Optional

logger = logging.getLogger(__name__)

def is_wsl() -> bool:
    """Detects if running under Windows Subsystem for Linux (WSL)."""
    if sys.platform == "linux":
        try:
            with open("/proc/version", "r") as f:
                if "microsoft" in f.read().lower():
                    return True
        except Exception:
            pass
    return False

def resize_and_compress_image(image_bytes: bytes, max_dim: int = 1024, quality: int = 85) -> bytes:
    """
    Downsizes and compresses an image in-memory to prevent large payloads from exhausting LLM context.
    If PIL is not available, returns the original bytes untouched.
    """
    try:
        from PIL import Image
        import io
        
        img = Image.open(io.BytesIO(image_bytes))
        width, height = img.size
        
        if width > max_dim or height > max_dim:
            if width > height:
                new_width = max_dim
                new_height = int(height * (max_dim / width))
            else:
                new_height = max_dim
                new_width = int(width * (max_dim / height))
            logger.info(f"Resizing clipboard image from {width}x{height} to {new_width}x{new_height}")
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        # Save as PNG or JPEG depending on alpha channel
        out_buf = io.BytesIO()
        if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
            img.save(out_buf, format="PNG")
        else:
            img.save(out_buf, format="JPEG", quality=quality)
        return out_buf.getvalue()
    except Exception as e:
        logger.debug(f"PIL image resizing failed, returning original bytes: {e}")
        return image_bytes

def read_clipboard_image() -> Optional[bytes]:
    """
    Reads an image from the system clipboard, returning raw PNG/JPEG bytes if successful.
    Returns None if no image is on the clipboard or clipboard access is unavailable.
    """
    # 1. WSL2 / Windows Clipboard Access
    if is_wsl():
        try:
            # Check if powershell.exe is available
            ps_cmd = (
                "Add-Type -AssemblyName System.Windows.Forms, System.Drawing; "
                "$img = [System.Windows.Forms.Clipboard]::GetImage(); "
                "if ($img -ne $null) { "
                "  $ms = New-Object System.IO.MemoryStream; "
                "  $img.Save($ms, [System.Drawing.Imaging.ImageFormat]::Png); "
                "  [Convert]::ToBase64String($ms.ToArray()) "
                "}"
            )
            process = subprocess.run(
                ["powershell.exe", "-NoProfile", "-Command", ps_cmd],
                capture_output=True,
                text=True,
                check=False
            )
            if process.returncode == 0:
                output = process.stdout.strip()
                if output:
                    img_bytes = base64.b64decode(output)
                    return resize_and_compress_image(img_bytes)
        except Exception as e:
            logger.debug(f"WSL powershell clipboard read failed: {e}")

    # 2. macOS Clipboard Access
    elif sys.platform == "darwin":
        # Attempt 1: pngpaste binary (highly recommended)
        try:
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                tmp_path = tmp.name
            try:
                # Try running pngpaste
                res = subprocess.run(["pngpaste", tmp_path], capture_output=True, check=False)
                if res.returncode == 0:
                    with open(tmp_path, "rb") as f:
                        img_bytes = f.read()
                    return resize_and_compress_image(img_bytes)
            finally:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
        except Exception as e:
            logger.debug(f"macOS pngpaste failed: {e}")

        # Attempt 2: AppleScript (osascript fallback)
        try:
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                tmp_path = tmp.name
            try:
                apple_script = f'write (the clipboard as «class PNGf») to (open for access POSIX file "{tmp_path}" with write permission)'
                res = subprocess.run(["osascript", "-e", apple_script], capture_output=True, check=False)
                if res.returncode == 0:
                    with open(tmp_path, "rb") as f:
                        img_bytes = f.read()
                    return resize_and_compress_image(img_bytes)
            finally:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
        except Exception as e:
            logger.debug(f"macOS osascript clipboard read failed: {e}")

    # 3. Linux (X11 / Wayland) Clipboard Access
    elif sys.platform.startswith("linux"):
        # Check Wayland
        is_wayland = os.environ.get("XDG_SESSION_TYPE") == "wayland"
        if is_wayland:
            try:
                res = subprocess.run(["wl-paste", "-t", "image/png"], capture_output=True, check=False)
                if res.returncode == 0 and res.stdout:
                    return resize_and_compress_image(res.stdout)
            except Exception as e:
                logger.debug(f"Linux wl-paste failed: {e}")

        # Fallback to X11 (xclip)
        try:
            res = subprocess.run(["xclip", "-selection", "clipboard", "-t", "image/png", "-o"], capture_output=True, check=False)
            if res.returncode == 0 and res.stdout:
                return resize_and_compress_image(res.stdout)
        except Exception as e:
            logger.debug(f"Linux xclip failed: {e}")

    return None
