"""
Tests for the audit-tier bootstrap chain, the appeal path, and the fail-open fix.

The property under test throughout: a cheap rung may only close a review where it
has been *shown* to be safe, and everywhere else its opinion escalates.
"""
import sqlite3

import pytest

from tools.audit.calibration import (
    TierCalibration,
    _wilson_lower_bound,
    categorize,
    normalize_verdict,
)


@pytest.fixture
def calib(tmp_path, monkeypatch):
    """A calibration store backed by a throwaway database."""
    db = tmp_path / "calibration_test.db"
    store = TierCalibration()
    monkeypatch.setattr(
        store, "_connect",
        lambda: sqlite3.connect(db, timeout=5.0),
    )
    return store


@pytest.fixture(autouse=True)
def calibration_settings(monkeypatch):
    from tools.infrastructure.config import settings
    monkeypatch.setattr(settings, "AUDIT_CALIBRATION_ENABLED", True, raising=False)
    # Mirror the production defaults — a calibration policy tested under
    # different thresholds than it ships with is not tested.
    monkeypatch.setattr(settings, "AUDIT_CALIBRATION_MIN_SAMPLES", 25, raising=False)
    monkeypatch.setattr(settings, "AUDIT_CALIBRATION_MIN_AGREEMENT", 0.85, raising=False)
    monkeypatch.setattr(settings, "AUDIT_CALIBRATION_SAMPLE_RATE", 0.0, raising=False)
    return settings


# --------------------------------------------------------------------------
# Wilson bound
# --------------------------------------------------------------------------

def test_perfect_but_tiny_sample_does_not_unlock():
    """3/3 is a ratio of 1.0 and proves nothing. The bound must reflect that."""
    assert _wilson_lower_bound(3, 3) < 0.5


def test_bound_rises_with_evidence():
    assert _wilson_lower_bound(50, 50) > _wilson_lower_bound(10, 10)


def test_empty_sample_is_zero():
    assert _wilson_lower_bound(0, 0) == 0.0


# --------------------------------------------------------------------------
# The gate
# --------------------------------------------------------------------------

def test_uncalibrated_category_may_not_autoapprove(calib):
    verdict = calib.may_autoapprove("court_2a", "shell_exec")
    assert verdict.trusted is False
    assert "not yet calibrated" in verdict.reason


def test_category_unlocks_after_enough_safe_approvals(calib):
    for _ in range(25):
        calib.record_pair("court_2a", "ui_style", "APPROVED", "APPROVED")
    verdict = calib.may_autoapprove("court_2a", "ui_style")
    assert verdict.trusted is True
    assert verdict.safe_approvals == 25


def test_one_unsafe_approval_in_the_minimum_sample_keeps_it_locked(calib):
    """Approving something the authority rejects is the only fatal error, and a
    single instance at the minimum sample count must be enough to withhold trust."""
    for _ in range(24):
        calib.record_pair("court_2a", "sql", "APPROVED", "APPROVED")
    calib.record_pair("court_2a", "sql", "APPROVED", "REJECTED")
    verdict = calib.may_autoapprove("court_2a", "sql")
    assert verdict.trusted is False
    assert verdict.lower_bound < 0.85


def test_false_rejections_do_not_block_graduation(calib):
    """Rejecting safe code is expensive, not dangerous. It must not gate approvals."""
    for _ in range(25):
        calib.record_pair("court_2a", "network", "APPROVED", "APPROVED")
    for _ in range(20):
        calib.record_pair("court_2a", "network", "REJECTED", "APPROVED")
    assert calib.may_autoapprove("court_2a", "network").trusted is True


def test_calibration_is_per_category(calib):
    for _ in range(25):
        calib.record_pair("court_2a", "ui_style", "APPROVED", "APPROVED")
    assert calib.may_autoapprove("court_2a", "ui_style").trusted is True
    assert calib.may_autoapprove("court_2a", "shell_exec").trusted is False


def test_calibration_is_per_tier(calib):
    for _ in range(25):
        calib.record_pair("court_2a", "ui_style", "APPROVED", "APPROVED")
    assert calib.may_autoapprove("guardrail_2c", "ui_style").trusted is False


