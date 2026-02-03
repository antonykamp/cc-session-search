"""Tests for conversation parser token counting and cost calculation."""

import json
import tempfile
from pathlib import Path

from cc_session_search.core.conversation_parser import (
    JSONLParser,
    CLAUDE_PRICING,
    CACHE_WRITE_5M_MULTIPLIER,
    CACHE_WRITE_1H_MULTIPLIER,
    CACHE_READ_MULTIPLIER,
)


def _write_jsonl(lines):
    """Write JSONL lines to a temp file and return its Path."""
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False)
    for obj in lines:
        f.write(json.dumps(obj) + "\n")
    f.close()
    return Path(f.name)


def _make_assistant_msg(
    api_msg_id,
    uuid,
    parent_uuid,
    model,
    input_tokens,
    output_tokens,
    cache_creation,
    cache_read,
    cache_5m=0,
    cache_1h=0,
    content_type="text",
    content_text="Hello",
):
    content_block = {"type": content_type}
    if content_type == "text":
        content_block["text"] = content_text
    elif content_type == "tool_use":
        content_block["id"] = "toolu_test"
        content_block["name"] = "Read"
        content_block["input"] = {"file_path": "/tmp/test"}

    return {
        "parentUuid": parent_uuid,
        "isSidechain": False,
        "userType": "external",
        "cwd": "/tmp",
        "sessionId": "test-session",
        "version": "2.1.29",
        "type": "assistant",
        "message": {
            "model": model,
            "id": api_msg_id,
            "type": "message",
            "role": "assistant",
            "content": [content_block],
            "stop_reason": None,
            "stop_sequence": None,
            "usage": {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cache_creation_input_tokens": cache_creation,
                "cache_read_input_tokens": cache_read,
                "cache_creation": {
                    "ephemeral_5m_input_tokens": cache_5m,
                    "ephemeral_1h_input_tokens": cache_1h,
                },
                "service_tier": "standard",
            },
        },
        "uuid": uuid,
        "timestamp": "2026-02-01T10:00:00.000Z",
    }


def _make_user_msg(uuid, parent_uuid=None, content="Hello"):
    return {
        "parentUuid": parent_uuid,
        "isSidechain": False,
        "userType": "external",
        "cwd": "/tmp",
        "sessionId": "test-session",
        "version": "2.1.29",
        "type": "user",
        "message": {"role": "user", "content": content},
        "uuid": uuid,
        "timestamp": "2026-02-01T10:00:00.000Z",
    }


class TestTokenCounting:
    """Verify token_count includes all token types."""

    def test_token_count_includes_all_fields(self):
        lines = [
            _make_user_msg("u1"),
            _make_assistant_msg(
                api_msg_id="msg_1",
                uuid="a1",
                parent_uuid="u1",
                model="claude-sonnet-4-5-20250929",
                input_tokens=100,
                output_tokens=50,
                cache_creation=2000,
                cache_read=5000,
                cache_1h=2000,
            ),
        ]
        path = _write_jsonl(lines)
        parser = JSONLParser()
        _, msgs = parser.parse_conversation_file(path)

        assistant = [m for m in msgs if m.role == "assistant"][0]
        assert assistant.token_count == 100 + 50 + 2000 + 5000

    def test_zero_tokens_for_user_messages(self):
        lines = [
            _make_user_msg("u1"),
            _make_assistant_msg(
                api_msg_id="msg_1",
                uuid="a1",
                parent_uuid="u1",
                model="claude-sonnet-4-5-20250929",
                input_tokens=100,
                output_tokens=50,
                cache_creation=0,
                cache_read=0,
            ),
        ]
        path = _write_jsonl(lines)
        parser = JSONLParser()
        _, msgs = parser.parse_conversation_file(path)

        user = [m for m in msgs if m.role == "user"][0]
        assert user.token_count == 0
        assert user.cost_usd == 0.0


