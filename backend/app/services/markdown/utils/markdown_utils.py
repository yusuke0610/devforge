from typing import Any


def field_line(label: str, value: str) -> str:
    """Format a bold label-value line."""
    return f"**{label}:** {value}"


def section_header(level: int, title: str) -> list[str]:
    """Return a markdown section header with trailing blank line."""
    prefix = "#" * level
    return [f"{prefix} {title}", ""]


def list_item(text: str) -> str:
    """Format a markdown list item."""
    return f"- {text}"


def format_period(start: str, end: str, is_current: bool) -> str:
    """Format a date period string. 在籍中は end を "" で受ける契約。"""
    return f"{start} - {'現在' if is_current else end}"


def get_str(payload: dict[str, Any], key: str, default: str = "") -> str:
    """Get a string value from payload with default."""
    return payload.get(key, default)
