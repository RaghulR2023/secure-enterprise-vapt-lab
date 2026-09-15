from contextlib import asynccontextmanager
import traceback

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import settings
from .database import Base, SessionLocal, engine
from .dependencies import require_admin
from .security_logging import log_event
from .seed import seed_data
from .routers import admin, auth, orders, products, users


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_data(db)
    log_event("application_start", {"mode": settings.app_mode})
    yield


app = FastAPI(
    title="TechCorp API",
    version="1.0.0",
    description="E-commerce API for the TechCorp VAPT laboratory.",
    docs_url="/docs" if settings.is_vulnerable() else None,
    redoc_url=None,
    openapi_url="/openapi.json" if settings.is_vulnerable() else None,
    lifespan=lifespan,
)

# ----------------------------------------------------------------------
# CORS
# ----------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


if not settings.is_vulnerable():
    from starlette.middleware.base import BaseHTTPMiddleware

    class SecurityHeadersMiddleware(BaseHTTPMiddleware):
        """Remediation of VULN-006: add hardened security headers."""

        async def dispatch(self, request: Request, call_next):
            response = await call_next(request)
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
            response.headers["Content-Security-Policy"] = "default-src 'self'"
            response.headers["X-XSS-Protection"] = "0"
            response.headers["Permissions-Policy"] = "camera=(), microphone=()"
            response.headers["Cache-Control"] = "no-store"
            return response

    app.add_middleware(SecurityHeadersMiddleware)


# ----------------------------------------------------------------------
# Error handling
# ----------------------------------------------------------------------
if settings.is_vulnerable():
    # FIXME (VULN-006): verbose error responses leak stack traces.
    @app.exception_handler(Exception)
    async def verbose_exception_handler(request: Request, exc: Exception):
        log_event("error", {"path": str(request.url), "error": str(exc)}, level="error")
        return JSONResponse(
            status_code=500,
            content={
                "detail": "Internal Server Error",
                "traceback": traceback.format_exc(),
            },
        )


# ----------------------------------------------------------------------
# Routers
# ----------------------------------------------------------------------
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(products.router)
app.include_router(orders.router)
app.include_router(admin.router)


@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok", "mode": settings.app_mode}