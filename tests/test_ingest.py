from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from langchain_core.documents import Document
from pypdf import PdfWriter

from kb import ingest


def upload(name, content):
    file = BytesIO(content)
    file.name = name
    return file


@pytest.mark.parametrize("extension", ["txt", "md", "MD"])
def test_load_text(tmp_path, extension):
    path = tmp_path / f"sample.{extension}"
    path.write_text("中文文档\n第二行", encoding="utf-8")
    docs = ingest.load_document(str(path), path.name)
    assert len(docs) == 1
    assert docs[0].page_content == "中文文档\n第二行"
    assert docs[0].metadata["source"] == str(path)


def test_load_pdf(tmp_path):
    # A locally generated blank PDF exercises the real PDF loader offline.
    path = tmp_path / "sample.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    writer.write(str(path))
    docs = ingest.load_document(str(path), path.name)
    assert len(docs) == 1
    assert docs[0].metadata["page"] == 0
    assert docs[0].page_content == ""
    assert docs[0].metadata["source"] == str(path)


def test_pdf_text_and_page_metadata(monkeypatch):
    loader = MagicMock()
    loader.load.return_value = [Document(page_content="PDF正文", metadata={"page": 2})]
    factory = MagicMock(return_value=loader)
    monkeypatch.setattr(ingest, "PyPDFLoader", factory)
    docs = ingest.load_document("placeholder.pdf", "sample.PDF")
    factory.assert_called_once_with("placeholder.pdf")
    loader.load.assert_called_once_with()
    assert docs[0].page_content == "PDF正文" and docs[0].metadata["page"] == 2


def test_unsupported_type():
    with pytest.raises(ValueError, match="不支持"):
        ingest.load_document("sample.docx", "sample.docx")


@pytest.fixture
def ingest_setup(monkeypatch, tmp_path):
    store = MagicMock()
    monkeypatch.setattr(ingest, "load_config", lambda: {"kb": {"chunk_size": 10, "chunk_overlap": 2}})
    monkeypatch.setattr(ingest, "get_vector_store_for_ingest", lambda: store)
    original = ingest.process_uploaded_file
    paths = []

    def save(file):
        path = original(file)
        paths.append(Path(path))
        return path

    monkeypatch.setattr(ingest.tempfile, "tempdir", str(tmp_path))
    monkeypatch.setattr(ingest, "process_uploaded_file", save)
    return store, paths


def test_split_sources_and_cleanup(ingest_setup):
    store, paths = ingest_setup
    result = ingest.process_documents([
        upload("a.txt", b"abcdefghijklmnopqrstuvwxyz"),
        upload("b.md", "第二个文件".encode("utf-8")),
    ])
    chunks = store.add_documents.call_args.args[0]
    store.add_documents.assert_called_once()
    assert "成功处理 2 个文件" in result
    assert len(chunks) > 2 and all(len(doc.page_content) <= 10 for doc in chunks)
    assert {doc.metadata["source"] for doc in chunks} == {"a.txt", "b.md"}
    a_chunks = [doc.page_content for doc in chunks if doc.metadata["source"] == "a.txt"]
    assert a_chunks[0][-2:] == a_chunks[1][:2]
    reconstructed = a_chunks[0] + "".join(chunk[2:] for chunk in a_chunks[1:])
    assert reconstructed == "abcdefghijklmnopqrstuvwxyz"
    assert [doc.page_content for doc in chunks if doc.metadata["source"] == "b.md"] == ["第二个文件"]
    assert all(doc.page_content for doc in chunks)
    assert f"分割为 {len(chunks)} 个文本块" in result
    assert [path.suffix for path in paths] == [".txt", ".md"]
    assert len(paths) == 2 and all(not path.exists() for path in paths)


def test_empty_documents(ingest_setup):
    store, paths = ingest_setup
    assert "没有读取到" in ingest.process_documents([])
    store.add_documents.assert_not_called()
    assert paths == []


@pytest.mark.parametrize("failure", ["parse", "store"])
def test_cleanup_after_error(ingest_setup, monkeypatch, failure):
    store, paths = ingest_setup
    if failure == "parse":
        monkeypatch.setattr(ingest, "load_document", MagicMock(side_effect=RuntimeError("failure")))
    else:
        store.add_documents.side_effect = RuntimeError("failure")
    with pytest.raises(RuntimeError, match="failure"):
        ingest.process_documents([upload("a.txt", b"content")])
    assert paths and all(not path.exists() for path in paths)
    if failure == "parse":
        store.add_documents.assert_not_called()
    else:
        store.add_documents.assert_called_once()


def test_uploaded_bytes_and_extension_are_preserved(ingest_setup):
    _, paths = ingest_setup
    content = "中文\n完整内容".encode("utf-8")
    path = Path(ingest.process_uploaded_file(upload("source.PDF", content)))
    try:
        assert path.exists()
        assert path.suffix == ".pdf"
        assert path.read_bytes() == content
        assert paths == [path]
    finally:
        path.unlink()