def test_indeterminate_verdicts_are_not_counted(calib):
    """ERROR / REVIEW_NEEDED / timeouts carry no signal and must not inflate samples."""
    assert calib.record_pair("court_2a", "sql", "REVIEW_NEEDED", "APPROVED") is False
    assert calib.record_pair("court_2a", "sql", "APPROVED", "ERROR") is False
    assert calib.may_autoapprove("court_2a", "sql").samples == 0


def test_unreadable_store_fails_closed(tmp_path, monkeypatch):
    """If we cannot prove a rung is trustworthy, it is not trustworthy."""
    store = TierCalibration()
    store._initialized = True  # skip schema creation

    def boom():
        raise sqlite3.OperationalError("disk gone")

    monkeypatch.setattr(store, "_connect", boom)
    verdict = store.may_autoapprove("court_2a", "ui_style")
    assert verdict.trusted is False


def test_disabling_calibration_restores_short_circuiting(calib, calibration_settings, monkeypatch):
    monkeypatch.setattr(calibration_settings, "AUDIT_CALIBRATION_ENABLED", False, raising=False)
    assert calib.may_autoapprove("court_2a", "shell_exec").trusted is True


# --------------------------------------------------------------------------
# Categoriser
# --------------------------------------------------------------------------

@pytest.mark.parametrize("code,expected", [
    ("subprocess.run(cmd, shell=True)", "shell_exec"),
    ("cur.execute('SELECT id FROM users')", "sql"),
    ("api_key = os.environ['KEY']", "secrets"),
    ("pickle.loads(blob)", "deserialization"),
    ("requests.get(url, timeout=5)", "network"),
    ("def moving_average(values, window):\n    return []", "general"),
])
def test_categorize(code, expected):
    assert categorize("", code) == expected


def test_categorize_prefers_the_dangerous_capability():
    """CSS plus a shell call is a shell case — calibrate on what can hurt."""
    code = ".card { padding: 8px; }\nos.system(user_input)"
    assert categorize("update the card styling", code) == "shell_exec"


@pytest.mark.parametrize("raw,expected", [
    ("approved", "APPROVED"), ("APPROVED", "APPROVED"), ("Rejected", "REJECTED"),
    ("REVIEW_NEEDED", None), ("", None), (None, None), (123, None),
])
def test_normalize_verdict(raw, expected):
    assert normalize_verdict(raw) == expected


# --------------------------------------------------------------------------
# The fail-open fix
# --------------------------------------------------------------------------

def test_dead_guardrail_escalates_instead_of_approving(monkeypatch):
    """A 404 against Ollama used to rubber-stamp everything that reached it."""
    import tools.audit.guardrail_agent as ga

    def dead_endpoint(*args, **kwargs):
        raise ConnectionError("connection refused")

    monkeypatch.setattr(ga.requests, "post", dead_endpoint)
    result = ga.run_guardrail_audit("def add(a, b):\n    return a + b\n", "add numbers")

    assert result["status"] == "escalate"
    assert result["status"] != "approved"
    assert "NOT an approval" in result["critique"]


def test_deterministic_rejection_still_fires(monkeypatch):
    """The calibration work must not weaken the heuristic layer."""
    import tools.audit.guardrail_agent as ga
    payload = (
        "import requests, base64\n"
        "url = base64.b64decode('aHR0cDovL2V2aWw=').decode()\n"
        "requests.get(url)\n"
    )
    result = ga.run_guardrail_audit(payload, "exfiltration test")
    assert result["status"] == "rejected"
    assert result["risk_level"] == "critical"
    assert result["appealable"] is False


def test_reading_a_secret_from_the_environment_is_not_a_breach(monkeypatch):
    """`.env` used to match the substring inside `os.environ`, so the correct way
    to handle a credential was a critical deterministic rejection — and the
    'secrets' category could never accumulate a safe approval."""
    import tools.audit.guardrail_agent as ga

    class FakeResponse:
        status_code = 200

        @staticmethod
        def json():
            return {"response": '{"status": "approved", "risk_level": "low", "critique": "ok"}'}

    monkeypatch.setattr(ga.requests, "post", lambda *a, **k: FakeResponse())
    result = ga.run_guardrail_audit(
        "import os\nkey = os.environ['EXAMPLE_API_KEY']\n", "load the api key"
    )
    assert result["status"] != "rejected"
    assert result.get("risk_level") != "critical"


