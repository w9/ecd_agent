"""Persist protocol chunks and raw CT.gov JSON in SQLite.

``protocol_chunks`` is the content table (stable INTEGER primary key ``id``).
``protocol_chunks_fts`` is an external-content FTS5 virtual table that uses
``content='protocol_chunks'`` and ``content_rowid='id'``. Triggers keep the
index in sync; a rebuild after bulk replace is the safety net.

``protocol_documents`` stores one raw ClinicalTrials.gov JSON document per NCT
so tools can ``json_extract`` nested fields without re-reading the cache files.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.rag.chunk import Chunk

CONTENT_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS protocol_chunks (
    id INTEGER PRIMARY KEY,
    nct_id TEXT NOT NULL,
    section TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    brief_title TEXT NOT NULL DEFAULT '',
    text TEXT NOT NULL,
    start_char INTEGER NOT NULL,
    end_char INTEGER NOT NULL,
    UNIQUE (nct_id, section, chunk_index)
);

CREATE INDEX IF NOT EXISTS idx_protocol_chunks_nct_id
    ON protocol_chunks (nct_id);

CREATE INDEX IF NOT EXISTS idx_protocol_chunks_section
    ON protocol_chunks (section);

CREATE TABLE IF NOT EXISTS protocol_documents (
    nct_id TEXT PRIMARY KEY,
    brief_title TEXT NOT NULL DEFAULT '',
    document JSON NOT NULL
);
"""

FTS_TABLE = "protocol_chunks_fts"

FTS_CREATE_SQL = f"""
CREATE VIRTUAL TABLE IF NOT EXISTS {FTS_TABLE} USING fts5(
    text,
    brief_title,
    section,
    nct_id,
    content='protocol_chunks',
    content_rowid='id',
    tokenize='porter unicode61'
);
"""

FTS_TRIGGER_SQL = f"""
DROP TRIGGER IF EXISTS protocol_chunks_ai;
DROP TRIGGER IF EXISTS protocol_chunks_ad;
DROP TRIGGER IF EXISTS protocol_chunks_au;

CREATE TRIGGER protocol_chunks_ai AFTER INSERT ON protocol_chunks BEGIN
    INSERT INTO {FTS_TABLE}(rowid, text, brief_title, section, nct_id)
    VALUES (new.id, new.text, new.brief_title, new.section, new.nct_id);
END;

CREATE TRIGGER protocol_chunks_ad AFTER DELETE ON protocol_chunks BEGIN
    INSERT INTO {FTS_TABLE}({FTS_TABLE}, rowid, text, brief_title, section, nct_id)
    VALUES ('delete', old.id, old.text, old.brief_title, old.section, old.nct_id);
END;

CREATE TRIGGER protocol_chunks_au AFTER UPDATE ON protocol_chunks BEGIN
    INSERT INTO {FTS_TABLE}({FTS_TABLE}, rowid, text, brief_title, section, nct_id)
    VALUES ('delete', old.id, old.text, old.brief_title, old.section, old.nct_id);
    INSERT INTO {FTS_TABLE}(rowid, text, brief_title, section, nct_id)
    VALUES (new.id, new.text, new.brief_title, new.section, new.nct_id);
END;
"""

@dataclass(frozen=True)
class ProtocolDocument:
    """One cached CT.gov study document stored as JSON."""

    nct_id: str
    brief_title: str
    document: dict[str, Any]


_INSERT_SQL = """
INSERT INTO protocol_chunks (
    nct_id, section, chunk_index, brief_title, text, start_char, end_char
) VALUES (?, ?, ?, ?, ?, ?, ?)
"""

_INSERT_DOCUMENT_SQL = """
INSERT INTO protocol_documents (nct_id, brief_title, document)
VALUES (?, ?, json(?))
"""

_SELECT_DOCUMENTS_SQL = """
SELECT nct_id, brief_title, document
FROM protocol_documents
ORDER BY nct_id
"""

_EXTRACT_SQL = """
SELECT nct_id, json_extract(document, ?) AS value, json_type(document, ?) AS value_type
FROM protocol_documents
ORDER BY nct_id
"""

_EXTRACT_ONE_SQL = """
SELECT nct_id, json_extract(document, ?) AS value, json_type(document, ?) AS value_type
FROM protocol_documents
WHERE nct_id = ? COLLATE NOCASE
"""

_SELECT_SQL = """
SELECT id, nct_id, section, chunk_index, brief_title, text, start_char, end_char
FROM protocol_chunks
ORDER BY id
"""

_SEARCH_SQL = f"""
SELECT
    c.id, c.nct_id, c.section, c.chunk_index, c.brief_title,
    c.text, c.start_char, c.end_char,
    bm25({FTS_TABLE}) AS rank
FROM {FTS_TABLE}
JOIN protocol_chunks AS c ON c.id = {FTS_TABLE}.rowid
WHERE {FTS_TABLE} MATCH ?
ORDER BY rank
LIMIT ?
"""


def connect(db_path: Path | str) -> sqlite3.Connection:
    """Open (or create) the protocols database."""
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    """Create the content table, FTS5 index, and sync triggers if needed."""
    conn.executescript(CONTENT_SCHEMA_SQL)
    existed = _fts_exists(conn)
    conn.executescript(FTS_CREATE_SQL)
    conn.executescript(FTS_TRIGGER_SQL)
    if not existed:
        rebuild_fts(conn)
    conn.commit()


