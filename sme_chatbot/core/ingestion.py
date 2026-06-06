"""Knowledge ingestion pipeline.

Document → text → semantic chunks → embeddings → upsert into the tenant's
Milvus collection (named `kb_<tenant_short>`).

Uses the **same embedder** that `ofofo_engine.retrieval.RetrievalService`
uses, so retrieval at query time stays compatible with the pre-existing
2 M-vector shared corpus.

Supported source formats:
    .pdf  via pypdf
    .docx via python-docx
    .txt  / .md  read directly
    .csv  / .xlsx via pandas — each row becomes one chunk
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------


@dataclass
class IngestionResult:
    document_id: str
    chunks_created: int
    chars_processed: int
    duration_s: float
    errors: list[str]


@dataclass
class Chunk:
    text: str
    section: str = ""
    metadata: dict[str, Any] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.metadata is None:
            self.metadata = {}


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------


def extract_text(path: Path, mime_type: str | None = None) -> list[Chunk]:
    """Dispatch on file extension or mime type."""
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return _extract_pdf(path)
    if suffix == ".docx":
        return _extract_docx(path)
    if suffix in (".txt", ".md"):
        return _extract_text_file(path)
    if suffix == ".csv":
        return _extract_csv(path)
    if suffix in (".xlsx", ".xls"):
        return _extract_xlsx(path)
    raise ValueError(f"unsupported file type: {suffix}")


def _extract_pdf(path: Path) -> list[Chunk]:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    chunks: list[Chunk] = []
    for i, page in enumerate(reader.pages):
        try:
            txt = (page.extract_text() or "").strip()
        except Exception:  # noqa: BLE001
            txt = ""
        if txt:
            chunks.append(Chunk(text=txt, section=f"page_{i + 1}"))
    return chunks


def _extract_docx(path: Path) -> list[Chunk]:
    from docx import Document

    doc = Document(str(path))
    current_section = "intro"
    chunks: list[Chunk] = []
    buffer: list[str] = []

    def flush() -> None:
        nonlocal buffer
        text = "\n".join(buffer).strip()
        if text:
            chunks.append(Chunk(text=text, section=current_section))
        buffer = []

    for para in doc.paragraphs:
        style = (para.style.name or "").lower() if para.style else ""
        if "heading" in style:
            flush()
            current_section = para.text.strip() or current_section
            continue
        if para.text.strip():
            buffer.append(para.text.strip())
    flush()
    return chunks


def _extract_text_file(path: Path) -> list[Chunk]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    return _semantic_chunk(text, section="body")


def _extract_csv(path: Path) -> list[Chunk]:
    import pandas as pd

    df = pd.read_csv(path)
    return _from_dataframe(df, source=path.name)


def _extract_xlsx(path: Path) -> list[Chunk]:
    import pandas as pd

    sheets = pd.read_excel(path, sheet_name=None)
    out: list[Chunk] = []
    for sheet_name, df in sheets.items():
        out.extend(_from_dataframe(df, source=f"{path.name}:{sheet_name}"))
    return out


def _from_dataframe(df, source: str) -> list[Chunk]:
    """One row → one chunk, with column names baked into the text."""
    chunks: list[Chunk] = []
    for idx, row in df.iterrows():
        parts = []
        for col, val in row.items():
            if val is None:
                continue
            sval = str(val).strip()
            if sval and sval.lower() != "nan":
                parts.append(f"{col}: {sval}")
        if parts:
            chunks.append(
                Chunk(
                    text=" | ".join(parts),
                    section=f"row_{idx}",
                    metadata={"source": source},
                )
            )
    return chunks


# ---------------------------------------------------------------------------
# Semantic chunking
# ---------------------------------------------------------------------------


def _semantic_chunk(
    text: str,
    *,
    target_tokens: int = 512,
    overlap_tokens: int = 50,
    section: str = "",
) -> list[Chunk]:
    """Heuristic chunker by paragraph and approximate token count.

    1 token ≈ 0.75 words. We use word count as a cheap proxy.
    """
    target_words = int(target_tokens / 0.75)
    overlap_words = int(overlap_tokens / 0.75)
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

    chunks: list[Chunk] = []
    buf: list[str] = []
    wc = 0
    for para in paragraphs:
        n = len(para.split())
        if wc + n > target_words and buf:
            chunks.append(Chunk(text="\n\n".join(buf).strip(), section=section))
            # carry overlap from the tail of the last chunk
            tail = " ".join(" ".join(buf).split()[-overlap_words:])
            buf = [tail] if tail else []
            wc = len(tail.split()) if tail else 0
        buf.append(para)
        wc += n
    if buf:
        chunks.append(Chunk(text="\n\n".join(buf).strip(), section=section))
    return chunks


# ---------------------------------------------------------------------------
# Ingest into Milvus via ofofo_engine.RetrievalService's underlying client
# ---------------------------------------------------------------------------


def ingest(
    *,
    retrieval_service,            # ofofo_engine.retrieval.RetrievalService
    tenant_id: str,
    document_id: str,
    document_type: str,
    source_path: Path,
    boost: float | None = None,
) -> IngestionResult:
    """Run the full pipeline for one uploaded document."""
    import time

    start = time.perf_counter()
    errors: list[str] = []

    try:
        chunks = extract_text(source_path)
    except Exception as exc:  # noqa: BLE001
        return IngestionResult(
            document_id=document_id,
            chunks_created=0,
            chars_processed=0,
            duration_s=time.perf_counter() - start,
            errors=[f"extract_failed: {exc}"],
        )

    # Re-chunk anything that's still too large (mainly PDF pages).
    refined: list[Chunk] = []
    for c in chunks:
        if len(c.text.split()) > 700:
            refined.extend(_semantic_chunk(c.text, section=c.section))
        else:
            refined.append(c)

    if not refined:
        return IngestionResult(
            document_id=document_id, chunks_created=0,
            chars_processed=0,
            duration_s=time.perf_counter() - start,
            errors=["no extractable text"],
        )

    coll = f"kb_{tenant_id.replace('-', '')[:12]}"
    effective_boost = boost if boost is not None else (1.5 if document_type == "manual_faq" else 1.0)

    model = retrieval_service.model
    client = retrieval_service.client

    # Ensure the collection exists. We piggy-back on the shared engine schema
    # — see ofofo_engine.milestone_two/src/vectordb/setup_collections.py for
    # the canonical definition.
    if coll not in client.list_collections():
        _ensure_tenant_collection(client, coll, dim=model.get_sentence_embedding_dimension())

    texts = [c.text[:2000] for c in refined]
    embeddings = model.encode(
        texts,
        batch_size=32,
        normalize_embeddings=True,
        show_progress_bar=False,
    )

    rows = [
        {
            "embedding": emb.tolist(),
            "text": c.text[:8000],
            "source": str(source_path.name),
            "section": c.section[:120],
            "author": "tenant",
            "date": "",
            "metadata_json": _safe_json(
                {**c.metadata,
                 "document_id": document_id,
                 "document_type": document_type,
                 "boost": effective_boost,}
            ),
        }
        for c, emb in zip(refined, embeddings, strict=False)
    ]

    try:
        client.insert(collection_name=coll, data=rows)
    except Exception as exc:  # noqa: BLE001
        errors.append(f"insert_failed: {exc}")

    return IngestionResult(
        document_id=document_id,
        chunks_created=len(refined),
        chars_processed=sum(len(c.text) for c in refined),
        duration_s=time.perf_counter() - start,
        errors=errors,
    )


def _safe_json(d: dict[str, Any]) -> str:
    import json
    try:
        return json.dumps(d, default=str)
    except Exception:
        return "{}"


def _ensure_tenant_collection(client, name: str, *, dim: int) -> None:
    """Mirror the parent project's collection schema."""
    from pymilvus import CollectionSchema, DataType, FieldSchema

    fields = [
        FieldSchema("id", DataType.INT64, is_primary=True, auto_id=True),
        FieldSchema("embedding", DataType.FLOAT_VECTOR, dim=dim),
        FieldSchema("text", DataType.VARCHAR, max_length=8192),
        FieldSchema("source", DataType.VARCHAR, max_length=256),
        FieldSchema("section", DataType.VARCHAR, max_length=128),
        FieldSchema("date", DataType.VARCHAR, max_length=64),
        FieldSchema("author", DataType.VARCHAR, max_length=256),
        FieldSchema("metadata_json", DataType.VARCHAR, max_length=4096),
    ]
    schema = CollectionSchema(fields=fields, enable_dynamic_field=True)
    index_params = client.prepare_index_params()
    # AUTOINDEX is supported by both Milvus Lite (local dev) and Zilliz Cloud's
    # serverless tier (production); FLAT is rejected by the latter.
    index_params.add_index(field_name="embedding", index_type="AUTOINDEX", metric_type="COSINE")
    client.create_collection(collection_name=name, schema=schema, index_params=index_params)
    log.info("created tenant collection: %s", name)
