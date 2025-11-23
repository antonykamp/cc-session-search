"""
Dashboard utility functions

Shared helper functions for the dashboard components.
"""

from typing import List, Dict, Any
from collections import Counter

from cc_session_search.core.conversation_parser import ParsedMessage


def extract_tool_calls(messages: List[ParsedMessage]) -> List[Dict[str, Any]]:
    """Extract all tool calls from messages"""
    tool_calls = []

    for idx, msg in enumerate(messages):
        if msg.role == 'assistant' and msg.tool_uses:
            # Handle new format: tool_calls array
            if 'tool_calls' in msg.tool_uses:
                for tool_block in msg.tool_uses['tool_calls']:
                    tool_calls.append({
                        'message_index': idx,
                        'timestamp': msg.timestamp,
                        'tool_name': tool_block.get('name', 'unknown'),
                        'tool_id': tool_block.get('id', 'unknown'),
                        'details': tool_block
                    })
            # Handle old format: direct tool_name field
            elif 'tool_name' in msg.tool_uses:
                tool_calls.append({
                    'message_index': idx,
                    'timestamp': msg.timestamp,
                    'tool_name': msg.tool_uses.get('tool_name', 'unknown'),
                    'details': msg.tool_uses
                })

    return tool_calls


def extract_system_messages(messages: List[ParsedMessage]) -> List[Dict[str, Any]]:
    """Extract system messages and reminders"""
    system_msgs = []

    for idx, msg in enumerate(messages):
        # Check for system reminders in content
        if 'system-reminder' in msg.content.lower() or msg.role == 'system':
            system_msgs.append({
                'message_index': idx,
                'timestamp': msg.timestamp,
                'role': msg.role,
                'content': msg.content[:200] + '...' if len(msg.content) > 200 else msg.content
            })

    return system_msgs


def get_tool_usage_stats(messages: List[ParsedMessage]) -> Dict[str, Any]:
    """Calculate tool usage statistics"""
    tool_calls = extract_tool_calls(messages)

    tool_counter = Counter()
    tool_sequences = []

    for call in tool_calls:
        tool_name = call['tool_name']
        tool_counter[tool_name] += 1
        tool_sequences.append(tool_name)

    return {
        'total_calls': len(tool_calls),
        'unique_tools': len(tool_counter),
        'tool_counts': dict(tool_counter),
        'tool_sequence': tool_sequences,
        'calls': tool_calls
    }


def build_tool_call_type_map(messages: List[ParsedMessage]) -> dict:
    """
    Build a mapping from tool_use_id to the type of tool call.
    This allows us to properly categorize tool results.
    """
    tool_call_types = {}

    for msg in messages:
        if msg.role == 'assistant' and msg.tool_uses and 'tool_calls' in msg.tool_uses:
            for tool_call in msg.tool_uses['tool_calls']:
                tool_id = tool_call.get('id')
                tool_name = tool_call.get('name', '')

                if not tool_id:
                    continue

                # Determine call type
                if tool_name == 'Task':
                    tool_call_types[tool_id] = 'subagent'
                elif tool_name.startswith('mcp__'):
                    tool_call_types[tool_id] = 'mcp'
                elif tool_name == 'Skill':
                    tool_call_types[tool_id] = 'skill'
                elif tool_name == 'Read':
                    tool_input = tool_call.get('input', {})
                    file_path = tool_input.get('file_path', '')
                    if '.claude/skills' in file_path:
                        tool_call_types[tool_id] = 'skill'
                    else:
                        tool_call_types[tool_id] = 'basic'
                else:
                    tool_call_types[tool_id] = 'basic'

    return tool_call_types


# Cache for tool call type mapping (per conversation)
_tool_call_type_cache = {}
_cache_key = None


