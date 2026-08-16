"""
Audit Tier Calibration — turns the cost-escalation ladder into a bootstrap chain.

The audit stack is a ladder of increasingly expensive reviewers:

    2c guardrail (llama3.2:3b)  →  2a court (COURT_LLM_MODEL)
                                →  Tier 2 cloud (AUDIT_LLM_MODEL)

Historically any rung could short-circuit the whole stack with an APPROVED, which
means a 3B model's opinion could be the last word on code written by a frontier
model. That is exactly the large-supervisor-gap regime where weak-to-strong
generalization plateaus: the cheap rung is only trustworthy on the subset of
work it actually understands.

This module measures which subset that is. Every time a cheap rung and a strong
rung both judge the same artifact, the pair is recorded per *category*. A cheap
rung is then allowed to auto-approve only in categories where its safe-approval
rate clears a Wilson lower bound at a minimum sample count. Everywhere else its
approval is downgraded to an escalation.

Asymmetry is deliberate and load-bearing:
  - A cheap APPROVE that the strong tier would have REJECTED is an UNSAFE
    disagreement — it ships a vulnerability. These are what the gate counts.
  - A cheap REJECT that the strong tier would have APPROVED is merely expensive
    (it costs an escalation or a heal loop). It never gates anything.

So "agreement" here means "did not falsely approve", not "matched verdicts".
"""
from __future__ import annotations

import math
import re
import sqlite3
import time
from contextlib import closing
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from tools.infrastructure.config import settings

# Categories are deterministic and keyword-driven on purpose: the thing deciding
# *whether* we can trust a model must not itself be a model call.
# ORDER IS THE POLICY. First match wins, so this list runs most-dangerous
# capability first: a snippet that both deserialises untrusted bytes and opens a
# file is calibrated as deserialization, because that is the capability that can
# execute code. Reordering these silently re-bins historical observations against
# new categories, so treat the order as part of the calibration contract.
CATEGORY_PATTERNS: List[Tuple[str, List[str]]] = [
    ("shell_exec", [
        r"\bos\.system\b", r"\bsubprocess\b", r"shell\s*=\s*True", r"\bpopen\b",
        r"\beval\s*\(", r"\bexec\s*\(", r"\bcompile\s*\(",
    ]),
    ("deserialization", [
        r"\bpickle\b", r"\byaml\.(safe_)?load\b", r"\bmarshal\b", r"\bshelve\b",
    ]),
    ("secrets", [
        r"api[_-]?key", r"\bsecret\b", r"\btoken\b", r"\bpassword\b",
        r"\bcredential", r"\.env\b",
    ]),
    # Deliberately narrow. Broad stems like r"\bpermission" or r"\bsession\b"
    # swallowed unrelated code (PermissionError in a path check, load_session in
    # a pickle call), which spread one category's evidence across three.
    ("auth", [
        r"\bauthenticat", r"\bauthoriz", r"\blogin\b", r"\bjwt\b",
        r"\bcurrent_user\b", r"\bDepends\s*\(", r"\brole[_-]?based\b",
        r"\bis_admin\b", r"\brbac\b", r"\bsession[_-]?(token|id|cookie)\b",
    ]),
    ("sql", [
        r"\bSELECT\b.*\bFROM\b", r"\bINSERT\s+INTO\b", r"\bUPDATE\b.*\bSET\b",
        r"\bDELETE\s+FROM\b", r"\bexecute\s*\(", r"\bcursor\b",
    ]),
    ("filesystem", [
        r"\bopen\s*\(", r"\bPath\s*\(", r"\bshutil\b", r"\bos\.remove\b",
        r"\bos\.path\.join\b", r"\brm\s+-rf\b",
    ]),
    ("network", [
        r"\brequests\.", r"\bhttpx\b", r"\baiohttp\b", r"\burllib\b",
        r"\bsocket\b", r"\bfetch\s*\(",
    ]),
    ("ui_style", [
        r"\bcss\b", r"\btailwind\b", r"\bclassName\b", r"\bstyled\b",
        r"\bglassmorphism\b", r"\bpadding\b", r"\bcolor:", r"\blayout\b",
        r"\bdangerouslySetInnerHTML\b",
    ]),
]

