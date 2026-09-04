from fastapi import APIRouter, Response

from app.config import get_settings
from app.database import check_db_connection
from app.models.schemas import DependencyStatus, HealthResponse
from app.providers.factory import check_all_providers

router = APIRouter(prefix="/api/health", tags=["Health"])


@router.get("", response_model=HealthResponse)
async def health(response: Response) -> HealthResponse:
    settings = get_settings()
    deps: list[DependencyStatus] = []

    db_ok = await check_db_connection()
    deps.append(DependencyStatus(name="database", ok=db_ok, detail=None if db_ok else "cannot connect"))

    provider_results = await check_all_providers()
    for name, (ok, detail) in provider_results.items():
        deps.append(DependencyStatus(name=f"provider:{name}", ok=ok, detail=detail))

    # DB down is a hard failure (nothing works without persistence).
    # The *active* default provider being down is also a hard failure for chat,
    # but the *other* (non-default) provider being down is only informational.
    default_provider_ok = next(
        (d.ok for d in deps if d.name == f"provider:{settings.default_llm_provider}"), False
    )

    if not db_ok:
        status = "down"
        response.status_code = 503
    elif not default_provider_ok:
        status = "degraded"
        response.status_code = 200
    else:
        status = "ok"
        response.status_code = 200

    return HealthResponse(status=status, dependencies=deps)