class TestCostCalculation:
    """Verify cost uses correct pricing multipliers."""

    def test_1h_cache_write_uses_2x_multiplier(self):
        lines = [
            _make_user_msg("u1"),
            _make_assistant_msg(
                api_msg_id="msg_1",
                uuid="a1",
                parent_uuid="u1",
                model="claude-sonnet-4-5-20250929",
                input_tokens=0,
                output_tokens=0,
                cache_creation=1_000_000,
                cache_read=0,
                cache_5m=0,
                cache_1h=1_000_000,
            ),
        ]
        path = _write_jsonl(lines)
        parser = JSONLParser()
        _, msgs = parser.parse_conversation_file(path)

        assistant = [m for m in msgs if m.role == "assistant"][0]
        base = CLAUDE_PRICING["claude-sonnet-4-5-20250929"]["input"]
        expected = base * CACHE_WRITE_1H_MULTIPLIER  # 1M tokens at 2×
        assert abs(assistant.cost_usd - expected) < 1e-6

    def test_5m_cache_write_uses_125x_multiplier(self):
        lines = [
            _make_user_msg("u1"),
            _make_assistant_msg(
                api_msg_id="msg_1",
                uuid="a1",
                parent_uuid="u1",
                model="claude-sonnet-4-5-20250929",
                input_tokens=0,
                output_tokens=0,
                cache_creation=1_000_000,
                cache_read=0,
                cache_5m=1_000_000,
                cache_1h=0,
            ),
        ]
        path = _write_jsonl(lines)
        parser = JSONLParser()
        _, msgs = parser.parse_conversation_file(path)

        assistant = [m for m in msgs if m.role == "assistant"][0]
        base = CLAUDE_PRICING["claude-sonnet-4-5-20250929"]["input"]
        expected = base * CACHE_WRITE_5M_MULTIPLIER  # 1M tokens at 1.25×
        assert abs(assistant.cost_usd - expected) < 1e-6

    def test_cache_read_uses_01x_multiplier(self):
        lines = [
            _make_user_msg("u1"),
            _make_assistant_msg(
                api_msg_id="msg_1",
                uuid="a1",
                parent_uuid="u1",
                model="claude-sonnet-4-5-20250929",
                input_tokens=0,
                output_tokens=0,
                cache_creation=0,
                cache_read=1_000_000,
            ),
        ]
        path = _write_jsonl(lines)
        parser = JSONLParser()
        _, msgs = parser.parse_conversation_file(path)

        assistant = [m for m in msgs if m.role == "assistant"][0]
        base = CLAUDE_PRICING["claude-sonnet-4-5-20250929"]["input"]
        expected = base * CACHE_READ_MULTIPLIER  # 1M tokens at 0.1×
        assert abs(assistant.cost_usd - expected) < 1e-6

    def test_mixed_cost_calculation(self):
        """Verify a realistic message with all token types."""
        lines = [
            _make_user_msg("u1"),
            _make_assistant_msg(
                api_msg_id="msg_1",
                uuid="a1",
                parent_uuid="u1",
                model="claude-sonnet-4-5-20250929",
                input_tokens=10,
                output_tokens=8,
                cache_creation=5041,
                cache_read=15364,
                cache_5m=0,
                cache_1h=5041,
            ),
        ]
        path = _write_jsonl(lines)
        parser = JSONLParser()
        _, msgs = parser.parse_conversation_file(path)

        assistant = [m for m in msgs if m.role == "assistant"][0]
        # Manual: (10/1M)*3 + (8/1M)*15 + (5041/1M)*3*2 + (15364/1M)*3*0.1
        expected = (
            (10 / 1e6) * 3.0
            + (8 / 1e6) * 15.0
            + (5041 / 1e6) * 3.0 * 2.0
            + (15364 / 1e6) * 3.0 * 0.1
        )
        assert abs(assistant.cost_usd - expected) < 1e-9

    def test_haiku_pricing(self):
        lines = [
            _make_user_msg("u1"),
            _make_assistant_msg(
                api_msg_id="msg_1",
                uuid="a1",
                parent_uuid="u1",
                model="claude-haiku-4-5-20251001",
                input_tokens=1000,
                output_tokens=500,
                cache_creation=0,
                cache_read=0,
            ),
        ]
        path = _write_jsonl(lines)
        parser = JSONLParser()
        _, msgs = parser.parse_conversation_file(path)

        assistant = [m for m in msgs if m.role == "assistant"][0]
        expected = (1000 / 1e6) * 1.0 + (500 / 1e6) * 5.0
        assert abs(assistant.cost_usd - expected) < 1e-9


class TestChunkDeduplication:
    """Verify usage is counted only once per API message ID."""

    def test_duplicate_chunks_counted_once(self):
        """Multiple JSONL lines with same API message ID should count usage once."""
        lines = [
            _make_user_msg("u1"),
            # Two chunks of the same API message (thinking + tool_use)
            _make_assistant_msg(
                api_msg_id="msg_1",
                uuid="a1",
                parent_uuid="u1",
                model="claude-sonnet-4-5-20250929",
                input_tokens=100,
                output_tokens=50,
                cache_creation=2000,
                cache_read=5000,
                cache_1h=2000,
                content_type="text",
                content_text="Let me check.",
            ),
            _make_assistant_msg(
                api_msg_id="msg_1",
                uuid="a2",
                parent_uuid="a1",
                model="claude-sonnet-4-5-20250929",
                input_tokens=100,
                output_tokens=50,
                cache_creation=2000,
                cache_read=5000,
                cache_1h=2000,
                content_type="tool_use",
            ),
        ]
        path = _write_jsonl(lines)
        parser = JSONLParser()
        _, msgs = parser.parse_conversation_file(path)

        assistants = [m for m in msgs if m.role == "assistant"]
        assert len(assistants) == 2

        # Only the first chunk should have usage
        assert assistants[0].token_count == 100 + 50 + 2000 + 5000
        assert assistants[0].cost_usd > 0

        # Second chunk should be zeroed out
        assert assistants[1].token_count == 0
        assert assistants[1].cost_usd == 0.0

    def test_different_api_messages_counted_separately(self):
        """Different API message IDs should each count usage."""
        lines = [
            _make_user_msg("u1"),
            _make_assistant_msg(
                api_msg_id="msg_1",
                uuid="a1",
                parent_uuid="u1",
                model="claude-sonnet-4-5-20250929",
                input_tokens=100,
                output_tokens=50,
                cache_creation=0,
                cache_read=0,
            ),
            _make_user_msg("u2", parent_uuid="a1", content="Thanks"),
            _make_assistant_msg(
                api_msg_id="msg_2",
                uuid="a2",
                parent_uuid="u2",
                model="claude-sonnet-4-5-20250929",
                input_tokens=200,
                output_tokens=80,
                cache_creation=0,
                cache_read=0,
            ),
        ]
        path = _write_jsonl(lines)
        parser = JSONLParser()
        _, msgs = parser.parse_conversation_file(path)

        assistants = [m for m in msgs if m.role == "assistant"]
        assert assistants[0].token_count == 150
        assert assistants[1].token_count == 280


