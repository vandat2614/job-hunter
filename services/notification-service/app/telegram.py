import asyncio
import logging

import httpx

from app.config import settings

log = logging.getLogger("telegram")


class PermanentError(Exception):
    """Retrying will not help (unknown chat, bot blocked, bad token)."""


class TemporaryError(Exception):
    """Worth retrying (network problem, rate limit, server error)."""


def classify_response(status: int, body: dict) -> Exception | None:
    """Map a Telegram HTTP response to None (success) or the error to raise."""
    if status == 200 and body.get("ok"):
        return None
    desc = body.get("description", "no description")
    if status == 429 or status >= 500:
        return TemporaryError(f"telegram {status}: {desc}")
    return PermanentError(f"telegram {status}: {desc}")


async def send_message(chat_id: str, text: str) -> str:
    """Send a message. Returns "sent" or "dry_run"."""
    if not settings.telegram_bot_token:
        log.info("[dry-run] to chat %s:\n%s", chat_id, text)
        return "dry_run"

    url = f"{settings.telegram_api_base}/bot{settings.telegram_bot_token}/sendMessage"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json={"chat_id": chat_id, "text": text})
    except httpx.HTTPError as e:
        # Do not chain or print the original error: its message may contain the URL (and the token)
        raise TemporaryError(f"network error: {type(e).__name__}") from None

    try:
        body = resp.json()
    except ValueError:
        body = {}

    if resp.status_code == 429:
        retry_after = body.get("parameters", {}).get("retry_after", 1)
        await asyncio.sleep(min(retry_after, 30))

    err = classify_response(resp.status_code, body)
    if err:
        raise err
    return "sent"
