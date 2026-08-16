import os
import shutil
from pathlib import Path
from langchain_chroma import Chroma
from models.llm import load_config, get_embeddings


def get_vector_store():
    """获取或创建向量数据库"""
    config = load_config()
    persist_dir = config.get("kb", {}).get("persist_directory", "./data/vector_store")
    embeddings = get_embeddings(config)

    return Chroma(
        persist_directory=persist_dir,
        embedding_function=embeddings,
    )


def get_vector_store_for_ingest():
    """获取用于入库的向量数据库（允许添加文档）"""
    return get_vector_store()


def clear_vector_store():
    """清空向量数据库"""
    config = load_config()
    persist_dir = config.get("kb", {}).get("persist_directory", "../data/vector_store")
    # if os.path.exists(persist_dir):
    #     shutil.rmtree(persist_dir)
    # return "知识库已清空"
    # 通过 Chroma API 删除所有集合，避免文件句柄冲突
    try:
        vs = get_vector_store()
        # 获取底层 Chroma 客户端，删除所有集合
        client = vs._client
        for collection in client.list_collections():
            client.delete_collection(collection.name)
        return "知识库已清空"
    except Exception as e:
        # 如果 API 方式失败，回退到删除目录（先尝试释放句柄）
        if os.path.exists(persist_dir):
            shutil.rmtree(persist_dir, ignore_errors=True)
        return f"知识库已清空（部分文件可能残留: {e}）"
