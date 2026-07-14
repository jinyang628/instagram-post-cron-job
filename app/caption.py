from __future__ import annotations

import json
import logging
import urllib.error
import urllib.parse
import urllib.request

from dotenv import load_dotenv

from app.errors import CaptionGenerationError
from app.prompts import SYSTEM_PROMPT, USER_PROMPT

log = logging.getLogger(__name__)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODEL = "openrouter/free"

load_dotenv()


def generate_dad_joke(api_key: str) -> str:
    """Generate a single dad joke using OpenRouter's free-model router."""
    payload = {
        "model": OPENROUTER_MODEL,
        "messages": [
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
            {"role": "user", "content": USER_PROMPT},
        ],
        "max_tokens": 500,
        "temperature": 1,
    }
    request = urllib.request.Request(
        OPENROUTER_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            result = json.load(response)
    except urllib.error.HTTPError as exc:
        try:
            error_payload = json.load(exc)
            message = error_payload.get("error", {}).get("message", str(error_payload))
        except (json.JSONDecodeError, AttributeError):
            message = exc.reason
        raise CaptionGenerationError(
            f"OpenRouter API returned HTTP {exc.code}: {message}"
        ) from exc
    except urllib.error.URLError as exc:
        raise CaptionGenerationError(
            f"Could not reach OpenRouter: {exc.reason}"
        ) from exc
    except json.JSONDecodeError as exc:
        raise CaptionGenerationError("OpenRouter returned invalid JSON") from exc

    try:
        joke = result["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError, AttributeError) as exc:
        raise CaptionGenerationError(
            f"OpenRouter did not return a text caption: {result}"
        ) from exc
    if not joke:
        raise CaptionGenerationError("OpenRouter returned an empty caption")
    return joke
