from unittest.mock import MagicMock

import pytest
from langchain_core.documents import Document

from agent import tools


@pytest.mark.parametrize("text, expected", [
    ("没有标记", []),
    ("[来源: a.pdf]\n内容\n[来源: b.md]", [{"source": "a.pdf"}, {"source": "b.md"}]),
])
def test_parse_sources(text, expected):
    assert tools._parse_sources(text) == expected


def test_retrieve_content_and_sources(monkeypatch):
    store = MagicMock()
    store.similarity_search.return_value = [
        Document(page_content="第一段", metadata={"source": "a.pdf"}),
        Document(page_content="第二段"),
    ]
    monkeypatch.setattr(tools, "get_vector_store", lambda: store)
    result = tools.retrieve_knowledge.invoke({"query": "问题"})
    store.similarity_search.assert_called_once_with("问题", k=4)
    assert "[来源: a.pdf]\n第一段" in result
    assert "[来源: 未知来源]\n第二段" in result
    assert result.split("\n\n---\n\n") == ["[来源: a.pdf]\n第一段", "[来源: 未知来源]\n第二段"]
    assert tools._parse_sources(result) == [{"source": "a.pdf"}, {"source": "未知来源"}]


def test_empty_knowledge(monkeypatch):
    store = MagicMock()
    store.similarity_search.return_value = []
    monkeypatch.setattr(tools, "get_vector_store", lambda: store)
    result = tools.retrieve_knowledge.invoke({"query": "问题"})
    assert "没有找到" in result
    assert tools._parse_sources(result) == []
    store.similarity_search.assert_called_once_with("问题", k=4)


@pytest.mark.parametrize("stage", ["initialize", "search"])
def test_knowledge_failure(monkeypatch, stage):
    factory = MagicMock()
    if stage == "initialize":
        factory.side_effect = RuntimeError("unavailable")
    else:
        factory.return_value.similarity_search.side_effect = RuntimeError("unavailable")
    monkeypatch.setattr(tools, "get_vector_store", factory)
    result = tools.retrieve_knowledge.invoke({"query": "问题"})
    assert "尚未初始化" in result
    assert tools._parse_sources(result) == []
    factory.assert_called_once_with()
    if stage == "search":
        factory.return_value.similarity_search.assert_called_once_with("问题", k=4)
