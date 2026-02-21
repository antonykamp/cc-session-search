"""
Shared foundation types for session extraction pipeline.

Typed content blocks, token usage, and session file info.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class TextBlock:
    """A text content block from an assistant message."""
    text: str


@dataclass
class ThinkingBlock:
    """A thinking/reasoning content block from an assistant message."""
    text: str


@dataclass
class ToolCallBlock:
    """A tool call content block from an assistant message."""
    tool_name: str
    tool_id: str
    input: dict[str, Any]


@dataclass
class ToolResultBlock:
    """A tool result content block from a tool response message."""
    tool_use_id: str
    content: str
    raw: dict[str, Any]


ContentBlock = TextBlock | ThinkingBlock | ToolCallBlock | ToolResultBlock


@dataclass
class TokenUsage:
    """Typed token usage extracted from API responses."""
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_tokens: int = 0
    cache_read_tokens: int = 0
    cache_5m_tokens: int = 0
    cache_1h_tokens: int = 0
    cost_usd: float = 0.0

    @property
    def total(self) -> int:
        return self.input_tokens + self.output_tokens + self.cache_creation_tokens + self.cache_read_tokens


@dataclass
class SessionFileInfo:
    """Information about a discovered session file."""
    path: Path
    session_id: str
    is_subagent: bool
    parent_session_id: str | None = None