def get_message_type(msg: ParsedMessage, all_messages: List[ParsedMessage] = None) -> str:
    """
    Determine the display type of a message.

    Categories:
    - User messages
    - Assistant (text and thinking)
    - Basic tool calls and results
    - Meta messages
    - MCP (list, read, tool) and results
    - Skill (execute, read) and results
    - Subagent calls and results

    Note: System messages with <system-reminder> are treated as tool results
    (they contain code from Read operations with sanity check caveats)

    Args:
        msg: The message to categorize
        all_messages: Optional list of all messages (needed for tool result categorization)
    """
    global _tool_call_type_cache, _cache_key

    has_system_reminder = '<system-reminder>' in msg.content.lower()
    is_thinking = '[Thinking:' in msg.content

    # Check for meta messages first (highest priority)
    is_meta = msg.metadata.get('is_meta', False) if msg.metadata else False
    if is_meta:
        return 'meta'

    # User messages (excluding system messages with tool results)
    if msg.role == 'user' and not has_system_reminder:
        return 'user'

    # System messages with <system-reminder> are tool results from Read operations
    # They contain code with sanity check caveats - treat as basic tool results
    if has_system_reminder or msg.role == 'system':
        return 'basic_tool_result'

    # Assistant messages
    if msg.role == 'assistant':
        # Check if it's a tool call
        if msg.tool_uses and 'tool_calls' in msg.tool_uses:
            for tool_call in msg.tool_uses['tool_calls']:
                tool_name = tool_call.get('name', '')

                # Subagent call
                if tool_name == 'Task':
                    return 'subagent_call'

                # MCP calls
                if tool_name.startswith('mcp__'):
                    # Determine MCP type
                    if 'listResources' in tool_name or 'list' in tool_name.lower():
                        return 'mcp_list'
                    elif 'readResource' in tool_name or 'read' in tool_name.lower():
                        return 'mcp_read'
                    else:
                        return 'mcp_tool'

                # Skill calls
                if tool_name == 'Skill':
                    return 'skill_execute'

                # Skill read (Read tool on .claude/skills)
                if tool_name == 'Read':
                    tool_input = tool_call.get('input', {})
                    file_path = tool_input.get('file_path', '')
                    if '.claude/skills' in file_path:
                        return 'skill_read'

            # If we get here, it's a basic tool call
            return 'basic_tool_call'

        # Not a tool call - check if thinking or regular text
        if is_thinking:
            return 'assistant_thinking'
        else:
            return 'assistant_text'

    # Tool results - need to match to original call
    if msg.role == 'tool':
        if msg.tool_uses:
            # Subagent result
            if 'agentId' in msg.tool_uses:
                return 'subagent_result'

            # Try to match result to call type using tool_use_id
            if isinstance(msg.tool_uses, dict) and 'tool_use_id' in msg.tool_uses:
                tool_use_id = msg.tool_uses['tool_use_id']

                # Build or use cached mapping
                if all_messages:
                    cache_key_val = id(all_messages)
                    if _cache_key != cache_key_val:
                        _cache_key = cache_key_val
                        _tool_call_type_cache = build_tool_call_type_map(all_messages)

                    call_type = _tool_call_type_cache.get(tool_use_id)
                    if call_type == 'mcp':
                        return 'mcp_result'
                    elif call_type == 'skill':
                        return 'skill_result'
                    elif call_type == 'subagent':
                        return 'subagent_result'
                    elif call_type == 'basic':
                        return 'basic_tool_result'

            # Fallback: check tool_name if present
            if 'tool_name' in msg.tool_uses:
                tool_name = msg.tool_uses.get('tool_name', '')
                if tool_name.startswith('mcp__'):
                    return 'mcp_result'
                elif tool_name == 'Skill':
                    return 'skill_result'

        # Default to basic tool result
        return 'basic_tool_result'

    # File history snapshots - ignore
    if msg.metadata and msg.metadata.get('original_type') == 'file-history-snapshot':
        return 'file-history-snapshot'

    # Fallback - treat unknown as basic tool result
    return 'basic_tool_result'


