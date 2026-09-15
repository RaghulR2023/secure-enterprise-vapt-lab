from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..dependencies import get_current_user
from ..models import User
from ..schemas import UserOut, UserUpdate
from ..security_logging import log_event
from ..auth import hash_password

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("/me", response_model=UserOut)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.get("/{user_id}", response_model=UserOut)
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    target = db.query(User).filter(User.id == user_id).first()
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")

    # Secure (VULN-001-style object check): only self or an admin may read
    # another user's profile data. The vulnerable build skips this check.
    if not settings.is_vulnerable() and current_user.role != "ADMIN":
        if current_user.id != target.id:
            log_event(
                "authorization_failure",
                {"username": current_user.username, "target_user_id": target.id},
                level="warning",
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You may only view your own profile",
            )
    return target


@router.put("/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    target = db.query(User).filter(User.id == user_id).first()
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")

    if current_user.role != "ADMIN" and current_user.id != target.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="You may only edit your own profile"
        )

    if payload.email is not None:
        if db.query(User).filter(User.email == payload.email, User.id != target.id).first():
            raise HTTPException(status_code=409, detail="Email already registered")
        target.email = payload.email
    if payload.bio is not None:
        target.bio = payload.bio
    if payload.password is not None:
        target.password_hash = hash_password(payload.password)

    db.commit()
    db.refresh(target)
    log_event("user_updated", {"username": target.username, "actor": current_user.username})
    return target