import json
import re
import smtplib
import uuid
from email.mime.text import MIMEText
from pathlib import Path

from langchain_core.tools import tool

from kb.vector_store import get_vector_store
from models.llm import load_config


def _parse_sources(text: str) -> list[dict]:
    """从 RAG 返回文本中抽取来源标记"""
    sources = []
    for m in re.finditer(r'\[来源:\s*([^\]]+)\]', text):
        sources.append({"source": m.group(1)})
    return sources


@tool
def retrieve_knowledge(query: str) -> str:
    """从个人知识库中检索与问题相关的信息。
    当用户的问题可能涉及你已学习的文档内容时，使用此工具获取相关上下文。
    """
    try:
        vs = get_vector_store()
        docs = vs.similarity_search(query, k=4)
    except Exception:
        return "知识库尚未初始化，请先上传文档。"

    if not docs:
        return "知识库中没有找到与问题相关的信息。"

    results = []
    for doc in docs:
        source = doc.metadata.get("source", "未知来源")
        results.append(f"[来源: {source}]\n{doc.page_content}")

    return "\n\n---\n\n".join(results)


@tool
def send_email(subject: str, body: str, recipient: str = "") -> str:
    """发送邮件。
    subject: 邮件主题
    body: 邮件正文
    recipient: 收件人邮箱（留空则使用默认收件人）
    """
    config = load_config()
    email_cfg = config.get("email", {})
    if not recipient:
        recipient = email_cfg.get("default_recipient", "")

    if not all([email_cfg.get("smtp_server"), email_cfg.get("username"),
                email_cfg.get("password"), recipient]):
        return "邮件配置不完整，请先在侧边栏填写邮箱信息。"

    try:
        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"] = subject
        msg["From"] = email_cfg["username"]
        msg["To"] = recipient

        port = email_cfg.get("smtp_port", 587)
        with smtplib.SMTP(email_cfg["smtp_server"], port) as server:
            server.starttls()
            server.login(email_cfg["username"], email_cfg["password"])
            server.sendmail(email_cfg["username"], [recipient], msg.as_string())

        return f"邮件已成功发送至 {recipient}"
    except Exception as e:
        return f"邮件发送失败: {e}"


@tool
def propose_reminder(task: str, time: str, recipient: str = "") -> str:
    """提议一个定时提醒，需要用户确认后才能生效。
    当你觉得用户需要被提醒某件事时可以使用此工具。

    task: 提醒内容描述
    time: 提醒时间（用自然语言描述，如"下午3点"、"明天上午10点"）
    recipient: 通知邮箱（留空则使用默认收件人）
    """
    rid = str(uuid.uuid4())[:8]
    result = {
        "type": "reminder_proposal",
        "reminder_id": rid,
        "task": task,
        "time": time,
        "recipient": recipient,
    }
    return json.dumps(result, ensure_ascii=False)


# 工具列表，供 graph.py 导入
TOOLS = [retrieve_knowledge, send_email, propose_reminder]
TOOL_MAP = {t.name: t for t in TOOLS}
