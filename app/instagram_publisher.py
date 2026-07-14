"""Publish a single image to Instagram through the Instagram Graph API."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import date
from io import BytesIO
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from huggingface_hub import InferenceClient
from PIL import Image

from app.errors import CaptionGenerationError, ImageUploadError, InstagramError
from app.prompts import SYSTEM_PROMPT, USER_PROMPT
from app.utils import required_env

log = logging.getLogger(__name__)

load_dotenv()

ROOT = Path(__file__).resolve().parent
STATE_FILE = ROOT / ".last_successful_post"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODEL = "openrouter/free"


def generate_image(api_key: str, prompt: str) -> Image.Image:
    """Generate the image that will be uploaded and published."""
    client = InferenceClient(
        provider="nscale",
        api_key=api_key,
    )

    # output is a PIL.Image object
    image = client.text_to_image(
        prompt,
        model="black-forest-labs/FLUX.1-schnell",
    )
    return image


def upload_generated_image(
    image: Image.Image,
    *,
    cloud_name: str,
    api_key: str,
    api_secret: str,
) -> str:
    """Upload a PIL image to Cloudinary and return its public HTTPS URL."""
    output = BytesIO()
    if image.mode not in {"RGB", "L"}:
        image = image.convert("RGB")
    image.save(output, format="JPEG", quality=95)

    timestamp = str(int(time.time()))
    public_id = f"instagram-cron/{uuid.uuid4().hex}"
    signed_params = {"public_id": public_id, "timestamp": timestamp}
    signature_payload = "&".join(
        f"{key}={value}" for key, value in sorted(signed_params.items())
    )
    signature = hashlib.sha1(
        f"{signature_payload}{api_secret}".encode("utf-8")
    ).hexdigest()

    boundary = f"----instagram-cron-{uuid.uuid4().hex}"
    body = bytearray()
    fields = {
        **signed_params,
        "api_key": api_key,
        "signature": signature,
    }
    for name, value in fields.items():
        body.extend(f"--{boundary}\r\n".encode())
        body.extend(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
        body.extend(value.encode())
        body.extend(b"\r\n")
    body.extend(f"--{boundary}\r\n".encode())
    body.extend(b'Content-Disposition: form-data; name="file"; filename="post.jpg"\r\n')
    body.extend(b"Content-Type: image/jpeg\r\n\r\n")
    body.extend(output.getvalue())
    body.extend(b"\r\n")
    body.extend(f"--{boundary}--\r\n".encode())

    request = urllib.request.Request(
        f"https://api.cloudinary.com/v1_1/{urllib.parse.quote(cloud_name)}/image/upload",
        data=bytes(body),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            result = json.load(response)
    except urllib.error.HTTPError as exc:
        try:
            error_payload = json.load(exc)
            message = error_payload.get("error", {}).get("message", str(error_payload))
        except (json.JSONDecodeError, AttributeError):
            message = exc.reason
        raise ImageUploadError(
            f"Cloudinary returned HTTP {exc.code}: {message}"
        ) from exc
    except urllib.error.URLError as exc:
        raise ImageUploadError(f"Could not reach Cloudinary: {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise ImageUploadError("Cloudinary returned invalid JSON") from exc

    image_url = result.get("secure_url")
    if not isinstance(image_url, str) or not image_url.startswith("https://"):
        raise ImageUploadError(f"Cloudinary did not return a secure URL: {result}")
    return image_url


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


def publish_image(
    *,
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
        caption = generate_dad_joke(required_env("OPEN_ROUTER_API_KEY"))
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
        media_id = publish_image(
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
