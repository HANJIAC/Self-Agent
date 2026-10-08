import json
from unittest.mock import MagicMock

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from agent import graph, tools


def state(sources=None):
    return {"messages": [HumanMessage(content="问题")],
            "source_documents": sources or [], "pending_reminders": []}


def tool_call(name):
    return AIMessage(content="", tool_calls=[{"name": name, "args": {}, "id": "call-1"}])


@pytest.fixture
def make_graph(monkeypatch):
    monkeypatch.setattr(graph, "load_config", lambda: {})

    def build(responses, tool_map=None):
        llm = MagicMock()
        llm.bind_tools.return_value = llm
        llm.invoke.side_effect = responses
        monkeypatch.setattr(graph, "get_chat_llm", lambda config: llm)
        monkeypatch.setattr(graph, "TOOL_MAP", tool_map or {})
        return graph._build_graph(), llm

    return build


def test_direct_reply(make_graph):
    agent, llm = make_graph([AIMessage(content="回答")])
    result = agent.invoke(state())
    assert result["messages"][-1].content == "回答"
    assert llm.invoke.call_count == 1
    assert [type(message) for message in result["messages"]] == [HumanMessage, AIMessage]
    assert result["messages"][0].content == "问题"
    assert result["source_documents"] == []
    assert result["pending_reminders"] == []
    llm.bind_tools.assert_called_once_with(graph.TOOLS)


def test_unknown_tool(make_graph):
    agent, llm = make_graph([tool_call("missing"), AIMessage(content="回答")])
    result = agent.invoke(state())
    messages = [m for m in result["messages"] if isinstance(m, ToolMessage)]
    assert len(messages) == 1 and messages[0].tool_call_id == "call-1"
    assert "未知工具" in messages[0].content
    assert result["messages"][-1].content == "回答"
    assert llm.invoke.call_count == 2
    assert llm.invoke.call_args.args[0][-1].tool_call_id == "call-1"
    assert result["pending_reminders"] == []
    assert result["source_documents"] == []


def test_retrieve_deduplicates_sources(make_graph):
    tool = MagicMock()
    tool.invoke.return_value = "[来源: a.pdf]\n第一段\n[来源: a.pdf]\n第二段"
    agent, _ = make_graph([tool_call("retrieve_knowledge"), AIMessage(content="回答")],
                          {"retrieve_knowledge": tool})
    result = agent.invoke(state())
    assert result["source_documents"] == [{"source": "a.pdf"}]
    tool.invoke.assert_called_once_with({})
    assert result["messages"][-2].content == tool.invoke.return_value
    assert result["messages"][-2].tool_call_id == "call-1"
    assert result["pending_reminders"] == []


def test_reminder_pending_confirmation(make_graph):
    proposal = json.loads(tools.propose_reminder.invoke({"task": "开会", "time": "明天10点"}))
    assert proposal["reminder_id"] and proposal["type"] == "reminder_proposal"
    assert proposal["task"] == "开会"
    assert proposal["time"] == "明天10点"
    assert proposal["recipient"] == ""
    tool = MagicMock()
    tool.invoke.return_value = json.dumps(proposal, ensure_ascii=False)
    agent, _ = make_graph([tool_call("propose_reminder"), AIMessage(content="请确认")],
                          {"propose_reminder": tool})
    input_state = state()
    existing = {"reminder_id": "existing", "task": "旧提醒", "time": "11:00", "recipient": ""}
    input_state["pending_reminders"] = [existing]
    result = agent.invoke(input_state)
    assert result["pending_reminders"] == [existing, proposal]
    assert "请确认" in result["messages"][-2].content
    assert "开会" in result["messages"][-2].content
    assert "明天10点" in result["messages"][-2].content
    assert "默认收件人" in result["messages"][-2].content
    assert result["messages"][-2].tool_call_id == "call-1"
    assert result["source_documents"] == []
    assert input_state["pending_reminders"] == [existing]


def test_invalid_reminder_json(make_graph):
    tool = MagicMock()
    tool.invoke.return_value = "invalid json"
    agent, _ = make_graph([tool_call("propose_reminder"), AIMessage(content="失败")],
                          {"propose_reminder": tool})
    result = agent.invoke(state())
    assert result["pending_reminders"] == []
    assert result["messages"][-2].content == "invalid json"
    assert result["messages"][-2].tool_call_id == "call-1"
    assert result["messages"][-1].content == "失败"
    assert result["source_documents"] == []


def test_multiple_tools_forward_args_and_match_ids(make_graph):
    retrieve = MagicMock()
    retrieve.invoke.return_value = "[来源: plan.md]\n项目计划"
    mail = MagicMock()
    mail.invoke.return_value = "邮件已成功发送"
    calls = [
        {"name": "retrieve_knowledge", "args": {"query": "项目计划"}, "id": "retrieve-1"},
        {"name": "send_email", "args": {"subject": "计划", "body": "内容"}, "id": "mail-1"},
    ]
    agent, llm = make_graph([AIMessage(content="", tool_calls=calls), AIMessage(content="完成")],
                          {"retrieve_knowledge": retrieve, "send_email": mail})
    result = agent.invoke(state())
    retrieve.invoke.assert_called_once_with({"query": "项目计划"})
    mail.invoke.assert_called_once_with({"subject": "计划", "body": "内容"})
    messages = [message for message in result["messages"] if isinstance(message, ToolMessage)]
    assert [(message.tool_call_id, message.content) for message in messages] == [
        ("retrieve-1", retrieve.invoke.return_value), ("mail-1", mail.invoke.return_value),
    ]
    assert result["source_documents"] == [{"source": "plan.md"}]
    assert result["pending_reminders"] == []
    assert result["messages"][-1].content == "完成"
    assert llm.invoke.call_count == 2


@pytest.mark.xfail(strict=True, reason="已知缺陷：工具异常中断整轮对话")
def test_tool_failure_becomes_message(make_graph):
    tool = MagicMock()
    tool.invoke.side_effect = RuntimeError("tool failed")
    agent, _ = make_graph([tool_call("retrieve_knowledge"), AIMessage(content="失败说明")],
                          {"retrieve_knowledge": tool})
    result = agent.invoke(state())
    assert isinstance(result["messages"][-2], ToolMessage)
    assert result["messages"][-1].content == "失败说明"


@pytest.mark.xfail(strict=True, reason="已知缺陷：来源跨轮累积")
def test_sources_only_belong_to_current_turn(make_graph):
    tool = MagicMock()
    tool.invoke.return_value = "[来源: new.pdf]\n内容"
    agent, _ = make_graph([tool_call("retrieve_knowledge"), AIMessage(content="回答")],
                          {"retrieve_knowledge": tool})
    result = agent.invoke(state([{"source": "old.pdf"}]))
    assert result["source_documents"] == [{"source": "new.pdf"}]
