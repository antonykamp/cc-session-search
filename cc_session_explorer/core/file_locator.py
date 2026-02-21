"""
Session file discovery and location.

Centralizes the glob patterns for finding main sessions and subagent files,
replacing duplicated logic in searcher.py and experiment_collector.py.
"""

from pathlib import Path

from cc_session_explorer.core.models import SessionFileInfo


class SessionFileLocator:
    """Discovers session JSONL files in a project directory."""

    def find_main_sessions(self, directory: Path) -> list[SessionFileInfo]:
        """Find main (non-subagent) session files in the directory.

        Matches *.jsonl files directly in the directory, excluding
        agent-*.jsonl files (legacy subagent format).
        """
        results = []
        for f in directory.glob('*.jsonl'):
            if f.name.startswith('agent-'):
                continue
            results.append(SessionFileInfo(
                path=f,
                session_id=f.stem,
                is_subagent=False,
            ))
        return results

    def find_subagent_files(self, directory: Path, parent_id: str | None = None) -> list[SessionFileInfo]:
        """Find subagent session files.

        Searches both formats:
        - New format: {parent_id}/subagents/agent-*.jsonl
        - Legacy format: agent-*.jsonl at top level

        Args:
            directory: Project directory to search in.
            parent_id: If given, only return subagents for this parent session.
        """
        results = []

        # New format: {session_id}/subagents/agent-*.jsonl
        if parent_id:
            subagent_dir = directory / parent_id / 'subagents'
            if subagent_dir.exists():
                for f in subagent_dir.glob('agent-*.jsonl'):
                    results.append(SessionFileInfo(
                        path=f,
                        session_id=f.stem,
                        is_subagent=True,
                        parent_session_id=parent_id,
                    ))
        else:
            # Search all subdirectories for subagent files
            for f in directory.glob('*/subagents/agent-*.jsonl'):
                derived_parent_id = f.parent.parent.name
                results.append(SessionFileInfo(
                    path=f,
                    session_id=f.stem,
                    is_subagent=True,
                    parent_session_id=derived_parent_id,
                ))

        # Legacy format: agent-*.jsonl at top level
        for f in directory.glob('agent-*.jsonl'):
            results.append(SessionFileInfo(
                path=f,
                session_id=f.stem,
                is_subagent=True,
                parent_session_id=parent_id,
            ))

        return results
