from langgraph.graph import StateGraph, END
from langchain_core.messages import AIMessage, ToolMessage

from agent.state import AgentState
from agent.tools import TOOLS, TOOL_MAP, _parse_sources
from models.llm import load_config, get_chat_llm
import json


def _build_graph():
    config = load_config()
    llm = get_chat_llm(config)
    llm_with_tools = llm.bind_tools(TOOLS)

    def agent_node(state: AgentState) -> dict:
        messages = state["messages"]
        response = llm_with_tools.invoke(messages)
        return {"messages": [response]}

    def tools_node(state: AgentState) -> dict:
        last_message = state["messages"][-1]
        if not hasattr(last_message, "tool_calls") or not last_message.tool_calls:
            return {}

        new_messages = []
        new_sources = list(state.get("source_documents", []))
        new_reminders = list(state.get("pending_reminders", []))

        for tc in last_message.tool_calls:
            tool_name = tc["name"]
            tool_args = tc["args"]
            tool_call_id = tc["id"]
            tool_fn = TOOL_MAP.get(tool_name)

            if not tool_fn:
                new_messages.append(
                    ToolMessage(content=f"未知工具: {tool_name}", tool_call_id=tool_call_id)
                )
                continue

            result_str = tool_fn.invoke(tool_args)

            if tool_name == "propose_reminder":
                try:
                    parsed = json.loads(result_str)
                    human_text = (
                        f"📋 **提醒建议**\n"
                        f"- ⏰ **时间**：{parsed['time']}\n"
                        f"- 📋 **内容**：{parsed['task']}\n"
                        f"- 📧 **通知**：{parsed.get('recipient') or '默认收件人'}\n\n"
                        f"⚠️ **请确认是否设置此提醒？**"
                    )
                    new_reminders.append(parsed)
                    new_messages.append(ToolMessage(content=human_text, tool_call_id=tool_call_id))
                except json.JSONDecodeError:
                    new_messages.append(ToolMessage(content=result_str, tool_call_id=tool_call_id))
            else:
                new_messages.append(ToolMessage(content=result_str, tool_call_id=tool_call_id))

            if tool_name == "retrieve_knowledge":
                for s in _parse_sources(result_str):
                    if s not in new_sources:
                        new_sources.append(s)

        return {
            "messages": new_messages,
            "source_documents": new_sources,
            "pending_reminders": new_reminders,
        }

    def should_continue(state: AgentState) -> str:
        last_message = state["messages"][-1]
        if hasattr(last_message, "tool_calls") and last_message.tool_calls:
            return "tools"
        return END

    workflow = StateGraph(AgentState)
    workflow.add_node("agent", agent_node)
    workflow.add_node("tools", tools_node)
    workflow.set_entry_point("agent")
    workflow.add_conditional_edges("agent", should_continue, {"tools": "tools", END: END})
    workflow.add_edge("tools", "agent")

    return workflow.compile()


_graph_instance = None


def get_agent():
    global _graph_instance
    if _graph_instance is None:
        _graph_instance = _build_graph()
    return _graph_instance


def rebuild_agent():
    global _graph_instance
    _graph_instance = _build_graph()
    return _graph_instance