def test_actual_dotenv_access_is_still_a_breach(monkeypatch):
    import tools.audit.guardrail_agent as ga
    result = ga.run_guardrail_audit("data = open('.env').read()\n", "read config")
    assert result["status"] == "rejected"
    assert result["risk_level"] == "critical"


def test_uncalibrated_guardrail_approval_becomes_escalation(monkeypatch):
    """The 3B model may hold an opinion; it may not close the review with it."""
    import tools.audit.guardrail_agent as ga

    class FakeResponse:
        status_code = 200

        @staticmethod
        def json():
            return {"response": '{"status": "approved", "risk_level": "low", "critique": "looks fine"}'}

    monkeypatch.setattr(ga.requests, "post", lambda *a, **k: FakeResponse())
    result = ga.run_guardrail_audit("cur.execute(f'SELECT * FROM t WHERE id={x}')", "lookup")

    assert result["status"] == "escalate"
    assert result["local_opinion"] == "approved"
    assert "UNCALIBRATED" in result["critique"]


# --------------------------------------------------------------------------
# Appeals
# --------------------------------------------------------------------------

def test_deterministic_rejections_are_not_appealable():
    from tools.audit.supervisor_agent import _is_appealable
    assert _is_appealable({"status": "REJECTED", "appealable": False}) is False


def test_gateway_blocks_are_not_appealable():
    from tools.audit.supervisor_agent import _is_appealable
    assert _is_appealable({
        "status": "REJECTED",
        "tier": "System 2 Gateway: Hook Interceptor",
    }) is False


def test_design_guardrail_rejections_are_not_appealable():
    from tools.audit.supervisor_agent import _is_appealable
    assert _is_appealable({
        "status": "REJECTED",
        "tier": "System 2c: Design Guardrail",
    }) is False


def test_model_formed_rejections_are_appealable(monkeypatch):
    import tools.audit.supervisor_agent as sup
    monkeypatch.setattr(sup, "adversarial_court", object())
    assert _appealable(sup, {
        "status": "REJECTED",
        "tier": "System 2a: Adversarial LLM Court",
        "critique": "SQL injection on line 3",
    }) is True


def _appealable(sup, res):
    return sup._is_appealable(res)


def test_appeals_can_be_disabled(monkeypatch, calibration_settings):
    import tools.audit.supervisor_agent as sup
    monkeypatch.setattr(calibration_settings, "AUDIT_APPEALS_ENABLED", False, raising=False)
    assert sup._is_appealable({"status": "REJECTED", "tier": "System 2a"}) is False


@pytest.mark.asyncio
async def test_ambiguous_brief_concedes_without_convening_a_court(monkeypatch):
    """Contesting is explicit opt-in. Rambling is not an appeal."""
    import tools.audit.supervisor_agent as sup

    monkeypatch.setattr(sup, "_call_local_senior",
                        lambda s, u: ("Well, I do think the code is broadly reasonable here.", None))

    convened = []
    monkeypatch.setattr(sup, "adversarial_court",
                        type("C", (), {"run_appeal": lambda *a, **k: convened.append(1)})())

    upheld, entry = await sup._run_appeal("p", "code", "SQL injection on line 3")
    assert upheld is False
    assert entry is None
    assert convened == [], "an ambiguous brief must not cost a court round-trip"


@pytest.mark.asyncio
async def test_explicit_contest_convenes_the_court(monkeypatch):
    import tools.audit.supervisor_agent as sup

    brief = "CONTEST\nLine 3 uses a parameterised query with a tuple; the critique quotes an f-string that is not present."
    monkeypatch.setattr(sup, "_call_local_senior", lambda s, u: (brief, None))

    async def fake_appeal(proposal, code, critique, appellant_brief):
        assert appellant_brief == brief
        return {"ruling": "UPHELD", "confidence": 0.9, "critique": "refuted"}

    monkeypatch.setattr(sup, "adversarial_court",
                        type("C", (), {"run_appeal": staticmethod(fake_appeal)})())

    upheld, entry = await sup._run_appeal("p", "code", "SQL injection on line 3")
    assert upheld is True
    assert entry["confidence"] == 0.9


