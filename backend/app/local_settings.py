"""Operator configuration; no tool caller can select a storage path or remote service."""

import ipaddress
import json
import os
from pathlib import Path
from urllib.parse import urlsplit

from app.services.git_capture import AuthorizedRepository, authorize_repositories

BACKEND_ROOT = Path(__file__).resolve().parents[1]


def loopback_url(value: str) -> str:
    try:
        url = urlsplit(value)
        valid = (
            url.scheme == "http"
            and ipaddress.ip_address(url.hostname or "").is_loopback
            and url.port is not None
            and url.username is None
            and url.password is None
            and url.path in ("", "/")
            and not url.query
            and not url.fragment
        )
    except ValueError:
        valid = False
    if not valid:
        raise ValueError("A literal loopback HTTP URL with an explicit port is required.")
    return value.rstrip("/")


def api_url() -> str:
    return loopback_url(os.environ.get("INSPECTOR_API_URL", "http://127.0.0.1:8000"))


def web_url() -> str:
    return loopback_url(os.environ.get("INSPECTOR_WEB_URL", "http://127.0.0.1:5173"))


def database_path() -> Path:
    value = os.environ.get("INSPECTOR_DB_PATH")
    if value:
        path = Path(value)
        if not path.is_absolute():
            raise ValueError("INSPECTOR_DB_PATH must be absolute.")
        return path
    return BACKEND_ROOT / ".local" / "reviews.sqlite3"


def web_repositories() -> dict[str, AuthorizedRepository]:
    value = json.loads(os.environ.get("INSPECTOR_REPOSITORIES", "{}"))
    if not isinstance(value, dict) or not all(
        isinstance(k, str) and isinstance(v, str) for k, v in value.items()
    ):
        raise ValueError("INSPECTOR_REPOSITORIES must map IDs to absolute paths.")
    return authorize_repositories([f"{key}={path}" for key, path in value.items()]) if value else {}
