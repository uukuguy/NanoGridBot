"""Memory management for user conversations and context."""

from pathlib import Path
from datetime import datetime, timedelta
from typing import Any

from pydantic import BaseModel


class MemoryEntry(BaseModel):
    """A memory/context entry stored for a user or group."""
    id: int | None = None
    user_id: int | None = None
    group_folder: str | None = None
    session_id: str | None = None
    title: str
    content: str
    memory_type: str  # "conversation", "context", "note", "summary"
    tags: list[str] = []
    created_at: datetime = datetime.now()
    updated_at: datetime = datetime.now()


class ConversationArchive(BaseModel):
    """A conversation archive file."""
    id: int | None = None
    user_id: int | None = None
    group_folder: str
    session_id: str
    title: str
    file_path: str
    file_size: int = 0
    message_count: int = 0
    archived_at: datetime


class DailyMemory(BaseModel):
    """Daily memory summary for a date."""
    date: str  # YYYY-MM-DD
    user_id: int | None = None
    group_folder: str | None = None
    summary: str
    conversation_count: int = 0
    key_topics: list[str] = []


class MemoryService:
    """Service for managing user memories and conversation archives."""

    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.memory_dir = base_dir / "memory"
        self.archives_dir = base_dir / "archives"
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.archives_dir.mkdir(parents=True, exist_ok=True)

    def get_memory_path(self, user_id: int | None = None) -> Path:
        """Get the memory directory path for a user."""
        if user_id:
            path = self.memory_dir / str(user_id)
        else:
            path = self.memory_dir / "global"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def get_archives_path(self, user_id: int | None = None, group_folder: str | None = None) -> Path:
        """Get the archives directory path."""
        if user_id:
            path = self.archives_dir / str(user_id)
        else:
            path = self.archives_dir / "global"

        if group_folder:
            path = path / group_folder

        path.mkdir(parents=True, exist_ok=True)
        return path

    def list_conversations(
        self,
        user_id: int | None = None,
        group_folder: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """List conversation archives."""
        archives_path = self.get_archives_path(user_id, group_folder)
        conversations = []

        if not archives_path.exists():
            return []

        for file_path in sorted(archives_path.iterdir(), reverse=True):
            if file_path.suffix != ".md":
                continue

            stat = file_path.stat()
            conversations.append({
                "title": file_path.stem,
                "path": str(file_path),
                "size": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            })

            if len(conversations) >= limit:
                break

        return conversations

    def get_conversation(self, file_path: str) -> str | None:
        """Get conversation content by file path."""
        path = Path(file_path)
        if path.exists():
            return path.read_text()
        return None

    def list_by_date(
        self,
        user_id: int | None = None,
        group_folder: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[dict[str, Any]]:
        """List conversations grouped by date."""
        archives_path = self.get_archives_path(user_id, group_folder)
        date_groups: dict[str, list[dict]] = {}

        if not archives_path.exists():
            return []

        for file_path in sorted(archives_path.iterdir(), reverse=True):
            if file_path.suffix != ".md":
                continue

            # Parse date from filename: YYYY-MM-DD-title.md
            filename = file_path.stem
            if len(filename) >= 10 and filename[4] == "-" and filename[7] == "-":
                date = filename[:10]

                # Filter by date range
                if start_date and date < start_date:
                    continue
                if end_date and date > end_date:
                    continue

                if date not in date_groups:
                    date_groups[date] = []

                stat = file_path.stat()
                date_groups[date].append({
                    "title": filename[11:] if len(filename) > 11 else filename,
                    "path": str(file_path),
                    "size": stat.st_size,
                })

        return [
            {"date": date, "conversations": convs}
            for date, convs in sorted(date_groups.items(), reverse=True)
        ]

    def create_memory_note(
        self,
        user_id: int | None,
        group_folder: str | None,
        title: str,
        content: str,
        memory_type: str = "note",
        tags: list[str] | None = None,
    ) -> Path:
        """Create a new memory note."""
        memory_path = self.get_memory_path(user_id)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_title = "".join(c for c in title if c.isalnum() or c in " -_").strip()[:50]
        filename = f"{timestamp}_{safe_title}.md"
        file_path = memory_path / filename

        content_with_meta = f"""# {title}

**Type:** {memory_type}
**Created:** {datetime.now().isoformat()}
**Tags:** {", ".join(tags or [])}

---

{content}
"""
        file_path.write_text(content_with_meta)
        return file_path

    def search_memories(
        self,
        user_id: int | None = None,
        query: str | None = None,
        tags: list[str] | None = None,
        memory_type: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Search memories by content or tags."""
        memory_path = self.get_memory_path(user_id)
        results = []

        if not memory_path.exists():
            return []

        query_lower = query.lower() if query else None

        for file_path in memory_path.iterdir():
            if file_path.suffix != ".md":
                continue

            content = file_path.read_text()

            # Filter by query
            if query_lower and query_lower not in content.lower():
                continue

            # Filter by tags (in content)
            if tags:
                content_lower = content.lower()
                if not any(tag.lower() in content_lower for tag in tags):
                    continue

            # Filter by type (in content)
            if memory_type:
                if f"**Type:** {memory_type}" not in content:
                    continue

            stat = file_path.stat()

            # Extract title from content
            title = file_path.stem
            if content.startswith("# "):
                title = content.split("\n")[0][2:].strip()

            results.append({
                "title": title,
                "path": str(file_path),
                "size": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            })

            if len(results) >= limit:
                break

        return results

    def get_daily_summary(
        self,
        user_id: int | None = None,
        group_folder: str | None = None,
        date: str | None = None,
    ) -> DailyMemory | None:
        """Get or generate daily summary for a specific date."""
        if not date:
            date = datetime.now().strftime("%Y-%m-%d")

        # Check if summary exists
        summary_path = self.get_memory_path(user_id) / "daily_summaries"
        summary_file = summary_path / f"{date}.md"

        if summary_file.exists():
            content = summary_file.read_text()
            return DailyMemory(
                date=date,
                user_id=user_id,
                group_folder=group_folder,
                summary=content,
                conversation_count=0,
                key_topics=[],
            )

        # Generate from conversations
        conversations = self.list_by_date(user_id, group_folder, date, date)
        conv_list = next((c for c in conversations if c["date"] == date), None)

        if conv_list:
            summary = f"Found {len(conv_list['conversations'])} conversations on {date}."
            return DailyMemory(
                date=date,
                user_id=user_id,
                group_folder=group_folder,
                summary=summary,
                conversation_count=len(conv_list["conversations"]),
                key_topics=[],
            )

        return None


def create_memory_service(user_id: int | None = None) -> MemoryService:
    """Create a memory service instance."""
    from nanogridbot.config import get_config

    config = get_config()
    return MemoryService(config.data_dir)
