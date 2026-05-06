from fastapi import APIRouter, Depends

from gateway.infrastructure.auth.jwt import require_jwt

router = APIRouter(prefix="/v1", tags=["auth"])


@router.get("/me")
async def me(payload: dict = Depends(require_jwt)) -> dict:
    """Return the decoded JWT claims for the bearer token.

    Phase 4 verification stub — remove when a real protected endpoint lands.
    """
    return payload
