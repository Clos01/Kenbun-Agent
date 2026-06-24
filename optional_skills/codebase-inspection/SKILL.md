---
kenbun:
  mode: document
  fidelity: high
  tech_stack: [bash, python, pygount]
  discovery_required: false
---

# Codebase Inspection with pygount

Analyze repositories for lines of code, language breakdown, file counts, and code-vs-comment ratios using `pygount`.

---

## When to Use
- User asks for LOC (lines of code) count.
- User wants a language breakdown of a repo.
- User asks about codebase size or composition.
- User wants code-vs-comment ratios.
- General "how big is this repo" questions.

---

## Prerequisites
```bash
pip install --break-system-packages pygount 2>/dev/null || pip install pygount
```

---

## Common Workflows

### 1. Basic Summary (Most Common)
Get a full language breakdown with file counts, code lines, and comment lines:
```bash
cd /path/to/repo
pygount --format=summary \
  --folders-to-skip=".git,node_modules,venv,.venv,__pycache__,.cache,dist,build,.next,.tox,.eggs,*.egg-info" \
  .
```

> [!IMPORTANT]
> **Always use `--folders-to-skip`** to exclude dependency/build directories, otherwise `pygount` will crawl them and take a very long time or hang.

### 2. Common Folder Exclusions
Adjust based on the project type:
- **Python projects:**
  ```bash
  --folders-to-skip=".git,venv,.venv,__pycache__,.cache,dist,build,.tox,.eggs,.mypy_cache"
  ```
- **JavaScript/TypeScript projects:**
  ```bash
  --folders-to-skip=".git,node_modules,dist,build,.next,.cache,.turbo,coverage"
  ```
- **General catch-all:**
  ```bash
  --folders-to-skip=".git,node_modules,venv,.venv,__pycache__,.cache,dist,build,.next,.tox,vendor,third_party"
  ```

### 3. Filter by Specific Language
```bash
# Only count Python files
pygount --suffix=py --format=summary .

# Only count Python and YAML
pygount --suffix=py,yaml,yml --format=summary .
```

### 4. Detailed File-by-File Output
```bash
# Default format shows per-file breakdown
pygount --folders-to-skip=".git,node_modules,venv" .

# Sort by code lines (pipe through sort)
pygount --folders-to-skip=".git,node_modules,venv" . | sort -t$'\t' -k1 -nr | head -20
```

### 5. Output Formats
- **Summary table** (default recommendation):
  ```bash
  pygount --format=summary .
  ```
- **JSON output** for programmatic use:
  ```bash
  pygount --format=json .
  ```
- **Pipe-friendly summary** (Language, file count, code, docs, empty, string):
  ```bash
  pygount --format=summary . 2>/dev/null
  ```

---

## Interpreting Results
The summary table columns:
- **Language** — detected programming language
- **Files** — number of files of that language
- **Code** — lines of actual code (executable/declarative)
- **Comment** — lines that are comments or documentation
- **%** — percentage of total

### Special Pseudo-languages:
- `__empty__` — empty files.
- `__binary__` — binary files (images, compiled, etc.).
- `__generated__` — auto-generated files (detected heuristically).
- `__duplicate__` — files with identical content.
- `__unknown__` — unrecognized file types.

---

## Pitfalls
- **Missing exclusions:** Always exclude `.git`, `node_modules`, `venv` — without `--folders-to-skip`, `pygount` will crawl everything and may take minutes or hang on large dependency trees.
- **Markdown shows 0 code lines:** `pygount` classifies all Markdown content as comments, not code. This is expected behavior.
- **JSON files show low code counts:** `pygount` may count JSON lines conservatively. For accurate JSON line counts, use `wc -l` directly.
- **Large monorepos:** For very large repos, consider using `--suffix` to target specific languages rather than scanning everything.
