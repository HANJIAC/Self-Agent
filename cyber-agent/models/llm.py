import yaml
import os
from pathlib import Path
from langchain_openai import ChatOpenAI
from langchain_openai import OpenAIEmbeddings

CONFIG_PATH = Path(__file__).parent.parent / "config.yaml"


def load_config() -> dict:
    """加载配置文件"""
    if not CONFIG_PATH.exists():
        return _default_config()
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def save_config(config: dict):
    """保存配置文件"""
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.dump(config, f, allow_unicode=True, default_flow_style=False)


def _default_config() -> dict:
    return {
        "llm": {
            "provider": "deepseek",
            "api_key": "",
            "model": "deepseek-chat",
            "base_url": "https://api.deepseek.com",
            "embedding": {"model": "deepseek-embedding", "api_key": "", "base_url": ""},
        },
        "email": {
            "smtp_server": "smtp.qq.com",
            "smtp_port": 587,
            "username": "",
            "password": "",
            "default_recipient": "",
        },
        "kb": {"persist_directory": "./data/vector_store", "chunk_size": 500, "chunk_overlap": 50},
    }


def get_chat_llm(config: dict = None):
    """获取聊天 LLM 实例"""
    if config is None:
        config = load_config()
    llm_cfg = config["llm"]

    return ChatOpenAI(
        model=llm_cfg["model"],
        api_key=llm_cfg["api_key"],
        base_url=llm_cfg["base_url"],
        temperature=0.7,
    )


def get_embeddings(config: dict = None):
    """获取嵌入模型实例"""
    if config is None:
        config = load_config()
    llm_cfg = config["llm"]
    embed_cfg = llm_cfg.get("embedding", {})

    return OpenAIEmbeddings(
        model=embed_cfg.get("model", "deepseek-embedding"),
        api_key=embed_cfg.get("api_key") or llm_cfg["api_key"],
        base_url=embed_cfg.get("base_url") or llm_cfg["base_url"],
        check_embedding_ctx_length=False,
    )
