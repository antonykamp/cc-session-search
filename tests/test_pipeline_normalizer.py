"""Tests for the normalizer pipeline stage."""

import tempfile
from datetime import datetime, timezone
from pathlib import Path

from cc_session_explorer.core.models import (
    TextBlock,
    ThinkingBlock,
    ToolCallBlock,
    ToolResultBlock,
)
from cc_session_explorer.core.pipeline.reader import RawEntry
from cc_session_explorer.core.pipeline.normalizer import (
    normalize_entries,
    fix_missing_timestamps,
    SKIP_TYPES,
)


def _entry(data, line=1):
    return RawEntry(data=data, line_number=line)


class TestSkipTypes:
    def test_skips_queue_operation(self):
        entries = [_entry({"type": "queue-operation"})]
        result = normalize_entries(entries)
        assert result == []

    def test_skips_progress(self):
        entries = [_entry({"type": "progress"})]
        result = normalize_entries(entries)
        assert result == []

    def test_skips_file_history_snapshot(self):
        entries = [_entry({"type": "file-history-snapshot"})]
        result = normalize_entries(entries)
        assert result == []

    def test_skips_system(self):
        entries = [_entry({"type": "system"})]
        result = normalize_entries(entries)
        assert result == []

    def test_keeps_user_messages(self):
        entries = [_entry({
            "type": "user",
            "uuid": "u1",
            "message": {"role": "user", "content": "hello"},
            "timestamp": "2026-01-01T00:00:00Z",
        })]
        result = normalize_entries(entries)
        assert len(result) == 1
        assert result[0].role == "user"


class TestRoleReclassification:
    def test_reclassifies_tool_result_content_blocks(self):
        entries = [_entry({
            "type": "user",
            "uuid": "tr1",
            "message": {
                "role": "user",
                "content": [{"type": "tool_result", "tool_use_id": "abc", "content": "result"}],
            },
            "timestamp": "2026-01-01T00:00:00Z",
        })]
        result = normalize_entries(entries)
        assert result[0].role == "tool"

    def test_reclassifies_toolUseResult(self):
        entries = [_entry({
            "type": "user",
            "uuid": "tr2",
            "message": {"role": "user", "content": ""},
            "toolUseResult": {"output": "success"},
            "timestamp": "2026-01-01T00:00:00Z",
        })]
        result = normalize_entries(entries)
        assert result[0].role == "tool"

    def test_keeps_regular_user_as_user(self):
        entries = [_entry({
            "type": "user",
            "uuid": "u1",
            "message": {"role": "user", "content": "hello"},
            "timestamp": "2026-01-01T00:00:00Z",
        })]
        result = normalize_entries(entries)
        assert result[0].role == "user"


class TestContentBlockExtraction:
    def test_extracts_text_blocks(self):
        entries = [_entry({
            "type": "assistant",
            "uuid": "a1",
            "message": {
                "role": "assistant",
                "content": [{"type": "text", "text": "Hello world"}],
            },
            "timestamp": "2026-01-01T00:00:00Z",
        })]
        result = normalize_entries(entries)
        assert len(result[0].blocks) == 1
        assert isinstance(result[0].blocks[0], TextBlock)
        assert result[0].blocks[0].text == "Hello world"

    def test_extracts_thinking_blocks(self):
        entries = [_entry({
            "type": "assistant",
            "uuid": "a1",
            "message": {
                "role": "assistant",
                "content": [{"type": "thinking", "thinking": "Let me think..."}],
            },
            "timestamp": "2026-01-01T00:00:00Z",
        })]
        result = normalize_entries(entries)
        assert len(result[0].blocks) == 1
        assert isinstance(result[0].blocks[0], ThinkingBlock)
        assert result[0].blocks[0].text == "Let me think..."

    def test_extracts_tool_call_blocks(self):
        entries = [_entry({
            "type": "assistant",
            "uuid": "a1",
            "message": {
                "role": "assistant",
                "content": [{"type": "tool_use", "id": "t1", "name": "Read", "input": {"path": "/tmp"}}],
            },
            "timestamp": "2026-01-01T00:00:00Z",
        })]
        result = normalize_entries(entries)
        tool_blocks = [b for b in result[0].blocks if isinstance(b, ToolCallBlock)]
        assert len(tool_blocks) == 1
        assert tool_blocks[0].tool_name == "Read"
        assert tool_blocks[0].tool_id == "t1"

    def test_extracts_tool_result_blocks(self):
        entries = [_entry({
            "type": "user",
            "uuid": "tr1",
            "message": {
                "role": "user",
                "content": [{"type": "tool_result", "tool_use_id": "t1", "content": "file data"}],
            },
            "timestamp": "2026-01-01T00:00:00Z",
        })]
        result = normalize_entries(entries)
        result_blocks = [b for b in result[0].blocks if isinstance(b, ToolResultBlock)]
        assert len(result_blocks) == 1
        assert result_blocks[0].tool_use_id == "t1"

    def test_string_content_becomes_text_block(self):
        entries = [_entry({
            "type": "user",
            "uuid": "u1",
            "message": {"role": "user", "content": "plain text"},
            "timestamp": "2026-01-01T00:00:00Z",
        })]
        result = normalize_entries(entries)
        assert len(result[0].blocks) == 1
        assert isinstance(result[0].blocks[0], TextBlock)


class TestToolCallPlaceholderContent:
    def test_single_tool_call_placeholder(self):
        entries = [_entry({
            "type": "assistant",
            "uuid": "a1",
            "message": {
                "role": "assistant",
                "content": [{"type": "tool_use", "id": "t1", "name": "Read", "input": {}}],
            },
            "timestamp": "2026-01-01T00:00:00Z",
        })]
        result = normalize_entries(entries)
        assert result[0].content == "[Calling tool: Read]"

    def test_multi_tool_call_placeholder(self):
        entries = [_entry({
            "type": "assistant",
            "uuid": "a1",
            "message": {
                "role": "assistant",
                "content": [
                    {"type": "tool_use", "id": "t1", "name": "Read", "input": {}},
                    {"type": "tool_use", "id": "t2", "name": "Bash", "input": {}},
                ],
            },
            "timestamp": "2026-01-01T00:00:00Z",
        })]
        result = normalize_entries(entries)
        assert result[0].content == "[Calling 2 tools: Read, Bash]"


class TestTimestampParsing:
    def test_parses_iso_timestamp(self):
        entries = [_entry({
            "type": "user",
            "uuid": "u1",
            "message": {"role": "user", "content": "hi"},
            "timestamp": "2026-02-01T10:00:00.000Z",
        })]
        result = normalize_entries(entries)
        assert result[0].timestamp is not None
        assert result[0].timestamp.year == 2026

    def test_missing_timestamp_is_none(self):
        entries = [_entry({
            "type": "user",
            "uuid": "u1",
            "message": {"role": "user", "content": "hi"},
        })]
        result = normalize_entries(entries)
        assert result[0].timestamp is None


class TestFixMissingTimestamps:
    def test_fills_from_next_message(self, tmp_path):
        jsonl = tmp_path / "test.jsonl"
        jsonl.write_text("{}")

        entries = [_entry({
            "type": "user",
            "uuid": "u1",
            "message": {"role": "user", "content": "hi"},
        })]
        msgs = normalize_entries(entries)
        assert msgs[0].timestamp is None

        fixed = fix_missing_timestamps(msgs, jsonl)
        assert fixed[0].timestamp is not None

    def test_empty_list_is_noop(self, tmp_path):
        jsonl = tmp_path / "test.jsonl"
        jsonl.write_text("{}")

        result = fix_missing_timestamps([], jsonl)
        assert result == []
