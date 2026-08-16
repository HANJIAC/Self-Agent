# Self-Agent

一个个人开发的 RAG-Agent 小助手，支持上传文件进行智能问答、文档总结，并可创建定时任务发送邮件提醒。

## 功能特性

- **智能问答**：上传文件后，基于文件内容进行对话式问答
- **文档总结**：自动提取并总结上传文档的核心信息
- **定时提醒**：支持创建定时任务，通过邮件发送提醒通知

## 技术栈

- **Agent 框架**：LangGraph + LangChain
- **向量数据库**：ChromaDB
- **大模型接入**：LangChain-OpenAI
- **前端界面**：Streamlit
- **定时任务**：APScheduler
- **文档解析**：PyPDF、Unstructured、Markdown

## 快速开始

### 1. 安装依赖

```bash
pip install -r cyber-agent/requirements.txt
```

### 2. 配置信息

编辑 `config.yaml`，填入你的 API Key 和邮箱配置：

```yaml
api_key: "YOUR_API_KEY_HERE"
email: "YOUR_EMAIL_HERE"
```

### 3. 启动项目

```bash
python cyber-agent/run.py
```

启动后会自动打开浏览器，即可开始使用。
