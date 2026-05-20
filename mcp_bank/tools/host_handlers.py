from sqlalchemy.orm import Session

import game_services
from mcp.types import CallToolResult
from mcp_bank.errors import text_result
from mcp_bank.registry import bank_registry
from mcp_bank.tools.definitions import (
    HOST_ADVANCE_GAME_PHASE,
    HOST_END_GAME_SESSION,
    HOST_START_GAME_SESSION,
)
from models import User


@bank_registry.register(HOST_START_GAME_SESSION)
async def handle_host_start_game_session(
    db: Session,
    user: User,
    arguments: dict[str, object],
) -> CallToolResult:
    try:
        result = game_services.host_start_game_session(db, user)
    except ValueError as exc:
        return text_result(str(exc), is_error=True)
    return text_result(result["message"])


@bank_registry.register(HOST_END_GAME_SESSION)
async def handle_host_end_game_session(
    db: Session,
    user: User,
    arguments: dict[str, object],
) -> CallToolResult:
    try:
        result = game_services.host_end_game_session(db, user)
    except ValueError as exc:
        return text_result(str(exc), is_error=True)
    return text_result(result["message"])


@bank_registry.register(HOST_ADVANCE_GAME_PHASE)
async def handle_host_advance_game_phase(
    db: Session,
    user: User,
    arguments: dict[str, object],
) -> CallToolResult:
    try:
        result = game_services.host_advance_game_phase(db, user)
    except ValueError as exc:
        return text_result(str(exc), is_error=True)
    return text_result(result["message"])
