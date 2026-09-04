from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.db_models import Session as SessionModel
from app.models.schemas import SessionCreateRequest, SessionDetail, SessionSummary

router = APIRouter(prefix="/api/sessions", tags=["Sessions"])


@router.post("", response_model=SessionSummary, status_code=201)
async def create_session(
    body: SessionCreateRequest, db: AsyncSession = Depends(get_db)
) -> SessionSummary:
    session = SessionModel(title=body.title or "New session", user_metadata=body.user_metadata)
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return SessionSummary.model_validate(session, from_attributes=True)


@router.get("", response_model=list[SessionSummary])
async def list_sessions(db: AsyncSession = Depends(get_db)) -> list[SessionSummary]:
    result = await db.execute(select(SessionModel).order_by(SessionModel.updated_at.desc()).limit(50))
    sessions = result.scalars().all()
    return [SessionSummary.model_validate(s, from_attributes=True) for s in sessions]


@router.get("/{session_id}", response_model=SessionDetail)
async def get_session(session_id: UUID, db: AsyncSession = Depends(get_db)) -> SessionDetail:
    result = await db.execute(
        select(SessionModel)
        .where(SessionModel.id == session_id)
        .options(selectinload(SessionModel.messages))
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    return SessionDetail.model_validate(session, from_attributes=True)
