#!/usr/bin/env python3
"""
Claude Code Session Dashboard

Interactive Streamlit dashboard for analyzing and comparing Claude Code conversation sessions.
"""

import streamlit as st
from typing import Tuple

from cc_session_search.core.conversation_parser import JSONLParser, ParsedMessage, ConversationMetadata
from cc_session_search.core.searcher import SessionSearcher
from cc_session_search.session_selector import render_session_selector
from cc_session_search.conversation_view import render_conversation_view
from cc_session_search.comparison_view import render_comparison_view


# Page configuration
st.set_page_config(
    page_title="Claude Code Session Explorer",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)


# Initialize components
@st.cache_resource
def get_searcher():
    return SessionSearcher()


@st.cache_resource
def get_parser():
    return JSONLParser()


def load_conversation(session_id: str, project_name: str) -> Tuple[ConversationMetadata, list[ParsedMessage]]:
    """Load and parse a conversation file"""
    parser = get_parser()
    searcher = get_searcher()

    session_file = searcher.claude_dir / project_name / f"{session_id}.jsonl"
    if not session_file.exists():
        raise FileNotFoundError(f"Session file not found: {session_file}")

    return parser.parse_conversation_file(session_file)


def main():
    """Main dashboard application"""

    st.title("🔍 Claude Code Session Explorer")
    st.markdown("Interactive dashboard for analyzing and comparing Claude Code conversation sessions")

    # Check if session is being loaded from URL
    query_params = st.query_params
    if query_params:
        param_keys = list(query_params.keys())
        if any(k.startswith('project') or k.startswith('session') for k in param_keys):
            st.info("📎 Session loaded from shareable link")

    searcher = get_searcher()

    # Sidebar
    with st.sidebar:
        st.header("Session Selection")

        mode = st.radio(
            "Mode",
            ["Single Session", "Compare Sessions"],
            index=0
        )

        st.divider()

        # Session 1 selector
        st.subheader("Session 1")
        session1_info = render_session_selector(searcher, "1")

        session2_info = None
        if mode == "Compare Sessions":
            st.divider()
            st.subheader("Session 2")
            session2_info = render_session_selector(searcher, "2")

    # Main content
    if session1_info is None:
        st.warning("Please select a session from the sidebar")
        return

    try:
        # Load session 1
        project1, session1 = session1_info
        metadata1, messages1 = load_conversation(session1, project1)

        if mode == "Single Session":
            # Single session view
            st.header(f"📄 Session: {metadata1.session_id}")
            render_conversation_view(metadata1, messages1, "1")

        else:
            # Comparison mode
            if session2_info is None:
                st.warning("Please select a second session from the sidebar")
                return

            # Load session 2
            project2, session2 = session2_info
            metadata2, messages2 = load_conversation(session2, project2)

            # Render comparison
            render_comparison_view(metadata1, messages1, metadata2, messages2)

            # Individual session details
            st.divider()
            col1, col2 = st.columns(2)

            with col1:
                st.header("📄 Session 1 Details")
                render_conversation_view(metadata1, messages1, "1")

            with col2:
                st.header("📄 Session 2 Details")
                render_conversation_view(metadata2, messages2, "2")

    except Exception as e:
        st.error(f"Error loading conversation: {str(e)}")
        st.exception(e)


if __name__ == "__main__":
    main()
