"""
JSONL Parser for Claude Code conversation files.

Handles parsing of conversation files with metadata extraction,
message processing, and tool use analysis.
"""

import json
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass
from uuid import uuid4

logger = logging.getLogger(__name__)

# Claude pricing per million tokens (as of Jan 2025)
# Source: https://www.anthropic.com/pricing
# Claude pricing per million tokens
# Source: https://platform.claude.com/docs/en/about-claude/pricing
# Cache pricing multipliers:
#   5-min cache write: 1.25× base input
#   1-hour cache write: 2× base input
#   Cache read: 0.1× base input
CLAUDE_PRICING = {
    'claude-opus-4-5-20251101': {'input': 5.00, 'output': 25.00},    # Claude Opus 4.5
    'claude-sonnet-4-5-20250929': {'input': 3.00, 'output': 15.00},  # Claude Sonnet 4.5
    'claude-haiku-4-5-20251001': {'input': 1.00, 'output': 5.00},    # Claude Haiku 4.5
    'claude-3-5-sonnet-20241022': {'input': 3.00, 'output': 15.00},  # Claude 3.5 Sonnet
    'claude-3-5-sonnet-20240620': {'input': 3.00, 'output': 15.00},  # Claude 3.5 Sonnet (older)
    'claude-3-opus-20240229': {'input': 15.00, 'output': 75.00},     # Claude 3 Opus
    'claude-3-sonnet-20240229': {'input': 3.00, 'output': 15.00},    # Claude 3 Sonnet
    'claude-3-haiku-20240307': {'input': 0.25, 'output': 1.25},      # Claude 3 Haiku
}

CACHE_WRITE_5M_MULTIPLIER = 1.25
CACHE_WRITE_1H_MULTIPLIER = 2.0
CACHE_READ_MULTIPLIER = 0.1


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
    agent_type: Optional[str] = None  # e.g., "Explore", "Plan", "claude-code-guide"
    subagent_ids: List[str] = None  # List of child agent IDs (for parent sessions)

    def __post_init__(self):
        """Initialize mutable default values."""
        if self.subagent_ids is None:
            self.subagent_ids = []


