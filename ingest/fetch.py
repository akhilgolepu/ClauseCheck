"""Download the regulatory corpus and record it in data/corpus_manifest.json.

Raw files are not committed; this script plus the hashes in the manifest is how
the corpus is reproduced. Re-running verifies existing files against the
manifest instead of re-downloading, and refuses to silently accept a changed
upstream file. Pass --refresh to deliberately take new versions.

    python -m ingest.fetch [--refresh]
"""

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from core.settings import PROJECT_ROOT, get_settings

RAW_DIR = PROJECT_ROOT / "data" / "raw"
ECFR_TITLES_URL = "https://www.ecfr.gov/api/versioner/v1/titles.json"
ECFR_PART_URL = "https://www.ecfr.gov/api/versioner/v1/full/{date}/title-21.xml?part=11"


@dataclass(frozen=True)
class Source:
    doc_id: str
    title: str
    fmt: str
    url: str | None  # None: resolved at fetch time (eCFR is date-versioned)
    version: str | None  # None: the eCFR issue date is the version
    effective_date: str | None


SOURCES = [
    Source(
        doc_id="21CFR11",
        title="21 CFR Part 11: Electronic Records; Electronic Signatures",
        fmt="xml",
        url=None,
        version=None,
        effective_date="1997-08-20",
    ),
    Source(
        doc_id="EUGMP-A11",
        title="EudraLex Volume 4, Annex 11: Computerised Systems",
        fmt="pdf",
        url=(
            "https://health.ec.europa.eu/document/download/"
            "8d305550-dd22-4dad-8463-2ddb4a1345f1_en?filename=annex11_01-2011_en.pdf"
        ),
        version="Revision January 2011",
        effective_date="2011-06-30",
    ),
    Source(
        doc_id="ICH-Q9R1",
        title="ICH Q9(R1): Quality Risk Management",
        fmt="pdf",
        url=(
            "https://database.ich.org/sites/default/files/"
            "ICH_Q9%28R1%29_Guideline_Step4_2023_0126_0.pdf"
        ),
        version="Step 4, 18 January 2023",
        effective_date=None,
    ),
    Source(
        doc_id="ICH-Q10",
        title="ICH Q10: Pharmaceutical Quality System",
        fmt="pdf",
        url="https://database.ich.org/sites/default/files/Q10%20Guideline.pdf",
        version="Step 4, 4 June 2008",
        effective_date=None,
    ),
]


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def compute_corpus_version(documents: list[dict[str, Any]]) -> str:
    """Short hash over (doc_id, sha256) pairs: changes only when content changes."""
    pairs = sorted(f"{d['doc_id']}:{d['sha256']}" for d in documents)
    return sha256("\n".join(pairs).encode())[:12]


def latest_ecfr_issue_date(client: httpx.Client) -> str:
    titles = client.get(ECFR_TITLES_URL).raise_for_status().json()["titles"]
    return next(t["latest_issue_date"] for t in titles if t["number"] == 21)


def load_manifest(path: Path) -> dict[str, Any]:
    if path.is_file():
        return json.loads(path.read_text())
    return {"documents": []}


def fetch(refresh: bool = False) -> dict[str, Any]:
    manifest_path = get_settings().corpus_manifest_path
    previous = {d["doc_id"]: d for d in load_manifest(manifest_path)["documents"]}
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    documents = []

    with httpx.Client(follow_redirects=True, timeout=60) as client:
        for src in SOURCES:
            prev = previous.get(src.doc_id)
            path = RAW_DIR / f"{src.doc_id}.{src.fmt}"

            if prev and path.is_file() and not refresh:
                if sha256(path.read_bytes()) != prev["sha256"]:
                    sys.exit(f"{path} does not match the manifest hash; re-run with --refresh")
                print(f"{src.doc_id}: ok (cached)")
                documents.append(prev)
                continue

            version, url = src.version, src.url
            if url is None:
                # Reuse the recorded eCFR date for reproducibility unless refreshing.
                version = (
                    prev["version"] if prev and not refresh else latest_ecfr_issue_date(client)
                )
                url = ECFR_PART_URL.format(date=version)

            data = client.get(url).raise_for_status().content
            digest = sha256(data)
            if prev and digest != prev["sha256"] and not refresh:
                sys.exit(f"{src.doc_id}: upstream file changed; re-run with --refresh to accept")
            path.write_bytes(data)
            print(f"{src.doc_id}: downloaded {len(data):,} bytes")
            documents.append(
                {
                    "doc_id": src.doc_id,
                    "title": src.title,
                    "format": src.fmt,
                    "source_url": url,
                    "version": version,
                    "effective_date": src.effective_date,
                    "download_date": datetime.now(UTC).date().isoformat(),
                    "sha256": digest,
                    "file": str(path.relative_to(PROJECT_ROOT)),
                }
            )

    manifest = {"corpus_version": compute_corpus_version(documents), "documents": documents}
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"corpus_version {manifest['corpus_version']} -> {manifest_path}")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--refresh", action="store_true", help="take new upstream versions")
    fetch(refresh=parser.parse_args().refresh)


if __name__ == "__main__":
    main()
