import subprocess
import logging
from typing import Tuple
from tools.audit.guardrail_agent import guardrail_agent as guardrail_engine

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
        
        # 2. Command Sanitization (Simple example: block known dangerous patterns)
        dangerous_patterns = ["rm -rf /", "chmod 777", "curl | bash"]
        for p in dangerous_patterns:
            if p in command:
                return 1, "", f"❌ Security Violation: Dangerous command pattern detected: '{p}'"

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
