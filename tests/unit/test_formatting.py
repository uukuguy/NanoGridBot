"""Unit tests for formatting utilities."""

import json
from datetime import datetime

import pytest

from nanogridbot.utils.formatting import (
    _escape_xml,
    format_messages_xml,
    format_output_xml,
    parse_input_json,
    serialize_output,
)


class TestEscapeXml:
    """Test _escape_xml function."""

    def test_escape_ampersand(self):
        assert _escape_xml("a&b") == "a&amp;b"

    def test_escape_less_than(self):
        assert _escape_xml("a<b") == "a&lt;b"

    def test_escape_greater_than(self):
        assert _escape_xml("a>b") == "a&gt;b"

    def test_escape_double_quote(self):
        assert _escape_xml('a"b') == "a&quot;b"

    def test_escape_single_quote(self):
        assert _escape_xml("a'b") == "a&apos;b"

    def test_escape_empty_string(self):
        assert _escape_xml("") == ""

    def test_escape_none_like(self):
        """Test with falsy but non-None input."""
        assert _escape_xml("") == ""

    def test_escape_multiple_special_chars(self):
        assert _escape_xml('<a&b"c>') == "&lt;a&amp;b&quot;c&gt;"

    def test_no_escape_needed(self):
        assert _escape_xml("hello world") == "hello world"


class TestFormatMessagesXml:
    """Test format_messages_xml function."""

    def test_empty_messages(self):
        result = format_messages_xml([])
        assert "<messages>" in result
        assert "</messages>" in result

    def test_single_user_message(self):
        messages = [
            {
                "sender": "user1",
                "sender_name": "Alice",
                "content": "Hello",
                "timestamp": datetime(2024, 1, 1, 12, 0, 0),
                "is_from_me": False,
            }
        ]
        result = format_messages_xml(messages)
        assert 'role="user"' in result
        assert 'sender="Alice"' in result
        assert "Hello" in result

    def test_assistant_message(self):
        messages = [
            {
                "sender": "bot",
                "content": "Hi there",
                "timestamp": datetime(2024, 1, 1, 12, 0, 0),
                "is_from_me": True,
            }
        ]
        result = format_messages_xml(messages)
        assert 'role="assistant"' in result

    def test_message_with_string_timestamp(self):
        messages = [
            {
                "sender": "user1",
                "content": "test",
                "timestamp": "2024-01-01T12:00:00",
                "is_from_me": False,
            }
        ]
        result = format_messages_xml(messages)
        assert "2024-01-01T12:00:00" in result

    def test_message_with_special_chars(self):
        messages = [
            {
                "sender": "user1",
                "content": "<script>alert('xss')</script>",
                "timestamp": datetime(2024, 1, 1),
                "is_from_me": False,
            }
        ]
        result = format_messages_xml(messages)
        assert "&lt;script&gt;" in result

    def test_message_missing_fields_uses_defaults(self):
        messages = [{}]
        result = format_messages_xml(messages)
        assert 'sender="unknown"' in result
        assert 'role="user"' in result

    def test_sender_name_fallback_to_sender(self):
        messages = [
            {
                "sender": "user123",
                "sender_name": None,
                "content": "test",
                "timestamp": datetime(2024, 1, 1),
                "is_from_me": False,
            }
        ]
        result = format_messages_xml(messages)
        assert 'sender="user123"' in result

    def test_multiple_messages(self):
        messages = [
            {
                "sender": "a",
                "content": "msg1",
                "timestamp": datetime(2024, 1, 1),
                "is_from_me": False,
            },
            {
                "sender": "b",
                "content": "msg2",
                "timestamp": datetime(2024, 1, 2),
                "is_from_me": True,
            },
        ]
        result = format_messages_xml(messages)
        assert result.count("<message role=") == 2
        assert result.count("</message>") == 2


class TestFormatOutputXml:
    """Test format_output_xml function."""

    def test_success_output(self):
        result = format_output_xml("success", result="done")
        assert "<status>success</status>" in result
        assert "<result>done</result>" in result

    def test_error_output(self):
        result = format_output_xml("error", error="something failed")
        assert "<status>error</status>" in result
        assert "<error>something failed</error>" in result

    def test_with_session_id(self):
        result = format_output_xml("success", new_session_id="abc123")
        assert "<new_session_id>abc123</new_session_id>" in result

    def test_no_optional_fields(self):
        result = format_output_xml("success")
        assert "<output>" in result
        assert "</output>" in result
        assert "<result>" not in result
        assert "<error>" not in result

    def test_special_chars_in_result(self):
        result = format_output_xml("success", result="<b>bold</b>")
        assert "&lt;b&gt;bold&lt;/b&gt;" in result

    def test_all_fields(self):
        result = format_output_xml(
            "success",
            result="ok",
            error=None,
            new_session_id="sess1",
        )
        assert "<result>ok</result>" in result
        assert "<new_session_id>sess1</new_session_id>" in result


class TestParseInputJson:
    """Test parse_input_json function."""

    def test_valid_json(self):
        result = parse_input_json('{"key": "value"}')
        assert result == {"key": "value"}

    def test_nested_json(self):
        result = parse_input_json('{"a": {"b": 1}}')
        assert result["a"]["b"] == 1

    def test_invalid_json_raises(self):
        with pytest.raises(ValueError, match="Invalid JSON"):
            parse_input_json("not json")

    def test_empty_object(self):
        result = parse_input_json("{}")
        assert result == {}

    def test_array_json(self):
        result = parse_input_json("[1, 2, 3]")
        assert result == [1, 2, 3]


class TestSerializeOutput:
    """Test serialize_output function."""

    def test_simple_dict(self):
        result = serialize_output({"status": "ok"})
        assert json.loads(result) == {"status": "ok"}

    def test_unicode_preserved(self):
        result = serialize_output({"msg": "你好"})
        assert "你好" in result

    def test_nested_dict(self):
        data = {"a": {"b": [1, 2]}}
        result = serialize_output(data)
        assert json.loads(result) == data
