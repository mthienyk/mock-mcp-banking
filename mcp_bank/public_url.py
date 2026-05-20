"""URL publique HTTPS (proxy Railway, Claude MCP exige https)."""

from __future__ import annotations

import os

from starlette.requests import Request


def resolve_public_base_url(request: Request) -> str:
    """Base URL sans slash final, en https derrière Railway."""
    explicit = os.getenv("PUBLIC_BASE_URL", "").strip().rstrip("/")
    if explicit:
        return explicit

    railway_domain = os.getenv("RAILWAY_PUBLIC_DOMAIN", "").strip()
    if railway_domain:
        return f"https://{railway_domain}"

    forwarded_proto = request.headers.get("x-forwarded-proto", "").split(",")[0].strip()
    forwarded_host = request.headers.get("x-forwarded-host", "").split(",")[0].strip()
    host = forwarded_host or request.headers.get("host", request.url.netloc)

    if forwarded_proto and host:
        return f"{forwarded_proto}://{host}".rstrip("/")

    base = str(request.base_url).rstrip("/")
    if base.startswith("http://") and _should_upgrade_to_https(request):
        return "https://" + base[len("http://") :]
    return base


def _should_upgrade_to_https(request: Request) -> bool:
    if os.getenv("FORCE_HTTPS", "").lower() in {"1", "true", "yes"}:
        return True
    host = (request.headers.get("host") or "").lower()
    return not host.startswith("localhost") and "127.0.0.1" not in host
