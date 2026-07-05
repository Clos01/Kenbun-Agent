import logging
from typing import TypedDict, Annotated, Sequence
import operator
from langchain_core.messages import BaseMessage
from langgraph.graph import StateGraph, END
from tools.infrastructure.agents.architect_agent import architect_node
from tools.infrastructure.agents.coder_agent import coder_node
from tools.infrastructure.agents.reviewer_agent import reviewer_node

logger = logging.getLogger(__name__)

# --- CONFIGURATION ---
MAX_RETRIES = 3

# --- STATE DEFINITION ---
class SwarmState(TypedDict):
    """The State object passed through the LangGraph nodes."""
    messages: Annotated[Sequence[BaseMessage], operator.add]
    language: str
    current_code: str
    architect_instructions: str
    test_results: str
    error_log: str
    is_success: bool
    retry_count: int

# --- CONDITIONAL EDGES ---
def should_continue(state: SwarmState) -> str:
    """
    The Circuit Breaker logic.
    Decides whether to route back to Coder, end successfully, or halt due to infinite loops.
    """
    if state.get("is_success"):
        logger.info("✅ Swarm Graph: Execution succeeded! Ending workflow.")
        return "end"
        
    retry_count = state.get("retry_count", 0)
    if retry_count >= MAX_RETRIES:
        logger.warning(f"🚨 Swarm Graph: Circuit Breaker triggered! Max retries ({MAX_RETRIES}) reached.")
        return "human_escalation"
        
    logger.info(f"🔄 Swarm Graph: Code failed. Routing back to Coder (Attempt {retry_count + 1}/{MAX_RETRIES}).")
    return "coder"

# --- NODES ---
def human_escalation_node(state: SwarmState) -> SwarmState:
    """
    Fired when the Circuit Breaker is triggered.
    Halts execution and returns the final state to the user.
    """
    # Simply marks the end of the line. The final state will contain the last error.
    return state

# --- GRAPH CONSTRUCTION ---
def build_swarm_graph() -> StateGraph:
    """
    Builds and compiles the Multi-Agent Swarm graph using LangGraph.
    """
    workflow = StateGraph(SwarmState)
    
    # 1. Add Nodes
    workflow.add_node("architect", architect_node)
    workflow.add_node("coder", coder_node)
    workflow.add_node("reviewer", reviewer_node)
    workflow.add_node("human_escalation", human_escalation_node)
    
    # 2. Define Entry Point
    workflow.set_entry_point("architect")
    
    # 3. Define Edges
    # Architect outputs to Coder
    workflow.add_edge("architect", "coder")
    
    # Coder always passes output to Reviewer to test
    workflow.add_edge("coder", "reviewer")
    
    # Reviewer conditionally routes back to Coder, End, or Human
    workflow.add_conditional_edges(
        "reviewer",
        should_continue,
        {
            "coder": "coder",
            "end": END,
            "human_escalation": "human_escalation"
        }
    )
    
    # Human Escalation is a terminal node
    workflow.add_edge("human_escalation", END)
    
    # Compile
    return workflow.compile()
