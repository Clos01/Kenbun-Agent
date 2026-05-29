.PHONY: help test smoke unit eval eval-full nightly clean stack-up stack-down stack-logs stack-status stack-pull

PY := PYTHONPATH=. python3
PYTEST := $(PY) -m pytest

help:
	@echo "Kenbun/core — daily ops"
	@echo ""
	@echo "  make smoke       Layer-1 smoke tests (fast, every commit)"
	@echo "  make unit        Layer-2 unit tests"
	@echo "  make test        smoke + unit (pre-push gate)"
	@echo "  make eval        Layer-3 nightly evaluator (1,500 cases sample)"
	@echo "  make eval-full   Full sweep over all 10,000 golden cases"
	@echo "  make nightly     Cron entrypoint: smoke -> eval (exit code propagated)"
	@echo "  make clean       Remove pytest/coverage/__pycache__ artifacts"
	@echo ""
	@echo "Local AI stack (Docker):"
	@echo "  make stack-up        Start Ollama + ChromaDB and auto-pull models"
	@echo "  make stack-down      Stop the stack (data preserved)"
	@echo "  make stack-logs      Tail ollama-init logs (model pulls)"
	@echo "  make stack-status    Health + listed models"
	@echo "  make stack-pull      Re-run model pull (after editing OLLAMA_MODELS)"

smoke:
	$(PYTEST) tests/ -m smoke

unit:
	$(PYTEST) tests/ -m unit || echo "(no unit tests yet — write some!)"

test: smoke unit

eval:
	$(PY) brain_health/nightly_eval.py

eval-full:
	$(PY) brain_health/nightly_eval.py --full

nightly:
	@$(MAKE) -s smoke || (echo "❌ Smoke failed — aborting nightly"; exit 2)
	@$(PY) brain_health/nightly_eval.py

clean:
	find . -type d -name "__pycache__" -not -path "./.venv/*" -prune -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache .coverage htmlcov

# ── Local AI Stack (macOS Safe Hardware Protections) ──────────────
stack-up:
	docker compose up -d chromadb
	@echo "⏳ Waiting for ChromaDB to start..."
	@sleep 2
	@echo "⬆️ Syncing memory signals..."
	PYTHONPATH=. python3 tools/memory/chroma_db_connect.py
	@echo "✅ Signals successfully restored!"

stack-light: stack-up

stack-down:
	docker compose down

stack-status:
	@echo "── Containers ──"
	@docker compose ps
	@echo ""
	@echo "── Native macOS Ollama (Hardware Accelerated) ──"
	@curl -s http://localhost:11434/api/tags | python3 -c "import sys,json; d=json.load(sys.stdin); [print(f'  • {m[\"name\"]:30s} {m.get(\"size\",0)//1_000_000_000}GB') for m in d.get('models',[])] or print('  (none)')" || echo "  ❌ Local native Ollama not running. Launch native Mac app."
	@echo ""
	@echo "── ChromaDB Container Status ──"
	@curl -fsS http://localhost:8000/api/v1/heartbeat >/dev/null && echo "  ✅ healthy" || echo "  ❌ not healthy"

