import streamlit as st
from pathlib import Path

st.set_page_config(page_title="Cyber Agent", page_icon="🤖", layout="wide")

from models.llm import load_config, save_config
from kb.vector_store import clear_vector_store
from kb.ingest import process_documents
from agent.graph import get_agent, rebuild_agent
from agent.state import AgentState
from scheduler.service import get_scheduler
from langchain_core.messages import HumanMessage, AIMessage


# ---- 初始化会话状态 ----

if "agent_state" not in st.session_state:
    st.session_state.agent_state = AgentState(
        messages=[],
        source_documents=[],
        pending_reminders=[],
    )

if "chat_display" not in st.session_state:
    st.session_state.chat_display = []


# ---- 启动调度器（单例）----

scheduler = get_scheduler()


# ---- 展示最近触发的提醒 ----

triggered = scheduler.pop_triggered()
for t in triggered:
    st.toast(f"⏰ 提醒：{t['task']}", icon="⏰")


# ========== 侧边栏 ==========

with st.sidebar:
    st.title("🤖 Cyber Agent")

    config = load_config()

    # ---- 模型配置 ----
    with st.expander("⚙️ 模型配置", expanded=True):
        llm_cfg = config["llm"]
        provider = st.selectbox(
            "提供商",
            ["deepseek", "qwen"],
            index=0 if llm_cfg["provider"] == "deepseek" else 1,
        )
        api_key = st.text_input("API Key", value=llm_cfg["api_key"], type="password")
        model_name = st.text_input("模型名称", value=llm_cfg["model"])
        base_url = st.text_input("Base URL", value=llm_cfg["base_url"])

        st.divider()
        st.caption("嵌入模型配置")
        embed_cfg = llm_cfg.get("embedding", {})
        embed_model = st.text_input("模型名称", value=embed_cfg.get("model", ""))
        embed_key = st.text_input("API Key（可选）", value=embed_cfg.get("api_key", ""), type="password")
        embed_url = st.text_input("Base URL（可选）", value=embed_cfg.get("base_url", ""))

        if st.button("💾 保存配置", use_container_width=True):
            config["llm"] = {
                "provider": provider,
                "api_key": api_key,
                "model": model_name,
                "base_url": base_url,
                "embedding": {
                    "model": embed_model or "deepseek-embedding",
                    "api_key": embed_key,
                    "base_url": embed_url,
                },
            }
            save_config(config)
            rebuild_agent()
            st.success("✅ 配置已保存，Agent 已重新加载")

    # ---- 邮件配置 ----
    with st.expander("📧 邮件配置", expanded=False):
        email_cfg = config.get("email", {})
        smtp_srv = st.text_input("SMTP 服务器", value=email_cfg.get("smtp_server", ""))
        smtp_port = st.number_input("端口", value=email_cfg.get("smtp_port", 587))
        email_user = st.text_input("邮箱地址", value=email_cfg.get("username", ""))
        email_pass = st.text_input("授权码", value=email_cfg.get("password", ""), type="password")
        default_recv = st.text_input("默认收件人", value=email_cfg.get("default_recipient", ""))

        if st.button("💾 保存邮件配置", use_container_width=True):
            config["email"] = {
                "smtp_server": smtp_srv,
                "smtp_port": smtp_port,
                "username": email_user,
                "password": email_pass,
                "default_recipient": default_recv,
            }
            save_config(config)
            st.success("✅ 邮件配置已保存")

    # ---- 知识库管理 ----
    with st.expander("📚 知识库", expanded=False):
        uploaded = st.file_uploader(
            "上传文档（TXT/MD/PDF）",
            type=["txt", "md", "pdf"],
            accept_multiple_files=True,
        )
        if uploaded and st.button("📥 处理并入库", type="primary", use_container_width=True):
            with st.spinner("正在处理文档..."):
                result = process_documents(uploaded)
            st.success(result)

        if st.button("🗑️ 清空知识库", use_container_width=True):
            st.success(clear_vector_store())

    # ---- 提醒管理 ----
    with st.expander("⏰ 提醒管理", expanded=False):
        st.subheader("📋 待确认的提醒")
        pending = st.session_state.agent_state.get("pending_reminders", [])
        if pending:
            for i, r in enumerate(pending):
                st.markdown(f"**{r['task']}** — {r['time']}")
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("✅ 确认", key=f"pc_{i}", use_container_width=True):
                        rid, err = scheduler.add_reminder(
                            r["task"], r["time"],
                            r.get("recipient", ""),
                            reminder_id=r.get("reminder_id", ""),
                        )
                        if err:
                            st.error(err)
                        else:
                            st.session_state.agent_state["pending_reminders"].pop(i)
                            st.rerun()
                with col2:
                    if st.button("❌ 取消", key=f"pl_{i}", use_container_width=True):
                        st.session_state.agent_state["pending_reminders"].pop(i)
                        st.rerun()
        else:
            st.caption("暂无待确认的提醒")

        st.divider()
        st.subheader("✅ 已激活的提醒")
        active = scheduler.get_reminders()
        if active:
            for r in active:
                st.markdown(f"⏰ **{r['task']}** — {r['time']}")
        else:
            st.caption("暂无激活的提醒")


# ========== 主聊天区域 ==========

st.title("💬 对话")

# 展示历史对话
for msg in st.session_state.chat_display:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("sources"):
            with st.expander("📎 来源文档"):
                for s in msg["sources"]:
                    st.write(f"- {s['source']}")

# 输入框
if prompt := st.chat_input("输入你的问题..."):
    st.session_state.chat_display.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # 准备本轮 Agent 输入
    saved = st.session_state.agent_state
    agent_input = AgentState(
        messages=list(saved["messages"]),
        source_documents=list(saved.get("source_documents", [])),
        pending_reminders=list(saved.get("pending_reminders", [])),
    )
    agent_input["messages"].append(HumanMessage(content=prompt))

    # 运行 Agent
    agent = get_agent()
    with st.chat_message("assistant"):
        with st.spinner("🤔 思考中..."):
            try:
                final_state = agent.invoke(agent_input)
            except Exception as e:
                st.error(f"❌ Agent 运行出错: {e}")
                st.stop()

    # 保存新状态
    st.session_state.agent_state = final_state

    # 抽取最终回复
    final_response = ""
    for m in reversed(final_state["messages"]):
        if isinstance(m, AIMessage) and m.content:
            final_response = m.content
            break

    sources = final_state.get("source_documents", [])

    # 显示回复
    st.markdown(final_response)
    if sources:
        with st.expander("📎 来源文档"):
            for s in sources:
                st.write(f"- {s['source']}")

    # 存入显示列表
    st.session_state.chat_display.append({
        "role": "assistant",
        "content": final_response,
        "sources": sources,
    })

    # 如果产生了新提醒，刷新侧边栏
    if final_state.get("pending_reminders"):
        st.rerun()
