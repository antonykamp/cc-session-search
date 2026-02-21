"""
Core conversation search functionality
"""
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional
from cc_session_explorer.core.conversation_parser import JSONLParser



class SessionSearcher:
    """Core session search and analysis functionality"""

    def __init__(self):
        # Use local conversation parser
        self.parser = JSONLParser()

        self.claude_dir = Path.home() / '.claude' / 'projects'

    def discover_projects(self) -> List[Dict[str, Any]]:
        """Discover all Claude Code projects"""
        projects = []

        if not self.claude_dir.exists():
            return projects

        for project_dir in self.claude_dir.iterdir():
            if not project_dir.is_dir():
                continue

            # Count sessions
            session_files = list(project_dir.glob('*.jsonl'))
            if not session_files:
                continue

            # Get project info
            latest_session = max(session_files, key=lambda f: f.stat().st_mtime)
            latest_time = datetime.fromtimestamp(latest_session.stat().st_mtime)

            projects.append({
                'name': project_dir.name,
                'path': str(project_dir),
                'session_count': len(session_files),
                'latest_activity': latest_time.isoformat(),
                'decoded_name': self._decode_project_name(project_dir.name)
            })

        return sorted(projects, key=lambda p: p['latest_activity'], reverse=True)

    def _decode_project_name(self, encoded_name: str) -> str:
        """Decode Claude project directory names"""
        return encoded_name.replace('-', '/')

    def get_sessions_for_project(self, project_name: str, days_back: int = 7, include_subagents: bool = False) -> List[Dict[str, Any]]:
        """
        Get sessions for a specific project.

        Args:
            project_name: The project name (encoded)
            days_back: Number of days to look back
            include_subagents: If True, include subagents as separate items. If False, nest under parents.

        Returns:
            List of session dictionaries, with subagents nested under 'subagents' key
        """
        project_dir = self.claude_dir / project_name
        if not project_dir.exists():
            return []

        cutoff_time = datetime.now() - timedelta(days=days_back)
        sessions = []
        subagent_map = {}  # Map parent_session_id -> list of subagents

        for session_file in project_dir.glob('*.jsonl'):
            mod_time = datetime.fromtimestamp(session_file.stat().st_mtime)
            if mod_time < cutoff_time:
                continue

            try:
                # Quick parse for metadata only (no expensive token counting)
                conversation_metadata, message_count = self.parser.parse_metadata_only(session_file)

                session_dict = {
                    'session_id': conversation_metadata.session_id,
                    'file_path': str(session_file),
                    'message_count': message_count,
                    'started_at': conversation_metadata.started_at.isoformat() if conversation_metadata.started_at else None,
                    'ended_at': conversation_metadata.ended_at.isoformat() if conversation_metadata.ended_at else None,
                    'working_directory': conversation_metadata.working_directory,
                    'git_branch': conversation_metadata.git_branch,
                    'is_subagent': conversation_metadata.is_subagent,
                    'agent_id': conversation_metadata.agent_id,
                    'agent_type': conversation_metadata.agent_type
                }

                if conversation_metadata.is_subagent:
                    # Store subagent for later nesting
                    parent_id = conversation_metadata.parent_session_id
                    if parent_id not in subagent_map:
                        subagent_map[parent_id] = []
                    subagent_map[parent_id].append(session_dict)
                else:
                    # Regular session
                    sessions.append(session_dict)

            except Exception:
                # Skip corrupted files
                continue

        # Discover new-format subagents: {parent_id}/subagents/agent-*.jsonl
        for session_file in project_dir.glob('*/subagents/agent-*.jsonl'):
            mod_time = datetime.fromtimestamp(session_file.stat().st_mtime)
            if mod_time < cutoff_time:
                continue

            try:
                conversation_metadata, message_count = self.parser.parse_metadata_only(session_file)

                session_dict = {
                    'session_id': conversation_metadata.session_id,
                    'file_path': str(session_file),
                    'message_count': message_count,
                    'started_at': conversation_metadata.started_at.isoformat() if conversation_metadata.started_at else None,
                    'ended_at': conversation_metadata.ended_at.isoformat() if conversation_metadata.ended_at else None,
                    'working_directory': conversation_metadata.working_directory,
                    'git_branch': conversation_metadata.git_branch,
                    'is_subagent': conversation_metadata.is_subagent,
                    'agent_id': conversation_metadata.agent_id,
                    'agent_type': conversation_metadata.agent_type
                }

                if conversation_metadata.is_subagent:
                    parent_id = conversation_metadata.parent_session_id
                    if parent_id not in subagent_map:
                        subagent_map[parent_id] = []
                    subagent_map[parent_id].append(session_dict)
                else:
                    sessions.append(session_dict)

            except Exception:
                continue

        # Nest subagents under their parents (unless include_subagents is True)
        if not include_subagents:
            for session in sessions:
                session_id = session['session_id']
                if session_id in subagent_map:
                    session['subagents'] = subagent_map[session_id]
                else:
                    session['subagents'] = []
        else:
            # Include subagents as flat list
            for subagents in subagent_map.values():
                sessions.extend(subagents)

        return sorted(sessions, key=lambda s: s['started_at'] or '1970-01-01', reverse=True)

    def find_subagents_for_session(self, session_id: str, project_name: str) -> List[Dict[str, Any]]:
        """
        Find all subagent sessions that belong to a parent session.

        Args:
            session_id: The parent session ID
            project_name: The project name (encoded)

        Returns:
            List of subagent metadata dictionaries
        """
        project_dir = self.claude_dir / project_name
        if not project_dir.exists():
            return []

        subagents = []

        # New format: {session_id}/subagents/agent-{id}.jsonl
        subagent_dir = project_dir / session_id / 'subagents'
        if subagent_dir.exists():
            for agent_file in subagent_dir.glob('agent-*.jsonl'):
                try:
                    metadata, _ = self.parser.parse_metadata_only(agent_file)

                    subagents.append({
                        'agent_id': metadata.agent_id,
                        'agent_type': metadata.agent_type or 'Unknown',
                        'session_id': metadata.session_id,
                        'file_path': str(agent_file),
                        'message_count': metadata.message_count,
                        'started_at': metadata.started_at.isoformat() if metadata.started_at else None,
                        'ended_at': metadata.ended_at.isoformat() if metadata.ended_at else None
                    })
                except Exception:
                    continue

        # Legacy format: agent-*.jsonl in the project directory
        for agent_file in project_dir.glob('agent-*.jsonl'):
            try:
                metadata, _ = self.parser.parse_metadata_only(agent_file)

                if metadata.is_subagent and metadata.parent_session_id == session_id:
                    subagents.append({
                        'agent_id': metadata.agent_id,
                        'agent_type': metadata.agent_type or 'Unknown',
                        'session_id': metadata.session_id,
                        'file_path': str(agent_file),
                        'message_count': metadata.message_count,
                        'started_at': metadata.started_at.isoformat() if metadata.started_at else None,
                        'ended_at': metadata.ended_at.isoformat() if metadata.ended_at else None
                    })
            except Exception:
                continue

        return subagents

    def get_session_with_subagents(self, session_id: str, project_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Get a session with its subagents and aggregate metrics.

        Args:
            session_id: The session ID to retrieve
            project_name: Optional project name filter

        Returns:
            Dictionary containing session metadata, messages, and subagent info
        """
        # Find the session file
        session_file = None
        found_project = None

        if project_name:
            potential_file = self.claude_dir / project_name / f"{session_id}.jsonl"
            if potential_file.exists():
                session_file = potential_file
                found_project = project_name
        else:
            # Search all projects
            for project_dir in self.claude_dir.iterdir():
                if not project_dir.is_dir():
                    continue
                potential_file = project_dir / f"{session_id}.jsonl"
                if potential_file.exists():
                    session_file = potential_file
                    found_project = project_dir.name
                    break

        if not session_file:
            return None

        # Parse the main session
        metadata, messages = self.parser.parse_conversation_file(session_file)

        # Find subagents
        subagents = self.find_subagents_for_session(session_id, found_project)

        # Calculate aggregate metrics
        total_tokens = sum(msg.token_count for msg in messages)
        total_cost = sum(msg.cost_usd for msg in messages)

        # Parse subagent sessions for aggregate metrics
        subagent_details = []
        all_subagent_messages = []
        for subagent in subagents:
            try:
                sub_metadata, sub_messages = self.parser.parse_conversation_file(Path(subagent['file_path']))
                sub_tokens = sum(msg.token_count for msg in sub_messages)
                sub_cost = sum(msg.cost_usd for msg in sub_messages)

                total_tokens += sub_tokens
                total_cost += sub_cost

                all_subagent_messages.extend(sub_messages)

                subagent_details.append({
                    **subagent,
                    'token_count': sub_tokens,
                    'cost_usd': sub_cost
                })
            except Exception:
                subagent_details.append(subagent)

        return {
            'metadata': metadata,
            'messages': messages,
            'subagent_messages': all_subagent_messages,
            'subagents': subagent_details,
            'aggregate_metrics': {
                'total_tokens': total_tokens,
                'total_cost_usd': total_cost,
                'session_count': 1 + len(subagents),
                'main_session_tokens': sum(msg.token_count for msg in messages),
                'main_session_cost': sum(msg.cost_usd for msg in messages),
                'subagent_tokens': total_tokens - sum(msg.token_count for msg in messages),
                'subagent_cost': total_cost - sum(msg.cost_usd for msg in messages)
            }
        }