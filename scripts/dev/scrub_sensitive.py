#!/usr/bin/env python3
"""Scrub / detect personal + private-infrastructure data before it reaches a
public commit.

Two modes:
  --fix     rewrite tracked files in place, replacing sensitive values with
            generic placeholders (used once to clean the tree)
  --check   scan tracked files and exit non-zero if any sensitive pattern is
            found (used by the pre-commit hook; the default mode)

This exists because the Kenbun -> kenbun-agent sync (run_supervisor.py) copies a
private working tree into a public repo. The 2026-07 open-source scrub missed
home paths, tailnet IPs, and the dev host name; this makes the check mechanical.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

# Ordered longest-first so nested paths are replaced before their prefixes.
LITERAL_REPLACEMENTS: list[tuple[str, str]] = [
    ("/Users/carlosrivas/Dev/kenbun-agent", "/path/to/kenbun-agent"),
    ("/Users/carlosrivas/Dev/Kenbun", "/path/to/Kenbun"),
    ("/Users/carlosrivas/.gemini", "~/.gemini"),
    ("/Users/carlosrivas", "~"),
    ("lg2025.tailbe4852.ts.net", "remote-host.example"),
    ("100.104.211.61", "127.0.0.1"),
    ("100.120.241.65", "127.0.0.1"),
    ("100.92.127.1", "127.0.0.1"),
    ("100.83.16.93", "127.0.0.1"),
    ("lg2025", "remote-host"),  # any bare mentions left in prose
]

# Detection patterns for --check. Deliberately broad: catches the specific
# leaked values AND the general shapes (any /Users/<name>, any CGNAT/tailnet
# 100.64-127.x, any API-key-looking token) so a NEW machine's data is caught too.
DETECT_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    # Real usernames only — the generic placeholders below are allowed to stay.
    ("home path", re.compile(
        r"/Users/(?!(?:runner|dev|user|username|you|me|home|path|example|foo|bar|"
        r"\.\.\.)/)[A-Za-z0-9._-]+/"
    )),
    ("tailnet/CGNAT IP", re.compile(r"\b100\.(?:6[4-9]|[7-9]\d|1[0-1]\d|12[0-7])\.\d{1,3}\.\d{1,3}\b")),
    ("dev host name", re.compile(r"\btailbe4852\b|\blg2025\b")),
    ("google api key", re.compile(r"\bAIza[0-9A-Za-z_\-]{30,}\b")),
    ("openai/anthropic key", re.compile(r"\b(?:sk|xai|ant)-[A-Za-z0-9]{20,}\b")),
    ("github token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b")),
]

# Files the scrubber must never rewrite/scan (it names the patterns itself).
SELF = "scripts/dev/scrub_sensitive.py"


def tracked_files() -> list[Path]:
    out = subprocess.run(
        ["git", "-C", str(REPO), "ls-files"],
        capture_output=True, text=True, check=True,
    ).stdout.splitlines()
    files = []
    for rel in out:
        if rel == SELF:
            continue
        p = REPO / rel
        if p.is_file() and not p.is_symlink():
            files.append(p)
    return files


def read_text(p: Path) -> str | None:
    try:
        return p.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return None  # binary or unreadable — skip


def fix() -> int:
    changed = 0
    for p in tracked_files():
        text = read_text(p)
        if text is None:
            continue
        new = text
        # Special-case: drop the hardcoded-hostname routing fallback line.
        if p.name == "llm_router.py":
            new = re.sub(r'\n[ \t]*or "lg2025" in url\.lower\(\)', "", new)
        for needle, repl in LITERAL_REPLACEMENTS:
            new = new.replace(needle, repl)
        if new != text:
            p.write_text(new, encoding="utf-8")
            changed += 1
            print(f"scrubbed {p.relative_to(REPO)}")
    print(f"\n{changed} file(s) scrubbed")
    return 0


def check() -> int:
    hits: list[str] = []
    for p in tracked_files():
        text = read_text(p)
        if text is None:
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            for label, pat in DETECT_PATTERNS:
                if pat.search(line):
                    hits.append(f"{p.relative_to(REPO)}:{lineno}: {label}: {line.strip()[:120]}")
    if hits:
        print("✗ sensitive data found in tracked files:\n")
        print("\n".join(hits))
        print(f"\n{len(hits)} hit(s). Run: python scripts/dev/scrub_sensitive.py --fix")
        return 1
    print("✓ no sensitive data in tracked files")
    return 0


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "--check"
    if mode == "--fix":
        raise SystemExit(fix())
    raise SystemExit(check())
