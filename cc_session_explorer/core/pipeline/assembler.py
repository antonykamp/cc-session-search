"""
Assembly stage.

Extracts conversation metadata from raw entries and assembles
NormalizedMessages into ParsedMessage instances.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from cc_session_explorer.core.models import TokenUsage
from cc_session_explorer.core.pipeline.reader import RawEntry
from cc_session_explorer.core.pipeline.normalizer import NormalizedMessage

logger = logging.getLogger(__name__)


def extract_metadata(file_path: Path, entries: list[RawEntry]):
    """Extract ConversationMetadata from file path and raw entries.

    Returns a ConversationMetadata instance. Import is deferred to
    avoid circular imports with conversation_parser.
    """
    from cc_session_explorer.core.conversation_parser import ConversationMetadata

    raw_messages = [e.data for e in entries]

    # Determine project path and name based on file location
    if file_path.parent.name == 'subagents':
        project_path = str(file_path.parent.parent.parent)
        project_name = file_path.parent.parent.parent.name
    else:
        project_path = str(file_path.parent)
        project_name = file_path.parent.name

    # Prefer sessionId from messages over filename stem
    session_id = file_path.stem
    if file_path.parent.name != 'subagents':
        for msg in raw_messages:
            if 'sessionId' in msg and msg['sessionId']:
                session_id = msg['sessionId']
                break

    git_branch = None
    working_directory = None
    slug = None
    version = None

    is_subagent = False
    parent_session_id = None
    agent_id = None
    agent_type = None

    for msg in raw_messages:
        if 'gitBranch' in msg and msg['gitBranch'] and not git_branch:
            git_branch = msg['gitBranch']
        if 'cwd' in msg and msg['cwd'] and not working_directory:
            working_directory = msg['cwd']
        if 'slug' in msg and msg['slug'] and not slug:
            slug = msg['slug']
        if 'version' in msg and msg['version'] and not version:
            version = msg['version']

        if not is_subagent and msg.get('agentId'):
            is_subagent = True
            agent_id = msg.get('agentId')
            parent_session_id = msg.get('sessionId')

            message_data = msg.get('message', {})
            if message_data.get('role') == 'assistant':
                content = message_data.get('content', [])
                if isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get('type') == 'text':
                            text = block.get('text', '')
                            if 'explore' in text.lower() or 'exploration' in text.lower():
                                agent_type = 'Explore'
                            elif 'plan' in text.lower():
                                agent_type = 'Plan'
                            elif 'claude code' in text.lower() or 'documentation' in text.lower():
                                agent_type = 'claude-code-guide'
                            break

    return ConversationMetadata(
        project_name=project_name,
        project_path=project_path,
        session_id=session_id,
        git_branch=git_branch,
        started_at=None,
        ended_at=None,
        working_directory=working_directory,
        message_count=0,
        file_path=str(file_path),
        slug=slug,
        version=version,
        is_subagent=is_subagent,
        parent_session_id=parent_session_id,
        agent_id=agent_id,
        agent_type=agent_type,
    )


def assemble_messages(normalized: list[NormalizedMessage], file_path: Path):
    """Assemble NormalizedMessages into ParsedMessage instances.

    Returns a list of ParsedMessage instances. Import is deferred to
    avoid circular imports with conversation_parser.
    """
    from cc_session_explorer.core.conversation_parser import ParsedMessage

    messages = []
    for msg in normalized:
        usage: TokenUsage = msg.raw_metadata.pop('_enriched_usage', TokenUsage())

        # Add typed blocks to metadata for consumers that want them
        msg_metadata = dict(msg.raw_metadata)
        msg_metadata['blocks'] = msg.blocks

        messages.append(ParsedMessage(
            uuid=msg.uuid,
            role=msg.role,
            content=msg.content,
            timestamp=msg.timestamp,
            tool_uses=msg.tool_uses,
            metadata=msg_metadata,
            token_count=usage.total,
            cost_usd=usage.cost_usd,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cache_creation_tokens=usage.cache_creation_tokens,
            cache_read_tokens=usage.cache_read_tokens,
        ))
    return messages


def count_conversation_messages(entries: list[RawEntry]) -> int:
    """Quick count of actual conversation messages without full normalization."""
    return sum(1 for e in entries if e.data.get('type') in ('user', 'assistant'))


def extract_timestamps_from_entries(entries: list[RawEntry]) -> list[datetime]:
    """Extract all valid timestamps from raw entries."""
    timestamps = []
    for entry in entries:
        raw_ts = entry.data.get('timestamp')
        if raw_ts:
            try:
                ts = datetime.fromisoformat(raw_ts.replace('Z', '+00:00'))
                timestamps.append(ts)
            except (ValueError, TypeError):
                pass
    return timestamps
