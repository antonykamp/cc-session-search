"""
Session selector component for the dashboard
"""

import streamlit as st
from typing import Optional, Tuple

from cc_session_search.core.searcher import SessionSearcher


def render_session_selector(searcher: SessionSearcher, key_suffix: str) -> Optional[Tuple[str, str]]:
    """
    Render session selector and return (project_name, session_id)
    
    Args:
        searcher: SessionSearcher instance
        key_suffix: Unique suffix for widget keys (e.g., "1" or "2")
        
    Returns:
        Tuple of (project_name, session_id) or None if selection is invalid
    """
    # Check for URL query parameters
    query_params = st.query_params
    url_project = query_params.get(f'project{key_suffix}', None)
    url_session = query_params.get(f'session{key_suffix}', None)

    # Get projects
    projects = searcher.discover_projects()
    if not projects:
        st.warning(f"No projects found in {searcher.claude_dir}")
        return None

    # Project selector
    project_names = [p['name'] for p in projects]
    project_display = [f"{p['decoded_name']} ({p['session_count']} sessions)" for p in projects]

    # Pre-select from URL if available
    default_project_idx = 0
    if url_project and url_project in project_names:
        default_project_idx = project_names.index(url_project)

    selected_idx = st.selectbox(
        f"Select Project {key_suffix}",
        range(len(projects)),
        format_func=lambda i: project_display[i],
        index=default_project_idx,
        key=f"project_{key_suffix}"
    )

    selected_project = project_names[selected_idx]

    # Session selector
    sessions = searcher.get_sessions_for_project(selected_project, days_back=30, include_subagents=False)
    if not sessions:
        st.warning(f"No sessions found for project {selected_project}")
        return None

    # Build display list with nested subagents
    session_display = []
    session_ids = []

    for s in sessions:
        # Main session
        date_str = s['started_at'][:10] if s['started_at'] else 'unknown'
        subagent_count = len(s.get('subagents', []))
        subagent_suffix = f" +{subagent_count} subagent{'s' if subagent_count != 1 else ''}" if subagent_count > 0 else ""

        display_text = f"{date_str} ({s['message_count']} msgs{subagent_suffix}) - {s['session_id'][:20]}..."
        session_display.append(display_text)
        session_ids.append(s['session_id'])

        # Add subagents as indented options
        for sub in s.get('subagents', []):
            sub_date = sub['started_at'][:10] if sub['started_at'] else 'unknown'
            agent_type = sub.get('agent_type', 'Unknown')
            sub_display = f"  ↳ [{agent_type}] {sub_date} ({sub['message_count']} msgs) - {sub['session_id'][:25]}..."
            session_display.append(sub_display)
            session_ids.append(sub['session_id'])

    # Pre-select from URL if available
    default_session_idx = 0
    if url_session and url_session in session_ids:
        default_session_idx = session_ids.index(url_session)

    session_idx = st.selectbox(
        f"Select Session {key_suffix}",
        range(len(session_ids)),
        format_func=lambda i: session_display[i],
        index=default_session_idx,
        key=f"session_{key_suffix}"
    )

    selected_session = session_ids[session_idx]

    return (selected_project, selected_session)
