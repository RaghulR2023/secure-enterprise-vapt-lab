"""Application configuration.

Every tunable is read from environment variables so that the *same*
codebase can run in either `vulnerable` or `secure` mode. The mode is
selected with the APP_MODE environment variable:

    APP_MODE=secure      (default) - remediated, hardened build
    APP_MODE=vulnerable           - intentionally vulnerable lab build
"""

import os
import secrets

SECURE = "secure"
VULNERABLE = "vulnerable"


class Settings:
    """Runtime settings for the TechCorp backend."""

    def __init__(self) -> None:
        mode = os.getenv("APP_MODE", SECURE).strip().lower()
        self.app_mode = mode if mode in (SECURE, VULNERABLE) else SECURE

        self.database_url = os.getenv(
            "DATABASE_URL",
            "postgresql+psycopg2://techcorp:techcorp@postgres:5432/techcorp",
        )

        # ------------------------------------------------------------------
        # JWT / authentication
        # ------------------------------------------------------------------
        if self.app_mode == VULNERABLE:
            # FIXME (VULN-003): hard-coded, world-known signing secret.
            # This is an intentional lab weakness - see docs/vapt-report.
            self.secret_key = os.getenv(
                "SECRET_KEY", "techcorp-fixed-lab-secret-key-please-change"
            )
            # 0 means "no expiry": tokens are valid forever (VULN-003).
            self.access_token_expire_minutes = int(
                os.getenv("TOKEN_EXPIRE_MINUTES", "0")
            )
        else:
            # Secure: prefer the injected env secret; generate one at boot
            # otherwise. Tokens expire after 30 minutes by default.
            self.secret_key = os.getenv("SECRET_KEY") or secrets.token_urlsafe(48)
            self.access_token_expire_minutes = int(
                os.getenv("TOKEN_EXPIRE_MINUTES", "30")
            )

        # ------------------------------------------------------------------
        # CORS
        # ------------------------------------------------------------------
        self.cors_origins = self._cors()

        self.debug = self.app_mode == VULNERABLE  # FIXME (VULN-006): debug mode

    def is_vulnerable(self) -> bool:
        return self.app_mode == VULNERABLE

    def _cors(self) -> list[str]:
        if self.app_mode == VULNERABLE:
            return ["*"]  # FIXME (VULN-006): wildcard CORS in lab build
        raw = os.getenv(
            "CORS_ORIGINS",
            "http://localhost:8080,http://localhost,http://127.0.0.1:8080",
        )
        return [o.strip() for o in raw.split(",") if o.strip()]


settings = Settings()