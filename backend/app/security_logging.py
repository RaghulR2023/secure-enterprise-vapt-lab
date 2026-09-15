"""Structured security event logging.

Only non-sensitive fields are logged. Passwords, tokens and secrets are
never written to the log stream. Usernames are logged because they are
needed to reconstruct an attack narrative during forensic analysis.

The logger attaches its own StreamHandler explicitly so that security
events survive regardless of how the web server (uvicorn) configures
the root logging hierarchy.
"""

import json
import logging
import sys
from typing import Optional

_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"

logger = logging.getLogger("techcorp.security")
logger.setLevel(logging.INFO)
logger.propagate = False

if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(_FORMAT))
    logger.addHandler(handler)


def log_event(
    event: str,
    detail: Optional[dict] = None,
    level: str = "info",
) -> None:
    record = {"event": event, "detail": detail or {}}
    message = json.dumps(record, default=str)
    getattr(logger, level, logger.info)(message)