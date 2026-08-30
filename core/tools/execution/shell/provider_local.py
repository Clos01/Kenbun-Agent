"""shell capability -- local Service Provider (DSH-02).

Wraps the existing `tools.utils.safe_exec.safe_run`: allowlist-validated, no
shell, parent secrets scrubbed from the child env. This is the default provider.
"""
from __future__ import annotations

import logging
import subprocess
from typing import Optional

from tools.utils.safe_exec import UnsafeCommandError, safe_run

from .definition import EXIT_BLOCKED, EXIT_TIMEOUT, ShellResult, redact_command

logger = logging.getLogger("kenbun.shell")


class LocalShellProvider:
    name = "local"

    def run(
        self,
        command: str,
        *,
        cwd: Optional[str] = None,
        timeout: Optional[float] = 30.0,
    ) -> ShellResult:
        try:
            # env=None -> safe_run uses its secret-scrubbed copy of os.environ.
            cp = safe_run(
                command, cwd=cwd, timeout=timeout, env=None,
                capture_output=True, text=True, check=False,
            )
        except UnsafeCommandError as e:
            # The exception text embeds the offending token (`Path(argv[0]).name`),
            # which is `NAME=value` for an env-assignment prefix -- so it is NOT
            # log-safe. Log the redacted label only; the raw reason goes back to
            # the trusted immediate caller in `stderr`, never to a shared sink.
            logger.warning("shell[local]: blocked by allowlist: %s", redact_command(command))
            return ShellResult(
                command=command, exit_code=EXIT_BLOCKED, stdout="",
                stderr=f"blocked by allowlist: {e}", blocked=True, provider=self.name,
            )
        except subprocess.TimeoutExpired as e:
            logger.warning("shell[local]: timed out after %ss: %s", timeout, redact_command(command))
            return ShellResult(
                command=command, exit_code=EXIT_TIMEOUT,
                stdout=_as_text(e.stdout), stderr=_as_text(e.stderr),
                timed_out=True, provider=self.name,
            )
        return ShellResult(
            command=command, exit_code=cp.returncode,
            stdout=cp.stdout or "", stderr=cp.stderr or "", provider=self.name,
        )


def _as_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace")
    return str(value)
