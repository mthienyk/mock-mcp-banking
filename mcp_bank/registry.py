from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from mcp.types import CallToolResult, Tool
from sqlalchemy.orm import Session

from database import SessionLocal
from mcp_bank.errors import text_result
from mcp_bank.runtime import require_session
from models import User

ToolHandler = Callable[[Session, User, dict[str, object]], Awaitable[CallToolResult]]


@dataclass(frozen=True)
class RegisteredTool:
    definition: Tool
    handler: ToolHandler


class ToolRegistry:
    """Single registry: tool schemas and handlers stay in sync."""

    def __init__(self) -> None:
        self._tools: dict[str, RegisteredTool] = {}

    def register(self, definition: Tool) -> Callable[[ToolHandler], ToolHandler]:
        def decorator(handler: ToolHandler) -> ToolHandler:
            if definition.name in self._tools:
                raise ValueError(f"Duplicate MCP tool: {definition.name}")
            self._tools[definition.name] = RegisteredTool(definition, handler)
            return handler

        return decorator

    def list_tools(self) -> list[Tool]:
        return [entry.definition for entry in self._tools.values()]

    async def dispatch(
        self,
        name: str,
        arguments: dict[str, object] | None,
    ) -> CallToolResult:
        entry = self._tools.get(name)
        if entry is None:
            return text_result(f"Outil inconnu : {name}", is_error=True)

        session = require_session()
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.id == session.user_id).first()
            if user is None:
                return text_result("Utilisateur introuvable.", is_error=True)
            return await entry.handler(db, user, arguments or {})
        finally:
            db.close()


bank_registry = ToolRegistry()
