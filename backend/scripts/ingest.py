"""Parse staged transcript files, chunk them, embed the chunks, and upsert
into transcript_chunks. Idempotent per source file: re-running deletes and
re-inserts that episode's chunks rather than duplicating them.

Usage:
    python -m scripts.ingest              # ingest everything in data/staged/
    python -m scripts.ingest --file X.md  # ingest a single staged file
"""
import argparse
import asyncio
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import structlog  # noqa: E402
from sqlalchemy import delete, insert  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.database import db_session_ctx  # noqa: E402
from app.models.db_models import TranscriptChunk  # noqa: E402
from app.rag.embeddings import embed_batch  # noqa: E402

logger = structlog.get_logger(__name__)

STAGED_DIR = Path(__file__).resolve().parents[1] / "data" / "staged"

FRONT_MATTER_RE = re.compile(r"^---\n(.*?)\n---\n(.*)$", re.DOTALL)


def parse_front_matter(raw: str) -> tuple[dict, str]:
    match = FRONT_MATTER_RE.match(raw)
    if not match:
        return {}, raw
    meta_block, body = match.groups()
    meta = {}
    for line in meta_block.splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            meta[key.strip()] = value.strip()
    return meta, body.strip()


def chunk_text(body: str, target_tokens: int, overlap_tokens: int) -> list[str]:
    """Recursive-ish character splitter approximating token counts at ~4
    chars/token, splitting on paragraph boundaries first, falling back to
    sentence boundaries, so chunks don't cut mid-idea.
    """
    target_chars = target_tokens * 4
    overlap_chars = overlap_tokens * 4

    paragraphs = [p.strip() for p in body.split("\n\n") if p.strip()]
    chunks: list[str] = []
    current = ""

    for para in paragraphs:
        if len(current) + len(para) + 2 <= target_chars:
            current = f"{current}\n\n{para}".strip()
        else:
            if current:
                chunks.append(current)
            if len(para) > target_chars:
                # paragraph itself is too long; split on sentences
                sentences = re.split(r"(?<=[.!?])\s+", para)
                buf = ""
                for sent in sentences:
                    if len(buf) + len(sent) + 1 <= target_chars:
                        buf = f"{buf} {sent}".strip()
                    else:
                        if buf:
                            chunks.append(buf)
                        buf = sent
                if buf:
                    current = buf
                else:
                    current = ""
            else:
                current = para

    if current:
        chunks.append(current)

    # apply overlap by prepending the tail of the previous chunk
    overlapped = []
    for i, c in enumerate(chunks):
        if i == 0 or overlap_chars <= 0:
            overlapped.append(c)
        else:
            tail = chunks[i - 1][-overlap_chars:]
            overlapped.append(f"{tail}\n...\n{c}")
    return overlapped


def extract_timestamp_ref(chunk: str) -> str | None:
    match = re.search(r"\[(\d{1,2}:\d{2}(?::\d{2})?)\]", chunk)
    return match.group(1) if match else None


async def ingest_file(path: Path) -> int:
    settings = get_settings()
    raw = path.read_text(encoding="utf-8")
    meta, body = parse_front_matter(raw)

    episode_title = meta.get("title", path.stem)
    guest_name = meta.get("guest")
    source_url = meta.get("source_url")

    chunks = chunk_text(body, settings.chunk_target_tokens, settings.chunk_overlap_tokens)
    if not chunks:
        logger.warning("ingest.no_chunks", file=str(path))
        return 0

    vectors = await embed_batch(chunks)

    async with db_session_ctx() as session:
        await session.execute(
            delete(TranscriptChunk).where(TranscriptChunk.episode_title == episode_title)
        )
        rows = [
            {
                "episode_title": episode_title,
                "guest_name": guest_name,
                "source_url": source_url,
                "timestamp_ref": extract_timestamp_ref(chunk),
                "chunk_text": chunk,
                "chunk_index": i,
                "embedding": vector,
            }
            for i, (chunk, vector) in enumerate(zip(chunks, vectors))
        ]
        await session.execute(insert(TranscriptChunk), rows)
        await session.commit()

    logger.info("ingest.file_complete", file=str(path), chunks=len(chunks), episode=episode_title)
    return len(chunks)


async def main_async(single_file: str | None) -> None:
    if not STAGED_DIR.exists():
        print(f"No staged directory at {STAGED_DIR}. Run scripts/download_transcripts.py first.")
        return

    files = [STAGED_DIR / single_file] if single_file else sorted(STAGED_DIR.glob("*.md"))
    if not files:
        print(f"No transcript files found in {STAGED_DIR}.")
        return

    total = 0
    for f in files:
        n = await ingest_file(f)
        total += n
        print(f"  ingested {f.name}: {n} chunks")

    print(f"Done. {total} chunks ingested across {len(files)} file(s).")


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest staged transcripts into pgvector.")
    parser.add_argument("--file", help="Ingest a single file from data/staged/", default=None)
    args = parser.parse_args()
    asyncio.run(main_async(args.file))


if __name__ == "__main__":
    main()
