"""Tests for type definitions."""

from datetime import datetime

import pytest

from nanogridbot.types import (
    ChannelType,
    ContainerConfig,
    ContainerOutput,
    Message,
    MessageRole,
    RegisteredGroup,
    ScheduleType,
    ScheduledTask,
    TaskStatus,
)


class TestMessage:
    """Test Message model."""

    def test_message_creation(self):
        """Test creating a Message instance."""
        msg = Message(
            id="msg_001",
            chat_jid="telegram:123456",
            sender="user_123",
            sender_name="Test User",
            content="Hello, world!",
            timestamp=datetime.now(),
        )
        assert msg.id == "msg_001"
        assert msg.chat_jid == "telegram:123456"
        assert msg.sender == "user_123"
        assert msg.content == "Hello, world!"
        assert msg.is_from_me is False

    def test_message_from_me(self):
        """Test message with is_from_me=True."""
        msg = Message(
            id="msg_002",
            chat_jid="telegram:123456",
            sender="bot_123",
            content="Response message",
            timestamp=datetime.now(),
            is_from_me=True,
        )
        assert msg.is_from_me is True


class TestChannelType:
    """Test ChannelType enum."""

    def test_channel_types(self):
        """Test all channel types are defined."""
        assert ChannelType.WHATSAPP.value == "whatsapp"
        assert ChannelType.TELEGRAM.value == "telegram"
        assert ChannelType.SLACK.value == "slack"
        assert ChannelType.DISCORD.value == "discord"
        assert ChannelType.QQ.value == "qq"
        assert ChannelType.FEISHU.value == "feishu"
        assert ChannelType.WECOM.value == "wecom"
        assert ChannelType.DINGTALK.value == "dingtalk"


class TestRegisteredGroup:
    """Test RegisteredGroup model."""

    def test_registered_group_creation(self):
        """Test creating a RegisteredGroup instance."""
        group = RegisteredGroup(
            jid="telegram:123456",
            name="Test Group",
            folder="test_group",
        )
        assert group.jid == "telegram:123456"
        assert group.name == "Test Group"
        assert group.folder == "test_group"
        assert group.requires_trigger is True
        assert group.trigger_pattern is None

    def test_registered_group_with_trigger(self):
        """Test group with trigger pattern."""
        group = RegisteredGroup(
            jid="telegram:123456",
            name="Test Group",
            folder="test_group",
            trigger_pattern="@assistant",
            requires_trigger=True,
        )
        assert group.trigger_pattern == "@assistant"
        assert group.requires_trigger is True


class TestContainerConfig:
    """Test ContainerConfig model."""

    def test_container_config_defaults(self):
        """Test default ContainerConfig values."""
        config = ContainerConfig()
        assert config.additional_mounts == []
        assert config.timeout is None
        assert config.max_output_size is None

    def test_container_config_with_values(self):
        """Test ContainerConfig with custom values."""
        config = ContainerConfig(
            timeout=300,
            max_output_size=100000,
            additional_mounts=[{"type": "bind", "source": "/tmp", "target": "/app/tmp"}],
        )
        assert config.timeout == 300
        assert config.max_output_size == 100000
        assert len(config.additional_mounts) == 1


class TestScheduledTask:
    """Test ScheduledTask model."""

    def test_scheduled_task_creation(self):
        """Test creating a ScheduledTask instance."""
        task = ScheduledTask(
            group_folder="test_group",
            prompt="Analyze the latest messages",
            schedule_type=ScheduleType.CRON,
            schedule_value="0 * * * *",
        )
        assert task.group_folder == "test_group"
        assert task.prompt == "Analyze the latest messages"
        assert task.schedule_type == ScheduleType.CRON
        assert task.schedule_value == "0 * * * *"
        assert task.status == TaskStatus.ACTIVE

    def test_scheduled_task_with_target(self):
        """Test task with target chat."""
        task = ScheduledTask(
            group_folder="test_group",
            prompt="Daily summary",
            schedule_type=ScheduleType.CRON,
            schedule_value="0 9 * * *",
            target_chat_jid="telegram:123456",
        )
        assert task.target_chat_jid == "telegram:123456"


class TestContainerOutput:
    """Test ContainerOutput model."""

    def test_container_output_success(self):
        """Test successful container output."""
        output = ContainerOutput(
            status="success",
            result="Analysis complete",
        )
        assert output.status == "success"
        assert output.result == "Analysis complete"
        assert output.error is None

    def test_container_output_error(self):
        """Test error container output."""
        output = ContainerOutput(
            status="error",
            error="Container execution failed",
        )
        assert output.status == "error"
        assert output.error == "Container execution failed"
        assert output.result is None
