"""
Codebase Feedback Mapper — Semantic & AST Dictionary Lookup for Client Video Insights.

Maps transcribed quotes, UI routes, and feature critiques to exact source code files,
React components, API handlers, and lines of code within the target project
(e.g. eko-veritas-prod, nevermiss-ai, or Kenbun).
"""

import os
import re
import ast
import json
import logging
from typing import Dict, List, Set, Optional, Tuple, Any, Union
from pathlib import Path

logger = logging.getLogger("tools.codebase.feedback_mapper")


class CodebaseFeedbackMapper:
    """Indexes codebase structure and maps natural language feedback to concrete code symbols."""

    def __init__(self, target_project_path: Optional[str] = None):
        self.project_path = Path(
            target_project_path or "/Users/carlosrivas/Dev/Projects/eko-veritas-prod"
        ).resolve()
        self.symbol_index: Dict[str, List[Dict[str, Any]]] = {}
        self.route_index: Dict[str, str] = {}
        self._build_code_index()

    def _build_code_index(self):
        """Scans the project to index routes, React components, and exported functions."""
        if not self.project_path.exists():
            logger.warning(f"⚠️ Target project path does not exist: {self.project_path}")
            return

        # 1. Index Next.js Page & API Routes
        app_dir = self.project_path / "src" / "app"
        if not app_dir.exists():
            app_dir = self.project_path / "app"

        if app_dir.exists():
            for root, _, files in os.walk(app_dir):
                for file in files:
                    if file in ("page.tsx", "page.jsx", "page.js", "route.ts", "route.js"):
                        full_p = Path(root) / file
                        rel_p = full_p.relative_to(self.project_path)
                        # Derive route URL from folder structure
                        route_segment = str(full_p.parent.relative_to(app_dir))
                        # Clean route segment: strip route groups like (dashboard)
                        clean_route = "/" + re.sub(r"\([^)]+\)/?", "", route_segment).strip("/")
                        if clean_route == "/.":
                            clean_route = "/"
                        self.route_index[clean_route] = str(rel_p)

        # 2. Index Component and Symbol names
        for root, dirs, files in os.walk(self.project_path):
            # Skip noise directories
            dirs[:] = [d for d in dirs if d not in ("node_modules", ".next", ".git", "dist", "build", ".cache")]
            for file in files:
                if file.endswith((".tsx", ".ts", ".jsx", ".js", ".py")):
                    file_p = Path(root) / file
                    rel_p = str(file_p.relative_to(self.project_path))
                    self._index_file_symbols(file_p, rel_p)

    def _index_file_symbols(self, file_path: Path, relative_path: str):
        """Indexes symbols, exported functions, and React component names in a file."""
        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return

        # Python files
        if file_path.suffix == ".py":
            try:
                tree = ast.parse(content)
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                        self._add_symbol(node.name.lower(), {
                            "symbol": node.name,
                            "type": "class" if isinstance(node, ast.ClassDef) else "function",
                            "file": relative_path,
                            "line": node.lineno
                        })
            except Exception:
                pass
            return

        # TypeScript / JavaScript files (Regex extraction)
        # Components / Functions: export function Name or export const Name = ...
        comp_matches = re.finditer(r"(?:export\s+(?:default\s+)?)?(?:function|const|class)\s+([A-Z]\w+)", content)
        for m in comp_matches:
            name = m.group(1)
            line_no = content[:m.start()].count("\n") + 1
            self._add_symbol(name.lower(), {
                "symbol": name,
                "type": "component",
                "file": relative_path,
                "line": line_no
            })

    def _add_symbol(self, key: str, entry: Dict[str, Any]):
        if key not in self.symbol_index:
            self.symbol_index[key] = []
        self.symbol_index[key].append(entry)

    def ground_quote_to_code(self, quote: str, ui_route: Optional[str] = None) -> Dict[str, Any]:
        """
        Takes a verbatim client quote and maps it to concrete code symbols and files.
        """
        matched_files = set()
        matched_symbols = []
        
        # 1. Check UI Route Grounding
        if ui_route and ui_route in self.route_index:
            mapped_file = self.route_index[ui_route]
            matched_files.add(mapped_file)

        # 2. Tokenize and search symbol index
        words = re.findall(r"\b[a-zA-Z0-9_-]{3,}\b", quote.lower())
        for word in words:
            if word in self.symbol_index:
                for entry in self.symbol_index[word]:
                    matched_symbols.append(entry)
                    matched_files.add(entry["file"])

        # 3. Formulate Audit Proactive Question & Gap Analysis
        proactive_audit = self._formulate_audit_questions(quote, list(matched_files))

        return {
            "quote": quote,
            "associated_route": ui_route,
            "matched_files": sorted(list(matched_files)),
            "matched_symbols": matched_symbols[:5],
            "proactive_audit": proactive_audit
        }

    def _formulate_audit_questions(self, quote: str, matched_files: List[str]) -> Dict[str, Any]:
        """Formulates proactive questions to clarify business requirements and bridge technical debt."""
        gap_detected = False
        audit_note = "Implementation aligned with standard patterns."
        
        quote_lower = quote.lower()
        if any(k in quote_lower for k in ["where", "how come", "why", "didn't see", "missing", "expected"]):
            gap_detected = True
            audit_note = f"Client expressed ambiguity or missing expectation. Requires code inspection on: {', '.join(matched_files[:2]) or 'target route'}."

        return {
            "gap_detected": gap_detected,
            "recommended_investigation": audit_note,
            "clarification_prompt": f"Verify if the logic in {matched_files[:1] or ['current page']} fulfills: '{quote[:100]}...'"
        }

    def ground_feedback_envelope(self, intelligence_envelope: Dict[str, Any]) -> Dict[str, Any]:
        """
        Grounds an entire video intelligence envelope across all quotes and detected routes.
        """
        verbatim_quotes = intelligence_envelope.get("verbatim_quotes", [])
        detected_routes = intelligence_envelope.get("detected_ui_routes", [])

        grounded_items = []
        for q in verbatim_quotes:
            quote_text = q.get("quote", "")
            # Correlate with detected routes
            assigned_route = detected_routes[0] if detected_routes else None
            grounding = self.ground_quote_to_code(quote_text, assigned_route)
            grounding["start_timestamp"] = q.get("start_timestamp", 0.0)
            grounding["end_timestamp"] = q.get("end_timestamp", 0.0)
            grounded_items.append(grounding)

        # Unique files involved across all feedback
        all_involved_files = set()
        for item in grounded_items:
            all_involved_files.update(item.get("matched_files", []))

        return {
            "total_quotes_grounded": len(grounded_items),
            "involved_codebase_files": sorted(list(all_involved_files)),
            "grounded_quotes": grounded_items
        }
