from __future__ import annotations

import hashlib
import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from io import BytesIO

from dotenv import load_dotenv
from huggingface_hub import InferenceClient
from PIL import Image

from app.errors import ImageUploadError

log = logging.getLogger(__name__)

load_dotenv()


def generate_image(api_key: str, prompt: str) -> Image.Image:
    """Generate the image that will be uploaded and published."""
    client = InferenceClient(
        provider="nscale",
        api_key=api_key,
    )

    image = client.text_to_image(
        prompt,
        model="black-forest-labs/FLUX.1-schnell",
    )
    return image


def upload_generated_image(
    image: Image.Image,
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
