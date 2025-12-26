from typing import List, TypedDict, Optional, Any
from langchain_core.messages import BaseMessage

# Global State: Shared, stable facts and artifacts
class GlobalState(TypedDict, total=False):
    query: str
    facts: List[str]
    user_id: Optional[str]
    session_id: Optional[str]
    # You can add more shared artifacts here, e.g.,
    # context_documents: List[str]
    # user_preferences: Dict[str, Any]

# Local State: Process and control variables for a specific agent
class AgentState(GlobalState, total=False):
    """
    Base state for an agent, combining GlobalState with Local State.
    """
    # Local message history for this agent's specific context
    message: List[BaseMessage]
    # Local output/scratchpad
    output: Optional[str]
    # Control variables
    max_iterations: int

# Specific aliases for clarity
PlannerState = AgentState
ToolState = AgentState

# Legacy alias to minimize breakage during refactor, 
# though we should prefer using the specific states.
GraphState = AgentState