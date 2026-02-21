"""Tests for the JSONL reader pipeline stage."""

import json
import tempfile
from pathlib import Path

import pytest

from cc_session_explorer.core.pipeline.reader import read_jsonl, RawEntry


def _write_file(content: str, suffix=".jsonl") -> Path:
    f = tempfile.NamedTemporaryFile(mode="w", suffix=suffix, delete=False)
    f.write(content)
    f.close()
    return Path(f.name)


class TestReadJsonl:
    def test_reads_valid_entries(self):
        content = (
            json.dumps({"type": "user", "uuid": "u1"}) + "\n"
            + json.dumps({"type": "assistant", "uuid": "a1"}) + "\n"
        )
        path = _write_file(content)
        entries = read_jsonl(path)

        assert len(entries) == 2
        assert entries[0].data["uuid"] == "u1"
        assert entries[0].line_number == 1
        assert entries[1].data["uuid"] == "a1"
        assert entries[1].line_number == 2

    def test_skips_blank_lines(self):
        content = (
            json.dumps({"type": "user"}) + "\n"
            + "\n"
            + "   \n"
            + json.dumps({"type": "assistant"}) + "\n"
        )
        path = _write_file(content)
        entries = read_jsonl(path)

        assert len(entries) == 2

    def test_skips_invalid_json(self):
        content = (
            json.dumps({"type": "user"}) + "\n"
            + "not valid json\n"
            + json.dumps({"type": "assistant"}) + "\n"
        )
        path = _write_file(content)
        entries = read_jsonl(path)

        assert len(entries) == 2

    def test_raises_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            read_jsonl(Path("/nonexistent/path.jsonl"))

    def test_raises_on_empty_file(self):
        path = _write_file("")
        with pytest.raises(ValueError, match="No valid messages"):
            read_jsonl(path)

    def test_raises_on_all_invalid_json(self):
        path = _write_file("not json\nalso not json\n")
        with pytest.raises(ValueError, match="No valid messages"):
            read_jsonl(path)

    def test_line_numbers_account_for_blanks(self):
        content = (
            "\n"  # line 1 blank
            + json.dumps({"type": "user"}) + "\n"  # line 2
            + "\n"  # line 3 blank
            + json.dumps({"type": "assistant"}) + "\n"  # line 4
        )
        path = _write_file(content)
        entries = read_jsonl(path)

        assert entries[0].line_number == 2
        assert entries[1].line_number == 4
