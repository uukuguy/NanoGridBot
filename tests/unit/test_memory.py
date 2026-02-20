"""Unit tests for memory module."""

import pytest
from pathlib import Path
from datetime import datetime
from unittest.mock import patch, MagicMock

from nanogridbot.memory import (
    MemoryService,
    MemoryEntry,
    ConversationArchive,
    DailyMemory,
    create_memory_service,
)


@pytest.fixture
def temp_dir(tmp_path):
    """Create a temporary directory for testing."""
    return tmp_path


@pytest.fixture
def memory_service(temp_dir):
    """Create a MemoryService instance with temporary directory."""
    return MemoryService(temp_dir)


class TestMemoryService:
    """Test MemoryService functionality."""

    def test_get_memory_path_global(self, memory_service, temp_dir):
        """Test getting global memory path."""
        path = memory_service.get_memory_path(user_id=None)
        assert path == temp_dir / "memory" / "global"
        assert path.exists()

    def test_get_memory_path_user(self, memory_service, temp_dir):
        """Test getting user-specific memory path."""
        path = memory_service.get_memory_path(user_id=123)
        assert path == temp_dir / "memory" / "123"
        assert path.exists()

    def test_get_archives_path(self, memory_service, temp_dir):
        """Test getting archives path."""
        path = memory_service.get_archives_path(user_id=123, group_folder="mygroup")
        assert path == temp_dir / "archives" / "123" / "mygroup"
        assert path.exists()

    def test_list_conversations_empty(self, memory_service):
        """Test listing conversations when none exist."""
        conversations = memory_service.list_conversations(user_id=1)
        assert conversations == []

    def test_list_conversations_with_files(self, memory_service, temp_dir):
        """Test listing conversations with archive files."""
        archives = temp_dir / "archives" / "1" / "testgroup"
        archives.mkdir(parents=True)

        # Create test markdown files
        (archives / "2026-01-15-discussion.md").write_text("# Test")
        (archives / "2026-01-16-meeting.md").write_text("# Meeting")

        conversations = memory_service.list_conversations(user_id=1, group_folder="testgroup")

        assert len(conversations) == 2
        assert conversations[0]["title"] == "2026-01-16-meeting"
        assert conversations[1]["title"] == "2026-01-15-discussion"

    def test_list_conversations_with_limit(self, memory_service, temp_dir):
        """Test listing conversations with limit."""
        archives = temp_dir / "archives" / "1" / "testgroup"
        archives.mkdir(parents=True)

        for i in range(10):
            (archives / f"2026-01-{i+10:02d}-conv{i}.md").write_text("# Test")

        conversations = memory_service.list_conversations(user_id=1, group_folder="testgroup", limit=5)
        assert len(conversations) == 5

    def test_get_conversation(self, memory_service, temp_dir):
        """Test getting conversation content."""
        archives = temp_dir / "archives" / "1" / "testgroup"
        archives.mkdir(parents=True)

        file_path = archives / "2026-01-15-test.md"
        file_path.write_text("# Test Conversation\n\nHello world")

        content = memory_service.get_conversation(str(file_path))
        assert content == "# Test Conversation\n\nHello world"

    def test_get_conversation_not_found(self, memory_service):
        """Test getting non-existent conversation."""
        content = memory_service.get_conversation("/nonexistent/path.md")
        assert content is None

    def test_list_by_date(self, memory_service, temp_dir):
        """Test listing conversations by date."""
        archives = temp_dir / "archives" / "1" / "testgroup"
        archives.mkdir(parents=True)

        # Create files with different dates
        (archives / "2026-01-15-topic-a.md").write_text("# A")
        (archives / "2026-01-15-topic-b.md").write_text("# B")
        (archives / "2026-01-16-topic-c.md").write_text("# C")

        result = memory_service.list_by_date(user_id=1, group_folder="testgroup")

        assert len(result) == 2
        assert result[0]["date"] == "2026-01-16"
        assert len(result[0]["conversations"]) == 1
        assert result[1]["date"] == "2026-01-15"
        assert len(result[1]["conversations"]) == 2

    def test_list_by_date_with_range(self, memory_service, temp_dir):
        """Test listing conversations with date range filter."""
        archives = temp_dir / "archives" / "1" / "testgroup"
        archives.mkdir(parents=True)

        (archives / "2026-01-10-old.md").write_text("# Old")
        (archives / "2026-01-15-mid.md").write_text("# Mid")
        (archives / "2026-01-20-new.md").write_text("# New")

        result = memory_service.list_by_date(
            user_id=1,
            group_folder="testgroup",
            start_date="2026-01-12",
            end_date="2026-01-18",
        )

        assert len(result) == 1
        assert result[0]["date"] == "2026-01-15"

    def test_create_memory_note(self, memory_service, temp_dir):
        """Test creating a memory note."""
        file_path = memory_service.create_memory_note(
            user_id=1,
            group_folder="testgroup",
            title="Test Note",
            content="This is a test note content.",
            memory_type="note",
            tags=["test", "important"],
        )

        assert file_path.exists()
        content = file_path.read_text()
        assert "# Test Note" in content
        assert "This is a test note content." in content
        assert "**Type:** note" in content

    def test_search_memories_by_content(self, memory_service, temp_dir):
        """Test searching memories by content."""
        memory_path = memory_service.get_memory_path(user_id=1)
        (memory_path / "note1.md").write_text("# Note 1\n\nPython programming")
        (memory_path / "note2.md").write_text("# Note 2\n\nJavaScript development")

        results = memory_service.search_memories(user_id=1, query="python")

        assert len(results) == 1
        # The title is extracted from the markdown heading
        assert "Note 1" in results[0]["title"]

    def test_search_memories_by_tags(self, memory_service, temp_dir):
        """Test searching memories by tags."""
        memory_path = memory_service.get_memory_path(user_id=1)
        (memory_path / "note1.md").write_text("# Note\n**Tags:** python, code\n\nContent")
        (memory_path / "note2.md").write_text("# Note\n**Tags:** javascript\n\nContent")

        results = memory_service.search_memories(user_id=1, tags=["python"])

        assert len(results) == 1

    def test_get_daily_summary_existing(self, memory_service, temp_dir):
        """Test getting existing daily summary."""
        memory_path = memory_service.get_memory_path(user_id=1) / "daily_summaries"
        memory_path.mkdir(parents=True)
        (memory_path / "2026-01-15.md").write_text("Daily summary content")

        summary = memory_service.get_daily_summary(user_id=1, date="2026-01-15")

        assert summary is not None
        assert summary.date == "2026-01-15"
        assert summary.summary == "Daily summary content"

    def test_get_daily_summary_generated(self, memory_service, temp_dir):
        """Test getting generated daily summary from conversations."""
        archives = temp_dir / "archives" / "1" / "testgroup"
        archives.mkdir(parents=True)
        (archives / "2026-01-15-topic.md").write_text("# Topic")

        summary = memory_service.get_daily_summary(user_id=1, group_folder="testgroup", date="2026-01-15")

        assert summary is not None
        assert summary.date == "2026-01-15"
        assert summary.conversation_count == 1

    def test_get_daily_summary_not_found(self, memory_service):
        """Test getting daily summary when no data exists."""
        summary = memory_service.get_daily_summary(user_id=1, date="2026-01-01")
        assert summary is None


class TestCreateMemoryService:
    """Test create_memory_service factory function."""

    def test_create_memory_service(self, temp_dir):
        """Test creating memory service via factory."""
        from nanogridbot import config as config_module
        original_get_config = getattr(config_module, 'get_config', None)

        mock_config = MagicMock()
        mock_config.data_dir = temp_dir

        try:
            config_module.get_config = lambda: mock_config
            service = create_memory_service(user_id=123)

            assert isinstance(service, MemoryService)
            assert service.base_dir == temp_dir
        finally:
            if original_get_config:
                config_module.get_config = original_get_config
