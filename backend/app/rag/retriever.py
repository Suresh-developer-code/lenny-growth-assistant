"""pgvector-backed similarity retrieval over transcript_chunks."""
from typing import Any

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.rag.embeddings import embed_text

logger = structlog.get_logger(__name__)


class TranscriptRetriever:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.settings = get_settings()

    async def retrieve_relevant_chunks(
        self,
        query: str,
        top_k: int | None = None,
        similarity_threshold: float | None = None,
    ) -> list[dict[str, Any]]:
        top_k = top_k or self.settings.retrieval_top_k
        similarity_threshold = (
            similarity_threshold
            if similarity_threshold is not None
            else self.settings.retrieval_similarity_threshold
        )

        query_vector = await embed_text(query)

        stmt = text(
            """
            SELECT
                episode_title,
                guest_name,
                chunk_text,
                timestamp_ref,
                source_url,
                1 - (embedding <=> CAST(:vector AS vector)) AS similarity_score
            FROM transcript_chunks
            WHERE 1 - (embedding <=> CAST(:vector AS vector)) >= :threshold
            ORDER BY similarity_score DESC
            LIMIT :limit
            """
        )

        result = await self.session.execute(
            stmt,
            {"vector": str(query_vector), "threshold": similarity_threshold, "limit": top_k},
        )
        rows = result.fetchall()

        chunks = [
            {
                "episode": r.episode_title,
                "guest": r.guest_name,
                "text": r.chunk_text,
                "timestamp": r.timestamp_ref,
                "source_url": r.source_url,
                "score": float(r.similarity_score),
            }
            for r in rows
        ]

        logger.info(
            "retrieval.completed",
            query_preview=query[:80],
            result_count=len(chunks),
            threshold=similarity_threshold,
        )
        return chunks

    @staticmethod
    def format_context(chunks: list[dict[str, Any]]) -> str:
        if not chunks:
            return ""
        blocks = []
        for c in chunks:
            header = f"--- Episode: {c['episode']}"
            if c.get("guest"):
                header += f" (Guest: {c['guest']})"
            if c.get("timestamp"):
                header += f" [{c['timestamp']}]"
            header += " ---"
            blocks.append(f"{header}\n{c['text']}")
        return "\n\n".join(blocks)
