#!/usr/bin/env python3
"""
Claude Code Session Dashboard

Interactive Streamlit dashboard for analyzing and comparing Claude Code conversation sessions.
"""

import streamlit as st
from pathlib import Path
from datetime import datetime, timedelta
from collections import Counter, defaultdict
from typing import List, Dict, Any, Optional, Tuple
import json

from cc_session_search.core.conversation_parser import JSONLParser, ParsedMessage, ConversationMetadata
from cc_session_search.core.searcher import SessionSearcher
from cc_session_search.graph_visualizer import (
    create_plotly_graph,
    create_tool_usage_chart,
    create_message_timeline,
    create_comparison_chart
)


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


def load_conversation(session_id: str, project_name: str) -> Tuple[ConversationMetadata, List[ParsedMessage]]:
    """Load and parse a conversation file"""
    parser = get_parser()
    searcher = get_searcher()

    session_file = searcher.claude_dir / project_name / f"{session_id}.jsonl"
    if not session_file.exists():
        raise FileNotFoundError(f"Session file not found: {session_file}")

    return parser.parse_conversation_file(session_file)


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


def render_session_selector(key_suffix: str) -> Optional[Tuple[str, str]]:
    """Render session selector and return (project_name, session_id)"""
    searcher = get_searcher()

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
        st.info(f"📎 Loaded from link: {projects[default_project_idx]['decoded_name']}")

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
        st.success(f"📎 Session loaded from link")

    session_idx = st.selectbox(
        f"Select Session {key_suffix}",
        range(len(sessions)),
        format_func=lambda i: session_display[i],
        index=default_session_idx,
        key=f"session_{key_suffix}"
    )

    selected_session = sessions[session_idx]['session_id']

    return (selected_project, selected_session)


