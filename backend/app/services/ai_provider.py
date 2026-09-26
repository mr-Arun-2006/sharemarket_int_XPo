from __future__ import annotations

import asyncio
import json
from urllib import error, request

from app.core.config import settings


async def generate_narrative(context: dict) -> dict:
    if not (settings.ai_base_url and settings.ai_api_key and settings.ai_model):
        return {"status": "not_configured", "narrative": None}

    prompt = (
        "You are a financial market research assistant. "
        "Explain only the supplied evidence. Never invent market values, events, sectors, "
        "institutional flows, index values, or news. State missing information explicitly. "
        "Use the requested language while keeping financial terminology in English. "
        "Do not give personalized investment advice or a buy/sell instruction. "
        "Return a concise but deep research-style diagnosis with: Overall Diagnosis, "
        "Key Reasons, Market Evidence, Data Gaps and Uncertainty.\n\n"
        + json.dumps(context, default=str, ensure_ascii=False)
    )
    payload = json.dumps({
        "model": settings.ai_model,
        "messages": [
            {"role": "system", "content": "Evidence-grounded EOD market intelligence."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
    }).encode("utf-8")

    def _call():
        url = settings.ai_base_url.rstrip("/")
        if not url.endswith("/chat/completions"):
            url += "/chat/completions"
        req = request.Request(
            url,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer " + settings.ai_api_key,
            },
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=settings.ai_timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except (error.URLError, TimeoutError, ValueError) as exc:
            raise RuntimeError(str(exc)) from exc

    try:
        response = await asyncio.to_thread(_call)
        choices = response.get("choices") or []
        message = choices[0].get("message", {}) if choices else {}
        content = message.get("content")
        if not content:
            return {"status": "empty_response", "narrative": None}
        return {"status": "generated", "narrative": content}
    except Exception as exc:
        return {"status": "provider_error", "narrative": None, "error": str(exc)}
