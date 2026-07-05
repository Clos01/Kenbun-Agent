import pytest
from langchain_core.messages import HumanMessage
from tools.infrastructure.swarm_graph import build_swarm_graph

def test_circuit_breaker_halts_infinite_loop(monkeypatch):
    """
    Test that the Swarm Graph correctly halts after 3 retries (4 total loops)
    if the Reviewer Agent consistently returns failure.
    """
    
    # 0. Mock Architect Agent
    def mock_architect_node(state):
        return {
            "architect_instructions": "mock instructions"
        }

    # 1. Mock Coder Agent to just return a dummy script
    def mock_coder_node(state):
        return {
            "current_code": "print('hello world')",
        }

    # 2. Mock Reviewer Agent to always fail
    def mock_reviewer_node(state):
        retry_count = state.get("retry_count", 0)
        return {
            "test_results": "Mock error",
            "error_log": "SyntaxError: invalid syntax",
            "is_success": False,
            "retry_count": retry_count + 1
        }
    
    # Patch the actual nodes in the module
    import tools.infrastructure.swarm_graph as sg
    monkeypatch.setattr(sg, "architect_node", mock_architect_node)
    monkeypatch.setattr(sg, "coder_node", mock_coder_node)
    monkeypatch.setattr(sg, "reviewer_node", mock_reviewer_node)
    
    graph = sg.build_swarm_graph()
    
    initial_state = {
        "messages": [HumanMessage(content="Write a script that prints hello world")],
        "language": "python",
        "current_code": "",
        "architect_instructions": "",
        "test_results": "",
        "error_log": "",
        "is_success": False,
        "retry_count": 0
    }
    
    final_state = graph.invoke(initial_state)
    
    # Assertions
    assert final_state["is_success"] is False
    assert final_state["retry_count"] == 3
    
def test_truncation_logic():
    """Test the truncation heuristic for large stack traces."""
    from tools.infrastructure.agents.reviewer_agent import truncate_stack_trace
    
    # Create a dummy stack trace of 500 lines
    massive_trace = "\n".join([f"Line {i}" for i in range(500)])
    
    # Truncate to 100 lines
    truncated = truncate_stack_trace(massive_trace, max_lines=100)
    
    lines = truncated.split("\n")
    # 50 lines head + 1 line truncation message + 50 lines tail = 101 lines
    assert len(lines) == 101
    assert "Line 0" in lines[0]
    assert "Line 499" in lines[-1]
    assert "TRUNCATED" in lines[50]
