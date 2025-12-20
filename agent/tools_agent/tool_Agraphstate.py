# graph state management
from typing import List, TypedDict, Optional
from langchain_core.messages import BaseMessage

# query is user input
# facts are retrieved information
# output is agent output
# message is the comments or thoughts of the agent
class GraphState(TypedDict, total=False):
    query: str
    facts: List[str]
    output: Optional[str]
    # running chat history
    message: List[BaseMessage]
    user_id: Optional[str]
    # optional iteration guard if used by runner
    max_iterations: int
    