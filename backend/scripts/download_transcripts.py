"""Stage transcript files for ingestion.

Two modes:
  1. Online: if TRANSCRIPT_SOURCE_URL is set, fetch an index of transcript
     files from that source (expects a repo/API that lists .md/.txt files,
     one per episode, front-matter formatted the same way as the sample
     corpus in backend/data/sample_transcripts/) and download them into
     backend/data/staged/.
  2. Offline/demo (default): copy the bundled sample corpus into
     backend/data/staged/ so `ingest.py` always has something to index
     without requiring network access or a licensing agreement to be in
     place first.

This script is intentionally the *only* place that talks to an external
transcript source, so swapping data sources later means editing one file.
"""
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings  # noqa: E402

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
SAMPLE_DIR = DATA_DIR / "sample_transcripts"
STAGED_DIR = DATA_DIR / "staged"


def stage_offline() -> int:
    STAGED_DIR.mkdir(parents=True, exist_ok=True)
    count = 0
    for f in SAMPLE_DIR.glob("*.md"):
        shutil.copy(f, STAGED_DIR / f.name)
        count += 1
    return count


def stage_online(source_url: str) -> int:
    """Placeholder for a real fetch against a transcript repository/API.

    Kept intentionally simple: point this at a GitHub repo's contents API,
    a public S3 bucket listing, or an internal CMS export, and write each
    fetched file into STAGED_DIR with the same front-matter shape used by
    the sample corpus. Not exercised in this environment (no external
    network access to arbitrary transcript sources), but wired up so a
    client engineer can drop in a real integration without touching
    ingest.py.
    """
    import httpx

    STAGED_DIR.mkdir(parents=True, exist_ok=True)
    resp = httpx.get(source_url, timeout=30.0)
    resp.raise_for_status()
    # Expecting a JSON array of {"filename": ..., "content": ...} objects.
    items = resp.json()
    count = 0
    for item in items:
        out_path = STAGED_DIR / item["filename"]
        out_path.write_text(item["content"], encoding="utf-8")
        count += 1
    return count


def main() -> None:
    settings = get_settings()
    if settings.transcript_source_url:
        print(f"Fetching transcripts from {settings.transcript_source_url} ...")
        n = stage_online(settings.transcript_source_url)
    else:
        print("TRANSCRIPT_SOURCE_URL not set — staging the bundled sample corpus for demo purposes.")
        n = stage_offline()
    print(f"Staged {n} transcript file(s) into {STAGED_DIR}")


if __name__ == "__main__":
    main()
