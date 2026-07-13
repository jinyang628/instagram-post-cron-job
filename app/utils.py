import os

from app.errors import InstagramError

def required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise InstagramError(f"Missing required setting: {name}")
    return value
