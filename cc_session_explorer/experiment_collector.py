"""
Experiment Collector Module

Collects metrics from all sessions belonging to an experiment
(identified by git branch pattern) and writes a CSV summary.
"""

import csv
import re
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
from collections import defaultdict

from cc_bench_schema.summary import SUMMARY_COLUMNS
from cc_session_explorer.core.conversation_parser import JSONLParser, ParsedMessage, ConversationMetadata
from cc_session_explorer.core.file_locator import SessionFileLocator
from cc_session_explorer.token_breakdown import classify_message, _build_tool_call_lookup

logger = logging.getLogger(__name__)

# Tools we track individually
TRACKED_TOOLS = ['Read', 'Glob', 'Edit', 'Skill', 'Bash', 'Grep']


def _parse_branch(branch: str, experiment_id: str) -> Optional[Dict[str, str]]:
    """Parse a branch name matching the experiment pattern.

    Branch format: <experiment-id>-run-<N>-iteration-<M>

    Returns dict with run_id and iteration_id, or None if no match.
    """
    pattern = rf'^{re.escape(experiment_id)}--run-(\d+)--iteration-(\d+)$'
    m = re.match(pattern, branch)
    if not m:
        return None
    return {'run_id': m.group(1), 'iteration_id': m.group(2)}


def _count_tool_calls(messages: List[ParsedMessage]) -> Dict[str, int]:
    """Count tool calls by tool name from assistant messages."""
    counts = defaultdict(int)
    for msg in messages:
        if msg.role == 'assistant' and msg.tool_uses and 'tool_calls' in msg.tool_uses:
            for tc in msg.tool_uses['tool_calls']:
                name = tc.get('name', 'unknown')
                counts[name] += 1
    return counts


def _count_chars(messages: List[ParsedMessage]) -> Dict[str, int]:
    """Count characters per category, attributing tool results to their tool."""
    tool_call_lookup = _build_tool_call_lookup(messages)
    chars = defaultdict(int)

    for msg in messages:
        category = classify_message(msg)

        # Attribute tool results to the calling tool
        if category == 'tool_result' and msg.tool_uses and isinstance(msg.tool_uses, dict):
            tool_use_id = msg.tool_uses.get('tool_use_id')
            if tool_use_id and tool_use_id in tool_call_lookup:
                category = tool_call_lookup[tool_use_id]

        chars[category] += len(msg.content)

    return chars


def _extract_subagent_types_from_parent(messages: List[ParsedMessage]) -> Dict[str, str]:
    """Extract subagent_type from Task tool calls in parent session.

    Returns a mapping from prompt text (first 200 chars) to subagent_type.
    """
    types = {}
    for msg in messages:
        if msg.role != 'assistant' or not msg.tool_uses or 'tool_calls' not in msg.tool_uses:
            continue
        for tc in msg.tool_uses['tool_calls']:
            if tc.get('name') == 'Task':
                inp = tc.get('input', {})
                subagent_type = inp.get('subagent_type', '')
                prompt = inp.get('prompt', '')
                if subagent_type and prompt:
                    types[prompt[:200]] = subagent_type
    return types


def _match_subagent_type(
    subagent_messages: List[ParsedMessage],
    parent_types: Dict[str, str],
    fallback_type: Optional[str],
) -> str:
    """Determine sub-agent type by matching first user message to parent Task calls."""
    # Find the first user message in the sub-agent session
    for msg in subagent_messages:
        if msg.role == 'user':
            content = msg.content[:200]
            # Try exact prefix match against parent Task prompts
            for prompt_prefix, stype in parent_types.items():
                if content == prompt_prefix:
                    return stype
            break

    return fallback_type or ''


def _compute_session_row(
    experiment_id: str,
    run_id: str,
    iteration_id: str,
    session_id: str,
    is_sub_agent: bool,
    sub_agent_type: str,
    metadata: ConversationMetadata,
    messages: List[ParsedMessage],
) -> Dict[str, Any]:
    """Compute a single CSV row for a session."""
    tool_counts = _count_tool_calls(messages)
    char_counts = _count_chars(messages)

    total_tool_calls = sum(tool_counts.values())
    total_tokens = sum(msg.token_count for msg in messages)
    num_messages = len(messages)
    cost_usd = sum(msg.cost_usd for msg in messages)

    duration_seconds = 0.0
    if metadata.started_at and metadata.ended_at:
        duration_seconds = (metadata.ended_at - metadata.started_at).total_seconds()

    total_chars = sum(char_counts.values())

    return {
        'experiment_id': experiment_id,
        'run_id': run_id,
        'iteration_id': iteration_id,
        'session_id': session_id,
        'is_sub_agent': is_sub_agent,
        'sub_agent_type': sub_agent_type,
        'total_tool_calls': total_tool_calls,
        'read_calls': tool_counts.get('Read', 0),
        'glob_calls': tool_counts.get('Glob', 0),
        'edit_calls': tool_counts.get('Edit', 0),
        'skill_calls': tool_counts.get('Skill', 0),
        'bash_calls': tool_counts.get('Bash', 0),
        'grep_calls': tool_counts.get('Grep', 0),
        'total_chars': total_chars,
        'thinking_chars': char_counts.get('thinking', 0),
        'read_chars': char_counts.get('Read', 0),
        'edit_chars': char_counts.get('Edit', 0),
        'bash_chars': char_counts.get('Bash', 0),
        'skill_chars': char_counts.get('Skill', 0),
        'total_tokens': total_tokens,
        'num_messages': num_messages,
        'cost_usd': round(cost_usd, 6),
        'duration_seconds': round(duration_seconds, 1),
        'started_at': metadata.started_at.isoformat() if metadata.started_at else '',
        'ended_at': metadata.ended_at.isoformat() if metadata.ended_at else '',
    }


