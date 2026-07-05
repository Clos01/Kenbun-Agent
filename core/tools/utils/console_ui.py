import sys
import shutil
import re

# Color palettes (Limestone & Sakura themed)
C_P = "\033[95m"       # Pink (Sakura)
C_G = "\033[92m"       # Green
C_Y = "\033[93m"       # Gold/Warning
C_C = "\033[96m"       # Cyan/Info
C_W = "\033[0m"        # Default Text Color (Automatically high-contrast on both Light and Dark themes)
C_D = "\033[90m"       # Dim grey
C_R = "\033[0m"        # Reset
C_RED = "\033[91m"     # Red/Danger
C_BOLD = "\033[1m"     # Bold
C_DIM = "\033[2m"      # Dim

# Helper functions for clean terminal display and dynamic layout
ANSI_ESCAPE = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')

def visible_len(text):
    """Calculates the printable length of a string, ignoring ANSI escape sequences."""
    return len(ANSI_ESCAPE.sub('', text))

def get_columns():
    """Gets the active terminal columns, defaulting to 80."""
    try:
        cols = shutil.get_terminal_size(fallback=(80, 24)).columns
        return cols if cols > 0 else 80
    except Exception:
        return 80

def clean_wrap_text(text, width):
    """
    Word-wraps long text to fit a given width cleanly, preserving original line breaks.
    If a single word exceeds the width, it is broken up into segments of length `width`.
    """
    if not text:
        return ""
    if width <= 0:
        width = 80
        
    wrapped_lines = []
    for line in text.splitlines():
        if not line.strip():
            wrapped_lines.append("")
            continue
        
        words = line.split(" ")
        current_line = []
        current_len = 0
        
        for word in words:
            word_len = visible_len(word)
            if word_len > width:
                # First flush current line
                if current_line:
                    wrapped_lines.append(" ".join(current_line))
                    current_line = []
                    current_len = 0
                
                # Split the long word into chunks of width while keeping ANSI codes intact
                has_ansi = bool(ANSI_ESCAPE.search(word))
                if not has_ansi:
                    for i in range(0, len(word), width):
                        wrapped_lines.append(word[i:i+width])
                else:
                    tokens = []
                    last_idx = 0
                    for m in ANSI_ESCAPE.finditer(word):
                        start, end = m.start(), m.end()
                        for c in word[last_idx:start]:
                            tokens.append((c, False))
                        tokens.append((word[start:end], True))
                        last_idx = end
                    for c in word[last_idx:]:
                        tokens.append((c, False))
                    
                    chunk_str = ""
                    chunk_len = 0
                    for tok, is_escape in tokens:
                        if is_escape:
                            chunk_str += tok
                        else:
                            if chunk_len >= width:
                                wrapped_lines.append(chunk_str)
                                chunk_str = tok
                                chunk_len = 1
                            else:
                                chunk_str += tok
                                chunk_len += 1
                    if chunk_str:
                        wrapped_lines.append(chunk_str)
            else:
                added_len = word_len + (1 if current_line else 0)
                if current_len + added_len <= width:
                    current_line.append(word)
                    current_len += added_len
                else:
                    if current_line:
                        wrapped_lines.append(" ".join(current_line))
                    current_line = [word]
                    current_len = word_len
        if current_line:
            wrapped_lines.append(" ".join(current_line))
    return "\n".join(wrapped_lines)

