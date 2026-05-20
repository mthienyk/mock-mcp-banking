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
