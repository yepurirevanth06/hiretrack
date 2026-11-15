from datetime import UTC, datetime, timedelta

import jwt
from pwdlib import PasswordHash

from app.core.config import settings
from app.core.exceptions import UnauthorizedError

password_hasher = PasswordHash.recommended()

# Used when the email doesn't exist, so a failed login takes the same time
# whether or not the account exists (prevents discovering emails by timing).
_DUMMY_HASH = password_hasher.hash("dummy-password-for-timing")


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, hashed: str | None) -> bool:
    if hashed is None:
        password_hasher.verify(password, _DUMMY_HASH)
        return False
    return password_hasher.verify(password, hashed)


def create_access_token(user_id: int, role: str, *, expires_minutes: int | None = None) -> str:
    now = datetime.now(UTC)
    minutes = settings.access_token_minutes if expires_minutes is None else expires_minutes
    payload = {
        "sub": str(user_id),
        "role": role,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> int:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            options={"require": ["exp", "sub"]},
        )
    except jwt.InvalidTokenError as exc:
        raise UnauthorizedError("Invalid or expired token") from exc

    if payload.get("type") != "access":
        raise UnauthorizedError("Invalid or expired token")
    return int(payload["sub"])
