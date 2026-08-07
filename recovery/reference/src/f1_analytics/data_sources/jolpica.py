"""Minimal Jolpica/Ergast client skeleton for future supplemental data checks."""

from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from f1_analytics.config import JOLPICA_BASE_URL


def build_endpoint_url(
    endpoint: str = "",
    *,
    params: dict[str, str | int] | None = None,
) -> str:
    base = JOLPICA_BASE_URL.rstrip("/")
    path = endpoint.strip("/")
    url = f"{base}/{path}" if path else base
    if params:
        url = f"{url}?{urlencode(params)}"
    return url


def fetch_json(
    endpoint: str = "",
    *,
    params: dict[str, str | int] | None = None,
    timeout_seconds: int = 30,
) -> dict:
    url = build_endpoint_url(endpoint, params=params)
    request = Request(url, headers={"User-Agent": "f1-analytics-local/1.0"})
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise RuntimeError(f"Jolpica request failed with HTTP {exc.code}: {url}") from exc
    except URLError as exc:
        raise RuntimeError(f"Jolpica request failed: {url} ({exc.reason})") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Jolpica response was not valid JSON: {url}") from exc

