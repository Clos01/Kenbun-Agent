import numpy as np
import re
from typing import Dict, Any, List, Tuple
from pathlib import Path
from tools.infrastructure.topology_manager import log_swarm_event

class MARSAuditor:
    """
    Multivariate Adaptive Regression Splines (MARS) inspired Boundary Auditor.
    
    This system treats agent tasks as multi-dimensional curves. It uses basis 
    functions to define 'Knots' (thresholds) for code changes. If an agent 
    crosses a knot into a forbidden logic zone, the change is rejected.
    """
    
    def get_guidance(self, category: str) -> str:
        """Returns a string describing the safe spline for a category."""
        category = category.lower()
        if category not in self.category_knots:
            return ""
        
        knots = self.category_knots[category]
        guidance = [f"MARS BOUNDARY GUIDANCE ({category.upper()}):"]
        for dim, knot in knots.items():
            if knot < 0.2:
                guidance.append(f"- {dim.upper()}: Strictly limited (knot < {knot}). Avoid changes here.")
            elif knot > 0.7:
                guidance.append(f"- {dim.upper()}: High allowance (knot > {knot}). Primary focus area.")
            else:
                guidance.append(f"- {dim.upper()}: Moderate threshold ({knot}). Keep changes surgical.")
        
        return "\n".join(guidance)

    def __init__(self):
        # Define 'Knots' for different task categories
        # Scale: 0.0 to 1.0 (Density/Importance)
        self.category_knots = {
            "ui": {
                "css_density": 0.8,
                "logic_complexity": 0.3,
                "db_interaction": 0.05,
                "security_impact": 0.1
            },
            "security": {
                "css_density": 0.1,
                "logic_complexity": 0.6,
                "db_interaction": 0.2,
                "security_impact": 0.9
            },
            "bug_fix": {
                "css_density": 0.4,
                "logic_complexity": 0.7,
                "db_interaction": 0.4,
                "security_impact": 0.3
            },
            "architecture": {
                "css_density": 0.2,
                "logic_complexity": 0.9,
                "db_interaction": 0.8,
                "security_impact": 0.5
            }
        }

    def _extract_features(self, diff: str) -> Dict[str, float]:
        """Extracts numerical features from a code diff."""
        lines = diff.split('\n')
        total_lines = len(lines) if len(lines) > 0 else 1
        
        # 1. CSS Density (Presence of style, tailwind, css, sx)
        css_signals = len(re.findall(r"(class|className|style|css|@apply|flex|grid|px-|py-)", diff, re.I))
        css_density = min(1.0, css_signals / total_lines)
        
        # 2. Logic Complexity (Control flow: if, for, while, async, try, catch)
        logic_signals = len(re.findall(r"(if|for|while|async|await|try|catch|match|case)", diff, re.I))
        logic_complexity = min(1.0, (logic_signals * 2) / total_lines)
        
        # 3. DB Interaction (SQL, Supabase, Prisma, fetch, api)
        db_signals = len(re.findall(r"(select|from|where|insert|update|delete|prisma|supabase|db\.|execute|query|fetch|api)", diff, re.I))
        db_interaction = min(1.0, (db_signals * 3) / total_lines)
        
        # 4. Security Impact (auth, token, secret, jwt, salt, hash, crypto, process.env)
        sec_signals = len(re.findall(r"(auth|token|secret|jwt|salt|hash|crypto|process\.env|env\.|verify|sign)", diff, re.I))
        security_impact = min(1.0, (sec_signals * 5) / total_lines)
        
        return {
            "css_density": css_density,
            "logic_complexity": logic_complexity,
            "db_interaction": db_interaction,
            "security_impact": security_impact
        }

    def evaluate_boundary(self, category: str, diff: str) -> Tuple[bool, str]:
        """
        Evaluates the MARS basis function for a task category and a diff.
        
        Logic:
        BF(x) = max(0, X - knot)
        If BF(x) for a forbidden dimension is > threshold, boundary is breached.
        """
        category = category.lower()
        if category not in self.category_knots:
            category = "bug_fix" # Default
            
        knots = self.category_knots[category]
        features = self._extract_features(diff)
        
        breaches = []
        
        for dim, knot in knots.items():
            actual = features[dim]
            
            # BASIS FUNCTION: Detect if 'actual' exceeded the 'knot'
            # For certain categories, some dimensions are strictly capped.
            basis_value = max(0, actual - knot)
            
            # UI task shouldn't be doing heavy DB or Security work
            if category == "ui" and dim in ["db_interaction", "security_impact"] and basis_value > 0.1:
                breaches.append(f"MARS Knot Breach: {dim.upper()} ({actual:.2f}) exceeds UI safety threshold ({knot:.2f})")
            
            # Security task shouldn't be doing heavy CSS work
            if category == "security" and dim == "css_density" and basis_value > 0.3:
                breaches.append(f"MARS Knot Breach: CSS_DENSITY ({actual:.2f}) exceeds Security task threshold ({knot:.2f})")

            # General 'Out of Bounds' check
            if basis_value > 0.5:
                breaches.append(f"Extreme Deviation: {dim.upper()} ({actual:.2f}) is 50%+ over its intended knot.")

        if breaches:
            msg = " | ".join(breaches)
            log_swarm_event("DECISION", {
                "tool": "mars_auditor",
                "confidence": 0.9,
                "result": "REJECTED",
                "logic": msg,
                "output": msg
            })
            return False, msg
        
        msg = "On-Curve: No non-linear boundary breaches detected."
        log_swarm_event("DECISION", {
            "tool": "mars_auditor",
            "confidence": 0.5,
            "result": "APPROVED",
            "logic": msg,
            "output": msg
        })
        return True, msg

# Singleton Instance
mars_auditor = MARSAuditor()