@pytest.mark.asyncio
async def test_low_confidence_appeal_does_not_overturn(monkeypatch, calibration_settings):
    """A hesitant 'UPHELD' must not unblock code a prior tier rejected."""
    from tools.audit.adversarial_court import adversarial_court

    monkeypatch.setattr(calibration_settings, "AUDIT_APPEAL_MIN_CONFIDENCE", 0.75, raising=False)

    async def fake_llm(system, user, role):
        return '{"ruling": "UPHELD", "confidence": 0.4, "critique": "maybe fine"}'

    monkeypatch.setattr(adversarial_court, "_query_llm", fake_llm)
    monkeypatch.setattr(adversarial_court, "_gather_repo_context",
                        lambda *a, **k: _async_return(""))

    entry = await adversarial_court.run_appeal("p", "code", "finding", "brief")
    assert entry["ruling"] == "DISMISSED"
    assert "below the" in entry["critique"]


@pytest.mark.asyncio
async def test_confident_appeal_overturns(monkeypatch, calibration_settings):
    from tools.audit.adversarial_court import adversarial_court

    monkeypatch.setattr(calibration_settings, "AUDIT_APPEAL_MIN_CONFIDENCE", 0.75, raising=False)

    async def fake_llm(system, user, role):
        return '{"ruling": "UPHELD", "confidence": 0.93, "critique": "line 3 is parameterised"}'

    monkeypatch.setattr(adversarial_court, "_query_llm", fake_llm)
    monkeypatch.setattr(adversarial_court, "_gather_repo_context",
                        lambda *a, **k: _async_return(""))

    entry = await adversarial_court.run_appeal("p", "code", "finding", "brief")
    assert entry["ruling"] == "UPHELD"


@pytest.mark.asyncio
async def test_unparseable_appeal_ruling_fails_closed(monkeypatch):
    from tools.audit.adversarial_court import adversarial_court

    async def fake_llm(system, user, role):
        return "I think the appeal is probably fine honestly"

    monkeypatch.setattr(adversarial_court, "_query_llm", fake_llm)
    monkeypatch.setattr(adversarial_court, "_gather_repo_context",
                        lambda *a, **k: _async_return(""))

    entry = await adversarial_court.run_appeal("p", "code", "finding", "brief")
    assert entry["ruling"] == "DISMISSED"


async def _async_return(value):
    return value


# --------------------------------------------------------------------------
# Generative supervision
# --------------------------------------------------------------------------

def test_repo_context_changes_the_cache_key():
    """Context alters verdicts, so a verdict formed without it must not be replayed."""
    from tools.audit.adversarial_court import adversarial_court
    bare = adversarial_court._cache_key("proposal", "code", "")
    with_ctx = adversarial_court._cache_key("proposal", "code", "def helper(): ...")
    assert bare != with_ctx


@pytest.mark.asyncio
async def test_repo_context_retrieval_failure_is_non_fatal(monkeypatch, calibration_settings):
    """A court with no context beats a court that hangs on ChromaDB."""
    from tools.audit.adversarial_court import adversarial_court
    monkeypatch.setattr(calibration_settings, "COURT_REPO_CONTEXT_ENABLED", True, raising=False)

    import tools.memory.code_indexer as ci
    monkeypatch.setattr(ci, "search_code", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("chroma down")))

    ctx = await adversarial_court._gather_repo_context("add a helper", "def helper():\n    pass\n")
    assert ctx == ""


@pytest.mark.asyncio
async def test_repo_context_is_disabled_by_flag(monkeypatch, calibration_settings):
    from tools.audit.adversarial_court import adversarial_court
    monkeypatch.setattr(calibration_settings, "COURT_REPO_CONTEXT_ENABLED", False, raising=False)
    assert await adversarial_court._gather_repo_context("x", "def f(): pass") == ""


# --------------------------------------------------------------------------
# The model-pinning regression
# --------------------------------------------------------------------------

def test_audit_model_is_configurable_and_current():
    """The strong rung must never be pinned behind the executors it audits."""
    import inspect
    from tools.infrastructure.config import settings
    import tools.audit.supervisor_agent as sup

    source = inspect.getsource(sup)
    assert "claude-3-5-sonnet-20241022" not in source
    assert "settings.AUDIT_LLM_MODEL" in source
    assert settings.AUDIT_LLM_MODEL
