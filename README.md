# Self-Agent

一个个人开发的 agent-Agent 小助手，支持上传文件进行智能问答、文档总结，并可创建定时任务发送邮件提醒。

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
conda run -n agent python -m pip install -r requirements.txt
```
`agent`为开发环境名称

### 2. 配置信息

编辑 `config.yaml`，填入你的 API Key 和邮箱配置：

```yaml
api_key: "YOUR_API_KEY_HERE"
email: "YOUR_EMAIL_HERE"
```

或者启动项目后在网页侧边栏中填入你的API KEY 和邮箱相关配置

> **注意**：
> ```yaml
> email:
>     password: YOUR_EMAIL_SMTP_PASSWORD
> ```
> 中的`YOUR_EMAIL_SMTP_PASSWORD`不是你的邮箱账户密码，是邮箱SMTP服务提供的**授权码**

### 3. 启动项目

```bash
python cyber-agent/run.py
```

启动后会自动打开浏览器，即可开始使用。

## 单元测试

测试使用 pytest，覆盖提醒时间解析、文档处理、知识库检索、提醒管理、Agent 工具流程和邮件发送。大模型、向量数据库、SMTP 和后台调度器均使用 mock；不会调用模型 API、发送真实邮件或修改已有知识库。文档解析使用测试临时文件，Agent 流程使用真实 LangGraph 编排和模拟模型输出。

请在项目根目录使用 Conda 的 `agent` 环境安装依赖并运行：

```powershell
conda run -n agent python -m pip install -r requirements.txt
conda run -n agent python -m pytest
```

测试位于根目录的 `tests/`，与源码目录 `cyber-agent/` 平级；依赖文件 `requirements.txt` 也位于根目录。根目录的 `pytest.ini` 配置测试路径和模块导入路径。时间解析测试固定当前时间为 `2026-10-08 10:00:00`，不依赖实际执行日期。

如果 Windows 下 Conda 捕获中文测试输出时出现 GBK 编码错误，可在当前 PowerShell 会话中使用：

```powershell
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"
conda run --no-capture-output -n agent python -m pytest -q --tb=short
```

已知缺陷使用 `xfail(strict=True)` 记录期望行为：下午时间转换、无效时分处理、拒绝过去日期、非法完整日期被降级解析成当天时间、工具异常恢复和来源跨轮累积。这些用例的预期失败不代表功能已修复；修复后会显示 XPASS 并使测试失败，此时应移除相应 xfail 标记。
