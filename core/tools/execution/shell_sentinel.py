import subprocess
from typing import Tuple
from core.tools.audit.guardrail_agent import guardrail_agent as guardrail_engine

class ShellSentinel:
    """
    Secure wrapper for shell execution.
    Integrates with GuardrailEngine for path jailing and secret masking.
    """
    
    @staticmethod
    def execute(command: str, cwd: str = None) -> Tuple[int, str, str]:
        """
        Executes a shell command after safety validation.
        Returns: (exit_code, stdout, stderr)
        """
        # 1. Path Jailing
        if cwd and not guardrail_engine.validate_path(cwd):
            return 1, "", f"❌ Security Violation: CWD '{cwd}' is outside the PROJECT_ROOT."
        
        # 2. Command Sanitization (Strict Allowlist)
        # We parse the base executable and only allow approved tools.
        command_clean = command.strip()
        if not command_clean:
            return 1, "", "❌ Security Violation: Empty command."
            
        base_exec = command_clean.split()[0]
        allowed_executables = {"kenbun", "python", "python3", "pip", "npm", "npx", "node", "git", "ls", "cat", "grep", "echo", "pwd", "mkdir", "rm", "cp", "mv", "touch", "pytest", "ruff", "black"}
        
        if base_exec not in allowed_executables:
            return 1, "", f"❌ Security Violation: Command '{base_exec}' is not in the strict allowlist."

        dangerous_operators = [";", "&&", "||", "|", ">", "<", "`", "$("]
        for op in dangerous_operators:
            if op in command_clean:
                return 1, "", f"❌ Security Violation: Shell operator '{op}' is not allowed."

        # 3. Execution
        try:
            # We use shell=True carefully here because this is a developer tool, 
            # but in production, we would use list-based args.
            result = subprocess.run(
                command,
                shell=True,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            # 4. Secret Masking in Output
            stdout = guardrail_engine.mask_secrets(result.stdout)
            stderr = guardrail_engine.mask_secrets(result.stderr)
            
            return result.returncode, stdout, stderr
            
        except subprocess.TimeoutExpired:
            return 124, "", "❌ Command timed out (60s limit)."
        except Exception as e:
            return 1, "", f"❌ Execution error: {e}"

# Singleton Instance
shell_sentinel = ShellSentinel()