class TestSkipTypes:
    """Verify non-message types are skipped."""

    def test_queue_operation_skipped(self):
        lines = [
            {"type": "queue-operation", "operation": "dequeue",
             "timestamp": "2026-02-01T10:00:00.000Z", "sessionId": "s1"},
            _make_user_msg("u1"),
        ]
        path = _write_jsonl(lines)
        parser = JSONLParser()
        _, msgs = parser.parse_conversation_file(path)

        assert len(msgs) == 1
        assert msgs[0].role == "user"

    def test_progress_skipped(self):
        lines = [
            _make_user_msg("u1"),
            {"type": "progress", "data": {"type": "bash_progress", "output": "ok"},
             "uuid": "p1", "timestamp": "2026-02-01T10:00:00.000Z"},
        ]
        path = _write_jsonl(lines)
        parser = JSONLParser()
        _, msgs = parser.parse_conversation_file(path)

        assert len(msgs) == 1

    def test_file_history_snapshot_skipped(self):
        lines = [
            _make_user_msg("u1"),
            {"type": "file-history-snapshot", "messageId": "u1",
             "snapshot": {"messageId": "u1", "trackedFileBackups": {},
                          "timestamp": "2026-02-01T10:00:00.000Z"},
             "isSnapshotUpdate": False},
        ]
        path = _write_jsonl(lines)
        parser = JSONLParser()
        _, msgs = parser.parse_conversation_file(path)

        assert len(msgs) == 1

    def test_system_skipped(self):
        lines = [
            _make_user_msg("u1"),
            {"type": "system", "subtype": "stop_hook_summary",
             "uuid": "s1", "timestamp": "2026-02-01T10:00:00.000Z"},
        ]
        path = _write_jsonl(lines)
        parser = JSONLParser()
        _, msgs = parser.parse_conversation_file(path)

        assert len(msgs) == 1


class TestMetadataExtraction:
    """Verify metadata is extracted from new format fields."""

    def test_session_id_from_message(self):
        lines = [_make_user_msg("u1")]
        path = _write_jsonl(lines)
        parser = JSONLParser()
        meta, _ = parser.parse_conversation_file(path)

        assert meta.session_id == "test-session"

    def test_slug_extracted(self):
        msg = _make_user_msg("u1")
        msg["slug"] = "jiggly-sparking-waffle"
        lines = [msg]
        path = _write_jsonl(lines)
        parser = JSONLParser()
        meta, _ = parser.parse_conversation_file(path)

        assert meta.slug == "jiggly-sparking-waffle"

    def test_version_extracted(self):
        lines = [_make_user_msg("u1")]
        path = _write_jsonl(lines)
        parser = JSONLParser()
        meta, _ = parser.parse_conversation_file(path)

        assert meta.version == "2.1.29"


class TestExampleFiles:
    """Integration tests against actual example files."""

    def test_parse_example_session(self):
        path = Path("examples/9b8d23a2-1b9e-4aad-bf33-2f7b0147cd95.jsonl")
        if not path.exists():
            return  # skip if examples not available

        parser = JSONLParser()
        meta, msgs = parser.parse_conversation_file(path)

        assert meta.session_id == "9b8d23a2-1b9e-4aad-bf33-2f7b0147cd95"
        assert len(msgs) == 245

        # Verify first API message cost manually
        first_assistant = next(m for m in msgs if m.role == "assistant" and m.token_count > 0)
        expected_cost = (
            (10 / 1e6) * 3.0           # input
            + (8 / 1e6) * 15.0         # output
            + (5041 / 1e6) * 3.0 * 2.0 # 1h cache write
            + (15364 / 1e6) * 3.0 * 0.1  # cache read
        )
        assert abs(first_assistant.cost_usd - expected_cost) < 1e-9
        assert first_assistant.token_count == 10 + 8 + 5041 + 15364

    def test_parse_subagent_session(self):
        path = Path("examples/53b2584d-c767-4e34-8357-17cd17861dd2/subagents/agent-acda2e8.jsonl")
        if not path.exists():
            return

        parser = JSONLParser()
        meta, msgs = parser.parse_conversation_file(path)

        assert meta.is_subagent is True
        assert meta.agent_id == "acda2e8"
        assert meta.parent_session_id == "53b2584d-c767-4e34-8357-17cd17861dd2"
