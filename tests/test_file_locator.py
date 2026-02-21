"""Tests for SessionFileLocator."""

import json
import tempfile
from pathlib import Path

from cc_session_explorer.core.file_locator import SessionFileLocator


def _create_jsonl(directory: Path, name: str) -> Path:
    """Create a minimal JSONL file."""
    path = directory / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"type": "user", "message": {"role": "user", "content": "hi"}}) + "\n")
    return path


class TestFindMainSessions:
    def test_finds_jsonl_files(self, tmp_path):
        _create_jsonl(tmp_path, "session-1.jsonl")
        _create_jsonl(tmp_path, "session-2.jsonl")

        locator = SessionFileLocator()
        results = locator.find_main_sessions(tmp_path)

        assert len(results) == 2
        names = {r.session_id for r in results}
        assert names == {"session-1", "session-2"}
        assert all(not r.is_subagent for r in results)

    def test_excludes_agent_files(self, tmp_path):
        _create_jsonl(tmp_path, "session-1.jsonl")
        _create_jsonl(tmp_path, "agent-abc123.jsonl")

        locator = SessionFileLocator()
        results = locator.find_main_sessions(tmp_path)

        assert len(results) == 1
        assert results[0].session_id == "session-1"

    def test_empty_directory(self, tmp_path):
        locator = SessionFileLocator()
        results = locator.find_main_sessions(tmp_path)
        assert results == []


class TestFindSubagentFiles:
    def test_finds_new_format_subagents(self, tmp_path):
        parent_id = "abc-123"
        _create_jsonl(tmp_path, f"{parent_id}/subagents/agent-xyz.jsonl")

        locator = SessionFileLocator()
        results = locator.find_subagent_files(tmp_path, parent_id=parent_id)

        assert len(results) == 1
        assert results[0].session_id == "agent-xyz"
        assert results[0].is_subagent is True
        assert results[0].parent_session_id == parent_id

    def test_finds_legacy_format_subagents(self, tmp_path):
        _create_jsonl(tmp_path, "agent-legacy.jsonl")

        locator = SessionFileLocator()
        results = locator.find_subagent_files(tmp_path, parent_id="some-parent")

        assert len(results) == 1
        assert results[0].session_id == "agent-legacy"
        assert results[0].is_subagent is True

    def test_finds_all_subagents_without_parent_filter(self, tmp_path):
        _create_jsonl(tmp_path, "parent-1/subagents/agent-a.jsonl")
        _create_jsonl(tmp_path, "parent-2/subagents/agent-b.jsonl")
        _create_jsonl(tmp_path, "agent-c.jsonl")

        locator = SessionFileLocator()
        results = locator.find_subagent_files(tmp_path)

        assert len(results) == 3
        assert all(r.is_subagent for r in results)

    def test_derives_parent_id_from_directory(self, tmp_path):
        _create_jsonl(tmp_path, "my-session/subagents/agent-foo.jsonl")

        locator = SessionFileLocator()
        results = locator.find_subagent_files(tmp_path)

        new_format = [r for r in results if r.session_id == "agent-foo" and r.parent_session_id == "my-session"]
        assert len(new_format) == 1

    def test_no_subagents(self, tmp_path):
        _create_jsonl(tmp_path, "session.jsonl")

        locator = SessionFileLocator()
        results = locator.find_subagent_files(tmp_path, parent_id="session")

        assert results == []