def render_conversation_view(metadata: ConversationMetadata, messages: List[ParsedMessage], key_suffix: str):
    """Render conversation details"""

    # Metadata
    with st.expander(f"📊 Session Metadata", expanded=False):
        # Calculate duration
        duration_str = "N/A"
        if metadata.started_at and metadata.ended_at:
            duration = metadata.ended_at - metadata.started_at
            total_seconds = int(duration.total_seconds())
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            seconds = total_seconds % 60

            if hours > 0:
                duration_str = f"{hours}h {minutes}m {seconds}s"
            elif minutes > 0:
                duration_str = f"{minutes}m {seconds}s"
            else:
                duration_str = f"{seconds}s"

        col1, col2 = st.columns(2)
        with col1:
            st.write(f"**Session ID:** {metadata.session_id}")
            st.write(f"**Project:** {metadata.project_name}")
            st.write(f"**Working Dir:** {metadata.working_directory or 'N/A'}")
        with col2:
            st.write(f"**Messages:** {len(messages)}")
            st.write(f"**Git Branch:** {metadata.git_branch or 'N/A'}")
            st.write(f"**Started:** {metadata.started_at.strftime('%Y-%m-%d %H:%M:%S') if metadata.started_at else 'N/A'}")
            st.write(f"**Duration:** {duration_str}")

        # Copy link section
        st.divider()
        st.markdown("**📎 Share This Session:**")

        # Generate shareable link with query parameters
        import urllib.parse
        params = {
            f'project{key_suffix}': metadata.project_name,
            f'session{key_suffix}': metadata.session_id
        }
        query_string = urllib.parse.urlencode(params)
        shareable_link = f"?{query_string}"

        st.code(shareable_link, language=None)
        st.caption("📋 Copy and append to your dashboard URL to link directly to this session")

        # Display file path for local access
        with st.expander("🗂️ Local File Path", expanded=False):
            st.code(metadata.file_path, language="bash")

    # Tool usage stats
    tool_stats = get_tool_usage_stats(messages)

    with st.expander(f"🔧 Tool Usage ({tool_stats['total_calls']} calls)", expanded=True):
        if tool_stats['total_calls'] > 0:
            # Show tool counts
            tool_df_data = [
                {"Tool": tool, "Count": count}
                for tool, count in sorted(tool_stats['tool_counts'].items(), key=lambda x: x[1], reverse=True)
            ]
            st.dataframe(tool_df_data, use_container_width=True, hide_index=True)
        else:
            st.info("No tool calls in this conversation")

    # System messages
    system_msgs = extract_system_messages(messages)
    with st.expander(f"⚙️ System Messages ({len(system_msgs)})", expanded=False):
        if system_msgs:
            for msg in system_msgs:
                st.text(f"[{msg['message_index']}] {msg['content']}")
        else:
            st.info("No system messages found")

    # Messages browser
    with st.expander(f"💬 Messages Browser ({len(messages)} messages)", expanded=False):
        # Legend
        st.markdown("""
        **Message Type Legend:**
        - 👤 **User** (Blue) - User input messages
        - 🤖 **Assistant** (Green) - Regular assistant responses
        - 🧠 **Assistant Thinking** (Teal) - Internal reasoning/planning
        - 🔌 **MCP Tool Call** (Deep Purple) - External MCP server tool invocation
        - ⚡ **Assistant Tool Call** (Orange) - Built-in tool invocation
        - 🔧 **Tool Result** (Amber) - Tool execution results
        - ⚠️ **System** - Messages with system reminders
        """)
        st.divider()

        # Message type filter
        message_types = {
            'user': '👤 User',
            'assistant_text': '🤖 Assistant (Text)',
            'assistant_thinking': '🧠 Assistant (Thinking)',
            'assistant_mcp_call': '🔌 MCP Tool Call',
            'assistant_tool_call': '⚡ Assistant (Tool Call)',
            'tool': '🔧 Tool Result',
            'system': '⚠️ System',
            'file-history-snapshot': '📄 File History'
        }

        # Determine what message types exist in this conversation
        def get_message_type(msg):
            is_thinking = '[Thinking:' in msg.content
            is_tool_call = '[Calling tool:' in msg.content
            has_system_reminder = '<system-reminder>' in msg.content.lower()

            # Check for MCP tool calls
            is_mcp_call = False
            if msg.role == 'assistant' and msg.tool_uses and 'tool_calls' in msg.tool_uses:
                for tool_call in msg.tool_uses['tool_calls']:
                    tool_name = tool_call.get('name', '')
                    if tool_name.startswith('mcp__'):
                        is_mcp_call = True
                        break

            if msg.role == 'user':
                return 'user'
            elif msg.role == 'assistant':
                if is_thinking:
                    return 'assistant_thinking'
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

        # Get unique message types in this conversation with counts
        type_counts = {}
        for msg in messages:
            msg_type = get_message_type(msg)
            type_counts[msg_type] = type_counts.get(msg_type, 0) + 1

        # Create labels with counts
        present_type_labels = []
        for msg_type, count in sorted(type_counts.items(), key=lambda x: x[1], reverse=True):
            if msg_type in message_types:
                label = f"{message_types[msg_type]} ({count})"
                present_type_labels.append(label)

        # Create filter
        selected_type_labels = st.multiselect(
            "Filter by message type (click to select/deselect)",
            present_type_labels,
            default=present_type_labels,
            key=f"type_filter_{key_suffix}"
        )

        # Reverse lookup to get selected types (strip count from label)
        label_to_type = {v: k for k, v in message_types.items()}
        selected_types = []
        for label in selected_type_labels:
            # Strip count (everything after and including the last '(')
            base_label = label.rsplit(' (', 1)[0]
            if base_label in label_to_type:
                selected_types.append(label_to_type[base_label])

        # Filter messages
        filtered_messages = [msg for msg in messages if get_message_type(msg) in selected_types]

        # Show filter summary
        if len(filtered_messages) != len(messages):
            st.info(f"📊 Showing {len(filtered_messages)} of {len(messages)} messages")

        # Pagination
        messages_per_page = 20
        total_pages = (len(filtered_messages) + messages_per_page - 1) // messages_per_page

        if total_pages > 0:
            # Only show slider if there are multiple pages
            if total_pages > 1:
                page = st.slider(
                    "Page",
                    1, total_pages,
                    1,
                    key=f"page_{key_suffix}"
                )
            else:
                page = 1

            start_idx = (page - 1) * messages_per_page
            end_idx = min(start_idx + messages_per_page, len(filtered_messages))

            # Build bidirectional tool call ↔ result mapping
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

            for i, msg in enumerate(filtered_messages[start_idx:end_idx], start=start_idx):
                timestamp_str = msg.timestamp.strftime('%H:%M:%S') if msg.timestamp else 'N/A'

                # Determine message type and styling
                is_thinking = '[Thinking:' in msg.content
                is_tool_call = '[Calling tool:' in msg.content
                has_system_reminder = '<system-reminder>' in msg.content.lower()

                # Check if this is a tool call and find its result
                tool_result_idx = None
                tool_ids = []
                is_mcp_call = False
                mcp_tool_name = None

                if msg.role == 'assistant' and msg.tool_uses and 'tool_calls' in msg.tool_uses:
                    for tool_call in msg.tool_uses['tool_calls']:
                        tool_id = tool_call.get('id', '')
                        tool_name = tool_call.get('name', '')

                        # Check if this is an MCP tool call
                        if tool_name.startswith('mcp__'):
                            is_mcp_call = True
                            mcp_tool_name = tool_name.replace('mcp__', '').replace('__', ' → ')

                        if tool_id:
                            tool_ids.append(tool_id)
                            if tool_id in tool_id_to_result:
                                tool_result_idx = tool_id_to_result[tool_id]

                # Check if this is a tool result matching a call
                matching_call_id = None
                matching_call_idx = None
                if msg.role == 'tool' and msg.tool_uses:
                    if isinstance(msg.tool_uses, dict) and 'tool_use_id' in msg.tool_uses:
                        matching_call_id = msg.tool_uses['tool_use_id']
                        # Find the corresponding call index
                        if matching_call_id in tool_id_to_call:
                            matching_call_idx = tool_id_to_call[matching_call_id]

                # Set icon, color, and label based on message type
                if msg.role == 'user':
                    icon = "👤"
                    color = "#3498db"  # Blue
                    label = "USER"
                elif msg.role == 'assistant':
                    if is_thinking:
                        icon = "🧠"
                        color = "#1abc9c"  # Teal/turquoise
                        label = "ASSISTANT (THINKING)"
                    elif is_tool_call:
                        if is_mcp_call:
                            icon = "🔌"  # Plugin icon for MCP
                            color = "#8e44ad"  # Deep purple for MCP
                            label = f"MCP TOOL CALL: {mcp_tool_name}"
                        else:
                            icon = "⚡"
                            color = "#e67e22"  # Orange
                            label = "ASSISTANT (TOOL CALL)"
                        # Add result link if available
                        if tool_result_idx is not None:
                            label += f" → Result at [{tool_result_idx}]"
                    else:
                        icon = "🤖"
                        color = "#2ecc71"  # Green
                        label = "ASSISTANT"
                elif msg.role == 'tool':
                    icon = "🔧"
                    color = "#f39c12"  # Amber
                    label = "TOOL RESULT"
                    # Add link back to the tool call
                    if matching_call_idx is not None:
                        label += f" ← Called from [{matching_call_idx}]"
                    elif matching_call_id:
                        label += f" (ID: {matching_call_id[:12]}...)"
                else:
                    icon = "📄"
                    color = "#95a5a6"  # Gray
                    label = msg.role.upper()

                # Add system reminder indicator
                if has_system_reminder:
                    icon = "⚠️"
                    label += " (SYSTEM)"

                # Display message with colored header
                st.markdown(
                    f'<div style="background-color: {color}22; border-left: 4px solid {color}; padding: 10px; margin: 5px 0; border-radius: 5px;">'
                    f'<p style="margin: 0; color: {color}; font-weight: bold;">{icon} [{i}] {label} <span style="color: #7f8c8d; font-weight: normal; font-size: 0.9em;">({timestamp_str})</span></p>'
                    f'</div>',
                    unsafe_allow_html=True
                )

                # Truncate long content
                content_preview = msg.content[:500] + "..." if len(msg.content) > 500 else msg.content

                # Display content with appropriate styling
                if is_thinking:
                    st.markdown(f'<div style="padding: 10px; background-color: #f8f9fa; border-radius: 5px; font-style: italic; color: #6c757d;">{content_preview}</div>', unsafe_allow_html=True)
                elif is_tool_call:
                    st.markdown(f'<div style="padding: 10px; background-color: #fff3cd; border-radius: 5px; font-family: monospace; color: #856404;">{content_preview}</div>', unsafe_allow_html=True)

                    # Show detailed tool call information
                    if msg.tool_uses and 'tool_calls' in msg.tool_uses:
                        for tool_call in msg.tool_uses['tool_calls']:
                            tool_name = tool_call.get('name', 'unknown')
                            tool_input = tool_call.get('input', {})

                            with st.expander(f"🔍 Tool Details: {tool_name}", expanded=False):
                                st.json(tool_input)
                else:
                    st.markdown(f'<div style="padding: 10px;">{content_preview}</div>', unsafe_allow_html=True)

                # Display tool result details
                if msg.role == 'tool':
                    with st.expander("📦 Tool Result Details", expanded=False):
                        st.markdown("**Full Tool Result:**")
                        # Try to parse content as JSON
                        try:
                            parsed_json = json.loads(msg.content)
                            st.json(parsed_json)
                        except Exception:
                            st.code(msg.content, language='text')

                        # Show metadata if available
                        if msg.tool_uses:
                            st.markdown("**Metadata:**")
                            st.json(msg.tool_uses)

                st.divider()

    # Visualizations
    with st.expander(f"📈 Visualizations", expanded=True):
        tab1, tab2, tab3 = st.tabs(["Conversation Flow", "Tool Usage", "Timeline"])

        with tab1:
            fig = create_plotly_graph(messages, f"Conversation Flow - {metadata.session_id[:20]}...")
            st.plotly_chart(fig, use_container_width=True)

        with tab2:
            fig = create_tool_usage_chart(messages)
            st.plotly_chart(fig, use_container_width=True)

        with tab3:
            fig = create_message_timeline(messages)
            st.plotly_chart(fig, use_container_width=True)


