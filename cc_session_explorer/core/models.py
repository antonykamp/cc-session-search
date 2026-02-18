"""
Data models for conversation search
"""
from dataclasses import dataclass
from typing import Optional, List


@dataclass
class ConversationSummary:
    """Represents a summarized view of daily conversations"""
    date: str
    total_sessions: int
    total_messages: int
    summary_style: str
    summary_text: str
    key_topics: List[str]
    insights: List[str]
    stories: List[str]
    projects_mentioned: List[str]
    people_mentioned: List[str]
    error: Optional[str] = None
