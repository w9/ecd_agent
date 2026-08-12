"""Persist protocol chunks in SQLite.

``protocol_chunks`` is a regular content table with a stable INTEGER primary
key. A later FTS5 virtual table can use ``content='protocol_chunks'`` and
``content_rowid='id'`` without mixing search index and source rows.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from app.rag.chunk import Chunk

SCHEMA_SQL = """
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
"""

_INSERT_SQL = """
INSERT INTO protocol_chunks (
    nct_id, section, chunk_index, brief_title, text, start_char, end_char
) VALUES (?, ?, ?, ?, ?, ?, ?)
"""

_SELECT_SQL = """
SELECT id, nct_id, section, chunk_index, brief_title, text, start_char, end_char
FROM protocol_chunks
ORDER BY id
"""


def connect(db_path: Path | str) -> sqlite3.Connection:
    """Open (or create) the protocols database."""
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    """Create the content table if it does not exist."""
    conn.executescript(SCHEMA_SQL)


def replace_chunks(conn: sqlite3.Connection, chunks: list[Chunk]) -> list[Chunk]:
    """Replace all content rows and return them with assigned ids.

    Does not create or update FTS5. Rebuild the search index separately after
    this call once that virtual table exists.
    """
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
    conn.commit()
    return load_chunks(conn)


def load_chunks(conn: sqlite3.Connection) -> list[Chunk]:
    """Load content rows in primary-key order."""
    return [_row_to_chunk(row) for row in conn.execute(_SELECT_SQL)]


def save_chunks(db_path: Path | str, chunks: list[Chunk]) -> list[Chunk]:
    """Write chunks to ``db_path``, replacing any previous content rows."""
    conn = connect(db_path)
    try:
        return replace_chunks(conn, chunks)
    finally:
        conn.close()


def load_chunks_from_path(db_path: Path | str) -> list[Chunk]:
    """Load content rows from ``db_path``."""
    conn = connect(db_path)
    try:
        init_schema(conn)
        return load_chunks(conn)
    finally:
        conn.close()


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