def render_comparison_view(
    metadata1: ConversationMetadata, messages1: List[ParsedMessage],
    metadata2: ConversationMetadata, messages2: List[ParsedMessage]
):
    """Render side-by-side comparison"""

    st.header("🔄 Conversation Comparison")

    # Shareable link for comparison
    with st.expander("📎 Share This Comparison", expanded=False):
        import urllib.parse
        params = {
            'project1': metadata1.project_name,
            'session1': metadata1.session_id,
            'project2': metadata2.project_name,
            'session2': metadata2.session_id
        }
        query_string = urllib.parse.urlencode(params)
        shareable_link = f"?{query_string}"

        st.code(shareable_link, language=None)
        st.caption("📋 Copy and append to your dashboard URL to share this comparison")

    # High-level stats comparison
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Session 1 Messages", len(messages1))
        st.metric("Session 2 Messages", len(messages2))

    tool_stats1 = get_tool_usage_stats(messages1)
    tool_stats2 = get_tool_usage_stats(messages2)

    with col2:
        st.metric("Session 1 Tool Calls", tool_stats1['total_calls'])
        st.metric("Session 2 Tool Calls", tool_stats2['total_calls'])

    with col3:
        st.metric("Session 1 Unique Tools", tool_stats1['unique_tools'])
        st.metric("Session 2 Unique Tools", tool_stats2['unique_tools'])

    # Tool usage comparison
    st.subheader("🔧 Tool Usage Comparison")

    # Combine tool names from both sessions
    all_tools = set(tool_stats1['tool_counts'].keys()) | set(tool_stats2['tool_counts'].keys())

    comparison_data = []
    for tool in sorted(all_tools):
        count1 = tool_stats1['tool_counts'].get(tool, 0)
        count2 = tool_stats2['tool_counts'].get(tool, 0)
        diff = count2 - count1

        comparison_data.append({
            'Tool': tool,
            'Session 1': count1,
            'Session 2': count2,
            'Difference': diff,
            'Status': '🟢 More' if diff > 0 else ('🔴 Less' if diff < 0 else '⚪ Same')
        })

    st.dataframe(comparison_data, use_container_width=True, hide_index=True)

    # Visualization
    fig = create_comparison_chart(messages1, messages2)
    st.plotly_chart(fig, use_container_width=True)

    # Tool sequence comparison
    st.subheader("📊 Tool Call Sequences")

    col1, col2 = st.columns(2)

    with col1:
        st.write("**Session 1 Sequence:**")
        if tool_stats1['tool_sequence']:
            sequence_display = " → ".join(tool_stats1['tool_sequence'][:30])
            if len(tool_stats1['tool_sequence']) > 30:
                sequence_display += " → ..."
            st.code(sequence_display, language=None)
        else:
            st.info("No tool calls")

    with col2:
        st.write("**Session 2 Sequence:**")
        if tool_stats2['tool_sequence']:
            sequence_display = " → ".join(tool_stats2['tool_sequence'][:30])
            if len(tool_stats2['tool_sequence']) > 30:
                sequence_display += " → ..."
            st.code(sequence_display, language=None)
        else:
            st.info("No tool calls")

    # System messages comparison
    st.subheader("⚙️ System Messages Comparison")

    system_msgs1 = extract_system_messages(messages1)
    system_msgs2 = extract_system_messages(messages2)

    col1, col2 = st.columns(2)

    with col1:
        st.write(f"**Session 1:** {len(system_msgs1)} system messages")
        for msg in system_msgs1[:5]:
            st.text(f"[{msg['message_index']}] {msg['content'][:100]}...")
        if len(system_msgs1) > 5:
            st.info(f"+ {len(system_msgs1) - 5} more messages")

    with col2:
        st.write(f"**Session 2:** {len(system_msgs2)} system messages")
        for msg in system_msgs2[:5]:
            st.text(f"[{msg['message_index']}] {msg['content'][:100]}...")
        if len(system_msgs2) > 5:
            st.info(f"+ {len(system_msgs2) - 5} more messages")


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

    # Sidebar
    with st.sidebar:
        st.header("Session Selection")

        mode = st.radio(
            "Mode",
            ["Single Session", "Compare Sessions"],
            index=1
        )

        st.divider()

        # Session 1 selector
        st.subheader("Session 1")
        session1_info = render_session_selector("1")

        session2_info = None
        if mode == "Compare Sessions":
            st.divider()
            st.subheader("Session 2")
            session2_info = render_session_selector("2")

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
