import pytest
from unittest.mock import patch, MagicMock
from tools.audit.supervisor_agent import run_supervisor_audit

@pytest.mark.asyncio
async def test_ralph_loop_recovery_success():
    """Verify that if the first audit is REJECTED, the Ralph-Loop heals the code and returns APPROVED."""
    
    # 1. Mock the raw audit runner to reject the unsafe code, but approve the healed code
    async def mock_run_raw(user_proposal, code_snippet, memory_context, tech_key):
        if "unsafe" in code_snippet:
            return {
                "status": "REJECTED",
                "critique": "[SECURITY ALERT] Dangerous code containing unsafe patterns.",
                "tier": "Tier 1a: Adversarial LLM Court"
            }
        else:
            return {
                "status": "APPROVED",
                "critique": "Code is clean and safe.",
                "tier": "Tier 1a: Adversarial LLM Court"
            }
            
    # 2. Mock the local senior LLM healer to return safe healed code
    def mock_call_senior(system_prompt, user_message):
        healed_code = "```python\ndef safe_code():\n    print('safe execution')\n```"
        return healed_code, None
        
    # Mock settings.security to bypass the unattended cron_mode gate during testing
    from tools.infrastructure.config import settings
    mock_sec = MagicMock()
    mock_sec.cron_mode = "allow"
    mock_sec.approval_mode = "smart"
    mock_sec.approval_timeout = 45
    mock_sec.custom_hook_path = None
        
    with patch("tools.audit.supervisor_agent._run_supervisor_audit_raw", side_effect=mock_run_raw), \
         patch("tools.audit.supervisor_agent._call_local_senior", side_effect=mock_call_senior), \
         patch("tools.infrastructure.config.KenbunSettings.security", new_callable=MagicMock) as mock_settings_sec:
         
        mock_settings_sec.return_value = mock_sec
         
        # Execute supervisor audit on unsafe code snippet
        res = await run_supervisor_audit(
            user_proposal="Execute command",
            code_snippet="def unsafe_code(): import os; os.system('unsafe')",
            recovery_attempts_left=2
        )
        
        # Verify Ralph-Loop state and healed outcome
        assert res["status"] == "APPROVED"
        assert res.get("recovered_from_rejection") is True
        assert "safe_code" in res["healed_code"]
        assert "unsafe" not in res["healed_code"]

@pytest.mark.asyncio
async def test_ralph_loop_recovery_exhausted():
    """Verify that if the healed code is also rejected, recovery terminates after exhaustion."""
    
    # Mock to always reject
    async def mock_run_raw(user_proposal, code_snippet, memory_context, tech_key):
        return {
            "status": "REJECTED",
            "critique": "[SECURITY LOCK] Code permanently unsafe.",
            "tier": "Tier 1a: Adversarial LLM Court"
        }
        
    def mock_call_senior(system_prompt, user_message):
        return "```python\ndef unsafe_healed():\n    pass\n```", None
        
    from tools.infrastructure.config import settings
    mock_sec = MagicMock()
    mock_sec.cron_mode = "allow"
    mock_sec.approval_mode = "smart"
    mock_sec.approval_timeout = 45
    mock_sec.custom_hook_path = None
        
    with patch("tools.audit.supervisor_agent._run_supervisor_audit_raw", side_effect=mock_run_raw), \
         patch("tools.audit.supervisor_agent._call_local_senior", side_effect=mock_call_senior), \
         patch("tools.infrastructure.config.KenbunSettings.security", new_callable=MagicMock) as mock_settings_sec:
         
        mock_settings_sec.return_value = mock_sec
         
        res = await run_supervisor_audit(
            user_proposal="Execute command",
            code_snippet="def unsafe_code(): pass",
            recovery_attempts_left=2
        )
        
        # Verify it remains rejected after exhaustion
        assert res["status"] == "REJECTED"
        assert res.get("recovered_from_rejection") is not True