def draw_box(lines, title=None, border_color=C_G, text_color=C_W):
    """
    Draws a clean Limestone/Sakura styled box dynamically adjusted to terminal width.
    Each line in `lines` can contain ANSI escape codes. They will be wrapped cleanly.
    """
    cols = get_columns()
    box_width = min(cols, 80)
    if box_width < 40:
        box_width = cols
        
    content_width = box_width - 4  # 2 for border and spaces on each side
    if content_width <= 0:
        content_width = 36  # safe fallback
        
    # Border characters
    top_left = "┌"
    top_right = "┐"
    bottom_left = "└"
    bottom_right = "┘"
    horizontal = "─"
    horizontal_top = "─"
    horizontal_bottom = "─"
    vertical = "│"
    divider = "├"
    divider_right = "┤"
    
    # Print top border with title if present
    if title:
        vis_title = visible_len(title)
        if vis_title + 6 <= box_width:
            left_dash_count = (box_width - 2 - vis_title - 2) // 2
            right_dash_count = box_width - 2 - vis_title - 2 - left_dash_count
            top_border = f"{border_color}{top_left}{horizontal_top * left_dash_count} {title} {horizontal_top * right_dash_count}{top_right}{C_R}"
        else:
            top_border = f"{border_color}{top_left}{horizontal_top * (box_width - 2)}{top_right}{C_R}"
    else:
        top_border = f"{border_color}{top_left}{horizontal_top * (box_width - 2)}{top_right}{C_R}"
        
    print(top_border)
    
    for line in lines:
        if line == "---":
            print(f"{border_color}{divider}{horizontal * (box_width - 2)}{divider_right}{C_R}")
        else:
            wrapped_sublines = clean_wrap_text(line, content_width).splitlines()
            if not wrapped_sublines:
                print(f"{border_color}{vertical}{C_R} {' ' * content_width} {border_color}{vertical}{C_R}")
            for subline in wrapped_sublines:
                vis_len = visible_len(subline)
                padding = content_width - vis_len
                if padding < 0:
                    padding = 0
                print(f"{border_color}{vertical}{C_R} {text_color}{subline}{C_R}{' ' * padding} {border_color}{vertical}{C_R}")
                
    print(f"{border_color}{bottom_left}{horizontal_bottom * (box_width - 2)}{bottom_right}{C_R}")

def print_ollama_memory_education(context_type):
    """
    Prints an educational block detailing how Ollama serves weights, 
    VRAM/RAM constraints, and what the corrected configuration accomplishes.
    """
    edu_lines = [
        "🌸 KENBUN COGNITIVE ARCHITECTURE LESSON:",
        "----------------------------------------",
        "🧠 How Ollama Serves Model Weights:",
        "Ollama acts as a local runner that dynamically loads quantized model",
        "weights (stored in GGUF format) into your system's hardware memory.",
        "",
        "💾 VRAM & RAM Constraints:",
        "  • 1.5B/3B Models: Require ~2GB to 4GB of memory. Fit easily on standard",
        "    laptops (even CPU-only systems).",
        "  • 8B Models: Require ~6GB to 8GB of memory. Run fast on Apple Silicon",
        "    (M1/M2/M3) or dedicated NVIDIA GPUs.",
        "  • 70B Models: Require 40GB+ of VRAM. Fall back to CPU RAM if insufficient,",
        "    resulting in slow token generation rates (1-2 tokens/sec).",
        "",
        "🔄 Context Realignment:"
    ]
    if context_type == "mismatch_resolved":
        edu_lines.extend([
            "By correcting your URL or model name, we aligned the API client's",
            "expectations with the provider's capabilities. Cloud servers run",
            "remote inference on high-capacity servers using proprietary weights",
            "(e.g., GPT-4), whereas Ollama manages local execution on your machine."
        ])
    else: # pull_triggered
        edu_lines.extend([
            "Pulling the model downloads the weight files onto your local disk.",
            "Ollama then allocates standard VRAM/RAM buffers, registers the HTTP",
            "endpoints, and prepares to compile query vectors. This self-healing",
            "action restores local inference immediately!"
        ])
    
    edu_lines.extend([
        "---",
        "💡 Learn More: Run 'ollama list' in your terminal to see local models."
    ])
    
    draw_box(edu_lines, title="🧠 COGNITIVE EDUCATION DIAGNOSTIC", border_color=C_P, text_color=C_G)

