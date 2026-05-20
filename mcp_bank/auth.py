from fastapi import HTTPException, Request

from database import SessionLocal, ensure_database_initialized
from mcp_bank.context import BankSessionContext
import services


def extract_api_token(request: Request) -> str:
    """Read the bank API token from query string or Authorization header."""
    token = request.query_params.get("token")
    if token:
        return token

    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header.removeprefix("Bearer ").strip()

    raise HTTPException(
        status_code=401,
        detail=(
            "Authentification requise. Connectez-vous sur le site pour obtenir "
            "un jeton, puis passez-le en ?token=... ou Authorization: Bearer ..."
        ),
    )


def extract_token_from_scope(scope: dict[str, object]) -> str | None:
    """Extract token from ASGI scope query string or headers."""
    query_string = scope.get("query_string", b"")
    if isinstance(query_string, bytes):
        from urllib.parse import parse_qs

        params = parse_qs(query_string.decode())
        tokens = params.get("token", [])
        if tokens:
            return tokens[0]

    headers = scope.get("headers", [])
    if isinstance(headers, list):
        for raw_key, raw_value in headers:
            key = raw_key.decode().lower() if isinstance(raw_key, bytes) else str(raw_key).lower()
            if key == "authorization":
                value = raw_value.decode() if isinstance(raw_value, bytes) else str(raw_value)
                if value.startswith("Bearer "):
                    return value.removeprefix("Bearer ").strip()
    return None


def resolve_session(token: str) -> BankSessionContext:
    """Validate token and return the bound MCP session context."""
    ensure_database_initialized()
    db = SessionLocal()
    try:
        user = services.get_user_by_token(db, token)
        if not user:
            raise HTTPException(status_code=401, detail="Jeton d'API invalide.")
        return BankSessionContext(
            user_id=user.id,
            user_name=user.name,
            is_host=services.is_host(user),
        )
    finally:
        db.close()
