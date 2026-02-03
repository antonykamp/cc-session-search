"""
Token Breakdown Module

Attributes token usage to categories (text, thinking, tool calls by name,
tool results, user messages) by grouping messages that share the same API
message ID and splitting usage proportionally by content character length.
"""

from dataclasses import dataclass, field
from typing import Dict, List
from collections import defaultdict

from cc_session_search.core.conversation_parser import ParsedMessage


@dataclass
class CategoryTokens:
    """Token counts for a single category."""
    input_tokens: float = 0.0
    output_tokens: float = 0.0
    cache_creation_tokens: float = 0.0
    cache_read_tokens: float = 0.0
    cost_usd: float = 0.0
    estimated: bool = False  # True if tokens are estimated via len/4 heuristic

    @property
    def total_tokens(self) -> float:
        return (self.input_tokens + self.output_tokens +
                self.cache_creation_tokens + self.cache_read_tokens)

    def __iadd__(self, other: 'CategoryTokens') -> 'CategoryTokens':
        self.input_tokens += other.input_tokens
        self.output_tokens += other.output_tokens
        self.cache_creation_tokens += other.cache_creation_tokens
        self.cache_read_tokens += other.cache_read_tokens
        self.cost_usd += other.cost_usd
        return self


@dataclass
class TokenBreakdown:
    """Complete token breakdown by category."""
    categories: Dict[str, CategoryTokens] = field(default_factory=dict)
    total: CategoryTokens = field(default_factory=CategoryTokens)


def classify_message(msg: ParsedMessage) -> str:
    """
    Classify a message into a token category.

    Returns one of:
    - "thinking" for assistant thinking blocks
    - "text" for assistant text blocks
    - A tool name (e.g. "Read", "Bash") for tool call blocks
    - "tool_result" for tool result messages
    - "user" for user messages
    """
    if msg.role == 'user':
        return 'user'

    if msg.role == 'tool':
        return 'tool_result'

    if msg.role == 'assistant':
        content = msg.content
        # Thinking blocks are wrapped with [Thinking: ...] by the parser
        if content.startswith('[Thinking:'):
            return 'thinking'

        # Tool call blocks have placeholder content like [Calling tool: Read]
        if content.startswith('[Calling tool:'):
            # Extract tool name
            tool_name = content.split(':', 1)[1].strip().rstrip(']')
            return tool_name

        if content.startswith('[Calling ') and 'tools:' in content:
            # Multiple tools: [Calling 2 tools: Read, Bash]
            # Use the first tool name as a representative, or just "multi_tool"
            tools_part = content.split('tools:', 1)[1].strip().rstrip(']')
            tool_names = [t.strip() for t in tools_part.split(',')]
            if len(tool_names) == 1:
                return tool_names[0]
            return tool_names[0]  # attribute to first tool

        # Check tool_uses for tool call info even when content has text
        if msg.tool_uses and 'tool_calls' in msg.tool_uses:
            tool_calls = msg.tool_uses['tool_calls']
            if tool_calls:
                return tool_calls[0].get('name', 'text')

        return 'text'

    # Fallback for summary or other roles
    return msg.role


def _build_tool_call_lookup(messages: List[ParsedMessage]) -> Dict[str, str]:
    """Build a mapping from tool_use_id to tool name."""
    lookup = {}
    for msg in messages:
        if msg.role == 'assistant' and msg.tool_uses and 'tool_calls' in msg.tool_uses:
            for tc in msg.tool_uses['tool_calls']:
                tool_id = tc.get('id')
                tool_name = tc.get('name', 'unknown')
                if tool_id:
                    lookup[tool_id] = tool_name
    return lookup


def compute_token_breakdown(messages: List[ParsedMessage]) -> TokenBreakdown:
    """
    Compute token breakdown by category.

    Estimates all tokens uniformly using len(content)/4.
    Tool results are attributed to their calling tool's category.
    """
    breakdown = TokenBreakdown()

    # Build tool_use_id -> tool_name lookup so tool results
    # get attributed to the tool that produced them
    tool_call_lookup = _build_tool_call_lookup(messages)

    # Group messages by api_msg_id
    api_groups: Dict[str, List[ParsedMessage]] = defaultdict(list)
    ungrouped: List[ParsedMessage] = []

    for msg in messages:
        api_id = msg.metadata.get('api_msg_id')
        if api_id:
            api_groups[api_id].append(msg)
        else:
            ungrouped.append(msg)

    # Estimate all tokens uniformly using len(content)/4.
    # This keeps all categories on the same scale rather than mixing
    # API-reported numbers with estimates.
    all_messages = []
    for group in api_groups.values():
        # Deduplicate by content hash within each group
        seen_content = set()
        for m in group:
            content_key = hash(m.content)
            if content_key not in seen_content:
                seen_content.add(content_key)
                all_messages.append(m)
    all_messages.extend(ungrouped)

    for msg in all_messages:
        category = classify_message(msg)

        # For tool results, attribute to the calling tool's category
        if category == 'tool_result' and msg.tool_uses and isinstance(msg.tool_uses, dict):
            tool_use_id = msg.tool_uses.get('tool_use_id')
            if tool_use_id and tool_use_id in tool_call_lookup:
                category = tool_call_lookup[tool_use_id]

        if category not in breakdown.categories:
            breakdown.categories[category] = CategoryTokens()

        estimated = len(msg.content) / 4
        if estimated > 0:
            cat = breakdown.categories[category]
            cat.input_tokens += estimated
            cat.estimated = True

    # Compute totals
    total = CategoryTokens()
    for cat in breakdown.categories.values():
        total += cat
    breakdown.total = total

    return breakdown