def explain_command(cmd):
    """
    Parses a system command and prints a beautiful Limestone/Sakura styled card
    educating the user about the utility, why it is needed, and manual syntax.
    """
    cmd_clean = cmd.strip()
    cmd_lower = cmd_clean.lower()
    
    tool_name = "System CLI Command"
    why_needed = "Executing an operations command to inspect, configure, or run workspace processes."
    pro_tip = f"You can run this command directly in your shell: `{cmd_clean}`"
    
    # Identify Tool
    if cmd_lower.startswith("docker"):
        tool_name = "Docker Container Engine"
        why_needed = "Manages, starts, and inspects containerized services (like databases, services, or local LLMs) in isolated environments."
        pro_tip = "💡 Pro-Tip: You can run this command directly in your shell: `docker ps`"
    elif "ollama" in cmd_lower:
        tool_name = "Ollama Local Weights Manager"
        why_needed = "Downloads, serves, and manages large language model weights locally on your system hardware without external network APIs."
        pro_tip = "💡 Pro-Tip: You can run this command directly in your shell: `ollama list`"
    elif "ufw" in cmd_lower:
        tool_name = "UFW (Uncomplicated Firewall)"
        why_needed = "Controls local host network ports and regulates traffic to protect development servers from external access."
        pro_tip = "💡 Pro-Tip: You can run this command directly in your shell: `sudo ufw status`"
    elif cmd_lower.startswith("git"):
        tool_name = "Git Version Control"
        why_needed = "Tracks file changes, manages repository state, and handles project branches."
        pro_tip = "💡 Pro-Tip: You can run this command directly in your shell: `git status`"
    elif cmd_lower.startswith("npm") or cmd_lower.startswith("node"):
        tool_name = "Node.js Environment & Package Manager"
        why_needed = "Installs packages and runs JavaScript/TypeScript runtimes for web apps and tooling."
        pro_tip = "💡 Pro-Tip: You can run this command directly in your shell: `npm list`"
    elif "pip" in cmd_lower or cmd_lower.startswith("python"):
        tool_name = "Python Package & Runtime Utility"
        why_needed = "Manages Python dependencies, environments (virtualenvs), and executes Python-based scripting tools."
        pro_tip = "💡 Pro-Tip: You can run this command directly in your shell: `pip list`"
    elif any(cmd_lower.startswith(x) for x in ["mkdir", "rm", "cp", "mv", "ls", "cat", "chmod", "pwd", "whoami"]):
        tool_name = "POSIX OS Filesystem Operations"
        why_needed = "Performs filesystem manipulation tasks such as creating, moving, reading, copying, or deleting files and folders."
        pro_tip = f"💡 Pro-Tip: You can run this command directly in your shell: `ls -lh`"
        
    # Explainer Fatigue Mitigation: Do not show giant explainer for basic POSIX read-only commands
    if cmd_lower.strip() in ["ls", "pwd", "whoami", "clear", "ls -l", "ls -la"]:
        return

    lines = [
        f"🛠️  Tool Running: {C_W}{tool_name}{C_G}",
        f"🎯 Active Context: {why_needed}",
        "---",
        pro_tip
    ]
    
    draw_box(lines, title="💡 EDUCATIONAL TOOL EXPLAINER", border_color=C_P, text_color=C_G)

