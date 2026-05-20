import logging

from starlette.types import Receive, Scope, Send

from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from mcp_bank.server import get_shared_server

logger = logging.getLogger(__name__)

MCP_HTTP_PATH = "/mcp"


def create_session_manager() -> StreamableHTTPSessionManager:
    """Stateless Streamable HTTP (spec recommandé, scalable)."""
    return StreamableHTTPSessionManager(
        app=get_shared_server(),
        stateless=True,
        json_response=True,
    )


async def handle_streamable_http(
    manager: StreamableHTTPSessionManager,
    scope: Scope,
    receive: Receive,
    send: Send,
) -> None:
    await manager.handle_request(scope, receive, send)
