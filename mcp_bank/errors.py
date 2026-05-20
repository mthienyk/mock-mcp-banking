from mcp.types import CallToolResult, TextContent


def text_result(text: str, *, is_error: bool = False) -> CallToolResult:
    return CallToolResult(
        content=[TextContent(type="text", text=text)],
        isError=is_error,
    )


def parse_amount(arguments: dict[str, object], key: str = "amount") -> float | None:
    raw = arguments.get(key)
    if raw is None:
        return None
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    return value


def parse_string(arguments: dict[str, object], key: str) -> str:
    return str(arguments.get(key, "")).strip()


def parse_bool(arguments: dict[str, object], key: str) -> bool | None:
    raw = arguments.get(key)
    if raw is None:
        return None
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, str):
        lowered = raw.strip().lower()
        if lowered in {"true", "1", "yes", "oui"}:
            return True
        if lowered in {"false", "0", "no", "non"}:
            return False
    return None