class StreamingRenderer:
    """
    Intelligent streaming renderer that:
    1. Suppresses raw markdown code-fence tags (```execute, ```bash, etc)
    2. Buffers and hides code block contents until the closing fence
    3. Handles word-wrapping for normal prose in real-time
    4. Eliminates line-buffering latency for an elite streaming experience
    5. Formats inline code (backticks) as Bold Cyan for supreme CLI aesthetics
    6. Formats double asterisks as bold text
    """
    FENCE_OPEN = re.compile(r'^```(execute|bash|sh|spawn)', re.IGNORECASE)
    FENCE_CLOSE = re.compile(r'^```\s*$')

    def __init__(self, width: int):
        self.width = max(width, 40)
        self.current_line_len = 0
        self.word_buffer = ""
        self._line_buffer = ""     # accumulates current line to detect fences
        self._in_code_block = False
        self._code_lang = ""
        self._code_buffer = ""
        self._in_inline_code = False
        self._in_bold = False
        self._asterisk_count = 0

    def write(self, chunk: str):
        """Feed a streaming chunk of text."""
        for char in chunk:
            if self._in_code_block:
                self._line_buffer += char
                if char == '\n':
                    line = self._line_buffer.rstrip('\n')
                    if self.FENCE_CLOSE.match(line.strip()):
                        self._in_code_block = False
                        self._code_lang = ""
                        self._line_buffer = ""
                    else:
                        self._code_buffer += self._line_buffer
                        self._line_buffer = ""
            else:
                # If we are buffering a potential code fence line (starts with `)
                if self._line_buffer or char == '`':
                    self._line_buffer += char
                    if char == '\n':
                        line = self._line_buffer.rstrip('\n')
                        m = self.FENCE_OPEN.match(line.strip())
                        if m:
                            self._in_code_block = True
                            self._code_lang = m.group(1).lower() or "text"
                            self._code_buffer = ""
                            self._line_buffer = ""
                        else:
                            # Not a fence, process the accumulated line buffer as normal prose
                            content = self._line_buffer
                            self._line_buffer = ""
                            for c in content:
                                self._emit_char_prose(c)
                else:
                    # Normal prose — emit characters immediately with word-level buffering
                    self._emit_char_prose(char)

    def _check_and_flush_asterisks(self, current_char: str):
        """Helper to process and style double asterisks (bold) or single asterisks."""
        if self._asterisk_count > 0 and current_char != '*':
            if self._asterisk_count == 2:
                # Toggle bold style
                if not self._in_bold:
                    self._in_bold = True
                    sys.stdout.write("\033[90m**\033[1m") # Dim asterisks + Bold style
                else:
                    self._in_bold = False
                    sys.stdout.write("\033[0m\033[90m**\033[0m") # Reset + Dim asterisks + Reset
                sys.stdout.flush()
                self.current_line_len += 2
            else:
                # Print the single asterisk
                sys.stdout.write("*" * self._asterisk_count)
                sys.stdout.flush()
                self.current_line_len += self._asterisk_count
            self._asterisk_count = 0

    def _emit_char_prose(self, char: str):
        # First check and flush any buffered asterisks
        self._check_and_flush_asterisks(char)

        if char == '\n':
            if self.word_buffer:
                self._flush_word()
            sys.stdout.write('\n')
            sys.stdout.flush()
            self.current_line_len = 0
        elif char.isspace():
            if self.word_buffer:
                self._flush_word()
            if self.current_line_len > 0:
                sys.stdout.write(char)
                sys.stdout.flush()
                self.current_line_len += 1
        elif char == '*':
            if self.word_buffer:
                self._flush_word()
            self._asterisk_count += 1
            return
        elif char in '.,!?;:()[]{}<>-+_=/\\|&^%$#@~"\'`': # Handle punctuation including backtick
            if self.word_buffer:
                self._flush_word()
            
            if char == '`':
                # Toggle inline code styling
                if not self._in_inline_code:
                    self._in_inline_code = True
                    sys.stdout.write("\033[90m`\033[1;36m") # Dim grey backtick + Bold Cyan for the command
                else:
                    self._in_inline_code = False
                    sys.stdout.write("\033[0m\033[90m`\033[0m") # Reset + Dim grey backtick + Reset
                sys.stdout.flush()
                self.current_line_len += 1
                return

            if self.current_line_len + 1 > self.width:
                sys.stdout.write('\n')
                sys.stdout.flush()
                self.current_line_len = 0
            sys.stdout.write(char)
            sys.stdout.flush()
            self.current_line_len += 1
        else:
            self.word_buffer += char

    def _flush_word(self):
        w_len = visible_len(self.word_buffer)
        if self.current_line_len + w_len > self.width:
            sys.stdout.write('\n')
            sys.stdout.flush()
            self.current_line_len = 0
        sys.stdout.write(self.word_buffer)
        sys.stdout.flush()
        self.current_line_len += w_len
        self.word_buffer = ""

    def flush(self):
        """Flush any remaining buffers."""
        # Ensure any trailing asterisks are flushed before finishing
        self._check_and_flush_asterisks('\033')
        if self.word_buffer:
            self._flush_word()
        if self._line_buffer:
            content = self._line_buffer
            self._line_buffer = ""
            for c in content:
                self._emit_char_prose(c)
            self._check_and_flush_asterisks('\033')
            if self.word_buffer:
                self._flush_word()

    def get_captured_blocks(self):
        """Return (lang, content) of the last captured code block (unused but available)."""
        return self._code_lang, self._code_buffer

# Keep backward-compatible alias
StreamingWordWrapper = StreamingRenderer
