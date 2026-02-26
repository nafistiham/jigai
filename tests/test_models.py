"""Tests for data models."""

from jigai.models import IdleEvent, Session, SessionStatus


class TestSession:
    def test_default_session(self):
        session = Session()
        assert len(session.session_id) == 8
        assert session.tool_name == "unknown"
        assert session.status == SessionStatus.ACTIVE

    def test_display_name(self):
        session = Session(tool_name="Claude Code", session_id="abc123")
        assert session.to_display_name() == "Claude Code-abc123"


class TestIdleEvent:
    def test_creation(self):
        event = IdleEvent(
            session_id="test123",
            tool_name="Claude Code",
            working_dir="/home/user/project",
            last_output="Tests passed",
            idle_seconds=5.2,
        )
        assert event.session_id == "test123"
        assert event.tool_name == "Claude Code"
        assert event.detection_method == "pattern"

    def test_serialization(self):
        event = IdleEvent(
            session_id="test",
            tool_name="test",
            working_dir="/tmp",
        )
        data = event.model_dump()
        assert "session_id" in data
        assert "timestamp" in data
