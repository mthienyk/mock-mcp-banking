from mcp.server import Server
from mcp.types import CallToolResult

from mcp_bank.instructions import SERVER_INSTRUCTIONS
from mcp_bank.registry import bank_registry
from mcp_bank.resources.definitions import ALL_RESOURCES
from mcp_bank.resources.handlers import read_balances
from mcp_bank.tools import handlers as _tool_handlers  # noqa: F401

SERVER_NAME = "L'Élite MCP Bank"
SERVER_VERSION = "1.1.0"

_shared_server: Server | None = None


def _register_handlers(server: Server) -> None:
    @server.list_tools()
    async def list_tools():
        return bank_registry.list_tools()

    @server.call_tool()
    async def call_tool(
        name: str,
        arguments: dict[str, object] | None,
    ) -> CallToolResult:
        return await bank_registry.dispatch(name, arguments)

    @server.list_resources()
    async def list_resources():
        return list(ALL_RESOURCES)

    @server.read_resource()
    async def read_resource(uri):
        return await read_balances(uri)


def get_shared_server() -> Server:
    """Singleton MCP server (session identity comes from runtime context)."""
    global _shared_server
    if _shared_server is None:
        server = Server(
            name=SERVER_NAME,
            version=SERVER_VERSION,
            instructions=SERVER_INSTRUCTIONS,
        )
        _register_handlers(server)
        _shared_server = server
    return _shared_server
