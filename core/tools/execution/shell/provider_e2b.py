"""shell capability -- E2B / Docker sandbox Service Provider (DSH-02).

Not auto-registered: it depends on `e2b_runner` (which wants `E2B_API_KEY` or a
local Docker daemon). A profile or a test registers it explicitly:

    from tools.execution.shell import register_shell_provider
    from tools.execution.shell.provider_e2b import E2BShellProvider
    dispose = register_shell_provider(E2BShellProvider(), make_active=True)

Slice-1 limitation: `e2b_runner` today runs *code*, not a raw command, and
returns a pre-formatted string. This provider wraps the command in a one-line
python `subprocess` call and hands back the string opaquely. A later slice gives
`e2b_runner` a real command API and this provider parses structured output.
"""
from __future__ import annotations

from typing import Optional

from .definition import ShellResult


class E2BShellProvider:
    name = "e2b"

    def run(
        self,
        command: str,
        *,
        cwd: Optional[str] = None,
        timeout: Optional[float] = 30.0,
    ) -> ShellResult:
        from tools.execution.e2b_runner import run_code_safely

        script = (
            "import subprocess, sys\n"
            f"cp = subprocess.run({command!r}, shell=True, capture_output=True, text=True)\n"
            "sys.stdout.write(cp.stdout)\n"
            "sys.stderr.write(cp.stderr)\n"
            "raise SystemExit(cp.returncode)\n"
        )
        raw = run_code_safely(script, "python", int(timeout or 30))
        return ShellResult(
            command=command, exit_code=0, stdout=str(raw), stderr="",
            provider=self.name,
        )
