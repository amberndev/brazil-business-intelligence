"""
Email hooks — all stubs (no real SMTP).

TODO(backend): send via CONTACT_EMAIL — empty (replace with real SMTP/SES/Postmark call).
TODO(backend): welcome email — empty (replace with real SMTP/SES/Postmark call).

CONTACT_EMAIL is read from settings so it can be changed via env var without code changes.
"""
from __future__ import annotations

import logging

log = logging.getLogger(__name__)


async def send_contact_email(*, name: str, email: str, message: str) -> None:
    """Stub: fires when a user submits the PRO/ENTERPRISE contact form."""
    # TODO(backend): send via CONTACT_EMAIL — empty
    from .config import settings
    log.debug(
        "contact_email stub (would send to %s): from=%s <%s>",
        settings.contact_email,
        name,
        email,
    )


async def send_welcome_email(*, key: str, name: str | None, email: str | None) -> None:
    """Stub: fires after a new api_key row is inserted (FREE/STARTER self-serve)."""
    # TODO(backend): welcome email — empty
    log.debug(
        "welcome_email stub (would email %s): key_prefix=%s name=%s",
        email,
        key[:12] if key else "",
        name,
    )