FALLBACK_CATEGORY = "general"

# Verdict vocabularies differ per rung ("approved"/"APPROVED"/"APPROVE").
_APPROVE_TOKENS = {"approved", "approve", "pass", "passed", "safe", "ok"}
_REJECT_TOKENS = {"rejected", "reject", "fail", "failed", "unsafe", "blocked"}


def normalize_verdict(verdict: Any) -> Optional[str]:
    """Map a rung's verdict string onto APPROVED / REJECTED / None (indeterminate)."""
    if not isinstance(verdict, str):
        return None
    v = verdict.strip().lower()
    if v in _APPROVE_TOKENS:
        return "APPROVED"
    if v in _REJECT_TOKENS:
        return "REJECTED"
    return None


def categorize(proposal: str = "", code_snippet: str = "") -> str:
    """Classify an audit subject into a calibration category.

    Ordered most-dangerous-first: a snippet that shells out AND touches CSS is
    calibrated as shell_exec, because that is the capability that can hurt.
    """
    blob = f"{proposal or ''}\n{code_snippet or ''}"
    for category, patterns in CATEGORY_PATTERNS:
        for pattern in patterns:
            if re.search(pattern, blob, re.IGNORECASE):
                return category
    return FALLBACK_CATEGORY


def _wilson_lower_bound(successes: int, total: int, z: float = 1.96) -> float:
    """Lower bound of the 95% Wilson score interval with Yates's Continuity Correction.

    Used instead of the raw ratio so that 3/3 (ratio 1.0, lower bound 0.31) can
    never unlock a category. Small samples stay untrusted until they earn it.
    The continuity correction unconditionally tightens the bound to prevent
    optimistic safety inflation on small n.
    """
    if total <= 0:
        return 0.0
    if successes == 0:
        return 0.0
    p = successes / total
    n = total
    
    num = 2 * n * p + z**2 - 1 - z * math.sqrt(z**2 - 2 - 1/n + 4*p*(n*(1-p) + 1))
    den = 2 * (n + z**2)
    return max(0.0, num / den)


@dataclass
class CalibrationVerdict:
    """Result of asking whether a rung may auto-approve in a category."""
    trusted: bool
    reason: str
    unsafe_samples: int
    caught_unsafe: int
    lower_bound: float

    def as_dict(self) -> Dict[str, Any]:
        return {
            "trusted": self.trusted,
            "reason": self.reason,
            "unsafe_samples": self.unsafe_samples,
            "caught_unsafe": self.caught_unsafe,
            "sensitivity_lower_bound": round(self.lower_bound, 4),
        }


