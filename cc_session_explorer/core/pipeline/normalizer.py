"""
Message normalization stage.

Handles message type filtering, UUID extraction, timestamp parsing,
role reclassification, content block extraction, and tool use extraction.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, Union
from uuid import uuid4

from cc_session_explorer.core.models import (
    ContentBlock,
    TextBlock,
    ThinkingBlock,
    ToolCallBlock,
    ToolResultBlock,
)
from cc_session_explorer.core.pipeline.reader import RawEntry

logger = logging.getLogger(__name__)

# Message types that should be skipped during parsing
SKIP_TYPES = frozenset({'queue-operation', 'file-history-snapshot', 'progress', 'system'})


@dataclass
class NormalizedMessage:
    """Internal representation of a parsed message before enrichment."""
    uuid: str
    role: str
    blocks: list[ContentBlock]
    content: str
    timestamp: Optional[datetime]
    tool_uses: Optional[dict] = None
    raw_metadata: dict[str, Any] = field(default_factory=dict)
    api_msg_id: Optional[str] = None
    model: str = 'claude-sonnet-4-5-20250929'
    usage_data: dict[str, Any] = field(default_factory=dict)


def normalize_entries(entries: list[RawEntry], metadata_started_at: Optional[datetime] = None) -> list[NormalizedMessage]:
    """Normalize raw JSONL entries into structured messages.

    Args:
        entries: Raw JSONL entries from the reader stage.
        metadata_started_at: Conversation start time (for summary timestamp fallback).

    Returns:
        List of normalized messages (skipped types are filtered out).
    """
    messages = []
    for entry in entries:
        normalized = _normalize_entry(entry, metadata_started_at)
        if normalized is not None:
            messages.append(normalized)
    return messages


def _normalize_entry(entry: RawEntry, metadata_started_at: Optional[datetime]) -> Optional[NormalizedMessage]:
    """Normalize a single raw entry."""
    raw_msg = entry.data

    msg_type = raw_msg.get('type', 'unknown')

    # Skip non-message types
    if msg_type in SKIP_TYPES:
        return None

    # UUID extraction
    if msg_type == 'summary':
        msg_uuid = raw_msg.get('leafUuid', str(uuid4()))
    else:
        msg_uuid = raw_msg.get('uuid', str(uuid4()))

    # Timestamp parsing
    timestamp = _parse_timestamp(raw_msg, msg_type, metadata_started_at)

    # Message data and role
    if msg_type == 'summary':
        role = 'summary'
        message_data = {'content': raw_msg.get('summary', '')}
    else:
        message_data = raw_msg.get('message', {})
        role = message_data.get('role', msg_type)

    # Reclassify tool results
    role = _detect_tool_role(role, message_data, raw_msg)

    # Extract typed content blocks
    raw_content = message_data.get('content', '')
    blocks = _extract_content_blocks(raw_content, raw_msg, role)

    # Extract flattened text content (backward compat)
    content = _extract_content_text(raw_content)

    # Extract tool uses
    tool_uses = _extract_tool_uses(raw_msg, message_data, role, content)

    # If content is empty and we have tool calls, add placeholder
    if tool_uses and 'tool_calls' in tool_uses and not content.strip():
        tool_use_blocks = tool_uses['tool_calls']
        tool_names = [block.get('name', 'unknown') for block in tool_use_blocks]
        if len(tool_names) == 1:
            content = f"[Calling tool: {tool_names[0]}]"
        else:
            content = f"[Calling {len(tool_names)} tools: {', '.join(tool_names)}]"

    # Collect metadata
    is_meta = raw_msg.get('isMeta', False)
    model = message_data.get('model', 'claude-sonnet-4-5-20250929')
    api_msg_id = message_data.get('id')

    raw_metadata = {
        'original_type': msg_type,
        'cwd': raw_msg.get('cwd'),
        'git_branch': raw_msg.get('gitBranch'),
        'is_meta': is_meta,
        'model': model,
        'parent_uuid': raw_msg.get('parentUuid'),
        'is_sidechain': raw_msg.get('isSidechain', False),
        'agent_id': raw_msg.get('agentId'),
        'slug': raw_msg.get('slug'),
        'api_msg_id': api_msg_id,
    }

    usage_data = message_data.get('usage', {})

    return NormalizedMessage(
        uuid=msg_uuid,
        role=role,
        blocks=blocks,
        content=content,
        timestamp=timestamp,
        tool_uses=tool_uses,
        raw_metadata=raw_metadata,
        api_msg_id=api_msg_id,
        model=model,
        usage_data=usage_data,
    )


def _parse_timestamp(raw_msg: dict, msg_type: str, metadata_started_at: Optional[datetime]) -> Optional[datetime]:
    """Parse timestamp from a raw message."""
    if 'timestamp' in raw_msg and raw_msg['timestamp']:
        try:
            return datetime.fromisoformat(raw_msg['timestamp'].replace('Z', '+00:00'))
        except (ValueError, TypeError):
            pass
    elif msg_type == 'summary' and metadata_started_at:
        return metadata_started_at
    return None


def _detect_tool_role(role: str, message_data: dict, raw_msg: dict) -> str:
    """Detect and reclassify tool result messages."""
    if role != 'user':
        return role

    # Check for tool_result content blocks
    if isinstance(message_data.get('content'), list):
        content_blocks = message_data.get('content', [])
        if any(block.get('type') == 'tool_result' for block in content_blocks if isinstance(block, dict)):
            return 'tool'

    # Check for toolUseResult data
    if 'toolUseResult' in raw_msg:
        return 'tool'

    return role


def _extract_content_blocks(raw_content: Any, raw_msg: dict, role: str) -> list[ContentBlock]:
    """Extract typed content blocks from raw message content."""
    blocks: list[ContentBlock] = []

    if isinstance(raw_content, str):
        if raw_content:
            blocks.append(TextBlock(text=raw_content))
    elif isinstance(raw_content, list):
        for block in raw_content:
            if isinstance(block, dict):
                block_type = block.get('type')
                if block_type == 'text' and 'text' in block:
                    blocks.append(TextBlock(text=block['text']))
                elif block_type == 'thinking' and 'thinking' in block:
                    blocks.append(ThinkingBlock(text=block['thinking']))
                elif block_type == 'tool_use':
                    blocks.append(ToolCallBlock(
                        tool_name=block.get('name', 'unknown'),
                        tool_id=block.get('id', ''),
                        input=block.get('input', {}),
                    ))
                elif block_type == 'tool_result':
                    nested_content = block.get('content', '')
                    if isinstance(nested_content, list):
                        nested_content = '\n'.join(
                            b.get('text', str(b)) if isinstance(b, dict) else str(b)
                            for b in nested_content
                        )
                    elif not isinstance(nested_content, str):
                        nested_content = str(nested_content)
                    blocks.append(ToolResultBlock(
                        tool_use_id=block.get('tool_use_id', ''),
                        content=nested_content,
                        raw=block,
                    ))
            elif isinstance(block, str):
                blocks.append(TextBlock(text=block))
    elif isinstance(raw_content, dict):
        block_type = raw_content.get('type')
        if block_type == 'text' and 'text' in raw_content:
            blocks.append(TextBlock(text=raw_content['text']))
        elif block_type == 'thinking' and 'thinking' in raw_content:
            blocks.append(ThinkingBlock(text=raw_content['thinking']))

    # Also capture toolUseResult from top-level raw_msg
    if 'toolUseResult' in raw_msg and role == 'tool':
        tool_result_data = raw_msg['toolUseResult']
        # Extract tool_use_id from content blocks if present
        tool_use_id = ''
        if isinstance(raw_content, list):
            for block in raw_content:
                if isinstance(block, dict) and block.get('type') == 'tool_result' and 'tool_use_id' in block:
                    tool_use_id = block['tool_use_id']
                    break
        # Only add if we don't already have a ToolResultBlock
        if not any(isinstance(b, ToolResultBlock) for b in blocks):
            blocks.append(ToolResultBlock(
                tool_use_id=tool_use_id,
                content=str(tool_result_data) if not isinstance(tool_result_data, str) else tool_result_data,
                raw=tool_result_data if isinstance(tool_result_data, dict) else {'result': tool_result_data},
            ))

    return blocks


def _extract_content_text(content: Union[str, list, dict]) -> str:
    """Extract flattened text content from various content formats (backward compat)."""
    if isinstance(content, str):
        return content
    elif isinstance(content, list):
        text_parts = []
        for block in content:
            if isinstance(block, dict):
                block_type = block.get('type')
                if block_type == 'text' and 'text' in block:
                    text_parts.append(block['text'])
                elif block_type == 'thinking' and 'thinking' in block:
                    text_parts.append(f"[Thinking: {block['thinking']}]")
                elif 'content' in block:
                    text_parts.append(_extract_content_text(block['content']))
            elif isinstance(block, str):
                text_parts.append(block)
        return '\n'.join(text_parts)
    elif isinstance(content, dict):
        block_type = content.get('type')
        if block_type == 'text' and 'text' in content:
            return content['text']
        elif block_type == 'thinking' and 'thinking' in content:
            return f"[Thinking: {content['thinking']}]"
        elif 'content' in content:
            return _extract_content_text(content['content'])
        else:
            return str(content)
    else:
        return str(content) if content else ''


def _extract_tool_uses(raw_msg: dict, message_data: dict, role: str, content: str) -> Optional[dict]:
    """Extract tool use information from a message."""
    # For tool result messages, extract toolUseResult from top level
    if 'toolUseResult' in raw_msg:
        tool_uses = raw_msg['toolUseResult']
        if isinstance(message_data.get('content'), list):
            for block in message_data['content']:
                if isinstance(block, dict) and block.get('type') == 'tool_result':
                    if 'tool_use_id' in block:
                        if not isinstance(tool_uses, dict):
                            tool_uses = {}
                        tool_uses['tool_use_id'] = block['tool_use_id']
                        break
        return tool_uses

    # For assistant messages, extract tool_use blocks from content array
    if isinstance(message_data.get('content'), list):
        tool_use_blocks = [
            block for block in message_data['content']
            if isinstance(block, dict) and block.get('type') == 'tool_use'
        ]
        if tool_use_blocks:
            return {'tool_calls': tool_use_blocks}

    return None


def fix_missing_timestamps(messages: list[NormalizedMessage], file_path: Path) -> list[NormalizedMessage]:
    """Fix missing timestamps using next message timestamp or file modification time."""
    if not messages:
        return messages

    file_mtime = datetime.fromtimestamp(file_path.stat().st_mtime, tz=timezone.utc)

    for i, msg in enumerate(messages):
        if msg.timestamp is None:
            fallback_time = None
            for j in range(i + 1, len(messages)):
                if messages[j].timestamp:
                    fallback_time = messages[j].timestamp
                    break

            if fallback_time is None:
                fallback_time = file_mtime

            msg.timestamp = fallback_time

    return messages
