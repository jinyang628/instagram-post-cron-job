"""Publish a single image to Instagram through the Instagram Graph API."""

from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from app.caption import generate_dad_joke
from app.errors import CaptionGenerationError, ImageUploadError, InstagramError
from app.image import generate_image, upload_generated_image
from app.utils import required_env

log = logging.getLogger(__name__)

load_dotenv()

ROOT = Path(__file__).resolve().parent
STATE_FILE = ROOT / ".last_successful_post"


def request_json(url: str, data: dict[str, str] | None = None) -> dict[str, Any]:
    encoded = urllib.parse.urlencode(data).encode() if data is not None else None
    request = urllib.request.Request(
        url, data=encoded, method="POST" if data else "GET"
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        try:
            payload = json.load(exc)
            message = payload.get("error", {}).get("message", str(payload))
        except (json.JSONDecodeError, AttributeError):
            message = exc.reason
        raise InstagramError(
            f"Instagram API returned HTTP {exc.code}: {message}"
        ) from exc
    except urllib.error.URLError as exc:
        raise InstagramError(f"Could not reach Instagram: {exc.reason}") from exc


def publish_post(
    image_url: str,
    caption: str,
    access_token: str,
    instagram_user_id: str,
    graph_api_version: str,
) -> str:
    """Create an image container, wait for it, and publish it."""
    base_url = f"https://graph.instagram.com/{graph_api_version}"
    container = request_json(
        f"{base_url}/{instagram_user_id}/media",
        {
            "image_url": image_url,
            "caption": caption,
            "access_token": access_token,
        },
    )
    creation_id = container.get("id")
    if not creation_id:
        raise InstagramError(f"Instagram did not return a creation ID: {container}")

    status_url = f"{base_url}/{creation_id}?" + urllib.parse.urlencode(
        {"fields": "status_code,status", "access_token": access_token}
    )
    for attempt in range(12):
        status = request_json(status_url)
        status_code = status.get("status_code")
        if status_code == "FINISHED":
            break
        if status_code in {"ERROR", "EXPIRED"}:
            raise InstagramError(
                f"Instagram could not prepare the image: {status.get('status', status_code)}"
            )
        if attempt == 11:
            raise InstagramError("Timed out waiting for Instagram to prepare the image")
        time.sleep(5)

    published = request_json(
        f"{base_url}/{instagram_user_id}/media_publish",
        {"creation_id": creation_id, "access_token": access_token},
    )
    media_id = published.get("id")
    if not media_id:
        raise InstagramError(f"Instagram did not return a media ID: {published}")
    return str(media_id)


def main() -> int:
    today = date.today().isoformat()
    if STATE_FILE.exists() and STATE_FILE.read_text(encoding="utf-8").strip() == today:
        log.info(f"Already posted successfully on {today}; skipping.")
        return 0

    try:
        caption = generate_dad_joke(api_key=required_env("OPEN_ROUTER_API_KEY"))
        log.info("Generated today's dad-joke caption with OpenRouter.")
        image = generate_image(
            api_key=required_env("HF_TOKEN"),
            prompt=caption,
        )
        image_url = upload_generated_image(
            image,
            cloud_name=required_env("CLOUDINARY_CLOUD_NAME"),
            api_key=required_env("CLOUDINARY_API_KEY"),
            api_secret=required_env("CLOUDINARY_API_SECRET"),
        )
        log.info("Uploaded today's generated image to %s", image_url)
        media_id = publish_post(
            image_url=image_url,
            caption=caption,
            access_token=required_env("INSTAGRAM_ACCESS_TOKEN"),
            instagram_user_id=required_env("INSTAGRAM_USER_ID"),
            graph_api_version=os.getenv("GRAPH_API_VERSION", "v25.0"),
        )
    except (CaptionGenerationError, ImageUploadError, InstagramError) as exc:
        log.error(f"Post failed: {exc}")
        return 1

    STATE_FILE.write_text(today + "\n", encoding="utf-8")
    log.info(f"Published Instagram media {media_id} on {today}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
