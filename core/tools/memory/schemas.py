from pydantic import BaseModel, Field, field_validator, model_validator
from enum import Enum
from typing import Literal
from datetime import datetime, timezone
import hashlib

# ─────────────────────────────────────────────
# ENUMS
# ─────────────────────────────────────────────

class MemoryType(str, Enum):
    BUG_FIX        = "bug_fix"
    ARCH_DECISION  = "arch_decision"
    SYSTEM_RULE    = "system_rule"
    API_CONTRACT   = "api_contract"
    LESSON_LEARNED = "lesson_learned"

class AuditVerdict(str, Enum):
    APPROVED  = "approved"
    REJECTED  = "rejected"
    ESCALATED = "escalated"   # Requires human sign-off before promotion

class RegressionRisk(str, Enum):
    NONE   = "none"
    LOW    = "low"
    MEDIUM = "medium"
    HIGH   = "high"           # Auto-blocks promotion regardless of verdict

# ─────────────────────────────────────────────
# TIER 2 — WORKING MEMORY (Promotion Candidate)
# ─────────────────────────────────────────────

class Tier2WorkingMemory(BaseModel):
    """
    A validated, task-scoped memory unit eligible for promotion.
    Lives in a temporary per-task ChromaDB collection.
    Destroyed on task completion if not promoted.
    """
    task_id:        str   = Field(..., description="SHA-256 of repo root + task timestamp")
    project_id:     str   = Field(..., description="SHA-256 of repo root path")
    memory_type:    MemoryType
    title:          str   = Field(..., min_length=5, max_length=120)
    content:        str   = Field(..., min_length=20,
                                  description="Human-readable summary of the fix or decision")
    code_diff:      str | None = Field(None,
                                  description="Unified diff of the change, if applicable")
    file_paths:     list[str]  = Field(default_factory=list,
                                  description="Affected files. Required for bug_fix type.")
    tags:           list[str]  = Field(default_factory=list, min_length=1)
    created_at:     datetime   = Field(default_factory=lambda: datetime.now(timezone.utc))
    lint_passed:    bool = Field(False, description="System 2 Step 1: autofix_linter cleared")
    tests_written:  bool = Field(False, description="System 2 Step 2: shadow_tester confirmed")

    @field_validator("tags")
    @classmethod
    def tags_must_be_lowercase(cls, v: list[str]) -> list[str]:
        return [t.lower().strip() for t in v]

    @model_validator(mode="after")
    def bug_fix_requires_files(self) -> "Tier2WorkingMemory":
        if self.memory_type == MemoryType.BUG_FIX and not self.file_paths:
            raise ValueError("BUG_FIX memories must declare at least one affected file_path.")
        return self


# ─────────────────────────────────────────────
# SYSTEM 2 AUDIT RESULT
# ─────────────────────────────────────────────

class System2AuditResult(BaseModel):
    """
    Output of consult_supervisor(). Must be APPROVED with zero regressions
    for promotion to proceed. This is the gate.
    """
    auditor_model:      str            = Field(..., description="Model ID that ran the audit")
    verdict:            AuditVerdict
    regression_risk:    RegressionRisk
    security_flags:     list[str]      = Field(default_factory=list,
                                         description="e.g. ['hardcoded_secret', 'sql_injection']")
    structural_notes:   str | None     = None
    audit_timestamp:    datetime       = Field(default_factory=lambda: datetime.now(timezone.utc))

    @model_validator(mode="after")
    def high_risk_blocks_approval(self) -> "System2AuditResult":
        if self.regression_risk == RegressionRisk.HIGH and self.verdict == AuditVerdict.APPROVED:
            raise ValueError(
                "A HIGH regression_risk memory cannot be APPROVED. "
                "Downgrade risk assessment or escalate to human."
            )
        if self.security_flags and self.verdict == AuditVerdict.APPROVED:
            raise ValueError(
                f"Cannot approve memory with active security flags: {self.security_flags}"
            )
        return self


# ─────────────────────────────────────────────
# PROMOTION REQUEST — THE GATE ITSELF
# ─────────────────────────────────────────────

class PromotionRequest(BaseModel):
    """
    Combines the Tier 2 candidate + System 2 audit.
    promote() is the single entry point — it validates both and
    returns the Tier 3 payload ready for ChromaDB upsert.
    """
    candidate:    Tier2WorkingMemory
    audit:        System2AuditResult

    def promote(self) -> "Tier3PermanentMemory":
        # Gate 1: Pre-flight checks must have passed
        if not self.candidate.lint_passed:
            raise PermissionError("Promotion blocked: lint_passed is False. Run autofix_linter.")
        if not self.candidate.tests_written:
            raise PermissionError("Promotion blocked: tests_written is False. Run shadow_tester.")

        # Gate 2: Audit must be clean
        if self.audit.verdict != AuditVerdict.APPROVED:
            raise PermissionError(
                f"Promotion blocked: System 2 verdict is '{self.audit.verdict}'. "
                "Resolve audit findings before re-submitting."
            )

        # Gate 3: Deterministic content hash prevents silent mutation
        content_hash = hashlib.sha256(
            self.candidate.content.encode() + (self.candidate.code_diff or "").encode()
        ).hexdigest()

        return Tier3PermanentMemory(
            project_id      = self.candidate.project_id,
            title           = self.candidate.title,
            content         = self.candidate.content,
            memory_type     = self.candidate.memory_type,
            tags            = self.candidate.tags,
            file_paths      = self.candidate.file_paths,
            content_hash    = content_hash,
            auditor_model   = self.audit.auditor_model,
            regression_risk = self.audit.regression_risk,
            promoted_at     = datetime.now(timezone.utc),
            source_task_id  = self.candidate.task_id,
        )


# ─────────────────────────────────────────────
# TIER 3 — PERMANENT MEMORY (ChromaDB Payload)
# ─────────────────────────────────────────────

class Tier3PermanentMemory(BaseModel):
    """
    Immutable. Maps 1:1 to a ChromaDB document in kenbun.concepts.
    content_hash prevents silent overwrites — upsert must verify
    the hash matches before allowing any update.
    """
    project_id:      str
    title:           str
    content:         str
    memory_type:     MemoryType
    tags:            list[str]
    file_paths:      list[str]
    content_hash:    str        = Field(..., description="SHA-256 of content + code_diff")
    auditor_model:   str
    regression_risk: RegressionRisk
    promoted_at:     datetime
    source_task_id:  str

    # ChromaDB metadata dict — ready for collection.upsert()
    def to_chroma_metadata(self) -> dict:
        return {
            "project_id":      self.project_id,
            "title":           self.title,
            "memory_type":     self.memory_type.value,
            "tags":            ",".join(self.tags),
            "file_paths":      ",".join(self.file_paths),
            "content_hash":    self.content_hash,
            "auditor_model":   self.auditor_model,
            "regression_risk": self.regression_risk.value,
            "promoted_at":     self.promoted_at.isoformat(),
            "source_task_id":  self.source_task_id,
        }
