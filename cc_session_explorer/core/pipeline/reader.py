"""
JSONL file reader stage.

Reads raw entries from JSONL conversation files, shared by both
parse_conversation_file and parse_metadata_only.
"""

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class RawEntry:
    """A single parsed JSON object from a JSONL file."""
    data: dict[str, Any]
    line_number: int


def read_jsonl(file_path: Path) -> list[RawEntry]:
    """Read all valid JSON entries from a JSONL file.

    Skips blank lines and logs warnings for invalid JSON.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If no valid entries are found.
    """
    if not file_path.exists() or not file_path.is_file():
        raise FileNotFoundError(f"Conversation file not found: {file_path}")

    entries = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    entries.append(RawEntry(data=data, line_number=line_num))
                except json.JSONDecodeError as e:
                    logger.warning(f"Invalid JSON on line {line_num} in {file_path}: {e}")
                    continue
    except json.JSONDecodeError:
        raise
    except FileNotFoundError:
        raise
    except Exception as e:
        logger.error(f"Error reading file {file_path}: {e}")
        raise

    if not entries:
        raise ValueError(f"No valid messages found in {file_path}")

    return entries
