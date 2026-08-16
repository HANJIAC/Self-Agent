from typing import TypedDict, Annotated, Sequence
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage


class AgentState(TypedDict):
    """Agent 的状态定义"""
    messages: Annotated[Sequence[BaseMessage], add_messages]
    source_documents: list[dict]  # 来源文档信息 [{source, content}]
    pending_reminders: list[dict]  # 待用户确认的提醒 [{id, task, time, recipient}]
