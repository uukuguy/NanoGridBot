"""Message formatting utilities for IPC and output."""

from datetime import datetime
from typing import Any


def format_messages_xml(messages: list[dict[str, Any]]) -> str:
    """Format messages into XML format for Claude input.

    Args:
        messages: List of message dictionaries with keys:
            - sender: str
            - sender_name: str | None
            - content: str
            - timestamp: datetime
            - is_from_me: bool

    Returns:
        XML formatted message string
    """
    lines = ["<messages>"]

    for msg in messages:
        sender = msg.get("sender", "unknown")
        sender_name = msg.get("sender_name") or sender
        content = msg.get("content", "")
        timestamp = msg.get("timestamp")
        is_from_me = msg.get("is_from_me", False)

        # Format timestamp
        if isinstance(timestamp, datetime):
            ts_str = timestamp.isoformat()
        else:
            ts_str = str(timestamp)

        # Escape XML special characters in content
        content = _escape_xml(content)

        role = "assistant" if is_from_me else "user"

        lines.append(
            f'  <message role="{role}" sender="{_escape_xml(sender_name)}" timestamp="{ts_str}">'
        )
        lines.append(f"    {content}")
        lines.append("  </message>")

    lines.append("</messages>")

    return "\n".join(lines)


def _escape_xml(text: str) -> str:
    """Escape XML special characters.

    Args:
        text: Text to escape

    Returns:
        Escaped text
    """
    if not text:
        return ""

    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def format_output_xml(
    status: str,
    result: str | None = None,
    error: str | None = None,
    new_session_id: str | None = None,
) -> str:
    """Format container output into XML format.

    Args:
        status: "success" or "error"
        result: Result text (for success)
        error: Error message (for error)
        new_session_id: New session ID if created

    Returns:
        XML formatted output string
    """
    lines = ["<output>"]

    lines.append(f"  <status>{status}</status>")

    if result is not None:
        lines.append(f"  <result>{_escape_xml(result)}</result>")

    if error is not None:
        lines.append(f"  <error>{_escape_xml(error)}</error>")

    if new_session_id is not None:
        lines.append(f"  <new_session_id>{_escape_xml(new_session_id)}</new_session_id>")

    lines.append("</output>")

    return "\n".join(lines)


def parse_input_json(input_data: str) -> dict[str, Any]:
    """Parse JSON input from container.

    Args:
        input_data: JSON string input

    Returns:
        Parsed dictionary

    Raises:
        ValueError: If JSON is invalid
    """
    import json

    try:
        return json.loads(input_data)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON input: {e}") from e


def serialize_output(data: dict[str, Any]) -> str:
    """Serialize output data to JSON.

    Args:
        data: Output data dictionary

    Returns:
        JSON string
    """
    import json

    return json.dumps(data, ensure_ascii=False)
