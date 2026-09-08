#!/usr/bin/env python3
"""Download public ClinicalTrials.gov study JSON into data/protocols/.

This script only fetches and caches raw study documents. Parsing, chunking,
embedding, and retrieval happen in the ingest path and the app.

Usage:
    python scripts/fetch_protocols.py
    python scripts/fetch_protocols.py NCT04516746 NCT04368728
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import httpx

DEFAULT_NCT_IDS = [
    "NCT04516746",
    "NCT04368728",
    "NCT04470427",
]

# ClinicalTrials.gov API v2 study endpoint
CTG_STUDY_URL = "https://clinicaltrials.gov/api/v2/studies/{nct_id}"

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "protocols"


def fetch_study(nct_id: str, client: httpx.Client) -> dict:
    """Fetch a single study document from ClinicalTrials.gov v2 API."""
    url = CTG_STUDY_URL.format(nct_id=nct_id.upper())
    response = client.get(url)
    response.raise_for_status()
    return response.json()


def save_study(nct_id: str, payload: dict, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{nct_id.upper()}.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download public ClinicalTrials.gov study JSON files.",
    )
    parser.add_argument(
        "nct_ids",
        nargs="*",
        default=DEFAULT_NCT_IDS,
        help=f"NCT IDs to download (default: {' '.join(DEFAULT_NCT_IDS)})",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Directory for cached JSON (default: {DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="HTTP timeout in seconds (default: 30)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    nct_ids = [nct.strip().upper() for nct in args.nct_ids if nct.strip()]
    if not nct_ids:
        print("ERROR: No NCT IDs provided.", file=sys.stderr)
        return 1

    print(f"Downloading {len(nct_ids)} study/studies into {args.output_dir} ...")
    successes = 0
    failures = 0

    with httpx.Client(timeout=args.timeout, follow_redirects=True) as client:
        for nct_id in nct_ids:
            try:
                payload = fetch_study(nct_id, client)
                path = save_study(nct_id, payload, args.output_dir)
                print(f"  OK   {nct_id} -> {path}")
                successes += 1
            except httpx.HTTPStatusError as exc:
                print(
                    f"  FAIL {nct_id}: HTTP {exc.response.status_code} "
                    f"({exc.response.reason_phrase})",
                    file=sys.stderr,
                )
                failures += 1
            except httpx.HTTPError as exc:
                print(f"  FAIL {nct_id}: {exc}", file=sys.stderr)
                failures += 1
            except OSError as exc:
                print(f"  FAIL {nct_id}: could not write file ({exc})", file=sys.stderr)
                failures += 1

    print(f"Done. {successes} succeeded, {failures} failed.")
    return 0 if failures == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