class ExperimentCollector:
    """Collects metrics from experiment sessions and writes CSV."""

    def __init__(self, directory: str, experiment_id: str):
        self.directory = Path(directory)
        self.experiment_id = experiment_id
        self.parser = JSONLParser()
        self.locator = SessionFileLocator()

    def collect(self) -> List[Dict[str, Any]]:
        """Collect metrics for all sessions in the experiment.

        Returns list of row dicts ready for CSV output.
        """
        if not self.directory.exists() or not self.directory.is_dir():
            raise ValueError(f"Directory not found: {self.directory}")

        # Step 1: Discover main sessions matching the experiment
        main_sessions = self._discover_main_sessions()
        if not main_sessions:
            raise ValueError(
                f"No sessions found for experiment '{self.experiment_id}' in {self.directory}"
            )

        # Step 2: Discover sub-agent sessions grouped by parent
        subagent_map = self._discover_subagent_sessions()

        # Step 3: Process each main session and its sub-agents
        rows = []
        for session_info in main_sessions:
            session_rows = self._process_session(session_info, subagent_map)
            rows.extend(session_rows)

        # Sort by run_id, iteration_id, then sub-agents after parent
        rows.sort(key=lambda r: (
            int(r['run_id']),
            int(r['iteration_id']),
            r['is_sub_agent'],
            r['sub_agent_type'],
        ))

        return rows

    def write_csv(self, rows: List[Dict[str, Any]], output_path: Optional[str] = None) -> str:
        """Write rows to CSV file. Returns the output path."""
        if output_path is None:
            output_path = f"{self.experiment_id}--summary.csv"

        with open(output_path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=SUMMARY_COLUMNS)
            writer.writeheader()
            writer.writerows(rows)

        return output_path

    def _discover_main_sessions(self) -> List[Dict[str, Any]]:
        """Find main sessions whose branch matches the experiment."""
        sessions = []
        for file_info in self.locator.find_main_sessions(self.directory):
            try:
                metadata, _ = self.parser.parse_metadata_only(file_info.path)
            except Exception:
                logger.warning(f"Skipping unparseable file: {file_info.path}")
                continue

            if metadata.is_subagent:
                continue

            if not metadata.git_branch:
                continue

            parsed = _parse_branch(metadata.git_branch, self.experiment_id)
            if not parsed:
                continue

            sessions.append({
                'file_path': file_info.path,
                'session_id': metadata.session_id,
                'run_id': parsed['run_id'],
                'iteration_id': parsed['iteration_id'],
            })

        return sessions

    def _discover_subagent_sessions(self) -> Dict[str, List[Path]]:
        """Find all sub-agent session files grouped by parent session ID."""
        subagent_map: Dict[str, List[Path]] = defaultdict(list)

        for file_info in self.locator.find_subagent_files(self.directory):
            if file_info.parent_session_id:
                # New format: parent_id is derived from directory structure
                subagent_map[file_info.parent_session_id].append(file_info.path)
            else:
                # Legacy format: need to parse to find parent
                try:
                    metadata, _ = self.parser.parse_metadata_only(file_info.path)
                    if metadata.is_subagent and metadata.parent_session_id:
                        subagent_map[metadata.parent_session_id].append(file_info.path)
                except Exception:
                    continue

        return subagent_map

    def _process_session(
        self,
        session_info: Dict[str, Any],
        subagent_map: Dict[str, List[Path]],
    ) -> List[Dict[str, Any]]:
        """Process a main session and its sub-agents, returning CSV rows."""
        rows = []
        file_path = session_info['file_path']
        session_id = session_info['session_id']
        run_id = session_info['run_id']
        iteration_id = session_info['iteration_id']

        # Full parse of main session
        try:
            metadata, messages = self.parser.parse_conversation_file(file_path)
        except Exception as e:
            logger.warning(f"Failed to parse session {session_id}: {e}")
            return rows

        # Main session row
        rows.append(_compute_session_row(
            self.experiment_id, run_id, iteration_id, session_id,
            is_sub_agent=False, sub_agent_type='',
            metadata=metadata, messages=messages,
        ))

        # Extract subagent_type info from parent's Task tool calls
        parent_types = _extract_subagent_types_from_parent(messages)

        # Process sub-agent sessions
        subagent_files = subagent_map.get(session_id, [])
        for agent_file in subagent_files:
            try:
                sub_metadata, sub_messages = self.parser.parse_conversation_file(agent_file)
            except Exception as e:
                logger.warning(f"Failed to parse sub-agent {agent_file}: {e}")
                continue

            sub_type = _match_subagent_type(
                sub_messages, parent_types, sub_metadata.agent_type
            )

            rows.append(_compute_session_row(
                self.experiment_id, run_id, iteration_id,
                session_id=sub_metadata.session_id,
                is_sub_agent=True, sub_agent_type=sub_type,
                metadata=sub_metadata, messages=sub_messages,
            ))

        return rows