def build_tool_call_mapping(messages: List[ParsedMessage]) -> tuple[Dict[str, int], Dict[str, int]]:
    """
    Build bidirectional mapping between tool calls and results.
    
    Returns:
        tuple of (tool_id_to_call, tool_id_to_result) dictionaries
    """
    tool_id_to_result = {}  # tool_id -> result_idx
    tool_id_to_call = {}    # tool_id -> call_idx

    for msg_idx, msg in enumerate(messages):
        # Map tool calls
        if msg.role == 'assistant' and msg.tool_uses and 'tool_calls' in msg.tool_uses:
            for tool_call in msg.tool_uses['tool_calls']:
                tool_id = tool_call.get('id')
                if tool_id:
                    tool_id_to_call[tool_id] = msg_idx

        # Map tool results
        if msg.role == 'tool' and msg.tool_uses:
            if isinstance(msg.tool_uses, dict) and 'tool_use_id' in msg.tool_uses:
                tool_id = msg.tool_uses['tool_use_id']
                tool_id_to_result[tool_id] = msg_idx

    return tool_id_to_call, tool_id_to_result


def format_duration(started_at, ended_at) -> str:
    """Format duration between two timestamps"""
    if not started_at or not ended_at:
        return "N/A"
    
    duration = ended_at - started_at
    total_seconds = int(duration.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60

    if hours > 0:
        return f"{hours}h {minutes}m {seconds}s"
    elif minutes > 0:
        return f"{minutes}m {seconds}s"
    else:
        return f"{seconds}s"


# Color scheme:
# - User: Blue (#3498db)
# - Assistant: Green (#2ecc71)
# - Basic Tools: Orange (#e67e22)
# - Meta: Pink (#e91e63)
# - MCP: Purple (#8e44ad)
# - Skill: Violet (#9b59b6)
# - Subagent: Indigo (#6c5ce7)

MESSAGE_TYPE_INFO = {

    # User messages
    'user': ('👤', '#3498db', 'USER'),

    # Assistant messages (both same color)
    'assistant_text': ('🤖', '#2ecc71', 'ASSISTANT'),
    'assistant_thinking': ('💭', '#2ecc71', 'ASSISTANT (THINKING)'),

    # Basic tool calls
    'basic_tool_call': ('⚡', '#e67e22', 'TOOL CALL'),

    # Meta messages
    'meta': ('🏷️', '#e91e63', 'META'),

    # MCP calls (same purple color)
    'mcp_list': ('🔌📋', '#8e44ad', 'MCP LIST'),
    'mcp_read': ('🔌📖', '#8e44ad', 'MCP READ'),
    'mcp_tool': ('🔌⚡', '#8e44ad', 'MCP TOOL'),

    # Skill calls (same violet color)
    'skill_execute': ('🎯', '#9b59b6', 'SKILL EXECUTE'),
    'skill_read': ('🎯📖', '#9b59b6', 'SKILL READ'),

    # Subagent calls
    'subagent_call': ('🤖🔗', '#6c5ce7', 'SUBAGENT CALL'),

    # Tool results (colored by executor)
    'basic_tool_result': ('✅', '#e67e22', 'TOOL RESULT'),
    'mcp_result': ('🔌✅', '#8e44ad', 'MCP RESULT'),
    'skill_result': ('🎯✅', '#9b59b6', 'SKILL RESULT'),
    'subagent_result': ('🤖✅', '#6c5ce7', 'SUBAGENT RESULT'),
}

MESSAGE_TYPE_LABELS = {
    # User
    'user': '👤 User',

    # Assistant
    'assistant_text': '🤖 Assistant',
    'assistant_thinking': '💭 Assistant (Thinking)',

    # Basic tools
    'basic_tool_call': '⚡ Tool Call',

    # Meta
    'meta': '🏷️ Meta',

    # MCP
    'mcp_list': '🔌 MCP List',
    'mcp_read': '🔌 MCP Read',
    'mcp_tool': '🔌 MCP Tool',

    # Skill
    'skill_execute': '🎯 Skill Execute',
    'skill_read': '🎯 Skill Read',

    # Subagent
    'subagent_call': '🤖🔗 Subagent Call',

    # Tool results
    'basic_tool_result': '✅ Tool Result',
    'mcp_result': '🔌✅ MCP Result',
    'skill_result': '🎯✅ Skill Result',
    'subagent_result': '🤖✅ Subagent Result',
}
