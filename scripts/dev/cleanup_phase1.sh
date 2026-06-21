#!/usr/bin/env bash
# =============================================================================
#  Kenbun — Phase 1 Cleanup (chore/security-spring-cleaning)
# =============================================================================
#
#  Why this is a script and not done in-session:
#    The agent sandbox can read the mounted repo but cannot delete or rename
#    files inside it ("Operation not permitted"). Run this on your Mac to
#    finish the file-system side of Phase 1.
#
#  What it does (idempotent — safe to re-run):
#    1. Clears the stale .git/index.lock left by an earlier `git worktree
#       prune -v` invocation.
#    2. Prunes git worktree metadata + removes the 340MB .claude/worktrees/.
#    3. Creates scripts/dev/ and core/tests/scratch/.
#    4. Moves root-level scratch / migration scripts into their new homes
#       using `git mv` for tracked files and plain `mv` for untracked ones.
#
#  What it deliberately does NOT do:
#    * No commits, no pushes — you stage and review.
#    * No deletes of pyproject.toml, .env, or any tracked source file.
#
#  Usage:
#    cd /Users/carlosrivas/Dev/Kenbun
#    bash scripts/dev/cleanup_phase1.sh
# =============================================================================

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

echo "📍 Repo: $REPO_ROOT"
echo "📍 Branch: $(git rev-parse --abbrev-ref HEAD)"
echo

# ----------------------------------------------------------------------------
# 0. Clear stale git locks
# ----------------------------------------------------------------------------
echo "🔓 Clearing stale git index locks..."
for lock in .git/index.lock external/honcho/.git/index.lock; do
    if [[ -f "$lock" ]]; then
        rm -f "$lock" && echo "   removed: $lock"
    fi
done
echo

# ----------------------------------------------------------------------------
# 1. Prune worktrees and delete the .claude/worktrees directory
# ----------------------------------------------------------------------------
echo "🧹 Pruning git worktrees..."
git worktree prune -v 2>&1 | tail -5 || true

if [[ -d ".claude/worktrees" ]]; then
    size_before="$(du -sh .claude/worktrees 2>/dev/null | awk '{print $1}')"
    echo "   removing .claude/worktrees ($size_before)..."
    rm -rf .claude/worktrees
    echo "   ✅ done"
else
    echo "   .claude/worktrees already absent — skipping"
fi
echo

# ----------------------------------------------------------------------------
# 2. Create destination directories
# ----------------------------------------------------------------------------
echo "📁 Ensuring destination directories exist..."
mkdir -p scripts/dev core/tests/scratch
# Keep them committable even when empty
[[ -f scripts/dev/.gitkeep ]] || touch scripts/dev/.gitkeep
[[ -f core/tests/scratch/.gitkeep ]] || touch core/tests/scratch/.gitkeep
echo "   ✅ scripts/dev/ and core/tests/scratch/ ready"
echo

# ----------------------------------------------------------------------------
# 3. Move files — git mv for tracked, plain mv for untracked
# ----------------------------------------------------------------------------
# safe_move <src> <dst-dir>
safe_move() {
    local src="$1"
    local dest_dir="$2"
    if [[ ! -e "$src" ]]; then
        echo "   skip (missing): $src"
        return 0
    fi
    local dest="$dest_dir/$(basename "$src")"
    if [[ -e "$dest" ]]; then
        echo "   skip (already at dest): $dest"
        return 0
    fi
    if git ls-files --error-unmatch "$src" >/dev/null 2>&1; then
        git mv "$src" "$dest"
        echo "   git mv: $src → $dest"
    else
        mv "$src" "$dest"
        echo "   mv:     $src → $dest"
    fi
}

echo "📦 Relocating root-level test_*.py → core/tests/scratch/ ..."
# Use a glob expansion that survives no-match (nullglob)
shopt -s nullglob
for f in test_*.py; do
    safe_move "$f" "core/tests/scratch"
done
shopt -u nullglob
echo

echo "📦 Relocating migration / dev one-offs → scripts/dev/ ..."
for f in migrate.py migrate2.py fix_syntax.py req.py update_claude_config.py modify_docker_settings.py; do
    safe_move "$f" "scripts/dev"
done
echo

# ----------------------------------------------------------------------------
# 4. Report
# ----------------------------------------------------------------------------
echo "✅ Phase 1 file-system work complete."
echo
echo "📊 Repo size now: $(du -sh . 2>/dev/null | awk '{print $1}')"
echo "📊 .claude size: $(du -sh .claude 2>/dev/null | awk '{print $1}' || echo "—")"
echo
echo "🔍 Review with:"
echo "   git status"
echo "   git diff --stat"
echo
echo "When you're happy, commit with something like:"
echo '   git add -A && git commit -m "chore(repo): phase 1 — prune worktrees, relocate scratch scripts"'
