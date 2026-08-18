#!/usr/bin/env python3
"""Parse cached ClinicalTrials.gov JSON, chunk it, and store rows in SQLite.

Usage:
    python scripts/ingest_protocols.py
    python scripts/ingest_protocols.py --protocols-dir data/protocols --db data/protocols.db
"""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

from app.config import get_settings
from app.rag import persist_protocol_dir
from app.rag.chunk import approx_token_count

settings = get_settings()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Parse cached CT.gov JSON, chunk sections, and store them in SQLite.",
    )
    parser.add_argument(
        "--protocols-dir",
        type=Path,
        default=settings.protocols_dir,
        help=f"Directory of cached study JSON (default: {settings.protocols_dir})",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=settings.protocols_db_path,
        help=f"SQLite path for protocol_chunks (default: {settings.protocols_db_path})",
    )
    args = parser.parse_args()

    chunks = persist_protocol_dir(args.protocols_dir, args.db)
    if not chunks:
        print(f"No protocol chunks produced from {args.protocols_dir}")
        return 1

    by_nct = Counter(chunk.nct_id for chunk in chunks)
    by_section = Counter(chunk.section for chunk in chunks)
    print(f"Wrote {len(chunks)} chunks from {len(by_nct)} studies to {args.db}")
    print("  tables: protocol_chunks (content), protocol_chunks_fts (FTS5),")
    print("          protocol_documents (raw CT.gov JSON)")
    print("Per study:")
    for nct_id, count in sorted(by_nct.items()):
        print(f"  {nct_id}: {count} chunks")
    print("Per section:")
    for section, count in sorted(by_section.items()):
        print(f"  {section}: {count} chunks")

    longest = max(chunks, key=lambda chunk: approx_token_count(chunk.text))
    print(
        "Longest chunk: "
        f"{longest.nct_id} {longest.section}[{longest.chunk_index}] "
        f"~{approx_token_count(longest.text)} tokens "
        f"(chars {longest.start_char}:{longest.end_char})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
