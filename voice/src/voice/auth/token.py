from fastapi import HTTPException

from voice.config import settings


def verify_token(authorization: str | None) -> None:
    if not settings.api_token:
        return

    expected = f"Bearer {settings.api_token}"
    if authorization != expected:
        raise HTTPException(status_code=401, detail="Invalid token")
