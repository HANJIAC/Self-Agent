import os
import tempfile
from pathlib import Path
from typing import List
from langchain_community.document_loaders import (
    TextLoader,
    PyPDFLoader,
)
from langchain_text_splitters import RecursiveCharacterTextSplitter
from kb.vector_store import get_vector_store_for_ingest
from models.llm import load_config


def process_uploaded_file(uploaded_file) -> str:
    """将上传的文件保存到临时目录并返回路径"""
    suffix = Path(uploaded_file.name).suffix.lower()
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(uploaded_file.getvalue())
        return tmp.name


def load_document(file_path: str, file_name: str):
    """根据文件扩展名加载文档"""
    ext = Path(file_name).suffix.lower()

    if ext == ".txt":
        loader = TextLoader(file_path, encoding="utf-8")
    elif ext == ".md":
        loader = TextLoader(file_path, encoding="utf-8")
    elif ext == ".pdf":
        loader = PyPDFLoader(file_path)
    else:
        raise ValueError(f"不支持的文件格式: {ext}")

    return loader.load()


def process_documents(uploaded_files) -> str:
    """处理上传的文档并入库"""
    config = load_config()
    chunk_size = config.get("kb", {}).get("chunk_size", 500)
    chunk_overlap = config.get("kb", {}).get("chunk_overlap", 50)

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", "。", ".", " ", ""],
    )

    all_docs = []
    tmp_files = []

    try:
        for uploaded_file in uploaded_files:
            tmp_path = process_uploaded_file(uploaded_file)
            tmp_files.append(tmp_path)

            docs = load_document(tmp_path, uploaded_file.name)
            for doc in docs:
                doc.metadata["source"] = uploaded_file.name
            all_docs.extend(docs)

        if not all_docs:
            return "没有读取到任何文档内容"

        chunks = text_splitter.split_documents(all_docs)

        vector_store = get_vector_store_for_ingest()
        vector_store.add_documents(chunks)

        return f"✅ 成功处理 {len(uploaded_files)} 个文件，分割为 {len(chunks)} 个文本块并入库"

    finally:
        for tmp_path in tmp_files:
            try:
                os.unlink(tmp_path)
            except:
                pass
