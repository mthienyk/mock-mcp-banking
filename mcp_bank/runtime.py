from contextvars import ContextVar, Token

from mcp_bank.context import BankSessionContext

_session: ContextVar[BankSessionContext | None] = ContextVar("bank_session", default=None)


def bind_session(session: BankSessionContext) -> Token[BankSessionContext | None]:
    return _session.set(session)


def release_session(token: Token[BankSessionContext | None]) -> None:
    _session.reset(token)


def require_session() -> BankSessionContext:
    session = _session.get()
    if session is None:
        raise RuntimeError("No authenticated MCP session bound to this request.")
    return session
