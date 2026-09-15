from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..auth import create_access_token, hash_password, verify_password
from ..models import User
from ..schemas import LoginRequest, TokenResponse, UserCreate, UserOut
from ..security_logging import log_event

router = APIRouter(prefix="/api", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, db: Session = Depends(get_db)):
    if db.query(User).filter(User.username == payload.username).first():
        raise HTTPException(status_code=409, detail="Username already taken")
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=409, detail="Email already registered")

    user = User(
        username=payload.username,
        email=payload.email,
        password_hash=hash_password(payload.password),
        role="USER",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    log_event("user_registered", {"username": user.username})
    return user


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == payload.username).first()
    if user is None or not verify_password(payload.password, user.password_hash):
        log_event("login_failed", {"username": payload.username}, level="warning")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
        )
    if not user.is_active:
        log_event("login_failed", {"username": payload.username, "reason": "disabled"})
        raise HTTPException(status_code=403, detail="Account disabled")

    token = create_access_token(user.username)
    log_event("login_success", {"username": user.username, "role": user.role})
    return TokenResponse(access_token=token)