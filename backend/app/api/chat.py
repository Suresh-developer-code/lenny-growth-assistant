import json
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.db_models import Artifact, Message
from app.models.db_models import Session as SessionModel
from app.models.schemas import ChatRequest
from app.providers.base import ProviderUnavailableError
from app.providers.factory import get_provider
from app.rag.retriever import TranscriptRetriever
from app.skills.artifact_generator import (
    HTML_ARTIFACT_SYSTEM_SUFFIX,
    extract_artifact,
    strip_artifact_tags,
)
from app.skills.grounded_qa import build_grounded_prompt, chunks_to_sources
from app.skills.ship30_writer import build_ship30_prompt

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/chat", tags=["Chat"])


def _sse(event_type: str, payload: dict) -> str:
    return f"data: {json.dumps({'type': event_type, **payload})}\n\n"


async def _history_for_session(db: AsyncSession, session_id: UUID) -> list[dict[str, str]]:
    result = await db.execute(
        select(Message).where(Message.session_id == session_id).order_by(Message.created_at)
    )
    rows = result.scalars().all()
    return [{"role": m.role, "content": m.content} for m in rows if m.role in ("user", "assistant")]


@router.post("")
async def stream_chat(req: ChatRequest, db: AsyncSession = Depends(get_db)):
    session = await db.get(SessionModel, req.session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Session {req.session_id} not found")

    # Persist the user's message immediately, before any generation, so it
    # survives even if the provider call fails.
    user_message = Message(session_id=session.id, role="user", content=req.message, mode=req.mode)
    db.add(user_message)
    await db.commit()

    try:
        provider = get_provider(req.provider)
    except ProviderUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    retriever = TranscriptRetriever(db)
    wider_k = 8 if req.mode == "ship30" else None
    chunks = await retriever.retrieve_relevant_chunks(req.message, top_k=wider_k)
    sources = chunks_to_sources(chunks)

    if req.mode == "ship30":
        system_prompt = build_ship30_prompt(req.message, chunks)
    else:
        system_prompt = build_grounded_prompt(chunks)
        if req.mode == "artifact":
            system_prompt += "\n\n" + HTML_ARTIFACT_SYSTEM_SUFFIX

    history = await _history_for_session(db, session.id)

    async def event_generator():
        yield _sse("status", {"content": "Searching the transcript archive..."})
        yield _sse("sources", {"sources": sources})

        collected = ""
        try:
            async for token in provider.generate_response(history, system_prompt):
                collected += token
                yield _sse("token", {"content": token})
        except ProviderUnavailableError as exc:
            logger.warning("chat.provider_error", error=str(exc), provider=provider.name)
            yield _sse("error", {"content": str(exc)})
            yield "data: [DONE]\n\n"
            return

        # Persist the assistant turn (+ any artifact) after streaming completes.
        display_content = strip_artifact_tags(collected) if req.mode == "artifact" else collected
        assistant_message = Message(
            session_id=session.id,
            role="assistant",
            content=display_content,
            sources=sources,
            provider=provider.name,
            mode=req.mode,
        )
        db.add(assistant_message)
        await db.flush()

        parsed = extract_artifact(collected) if req.mode in ("artifact", "ship30") else None
        if req.mode == "ship30" and parsed is None:
            # Ship30 responses are markdown essays even without explicit <artifact> tags.
            from app.skills.artifact_generator import wrap_markdown_artifact

            title_guess = req.message[:60].strip() or "Growth Essay"
            parsed_content = collected
            artifact = Artifact(
                message_id=assistant_message.id,
                artifact_type="markdown",
                title=title_guess,
                content=parsed_content,
            )
            db.add(artifact)
            yield _sse(
                "artifact",
                {"artifact_type": "markdown", "title": title_guess, "content": parsed_content},
            )
        elif parsed is not None:
            artifact = Artifact(
                message_id=assistant_message.id,
                artifact_type=parsed.artifact_type,
                title=parsed.title,
                content=parsed.content,
            )
            db.add(artifact)
            yield _sse(
                "artifact",
                {
                    "artifact_type": parsed.artifact_type,
                    "title": parsed.title,
                    "content": parsed.content,
                },
            )

        await db.commit()
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
