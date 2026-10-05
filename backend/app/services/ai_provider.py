from __future__ import annotations

import json
import logging

import httpx

from app.core.config import settings

logger = logging.getLogger("sharem.ai")


async def generate_narrative(context: dict) -> dict:
    if not (settings.ai_base_url and settings.ai_api_key and settings.ai_model):
        return {"status": "not_configured", "narrative": None}

    context_json = json.dumps(context, default=str, ensure_ascii=False)
    if len(context_json) > settings.ai_max_context_chars:
        context_json = (
            context_json[: settings.ai_max_context_chars]
            + "\n[context truncated by server]"
        )

    prompt = (
        "You are a financial market research assistant. "
        "Explain only the supplied evidence. Never invent market values, events, sectors, "
        "institutional flows, index values, or news. State missing information explicitly. "
        "Use the requested language while keeping financial terminology in English. "
        "Do not give personalized investment advice or a buy/sell instruction. "
        "Return a concise but deep research-style diagnosis with: Overall Diagnosis, "
        "Key Reasons, Market Evidence, Data Gaps and Uncertainty.\n\n"
        + context_json
    )
    payload = {
        "model": settings.ai_model,
        "messages": [
            {"role": "system", "content": "Evidence-grounded EOD market intelligence."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
    }

    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(
                settings.ai_timeout_seconds,
                connect=min(10.0, settings.ai_timeout_seconds),
            ),
            follow_redirects=True,
        ) as client:
            url = settings.ai_base_url.rstrip("/")
            if not url.endswith("/chat/completions"):
                url += "/chat/completions"
            response = await client.post(
                url,
                json=payload,
                headers={
                    "Authorization": "Bearer " + settings.ai_api_key,
                    "Content-Type": "application/json",
                },
            )
            response.raise_for_status()
            data = response.json()

        choices = data.get("choices") or []
        message = choices[0].get("message", {}) if choices else {}
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            logger.warning("AI provider returned an empty response")
            return {"status": "empty_response", "narrative": None}

        return {"status": "generated", "narrative": content.strip()}
    except httpx.HTTPStatusError as exc:
        logger.warning("AI provider HTTP error status=%s", exc.response.status_code)
    except (httpx.HTTPError, ValueError, TypeError) as exc:
        logger.warning("AI provider request failed: %s", type(exc).__name__)
    except Exception:
        logger.exception("Unexpected AI provider failure")

    return {"status": "provider_error", "narrative": None}
