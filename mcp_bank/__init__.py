"""Serveur MCP Banque MCP (simulateur bancaire pour atelier)."""

from mcp_bank.auth import extract_api_token, resolve_session
from mcp_bank.server import SERVER_NAME, SERVER_VERSION, get_shared_server
from mcp_bank.streamable import MCP_HTTP_PATH, create_session_manager, handle_streamable_http
from mcp_bank.transport import sse_transport

__all__ = [
    "MCP_HTTP_PATH",
    "SERVER_NAME",
    "SERVER_VERSION",
    "create_session_manager",
    "extract_api_token",
    "get_shared_server",
    "handle_streamable_http",
    "resolve_session",
    "sse_transport",
]