class JSONLParser:
    """Parser for Claude Code JSONL conversation files."""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def parse_conversation_file(self, file_path: Path) -> Tuple[ConversationMetadata, List[ParsedMessage]]:
        """
        Parse a single JSONL conversation file.

        Args:
            file_path: Path to the JSONL file

        Returns:
            Tuple of (conversation_metadata, parsed_messages)
        """
        if not file_path.exists() or not file_path.is_file():
            raise FileNotFoundError(f"Conversation file not found: {file_path}")

        messages = []
        raw_messages = []

        # Read all lines from JSONL file
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        raw_message = json.loads(line)
                        raw_messages.append(raw_message)
                    except json.JSONDecodeError as e:
                        self.logger.warning(f"Invalid JSON on line {line_num} in {file_path}: {e}")
                        continue
        except Exception as e:
            self.logger.error(f"Error reading file {file_path}: {e}")
            raise

        if not raw_messages:
            raise ValueError(f"No valid messages found in {file_path}")

        # Extract conversation metadata
        metadata = self._extract_conversation_metadata(file_path, raw_messages)

        # Parse individual messages
        # Track API message IDs to avoid double-counting usage for chunked responses
        seen_api_msg_ids = set()
        for raw_msg in raw_messages:
            try:
                parsed_msg = self._parse_message(raw_msg, metadata, seen_api_msg_ids)
                if parsed_msg:
                    messages.append(parsed_msg)
            except Exception as e:
                self.logger.warning(f"Error parsing message in {file_path}: {e}")
                continue

        # Fix missing timestamps
        messages = self._fix_missing_timestamps(messages, file_path)

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
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                raw_messages = []
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        raw_message = json.loads(line)
                        raw_messages.append(raw_message)
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            self.logger.error(f"Error reading file {file_path}: {e}")
            raise

        if not raw_messages:
            raise ValueError(f"No valid messages found in {file_path}")

        # Extract conversation metadata
        metadata = self._extract_conversation_metadata(file_path, raw_messages)

        # Count messages quickly (only actual conversation messages)
        message_count = sum(1 for msg in raw_messages
                           if msg.get('type') in ('user', 'assistant'))

        # Get timestamps from raw messages for metadata
        timestamps = []
        for msg in raw_messages:
            if 'timestamp' in msg and msg['timestamp']:
                try:
                    ts = datetime.fromisoformat(msg['timestamp'].replace('Z', '+00:00'))
                    timestamps.append(ts)
                except (ValueError, TypeError):
                    pass

        if timestamps:
            metadata.started_at = min(timestamps)
            metadata.ended_at = max(timestamps)

        metadata.message_count = message_count

        return metadata, message_count

    def _extract_conversation_metadata(self, file_path: Path, raw_messages: List[Dict]) -> ConversationMetadata:
        """Extract metadata from conversation file and messages."""
        # Project information from file path
        # New format: ~/.claude/projects/{encoded-project-name}/{uuid}.jsonl
        # Old format: ~/.claude/projects/{encoded-project-name}/conversation-{uuid}.jsonl
        # Subagent format: ~/.claude/projects/{encoded-project-name}/{uuid}/subagents/agent-{id}.jsonl

        # Determine project path and name based on file location
        # Subagent files are nested: {project}/{session_id}/subagents/agent-{id}.jsonl
        if file_path.parent.name == 'subagents':
            # Subagent file: project is 3 levels up
            project_path = str(file_path.parent.parent.parent)
            project_name = file_path.parent.parent.parent.name
        else:
            project_path = str(file_path.parent)
            project_name = file_path.parent.name

        # Prefer sessionId from messages over filename stem,
        # but NOT for subagent files (their sessionId points to the parent session)
        session_id = file_path.stem
        if file_path.parent.name != 'subagents':
            for msg in raw_messages:
                if 'sessionId' in msg and msg['sessionId']:
                    session_id = msg['sessionId']
                    break

        # Extract other metadata from first available message
        git_branch = None
        working_directory = None
        slug = None
        version = None

        # Subagent detection
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

            # Detect subagent from first message with sidechain flag or agentId
            if not is_subagent and msg.get('agentId'):
                is_subagent = True
                agent_id = msg.get('agentId')
                # Parent session ID is the sessionId field for subagents
                parent_session_id = msg.get('sessionId')

                # Try to extract agent type from message content or metadata
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
            started_at=None,  # Will be filled after parsing messages
            ended_at=None,    # Will be filled after parsing messages
            working_directory=working_directory,
            message_count=0,  # Will be filled after parsing messages
            file_path=str(file_path),
            slug=slug,
            version=version,
            is_subagent=is_subagent,
            parent_session_id=parent_session_id,
            agent_id=agent_id,
            agent_type=agent_type
        )

    # Message types that should be skipped during parsing (not actual conversation messages)
    SKIP_TYPES = {'queue-operation', 'file-history-snapshot', 'progress', 'system'}

    def _parse_message(self, raw_msg: Dict, metadata: ConversationMetadata, seen_api_msg_ids: set = None) -> Optional[ParsedMessage]:
        """Parse a single message from the JSONL format."""
        try:
            # Extract basic fields
            msg_type = raw_msg.get('type', 'unknown')

            # Skip non-message types (queue operations, progress updates, etc.)
            if msg_type in self.SKIP_TYPES:
                return None

            # Handle UUID differently for summary vs regular messages
            if msg_type == 'summary':
                msg_uuid = raw_msg.get('leafUuid', str(uuid4()))
            else:
                msg_uuid = raw_msg.get('uuid', str(uuid4()))

            # Parse timestamp
            timestamp = None
            if 'timestamp' in raw_msg and raw_msg['timestamp']:
                try:
                    # Handle ISO format timestamp
                    timestamp = datetime.fromisoformat(raw_msg['timestamp'].replace('Z', '+00:00'))
                except (ValueError, TypeError) as e:
                    self.logger.debug(f"Could not parse timestamp '{raw_msg.get('timestamp')}': {e}")
            elif msg_type == 'summary' and metadata.started_at:
                # Summary messages don't have timestamps, use conversation start time
                timestamp = metadata.started_at

            # Handle different message formats
            if msg_type == 'summary':
                # Summary messages have a different structure
                role = 'summary'
                message_data = {'content': raw_msg.get('summary', '')}
            else:
                # Regular messages have a 'message' field
                message_data = raw_msg.get('message', {})
                role = message_data.get('role', msg_type)

            # Detect and reclassify tool results as tool messages
            # Tool results have role='user' but contain tool_result content blocks or toolUseResult data
            is_tool_response = False

            # Check for tool_result content blocks
            if role == 'user' and isinstance(message_data.get('content'), list):
                content_blocks = message_data.get('content', [])
                if any(block.get('type') == 'tool_result' for block in content_blocks if isinstance(block, dict)):
                    is_tool_response = True

            # Also check for toolUseResult data (alternative tool response format)
            if role == 'user' and 'toolUseResult' in raw_msg:
                is_tool_response = True

            # Reclassify as tool message
            if is_tool_response:
                role = 'tool'

            # Handle content - can be string or array of content blocks
            content = self._extract_content(message_data.get('content', ''))

            # Extract tool uses if present
            tool_uses = None
            # For tool result messages (role='tool'), extract toolUseResult from top level
            if 'toolUseResult' in raw_msg:
                tool_uses = raw_msg['toolUseResult']
                # Also extract tool_use_id from content blocks
                if isinstance(message_data.get('content'), list):
                    for block in message_data['content']:
                        if isinstance(block, dict) and block.get('type') == 'tool_result':
                            if 'tool_use_id' in block:
                                # Ensure tool_uses is a dict before assignment
                                if not isinstance(tool_uses, dict):
                                    tool_uses = {}
                                tool_uses['tool_use_id'] = block['tool_use_id']
                                break
            # For assistant messages, extract tool_use blocks from content array
            elif isinstance(message_data.get('content'), list):
                tool_use_blocks = [block for block in message_data['content']
                                 if isinstance(block, dict) and block.get('type') == 'tool_use']
                if tool_use_blocks:
                    # Store tool use information
                    tool_uses = {
                        'tool_calls': tool_use_blocks
                    }

                    # If content is empty and we have tool calls, add a placeholder
                    if not content.strip():
                        tool_names = [block.get('name', 'unknown') for block in tool_use_blocks]
                        if len(tool_names) == 1:
                            content = f"[Calling tool: {tool_names[0]}]"
                        else:
                            content = f"[Calling {len(tool_names)} tools: {', '.join(tool_names)}]"

            # Check for meta messages
            is_meta = raw_msg.get('isMeta', False)

            # Extract model for cost calculation
            model = message_data.get('model', 'claude-sonnet-4-5-20250929')  # Default to latest

            # Extract actual token usage from API response
            # In the new format, a single API response is split into multiple JSONL lines
            # (one per content block: thinking, text, tool_use). Each line has the same
            # message.id and identical usage data. We must only count usage once per API message.
            api_msg_id = message_data.get('id')
            usage_already_counted = False
            if api_msg_id and seen_api_msg_ids is not None:
                if api_msg_id in seen_api_msg_ids:
                    usage_already_counted = True
                else:
                    seen_api_msg_ids.add(api_msg_id)

            usage = message_data.get('usage', {})
            input_tokens = usage.get('input_tokens', 0)
            output_tokens = usage.get('output_tokens', 0)
            cache_creation_tokens = usage.get('cache_creation_input_tokens', 0)
            cache_read_tokens = usage.get('cache_read_input_tokens', 0)

            # Extract cache TTL breakdown for accurate pricing
            cache_creation_detail = usage.get('cache_creation', {})
            cache_5m_tokens = cache_creation_detail.get('ephemeral_5m_input_tokens', 0)
            cache_1h_tokens = cache_creation_detail.get('ephemeral_1h_input_tokens', 0)

            # Calculate tokens and cost
            token_count = 0
            cost_usd = 0.0

            try:
                # Only count usage for assistant messages, and only once per API message ID
                if role == 'assistant' and (input_tokens > 0 or output_tokens > 0 or cache_creation_tokens > 0 or cache_read_tokens > 0) and not usage_already_counted:
                    token_count = input_tokens + output_tokens + cache_creation_tokens + cache_read_tokens

                    pricing = CLAUDE_PRICING.get(model, CLAUDE_PRICING['claude-sonnet-4-5-20250929'])
                    base_input_price = pricing['input']

                    input_cost = (input_tokens / 1_000_000) * base_input_price
                    output_cost = (output_tokens / 1_000_000) * pricing['output']

                    # Cache write cost depends on TTL
                    if cache_5m_tokens or cache_1h_tokens:
                        # Use TTL-specific breakdown when available
                        cache_creation_cost = (
                            (cache_5m_tokens / 1_000_000) * base_input_price * CACHE_WRITE_5M_MULTIPLIER +
                            (cache_1h_tokens / 1_000_000) * base_input_price * CACHE_WRITE_1H_MULTIPLIER
                        )
                    else:
                        # Fallback for older files without TTL breakdown: assume 5-min cache
                        cache_creation_cost = (cache_creation_tokens / 1_000_000) * base_input_price * CACHE_WRITE_5M_MULTIPLIER

                    cache_read_cost = (cache_read_tokens / 1_000_000) * base_input_price * CACHE_READ_MULTIPLIER

                    cost_usd = input_cost + output_cost + cache_creation_cost + cache_read_cost
                else:
                    token_count = 0
                    cost_usd = 0.0
                    input_tokens = 0
                    output_tokens = 0
                    cache_creation_tokens = 0
                    cache_read_tokens = 0
            except Exception as e:
                self.logger.debug(f"Could not calculate token cost: {e}")

            # Collect additional metadata
            msg_metadata = {
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

            return ParsedMessage(
                uuid=msg_uuid,
                role=role,
                content=content,
                timestamp=timestamp,
                tool_uses=tool_uses,
                metadata=msg_metadata,
                token_count=token_count,
                cost_usd=cost_usd,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cache_creation_tokens=cache_creation_tokens,
                cache_read_tokens=cache_read_tokens
            )

        except Exception as e:
            self.logger.error(f"Error parsing message: {e}")
            return None

    def _extract_content(self, content: Union[str, List, Dict]) -> str:
        """
        Extract text content from various content formats.

        Content can be:
        - String: direct text
        - List: array of content blocks
        - Dict: single content block
        """
        if isinstance(content, str):
            return content
        elif isinstance(content, list):
            # Multiple content blocks - concatenate text parts
            text_parts = []
            for block in content:
                if isinstance(block, dict):
                    block_type = block.get('type')
                    # Extract text blocks
                    if block_type == 'text' and 'text' in block:
                        text_parts.append(block['text'])
                    # Extract thinking blocks (internal reasoning)
                    elif block_type == 'thinking' and 'thinking' in block:
                        text_parts.append(f"[Thinking: {block['thinking']}]")
                    # Handle nested content
                    elif 'content' in block:
                        text_parts.append(self._extract_content(block['content']))
                    # Skip tool_use blocks (already extracted separately)
                elif isinstance(block, str):
                    text_parts.append(block)
            return '\n'.join(text_parts)
        elif isinstance(content, dict):
            # Single content block
            block_type = content.get('type')
            if block_type == 'text' and 'text' in content:
                return content['text']
            elif block_type == 'thinking' and 'thinking' in content:
                return f"[Thinking: {content['thinking']}]"
            elif 'content' in content:
                return self._extract_content(content['content'])
            else:
                return str(content)
        else:
            return str(content) if content else ''

    def _fix_missing_timestamps(self, messages: List[ParsedMessage], file_path: Path) -> List[ParsedMessage]:
        """
        Fix missing timestamps using next message timestamp or file modification time.

        Common issue: First message often lacks timestamp.
        """
        if not messages:
            return messages

        # Get file modification time as fallback (make it timezone-aware UTC)
        file_mtime = datetime.fromtimestamp(file_path.stat().st_mtime, tz=timezone.utc)

        for i, msg in enumerate(messages):
            if msg.timestamp is None:
                # Try to use next message's timestamp
                fallback_time = None
                for j in range(i + 1, len(messages)):
                    if messages[j].timestamp:
                        fallback_time = messages[j].timestamp
                        break

                # If no later timestamp found, use file modification time
                if fallback_time is None:
                    fallback_time = file_mtime

                # Create new message with estimated timestamp
                messages[i] = ParsedMessage(
                    uuid=msg.uuid,
                    role=msg.role,
                    content=msg.content,
                    timestamp=fallback_time,
                    tool_uses=msg.tool_uses,
                    metadata=msg.metadata,
                    token_count=msg.token_count,
                    cost_usd=msg.cost_usd,
                    input_tokens=msg.input_tokens,
                    output_tokens=msg.output_tokens,
                    cache_creation_tokens=msg.cache_creation_tokens,
                    cache_read_tokens=msg.cache_read_tokens
                )

        return messages

    def extract_technical_events(self, messages: List[ParsedMessage]) -> List[Dict[str, Any]]:
        """
        Extract technical events from parsed messages.

        Returns list of technical events for later insertion into database.
        """
        events = []

        for msg in messages:
            if not msg.tool_uses:
                continue

            # Extract file operations
            if 'tool_name' in msg.tool_uses:
                tool_name = msg.tool_uses['tool_name']

                # Map tool names to event types
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

    # Find all JSONL files
    jsonl_files = list(directory.rglob("*.jsonl"))
    logger.info(f"Found {len(jsonl_files)} JSONL files in {directory}")

    for file_path in jsonl_files:
        try:
            conversation_metadata, messages = parser.parse_conversation_file(file_path)
            all_conversations.append(conversation_metadata)
            # Tag each message with its conversation session_id for proper grouping later
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

    # Find all JSONL files
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