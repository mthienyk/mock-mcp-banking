from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BankSessionContext:
    """Immutable identity bound to one MCP SSE connection."""

    user_id: int
    user_name: str
