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


def get_message_type(msg: ParsedMessage) -> str:
    """Determine the display type of a message"""
    is_thinking = '[Thinking:' in msg.content
    is_tool_call = '[Calling tool:' in msg.content
    has_system_reminder = '<system-reminder>' in msg.content.lower()

    # Check for meta messages (takes priority - should be separate from skill context)
    is_meta = msg.metadata.get('is_meta', False) if msg.metadata else False
    if is_meta:
        return 'meta'

    # Check for subagent result (tool role with toolUseResult containing agentId)
    if msg.role == 'tool' and msg.tool_uses:
        if 'agentId' in msg.tool_uses or 'agent_id' in msg.tool_uses:
            return 'subagent_result'

    # Check for MCP tool calls, skill calls, Task calls, and Read calls to .claude/skills
    is_mcp_call = False
    is_skill_call = False
    is_skill_read = False
    is_subagent_call = False
    if msg.role == 'assistant' and msg.tool_uses and 'tool_calls' in msg.tool_uses:
        is_tool_call = True
        for tool_call in msg.tool_uses['tool_calls']:
            tool_name = tool_call.get('name', '')
            if tool_name.startswith('mcp__'):
                is_mcp_call = True
                break
            elif tool_name == 'Task':
                is_subagent_call = True
                break
            elif tool_name == 'Skill':
                is_skill_call = True
                break
            elif tool_name == 'Read':
                # Check if reading from .claude/skills folder
                tool_input = tool_call.get('input', {})
                file_path = tool_input.get('file_path', '')
                if '.claude/skills' in file_path:
                    is_skill_read = True
                    break

    # Skill calls and skill reads are grouped as skill_context
    if is_skill_call or is_skill_read:
        return 'skill_context'
    elif msg.role == 'user':
        return 'user'
    elif msg.role == 'assistant':
        if is_thinking:
            return 'assistant_thinking'
        elif is_subagent_call:
            return 'assistant_subagent_call'
        elif is_mcp_call:
            return 'assistant_mcp_call'
        elif is_tool_call:
            return 'assistant_tool_call'
        else:
            return 'assistant_text'
    elif msg.role == 'tool':
        return 'tool'
    elif has_system_reminder:
        return 'system'
    else:
        return msg.role


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


MESSAGE_TYPE_INFO = {
    'user': ('👤', '#3498db', 'USER'),
    'assistant_text': ('🤖', '#2ecc71', 'ASSISTANT'),
    'assistant_thinking': ('🧠', '#1abc9c', 'ASSISTANT (THINKING)'),
    'skill_context': ('🎯', '#9b59b6', 'SKILL CONTEXT'),
    'meta': ('🏷️', '#e91e63', 'META'),
    'assistant_subagent_call': ('🤖🔗', '#6c5ce7', 'SUBAGENT CALL'),
    'assistant_tool_call': ('⚡', '#e67e22', 'ASSISTANT (TOOL CALL)'),
    'assistant_mcp_call': ('🔌', '#8e44ad', 'MCP TOOL CALL'),
    'tool': ('🔧', '#f39c12', 'TOOL RESULT'),
    'subagent_result': ('🤖✅', '#a29bfe', 'SUBAGENT RESULT'),
    'system': ('⚠️', '#e74c3c', 'SYSTEM'),
    'file-history-snapshot': ('📄', '#95a5a6', 'FILE HISTORY')
}

MESSAGE_TYPE_LABELS = {
    'user': '👤 User',
    'assistant_text': '🤖 Assistant (Text)',
    'assistant_thinking': '🧠 Assistant (Thinking)',
    'skill_context': '🎯 Skill Context',
    'meta': '🏷️ Meta',
    'assistant_subagent_call': '🤖🔗 Subagent Call',
    'assistant_mcp_call': '🔌 MCP Tool Call',
    'assistant_tool_call': '⚡ Assistant (Tool Call)',
    'tool': '🔧 Tool Result',
    'subagent_result': '🤖✅ Subagent Result',
    'system': '⚠️ System',
    'file-history-snapshot': '📄 File History'
}
