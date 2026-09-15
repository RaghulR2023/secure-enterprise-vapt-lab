"""Authentication primitives: password hashing and JWT token handling.

VULN-003 tracks the differences between the vulnerable and the secure
token implementations. Password storage uses bcrypt in BOTH builds; the
weakness in the vulnerable build is confined to the token layer.
"""

from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from .config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(subject: str) -> str:
    """Create an access token.

    In secure mode the token carries `exp`, `iat` and `type` claims.
    In vulnerable mode (expire = 0) no expiry claim is emitted, so the
    token never expires (VULN-003).
    """
    payload = {"sub": subject, "type": "access", "iat": datetime.now(timezone.utc)}
    if settings.access_token_expire_minutes > 0:
        expires = datetime.now(timezone.utc) + timedelta(
            minutes=settings.access_token_expire_minutes
        )
        payload["exp"] = expires
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decode_token(token: str) -> dict | None:
    """Decode and validate a token.

    python-jose enforces the `exp` claim automatically when present.
    Vulnerable mode additionally skips the `type` claim check.
    """
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
    except JWTError:
        return None
    if not settings.is_vulnerable() and payload.get("type") != "access":
        return None
    return payload