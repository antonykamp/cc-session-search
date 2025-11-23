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
    sessions = searcher.get_sessions_for_project(selected_project, days_back=30)
    if not sessions:
        st.warning(f"No sessions found for project {selected_project}")
        return None

    session_display = [
        f"{s['started_at'][:10] if s['started_at'] else 'unknown'} ({s['message_count']} msgs) - {s['session_id'][:20]}..."
        for s in sessions
    ]

    # Pre-select from URL if available
    default_session_idx = 0
    session_ids = [s['session_id'] for s in sessions]
    if url_session and url_session in session_ids:
        default_session_idx = session_ids.index(url_session)

    session_idx = st.selectbox(
        f"Select Session {key_suffix}",
        range(len(sessions)),
        format_func=lambda i: session_display[i],
        index=default_session_idx,
        key=f"session_{key_suffix}"
    )

    selected_session = sessions[session_idx]['session_id']

    return (selected_project, selected_session)
