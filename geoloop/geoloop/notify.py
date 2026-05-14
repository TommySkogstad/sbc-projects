"""Enkel ntfy-varsling for GeoLoop."""

from __future__ import annotations

import asyncio
import json
import logging
import os

import httpx

logger = logging.getLogger(__name__)

_NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "")
_NTFY_URL = os.environ.get("NTFY_URL", "https://ntfy.sh")
_NTFY_USER = os.environ.get("NTFY_USER", "")
_NTFY_PASS = os.environ.get("NTFY_PASS", "")
if not _NTFY_TOPIC:
    _NTFY_URL = ""


async def send(title: str, message: str, priority: str = "default", tags: str = "") -> None:
    """Send push-varsling via ntfy JSON API. Prøver opptil 3 ganger ved feil."""
    if not _NTFY_URL:
        return

    payload = {
        "topic": _NTFY_TOPIC,
        "title": title,
        "message": message,
        "priority": _priority_int(priority),
    }
    if tags:
        payload["tags"] = [t.strip() for t in tags.split(",")]

    auth = (_NTFY_USER, _NTFY_PASS) if _NTFY_USER else None

    for attempt in range(3):
        try:
            async with httpx.AsyncClient(auth=auth) as client:
                await client.post(
                    _NTFY_URL,
                    content=json.dumps(payload),
                    headers={"Content-Type": "application/json"},
                    timeout=10,
                )
            logger.debug("ntfy-varsling sendt: %s", title)
            return
        except Exception as e:
            if attempt < 2:
                await asyncio.sleep(2)
            else:
                logger.warning("Kunne ikke sende ntfy-varsling: %s (%s)", title, e)


def _priority_int(name: str) -> int:
    return {"min": 1, "low": 2, "default": 3, "high": 4, "urgent": 5}.get(name, 3)