def rebuild_fts(conn: sqlite3.Connection) -> None:
    """Rebuild the FTS5 index from ``protocol_chunks``."""
    conn.execute(f"INSERT INTO {FTS_TABLE}({FTS_TABLE}) VALUES ('rebuild')")


def replace_chunks(conn: sqlite3.Connection, chunks: list[Chunk]) -> list[Chunk]:
    """Replace all content rows, refresh FTS5, and return rows with ids."""
    init_schema(conn)
    conn.execute("DELETE FROM protocol_chunks")
    conn.executemany(
        _INSERT_SQL,
        [
            (
                chunk.nct_id,
                chunk.section,
                chunk.chunk_index,
                chunk.brief_title,
                chunk.text,
                chunk.start_char,
                chunk.end_char,
            )
            for chunk in chunks
        ],
    )
    rebuild_fts(conn)
    conn.commit()
    return load_chunks(conn)


def load_chunks(conn: sqlite3.Connection) -> list[Chunk]:
    """Load content rows in primary-key order."""
    return [_row_to_chunk(row) for row in conn.execute(_SELECT_SQL)]


def search_chunks(
    conn: sqlite3.Connection,
    query: str,
    *,
    limit: int = 8,
) -> list[tuple[Chunk, float]]:
    """Return BM25-ranked chunks for an FTS5 MATCH query."""
    stripped = query.strip()
    if not stripped or limit <= 0:
        return []
    rows = conn.execute(_SEARCH_SQL, (stripped, limit)).fetchall()
    return [(_row_to_chunk(row), float(row["rank"])) for row in rows]


def save_chunks(db_path: Path | str, chunks: list[Chunk]) -> list[Chunk]:
    """Write chunks to ``db_path``, replacing previous content and FTS rows."""
    conn = connect(db_path)
    try:
        return replace_chunks(conn, chunks)
    finally:
        conn.close()


def replace_documents(
    conn: sqlite3.Connection, documents: list[ProtocolDocument]
) -> list[ProtocolDocument]:
    """Replace all stored CT.gov JSON documents."""
    init_schema(conn)
    conn.execute("DELETE FROM protocol_documents")
    conn.executemany(
        _INSERT_DOCUMENT_SQL,
        [
            (doc.nct_id, doc.brief_title, json.dumps(doc.document, ensure_ascii=False))
            for doc in documents
        ],
    )
    conn.commit()
    return load_documents(conn)


def load_documents(conn: sqlite3.Connection) -> list[ProtocolDocument]:
    """Load stored study documents in NCT-ID order."""
    return [_row_to_document(row) for row in conn.execute(_SELECT_DOCUMENTS_SQL)]


def save_documents(
    db_path: Path | str, documents: list[ProtocolDocument]
) -> list[ProtocolDocument]:
    """Write JSON documents to ``db_path``, replacing previous rows."""
    conn = connect(db_path)
    try:
        return replace_documents(conn, documents)
    finally:
        conn.close()


def extract_json_field(
    db_path: Path | str,
    path: str,
    *,
    nct_id: str | None = None,
) -> list[dict[str, Any]]:
    """Return ``json_extract`` results for one path, optionally scoped to an NCT."""
    conn = connect(db_path)
    try:
        init_schema(conn)
        if nct_id:
            rows = conn.execute(_EXTRACT_ONE_SQL, (path, path, nct_id)).fetchall()
        else:
            rows = conn.execute(_EXTRACT_SQL, (path, path)).fetchall()
    except sqlite3.Error:
        return []
    finally:
        conn.close()
    return [_extract_payload(row, path) for row in rows]


def load_chunks_from_path(db_path: Path | str) -> list[Chunk]:
    """Load content rows from ``db_path``."""
    conn = connect(db_path)
    try:
        init_schema(conn)
        return load_chunks(conn)
    finally:
        conn.close()


def search_chunks_from_path(
    db_path: Path | str,
    query: str,
    *,
    limit: int = 8,
) -> list[tuple[Chunk, float]]:
    """Open ``db_path`` and run an FTS5 search."""
    conn = connect(db_path)
    try:
        init_schema(conn)
        return search_chunks(conn, query, limit=limit)
    finally:
        conn.close()


def _fts_exists(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (FTS_TABLE,),
    ).fetchone()
    return row is not None


def _row_to_document(row: sqlite3.Row) -> ProtocolDocument:
    raw = row["document"]
    document = json.loads(raw) if isinstance(raw, str) else raw
    if not isinstance(document, dict):
        document = {}
    return ProtocolDocument(
        nct_id=row["nct_id"],
        brief_title=row["brief_title"],
        document=document,
    )


def _extract_payload(row: sqlite3.Row, path: str) -> dict[str, Any]:
    value_type = row["value_type"]
    found = value_type is not None
    return {
        "nct_id": row["nct_id"],
        "path": path,
        "found": found,
        "value": _decode_json_extract(row["value"], value_type) if found else None,
        "json_type": value_type,
    }


def _decode_json_extract(value: Any, value_type: str | None) -> Any:
    if value_type in {"object", "array"} and isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    if value_type == "true":
        return True
    if value_type == "false":
        return False
    if value_type == "null":
        return None
    return value


def _row_to_chunk(row: sqlite3.Row) -> Chunk:
    return Chunk(
        id=int(row["id"]),
        nct_id=row["nct_id"],
        section=row["section"],
        chunk_index=int(row["chunk_index"]),
        brief_title=row["brief_title"],
        text=row["text"],
        start_char=int(row["start_char"]),
        end_char=int(row["end_char"]),
    )
