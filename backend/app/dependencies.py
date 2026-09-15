"""Shared FastAPI dependencies: current-user resolution and RBAC.

The `require_admin` dependency enforces role == 'ADMIN'. In the
vulnerable build, admin-endpoints deliberately use only
`get_current_user` (broken function-level authorization, VULN-002).
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from .auth import decode_token
from .database import get_db
from .models import User
from .security_logging import log_event

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/login")

_UNAUTHORIZED = status.HTTP_401_UNAUTHORIZED


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    payload = decode_token(token)
    if payload is None:
        log_event("auth_failure", {"reason": "invalid_or_expired_token"}, level="warning")
        raise HTTPException(
            status_code=_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    username = payload.get("sub")
    if not username:
        raise HTTPException(status_code=_UNAUTHORIZED, detail="Invalid token payload")
    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise HTTPException(status_code=_UNAUTHORIZED, detail="Unknown user")
    if not user.is_active:
        raise HTTPException(status_code=_UNAUTHORIZED, detail="Account disabled")
    return user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "ADMIN":
        log_event(
            "authorization_failure",
            {"username": current_user.username, "required_role": "ADMIN"},
            level="warning",
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Administrator role required"
        )
    return current_user