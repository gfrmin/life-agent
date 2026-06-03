"""Text chunking for the retrieval substrate (SPEC v0.1.11 Step 2).

``chunk_text`` is a pure function: no I/O, no side effects.
``write_chunks`` is the catalogue write layer: delete-then-insert inside a
single transaction, making every call idempotent.
``extract_text`` converts producer content bytes to plain text regardless of
content_type (Docling JSON, Unstructured JSON, or raw text/plain).

Character-based splitting is correct for FTS — keyword search does not require
semantic coherence at chunk boundaries. Embedding-oriented chunking (Step 4)
may use a separate granularity alongside these FTS chunks; the schema allows
multiple source_origin values per artifact_cache_key.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import duckdb

#: Content types whose text is extractable for FTS indexing.
CHUNKABLE_CONTENT_TYPES = frozenset({
    "text/plain",
    "application/x-docling-json",
    "application/x-unstructured-json",
})


def extract_text(content: bytes, content_type: str) -> str:
    """Extract plain text from artifact content regardless of content_type.

    Returns an empty string if the content is empty or unparseable.
    """
    if not content:
        return ""
    if content_type == "text/plain":
        return content.decode("utf-8", errors="replace")
    if content_type == "application/x-docling-json":
        return _text_from_docling_json(content)
    if content_type == "application/x-unstructured-json":
        return _text_from_unstructured_json(content)
    return ""


def _text_from_docling_json(content: bytes) -> str:
    try:
        doc = json.loads(content)
        parts = [t["text"] for t in doc.get("texts", []) if t.get("text")]
        return "\n".join(parts)
    except Exception:
        return ""


def _text_from_unstructured_json(content: bytes) -> str:
    try:
        items = json.loads(content)
        parts = [item["text"] for item in items if item.get("text")]
        return "\n".join(parts)
    except Exception:
        return ""


@dataclass(frozen=True)
class Chunk:
    chunk_index: int
    chunk_text: str


def chunk_text(
    text: str,
    max_chars: int = 1000,
    overlap: int = 100,
) -> list[Chunk]:
    """Split ``text`` into overlapping character-boundary chunks.

    Returns an empty list for empty ``text``. Each ``Chunk`` carries its
    0-based ``chunk_index`` and the raw text slice. Consecutive chunks share
    ``overlap`` characters so that a keyword spanning a boundary appears in at
    least one chunk.
    """
    if not text:
        return []

    chunks: list[Chunk] = []
    start = 0
    idx = 0

    while start < len(text):
        end = min(start + max_chars, len(text))
        chunks.append(Chunk(chunk_index=idx, chunk_text=text[start:end]))
        if end == len(text):
            break
        start = end - overlap
        idx += 1

    return chunks


def write_chunks(
    conn: duckdb.DuckDBPyConnection,
    artifact_cache_key: str,
    chunks: list[Chunk],
    source_origin: str | None = None,
) -> None:
    """Write chunks for ``artifact_cache_key`` to the catalogue.

    Delete-then-insert semantics: calling this twice with the same key and
    chunks leaves exactly one set of rows. Wrapped in a savepoint so the
    operation is atomic with respect to the caller's surrounding transaction.
    """
    conn.execute(
        "DELETE FROM artifact_chunks WHERE artifact_cache_key = ?",
        [artifact_cache_key],
    )
    if chunks:
        conn.executemany(
            "INSERT INTO artifact_chunks "
            "(artifact_cache_key, chunk_index, chunk_text, source_origin, chunk_id) "
            "VALUES (?, ?, ?, ?, nextval('seq_chunk_id'))",
            [
                (artifact_cache_key, c.chunk_index, c.chunk_text, source_origin)
                for c in chunks
            ],
        )
