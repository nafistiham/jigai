"""Tests for configuration management."""

import pytest

from jigai.config import JigAiConfig, NotificationConfig, DetectionConfig, ServerConfig


class TestJigAiConfig:
    def test_defaults(self):
        config = JigAiConfig()
        assert config.server.port == 9384
        assert config.server.bind == "0.0.0.0"
        assert config.notifications.macos is True
        assert config.notifications.sound == "Ping"
        assert config.notifications.show_last_output is True
        assert config.notifications.output_lines == 3
        assert config.detection.timeout_seconds == 30
        assert config.detection.cooldown_seconds == 5

    def test_custom_values(self):
        config = JigAiConfig(
            server=ServerConfig(port=8080),
            detection=DetectionConfig(timeout_seconds=60),
        )
        assert config.server.port == 8080
        assert config.detection.timeout_seconds == 60

    def test_notification_redact_patterns(self):
        config = JigAiConfig()
        assert len(config.notifications.redact_patterns) > 0

    def test_serialization_roundtrip(self):
        config = JigAiConfig()
        data = config.model_dump()
        restored = JigAiConfig(**data)
        assert restored.server.port == config.server.port
        assert restored.detection.timeout_seconds == config.detection.timeout_seconds


class TestNotificationConfig:
    def test_defaults(self):
        nc = NotificationConfig()
        assert nc.show_last_output is True
        assert nc.output_lines == 3
        assert nc.group_by_session is True

    def test_custom_redact(self):
        nc = NotificationConfig(
            redact_patterns=[r"SECRET_\w+", r"token=\S+"]
        )
        assert len(nc.redact_patterns) == 2
