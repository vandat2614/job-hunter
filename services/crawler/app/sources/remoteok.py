import re
from datetime import datetime, timezone

import httpx

SOURCE = "remoteok"
URL = "https://remoteok.com/api"


def _strip_html(s: str | None) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s or "")).strip()


def _to_message(item: dict) -> dict:
    smin, smax = item.get("salary_min") or 0, item.get("salary_max") or 0
    salary_text = f"${smin} - ${smax}" if smin and smax else None
    tags = ", ".join(item.get("tags") or [])
    return {
        "source": SOURCE,
        "source_job_id": str(item["id"]),
        "url": item.get("url") or item.get("apply_url") or "",
        "crawled_at": datetime.now(timezone.utc).isoformat(),
        "payload": {
            "title": item.get("position", "").strip(),
            "company": item.get("company", "").strip(),
            "location": item.get("location") or "Remote",
            "salary_text": salary_text,
            "description": f"{_strip_html(item.get('description'))} {tags}".strip(),
        },
    }


async def fetch() -> list[dict]:
    async with httpx.AsyncClient(timeout=30, headers={"User-Agent": "job-hunter-portfolio/0.1"}) as client:
        resp = await client.get(URL)
        resp.raise_for_status()
    data = resp.json()
    # The first element is a legal notice, not a job
    items = [d for d in data if isinstance(d, dict) and d.get("id") and d.get("position")]
    return [_to_message(i) for i in items]
