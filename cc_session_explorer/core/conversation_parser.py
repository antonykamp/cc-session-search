"""
JSONL Parser for Claude Code conversation files.

Handles parsing of conversation files with metadata extraction,
message processing, and tool use analysis.

This module is a thin coordinator that delegates to pipeline stages
in core/pipeline/. The public API (JSONLParser, ParsedMessage,
ConversationMetadata) remains unchanged.
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from datetime import datetime

# Re-export pricing constants for backward compatibility (used by tests)
from cc_session_explorer.core.pricing import (  # noqa: F401
    CLAUDE_PRICING,
    CACHE_WRITE_5M_MULTIPLIER,
    CACHE_WRITE_1H_MULTIPLIER,
    CACHE_READ_MULTIPLIER,
    PricingCalculator,
)
from cc_session_explorer.core.pipeline.reader import read_jsonl
from cc_session_explorer.core.pipeline.normalizer import normalize_entries, fix_missing_timestamps
from cc_session_explorer.core.pipeline.enricher import enrich_with_usage
from cc_session_explorer.core.pipeline.assembler import (
    extract_metadata,
    assemble_messages,
    count_conversation_messages,
    extract_timestamps_from_entries,
)

logger = logging.getLogger(__name__)


@dataclass
class ParsedMessage:
    """Represents a parsed message from a conversation."""
    uuid: str
    role: str  # 'user', 'assistant', 'system'
    content: str
    timestamp: Optional[datetime]
    tool_uses: Optional[Dict[str, Any]]
    metadata: Dict[str, Any]
    token_count: int = 0
    cost_usd: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_tokens: int = 0
    cache_read_tokens: int = 0


@dataclass
class ConversationMetadata:
    """Metadata extracted from a conversation file."""
    project_name: str
    project_path: str
    session_id: str
    git_branch: Optional[str]
    started_at: Optional[datetime]
    ended_at: Optional[datetime]
    working_directory: Optional[str]
    message_count: int
    file_path: str
    slug: Optional[str] = None
    version: Optional[str] = None
    # Subagent-related fields
    is_subagent: bool = False
    parent_session_id: Optional[str] = None
    agent_id: Optional[str] = None
    agent_type: Optional[str] = None
    subagent_ids: List[str] = None

    def __post_init__(self):
        """Initialize mutable default values."""
        if self.subagent_ids is None:
            self.subagent_ids = []


class JSONLParser:
    """Parser for Claude Code JSONL conversation files."""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._pricing = PricingCalculator()

    def parse_conversation_file(self, file_path: Path) -> Tuple[ConversationMetadata, List[ParsedMessage]]:
        """
        Parse a single JSONL conversation file.

        Args:
            file_path: Path to the JSONL file

        Returns:
            Tuple of (conversation_metadata, parsed_messages)
        """
        entries = read_jsonl(file_path)
        metadata = extract_metadata(file_path, entries)
        normalized = normalize_entries(entries, metadata.started_at)
        normalized = fix_missing_timestamps(normalized, file_path)
        enriched = enrich_with_usage(normalized, self._pricing)
        messages = assemble_messages(enriched, file_path)

        # Update metadata with final counts and timestamps
        if messages:
            metadata.message_count = len(messages)
            timestamps = [msg.timestamp for msg in messages if msg.timestamp]
            if timestamps:
                metadata.started_at = min(timestamps)
                metadata.ended_at = max(timestamps)

        return metadata, messages

    def parse_metadata_only(self, file_path: Path) -> Tuple[ConversationMetadata, int]:
        """
        Quick parse to extract only metadata without parsing all messages.
        Returns (metadata, message_count) - much faster than full parse.
        """
        entries = read_jsonl(file_path)
        metadata = extract_metadata(file_path, entries)

        message_count = count_conversation_messages(entries)

        timestamps = extract_timestamps_from_entries(entries)
        if timestamps:
            metadata.started_at = min(timestamps)
            metadata.ended_at = max(timestamps)

        metadata.message_count = message_count
        return metadata, message_count

    def extract_technical_events(self, messages: List[ParsedMessage]) -> List[Dict[str, Any]]:
        """
        Extract technical events from parsed messages.

        Returns list of technical events for later insertion into database.
        """
        events = []

        for msg in messages:
            if not msg.tool_uses:
                continue

            if 'tool_name' in msg.tool_uses:
                tool_name = msg.tool_uses['tool_name']

                event_type = self._map_tool_to_event_type(tool_name)
                if event_type:
                    event = {
                        'message_uuid': msg.uuid,
                        'event_type': event_type,
                        'timestamp': msg.timestamp,
                        'details': msg.tool_uses,
                        'file_path': msg.tool_uses.get('file_path')
                    }
                    events.append(event)

        return events

    def _map_tool_to_event_type(self, tool_name: str) -> Optional[str]:
        """Map tool names to standardized event types."""
        tool_mapping = {
            'Write': 'file_created',
            'Edit': 'file_modified',
            'MultiEdit': 'file_modified',
            'Read': 'file_accessed',
            'Bash': 'command_executed',
            'Grep': 'code_searched',
            'LS': 'directory_listed'
        }
        return tool_mapping.get(tool_name)


def parse_conversation_files(directory: Path) -> Tuple[List[ConversationMetadata], List[ParsedMessage]]:
    """
    Parse all JSONL conversation files in a directory.

    Args:
        directory: Directory containing conversation files

    Returns:
        Tuple of (all_conversations_metadata, all_messages)
    """
    parser = JSONLParser()
    all_conversations = []
    all_messages = []

    jsonl_files = list(directory.rglob("*.jsonl"))
    logger.info(f"Found {len(jsonl_files)} JSONL files in {directory}")

    for file_path in jsonl_files:
        try:
            conversation_metadata, messages = parser.parse_conversation_file(file_path)
            all_conversations.append(conversation_metadata)
            for message in messages:
                message.metadata['conversation_session_id'] = conversation_metadata.session_id
            all_messages.extend(messages)
            logger.debug(f"Parsed {len(messages)} messages from {file_path}")
        except Exception as e:
            logger.error(f"Failed to parse {file_path}: {e}")
            continue

    logger.info(f"Successfully parsed {len(all_conversations)} conversations with {len(all_messages)} total messages")
    return all_conversations, all_messages


def parse_conversation_files_grouped(directory: Path) -> List[Tuple[ConversationMetadata, List[ParsedMessage]]]:
    """
    Parse all JSONL conversation files in a directory, maintaining conversation-message grouping.

    Args:
        directory: Directory containing conversation files

    Returns:
        List of (conversation_metadata, messages) tuples
    """
    parser = JSONLParser()
    grouped_conversations = []

    jsonl_files = list(directory.rglob("*.jsonl"))
    logger.info(f"Found {len(jsonl_files)} JSONL files in {directory}")

    for file_path in jsonl_files:
        try:
            conversation_metadata, messages = parser.parse_conversation_file(file_path)
            grouped_conversations.append((conversation_metadata, messages))
            logger.debug(f"Parsed {len(messages)} messages from {file_path}")
        except Exception as e:
            logger.error(f"Failed to parse {file_path}: {e}")
            continue

    logger.info(f"Successfully parsed {len(grouped_conversations)} conversations")
    return grouped_conversations


if __name__ == "__main__":
    # Quick test
    import sys

    logging.basicConfig(level=logging.DEBUG)

    if len(sys.argv) > 1:
        test_path = Path(sys.argv[1])
        if test_path.is_file():
            parser = JSONLParser()
            metadata, messages = parser.parse_conversation_file(test_path)
            print(f"Project: {metadata.project_name}")
            print(f"Messages: {len(messages)}")
            print(f"Started: {metadata.started_at}")
            print(f"Ended: {metadata.ended_at}")
        else:
            conversations, messages = parse_conversation_files(test_path)
            print(f"Conversations: {len(conversations)}")
            print(f"Messages: {len(messages)}")
    else:
        print("Usage: python conversation_parser.py <file_or_directory>")