class TierCalibration:
    """Per-(tier, category) record of how often a cheap rung was safe to trust."""

    def __init__(self):
        self._initialized = False

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(settings.INTELLIGENCE_DB_PATH, timeout=5.0)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout=5000;")
        return conn

    def _ensure_schema(self):
        if self._initialized:
            return
        try:
            with closing(self._connect()) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS audit_tier_calibration (
                        tier TEXT NOT NULL,
                        category TEXT NOT NULL,
                        approvals INTEGER NOT NULL DEFAULT 0,
                        safe_approvals INTEGER NOT NULL DEFAULT 0,
                        rejections INTEGER NOT NULL DEFAULT 0,
                        false_rejections INTEGER NOT NULL DEFAULT 0,
                        unsafe_cases_seen INTEGER NOT NULL DEFAULT 0,
                        unsafe_rejections INTEGER NOT NULL DEFAULT 0,
                        updated_at REAL NOT NULL,
                        PRIMARY KEY (tier, category)
                    );
                """)
                # Handle migrations gracefully
                try:
                    conn.execute("ALTER TABLE audit_tier_calibration ADD COLUMN unsafe_cases_seen INTEGER NOT NULL DEFAULT 0")
                    conn.execute("ALTER TABLE audit_tier_calibration ADD COLUMN unsafe_rejections INTEGER NOT NULL DEFAULT 0")
                except sqlite3.OperationalError:
                    pass # Columns probably already exist
                    
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS audit_tier_calibration_log (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        tier TEXT NOT NULL,
                        category TEXT NOT NULL,
                        cheap_verdict TEXT,
                        strong_verdict TEXT,
                        source TEXT,
                        timestamp REAL NOT NULL
                    );
                """)
                conn.commit()
            self._initialized = True
        except Exception as e:
            print(f"⚠️ [CALIBRATION] Failed to initialize schema: {e}")

    def record_pair(
        self,
        tier: str,
        category: str,
        cheap_verdict: Any,
        strong_verdict: Any,
        source: str = "live",
    ) -> bool:
        """Record one paired observation. Returns True if it was counted.

        `strong_verdict` is either the verdict of a higher rung or a ground-truth
        label from the golden set — both are treated as the authority.
        """
        cheap = normalize_verdict(cheap_verdict)
        strong = normalize_verdict(strong_verdict)
        if cheap is None or strong is None:
            # An indeterminate verdict (ERROR, REVIEW_NEEDED, timeout) carries no
            # calibration signal. Counting it either way would be a lie.
            return False

        self._ensure_schema()
        approvals = 1 if cheap == "APPROVED" else 0
        safe_approvals = 1 if (cheap == "APPROVED" and strong == "APPROVED") else 0
        rejections = 1 if cheap == "REJECTED" else 0
        false_rejections = 1 if (cheap == "REJECTED" and strong == "APPROVED") else 0

        # Tracking Sensitivity
        unsafe_cases_seen = 1 if strong == "REJECTED" else 0
        unsafe_rejections = 1 if (cheap == "REJECTED" and strong == "REJECTED") else 0

        try:
            with closing(self._connect()) as conn:
                conn.execute(
                    """
                    INSERT INTO audit_tier_calibration
                        (tier, category, approvals, safe_approvals, rejections, false_rejections, unsafe_cases_seen, unsafe_rejections, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(tier, category) DO UPDATE SET
                        approvals = approvals + excluded.approvals,
                        safe_approvals = safe_approvals + excluded.safe_approvals,
                        rejections = rejections + excluded.rejections,
                        false_rejections = false_rejections + excluded.false_rejections,
                        unsafe_cases_seen = unsafe_cases_seen + excluded.unsafe_cases_seen,
                        unsafe_rejections = unsafe_rejections + excluded.unsafe_rejections,
                        updated_at = excluded.updated_at
                    """,
                    (tier, category, approvals, safe_approvals, rejections,
                     false_rejections, unsafe_cases_seen, unsafe_rejections, time.time()),
                )
                conn.execute(
                    """
                    INSERT INTO audit_tier_calibration_log
                        (tier, category, cheap_verdict, strong_verdict, source, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (tier, category, cheap, strong, source, time.time()),
                )
                conn.commit()
            return True
        except Exception as e:
            print(f"⚠️ [CALIBRATION] Failed to record pair: {e}")
            return False

    def may_autoapprove(self, tier: str, category: str) -> CalibrationVerdict:
        """May `tier` short-circuit the stack with an APPROVED in `category`?"""
        if not settings.AUDIT_CALIBRATION_ENABLED:
            return CalibrationVerdict(True, "calibration disabled", 0, 0, 1.0)

        self._ensure_schema()
        unsafe_cases = unsafe_rejections = 0
        try:
            with closing(self._connect()) as conn:
                row = conn.execute(
                    "SELECT unsafe_cases_seen, unsafe_rejections FROM audit_tier_calibration "
                    "WHERE tier = ? AND category = ?",
                    (tier, category),
                ).fetchone()
            if row:
                unsafe_cases, unsafe_rejections = int(row[0]), int(row[1])
        except Exception as e:
            # Fail CLOSED: if we cannot prove the rung is trustworthy, it is not.
            return CalibrationVerdict(False, f"calibration store unreadable: {e}", 0, 0, 0.0)

        min_samples = settings.AUDIT_CALIBRATION_MIN_SAMPLES
        if unsafe_cases < min_samples:
            return CalibrationVerdict(
                False,
                f"only {unsafe_cases}/{min_samples} unsafe cases recorded for "
                f"'{category}' — not yet calibrated",
                unsafe_cases, unsafe_rejections, _wilson_lower_bound(unsafe_rejections, unsafe_cases),
            )

        lower = _wilson_lower_bound(unsafe_rejections, unsafe_cases)
        threshold = settings.AUDIT_CALIBRATION_MIN_AGREEMENT
        if lower < threshold:
            return CalibrationVerdict(
                False,
                f"sensitivity lower bound {lower:.2f} < {threshold:.2f} over "
                f"{unsafe_cases} unsafe samples in '{category}'",
                unsafe_cases, unsafe_rejections, lower,
            )

        return CalibrationVerdict(
            True,
            f"calibrated: caught {unsafe_rejections}/{unsafe_cases} vulnerabilities, sensitivity lower bound {lower:.2f}",
            unsafe_cases, unsafe_rejections, lower,
        )

    def should_drift_check(self, tier: str, category: str) -> bool:
        """Should an *already trusted* approval be re-verified against the strong tier?

        Uncalibrated categories don't need this — they are already being escalated
        by the gate, which yields a paired observation for free. This covers the
        opposite risk: a category that graduated months ago and has been coasting
        while the models under it changed. Sampling at
        AUDIT_CALIBRATION_SAMPLE_RATE keeps the evidence fresh.
        """
        if not settings.AUDIT_CALIBRATION_ENABLED:
            return False
        rate = settings.AUDIT_CALIBRATION_SAMPLE_RATE
        if rate <= 0:
            return False
        if rate >= 1:
            return True
        import random
        return random.random() < rate

    def report(self) -> Dict[str, Any]:
        """Full calibration table — what each rung is and isn't trusted with."""
        self._ensure_schema()
        rows: List[Dict[str, Any]] = []
        try:
            with closing(self._connect()) as conn:
                for tier, category, approvals, safe, rejections, false_rej, unsafe_seen, unsafe_rej, updated in conn.execute(
                    "SELECT tier, category, approvals, safe_approvals, rejections, "
                    "false_rejections, unsafe_cases_seen, unsafe_rejections, updated_at FROM audit_tier_calibration "
                    "ORDER BY tier, category"
                ):
                    verdict = self.may_autoapprove(tier, category)
                    rows.append({
                        "tier": tier,
                        "category": category,
                        "approvals": approvals,
                        "safe_approvals": safe,
                        "unsafe_approvals": approvals - safe,
                        "rejections": rejections,
                        "false_rejections": false_rej,
                        "unsafe_cases_seen": unsafe_seen,
                        "unsafe_rejections": unsafe_rej,
                        "sensitivity_lower_bound": round(
                            _wilson_lower_bound(unsafe_rej, unsafe_seen), 4),
                        "auto_approve_allowed": verdict.trusted,
                        "updated_at": updated,
                    })
        except Exception as e:
            return {"error": f"Failed to read calibration table: {e}", "rows": []}

        return {
            "enabled": settings.AUDIT_CALIBRATION_ENABLED,
            "min_samples": settings.AUDIT_CALIBRATION_MIN_SAMPLES,
            "min_agreement": settings.AUDIT_CALIBRATION_MIN_AGREEMENT,
            "rows": rows,
        }


calibration = TierCalibration()
