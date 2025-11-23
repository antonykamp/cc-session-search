"""
Conversation view component for displaying session details
"""

import streamlit as st
import json
from typing import List

from cc_session_search.core.conversation_parser import ParsedMessage, ConversationMetadata
from cc_session_search.dashboard_utils import (
    extract_tool_calls,
    get_tool_usage_stats,
    get_message_type,
    build_tool_call_mapping,
    format_duration,
    MESSAGE_TYPE_INFO,
    MESSAGE_TYPE_LABELS
)
from cc_session_search.graph_visualizer import (
    create_plotly_graph,
    create_tool_usage_chart,
    create_message_timeline
)


def render_subagent_section(metadata: ConversationMetadata, key_suffix: str):
    """Render subagent information section if this is a parent or subagent session"""
    from cc_session_search.core.searcher import SessionSearcher

    # Display parent link if this is a subagent
    if metadata.is_subagent:
        st.info(f"🔗 **Subagent Session** — Agent Type: `{metadata.agent_type or 'Unknown'}` | Parent: `{metadata.parent_session_id}`")

        # Use link instead of button to avoid rerun conflicts
        parent_url = f"?mode=single&project1={metadata.project_name}&session1={metadata.parent_session_id}"
        st.markdown(f"[↗️ View Parent Session]({parent_url})")
        return

    # Find subagents for this session
    searcher = SessionSearcher()
    project_name = metadata.project_name

    # Extract the base session ID (remove .jsonl and conversation- prefix if present)
    session_id = metadata.session_id
    if session_id.startswith('conversation-'):
        session_id = session_id.replace('conversation-', '')

    subagents = searcher.find_subagents_for_session(session_id, project_name)

    if subagents:
        with st.expander(f"🤖 Subagent Sessions ({len(subagents)})", expanded=False):
            st.markdown("This session spawned the following subagent(s):")

            for sub in subagents:
                col1, col2, col3, col4 = st.columns([2, 2, 1, 1])

                with col1:
                    agent_type_badge = sub['agent_type'] or 'Unknown'
                    st.markdown(f"**{agent_type_badge}**")

                with col2:
                    st.caption(f"ID: `{sub['agent_id']}`")

                with col3:
                    st.caption(f"📝 {sub['message_count']} messages")

                with col4:
                    # Use link instead of button to avoid rerun conflicts
                    sub_url = f"?mode=single&project1={project_name}&session1={sub['session_id']}"
                    st.markdown(f"[View]({sub_url})")

                st.divider()


def render_metadata_section(metadata: ConversationMetadata, messages: List[ParsedMessage], key_suffix: str):
    """Render session metadata section"""
    from cc_session_search.core.searcher import SessionSearcher

    with st.expander(f"📊 Session Metadata", expanded=True):
        # Calculate message and token statistics for this session
        total_messages = len(messages)
        user_messages = sum(1 for msg in messages if msg.role == 'user')
        assistant_messages = sum(1 for msg in messages if msg.role == 'assistant')
        tool_messages = sum(1 for msg in messages if msg.role == 'tool')

        total_tokens = sum(msg.token_count for msg in messages)
        user_tokens = sum(msg.token_count for msg in messages if msg.role == 'user')
        assistant_tokens = sum(msg.token_count for msg in messages if msg.role == 'assistant')
        total_cost = sum(msg.cost_usd for msg in messages)

        duration_str = format_duration(metadata.started_at, metadata.ended_at)

        # Check for subagents and calculate aggregate metrics
        aggregate_metrics = None
        if not metadata.is_subagent:
            searcher = SessionSearcher()
            session_id = metadata.session_id
            if session_id.startswith('conversation-'):
                session_id = session_id.replace('conversation-', '')

            subagents = searcher.find_subagents_for_session(session_id, metadata.project_name)
            if subagents:
                # Get full session data with aggregate metrics
                session_data = searcher.get_session_with_subagents(session_id, metadata.project_name)
                if session_data:
                    aggregate_metrics = session_data['aggregate_metrics']

        # Display aggregate metrics if we have subagents
        if aggregate_metrics:
            st.markdown("**🌐 Aggregate Summary (Including Subagents)**")
            col1, col2, col3, col4 = st.columns(4)

            with col1:
                st.metric(
                    "Total Sessions",
                    f"{aggregate_metrics['session_count']}",
                    help="Main session + subagents"
                )

            with col2:
                st.metric(
                    "Total Tokens",
                    f"{aggregate_metrics['total_tokens']:,}",
                    delta=f"+{aggregate_metrics['subagent_tokens']:,} from subagents"
                )

            with col3:
                st.metric(
                    "Total Cost",
                    f"${aggregate_metrics['total_cost_usd']:.4f}",
                    delta=f"+${aggregate_metrics['subagent_cost']:.4f} from subagents"
                )

            with col4:
                pct_subagent = (aggregate_metrics['subagent_tokens'] / aggregate_metrics['total_tokens'] * 100) if aggregate_metrics['total_tokens'] > 0 else 0
                st.metric(
                    "Subagent %",
                    f"{pct_subagent:.1f}%",
                    help="Percentage of tokens from subagents"
                )

            st.divider()

        # Key metrics section - Messages and Tokens equally prominent
        st.markdown("**📈 Session Summary**")
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("Total Messages", f"{total_messages}")
            st.caption(f"👤 {user_messages} · 🤖 {assistant_messages} · 🔧 {tool_messages}")

        with col2:
            st.metric("Total Tokens", f"{total_tokens:,}")
            st.caption(f"Input: {user_tokens:,} | Output: {assistant_tokens:,}")

        with col3:
            st.metric("Total Cost", f"${total_cost:.4f}")
            if total_cost > 0 and total_messages > 0:
                avg_cost = total_cost / total_messages
                st.caption(f"${avg_cost:.6f} per message")

        with col4:
            st.metric("Duration", duration_str)
            if metadata.started_at:
                st.caption(f"{metadata.started_at.strftime('%Y-%m-%d %H:%M:%S')}")

        # Session details
        st.divider()
        st.markdown("**🔍 Session Details**")
        col1, col2 = st.columns(2)

        with col1:
            st.write(f"**Session ID:** {metadata.session_id}")
            st.write(f"**Project:** {metadata.project_name}")

        with col2:
            st.write(f"**Git Branch:** {metadata.git_branch or 'N/A'}")
            st.write(f"**Working Dir:** {metadata.working_directory or 'N/A'}")

        # Local file path
        st.divider()
        with st.expander("🗂️ Local File Path", expanded=False):
            st.code(metadata.file_path, language="bash")


def render_tool_usage_section(messages: List[ParsedMessage]):
    """Render tool usage statistics section"""
    tool_stats = get_tool_usage_stats(messages)

    with st.expander(f"🔧 Tool Usage ({tool_stats['total_calls']} calls)", expanded=True):
        if tool_stats['total_calls'] > 0:
            tool_df_data = [
                {"Tool": tool, "Count": count}
                for tool, count in sorted(tool_stats['tool_counts'].items(), key=lambda x: x[1], reverse=True)
            ]
            st.dataframe(tool_df_data, width='stretch', hide_index=True)
        else:
            st.info("No tool calls in this conversation")


def render_message_browser(messages: List[ParsedMessage], key_suffix: str):
    """Render the interactive message browser"""
    with st.expander(f"💬 Messages Browser ({len(messages)} messages)", expanded=False):
        # Legend
        st.markdown("""
        **Message Type Legend:**
        - 👤 **User** (Blue) - User input messages
        - 🤖 **Assistant** (Green) - Regular assistant responses
        - 🧠 **Assistant Thinking** (Teal) - Internal reasoning/planning
        - 🎯 **Skill Context** (Purple) - Skill calls and skill file reads
        - 🏷️ **Meta** (Pink) - Meta messages (caveats, system notes)
        - 🔌 **MCP Tool Call** (Deep Purple) - External MCP server tool invocation
        - ⚡ **Assistant Tool Call** (Orange) - Built-in tool invocation
        - 🔧 **Tool Result** (Amber) - Tool execution results
        - ⚠️ **System** - Messages with system reminders
        """)
        st.divider()

        # Get unique message types with counts
        type_counts = {}
        for msg in messages:
            msg_type = get_message_type(msg, messages)
            if msg_type != 'file-history-snapshot':  # Ignore file history
                type_counts[msg_type] = type_counts.get(msg_type, 0) + 1

        # Define hierarchical filter groups
        filter_groups = {
            'User': ['user'],
            'Assistant': ['assistant_text', 'assistant_thinking'],
            'All Tools': [
                'basic_tool_call', 'basic_tool_result',
                'mcp_list', 'mcp_read', 'mcp_tool', 'mcp_result',
                'skill_execute', 'skill_read', 'skill_result',
                'subagent_call', 'subagent_result'
            ],
            'Meta': ['meta'],
            '  → MCP Only': ['mcp_list', 'mcp_read', 'mcp_tool', 'mcp_result'],
            '  → Skills Only': ['skill_execute', 'skill_read', 'skill_result'],
            '  → Subagents Only': ['subagent_call', 'subagent_result']
        }

        # Create filter options with counts
        filter_options = []
        filter_type_mapping = {}  # Maps display label to list of message types

        for group_name, msg_types in filter_groups.items():
            # Count messages in this group
            count = sum(type_counts.get(mt, 0) for mt in msg_types)
            if count > 0:
                label = f"{group_name} ({count})"
                filter_options.append(label)
                filter_type_mapping[label] = msg_types

        # Message type filter with hierarchical groups
        selected_filters = st.multiselect(
            "Filter by message type",
            filter_options,
            default=[opt for opt in filter_options if not opt.startswith('  →')],  # Default: all except subgroups
            key=f"type_filter_{key_suffix}",
            help="Main categories select all messages. Subgroups (→) allow filtering specific tool types."
        )

        # Build selected types from hierarchical selection
        selected_types = set()
        for filter_label in selected_filters:
            selected_types.update(filter_type_mapping[filter_label])

        # Filter messages with original indices
        filtered_messages_with_idx = [
            (idx, msg) for idx, msg in enumerate(messages)
            if get_message_type(msg, messages) in selected_types
        ]

        # Show filter summary
        if len(filtered_messages_with_idx) != len(messages):
            st.info(f"📊 Showing {len(filtered_messages_with_idx)} of {len(messages)} messages")

        # Pagination
        messages_per_page = 20
        total_pages = (len(filtered_messages_with_idx) + messages_per_page - 1) // messages_per_page

        if total_pages > 0:
            page = 1
            if total_pages > 1:
                page = st.slider("Page", 1, total_pages, 1, key=f"page_{key_suffix}")

            start_idx = (page - 1) * messages_per_page
            end_idx = min(start_idx + messages_per_page, len(filtered_messages_with_idx))

            # Build tool call mappings
            tool_id_to_call, tool_id_to_result = build_tool_call_mapping(messages)

            # Render messages
            for original_idx, msg in filtered_messages_with_idx[start_idx:end_idx]:
                render_single_message(
                    msg, original_idx, messages,
                    tool_id_to_call, tool_id_to_result
                )


def render_single_message(
    msg: ParsedMessage,
    original_idx: int,
    all_messages: List[ParsedMessage],
    tool_id_to_call: dict,
    tool_id_to_result: dict
):
    """Render a single message with all its details"""
    from cc_session_search.dashboard_utils import get_message_type, MESSAGE_TYPE_INFO

    timestamp_str = msg.timestamp.strftime('%H:%M:%S') if msg.timestamp else 'N/A'

    # Get message type (pass all_messages for proper tool result categorization)
    msg_type = get_message_type(msg, all_messages)

    # Skip file history snapshots
    if msg_type == 'file-history-snapshot':
        return

    # Extract details for labeling
    tool_detail = None
    tool_result_idx = None
    matching_call_idx = None

    # For tool calls, extract tool-specific details
    if msg.role == 'assistant' and msg.tool_uses and 'tool_calls' in msg.tool_uses:
        for tool_call in msg.tool_uses['tool_calls']:
            tool_id = tool_call.get('id', '')
            tool_name = tool_call.get('name', '')
            tool_input = tool_call.get('input', {})

            # Extract specific details based on tool type
            if msg_type == 'subagent_call':
                tool_detail = tool_input.get('subagent_type', 'Unknown')
            elif msg_type in ('mcp_list', 'mcp_read', 'mcp_tool'):
                tool_detail = tool_name.replace('mcp__', '').replace('__', ' → ')
            elif msg_type == 'skill_execute':
                tool_detail = tool_input.get('skill', 'unknown')
            elif msg_type == 'skill_read':
                tool_detail = tool_input.get('file_path', '')
            elif msg_type == 'basic_tool_call':
                tool_detail = tool_name

            # Find result index
            if tool_id and tool_id in tool_id_to_result:
                tool_result_idx = tool_id_to_result[tool_id]
            break

    # For tool results, find matching call
    if msg.role == 'tool' and msg.tool_uses:
        if isinstance(msg.tool_uses, dict) and 'tool_use_id' in msg.tool_uses:
            matching_call_id = msg.tool_uses['tool_use_id']
            if matching_call_id in tool_id_to_call:
                matching_call_idx = tool_id_to_call[matching_call_id]

        # Extract agent ID for subagent results
        if msg_type == 'subagent_result':
            tool_detail = msg.tool_uses.get('agentId', 'unknown')

    # Get styling from MESSAGE_TYPE_INFO
    icon, color, base_label = MESSAGE_TYPE_INFO.get(msg_type, ('📄', '#95a5a6', 'UNKNOWN'))

    # Build label with details
    label = base_label
    if tool_detail:
        if msg_type in ('subagent_call', 'skill_execute', 'basic_tool_call'):
            label = f"{base_label}: {tool_detail}"
        elif msg_type in ('mcp_list', 'mcp_read', 'mcp_tool'):
            label = f"{base_label}: {tool_detail}"
        elif msg_type == 'skill_read':
            # Show just filename for skill read
            import os
            filename = os.path.basename(tool_detail) if tool_detail else 'unknown'
            label = f"{base_label}: {filename}"
        elif msg_type == 'subagent_result':
            label = f"{base_label} (Agent: {tool_detail})"

    # Add result/call links
    if tool_result_idx is not None:
        label += f" → Result at [{tool_result_idx}]"
    if matching_call_idx is not None:
        label += f" ← Called from [{matching_call_idx}]"

    # Format cost display
    cost_display = ""
    if msg.token_count > 0:
        cost_display = f'<span style="color: #7f8c8d; font-weight: normal; font-size: 0.85em;"> | {msg.token_count} tokens | ${msg.cost_usd:.6f}</span>'

    # Display message header
    st.markdown(
        f'<div style="background-color: {color}22; border-left: 4px solid {color}; '
        f'padding: 10px; margin: 5px 0; border-radius: 5px;">'
        f'<p style="margin: 0; color: {color}; font-weight: bold;">{icon} [{original_idx}] {label} '
        f'<span style="color: #7f8c8d; font-weight: normal; font-size: 0.9em;">({timestamp_str})</span>{cost_display}</p>'
        f'</div>',
        unsafe_allow_html=True
    )

    # Display message content
    is_thinking = msg_type == 'assistant_thinking'
    is_tool_call = msg_type in ('basic_tool_call', 'mcp_list', 'mcp_read', 'mcp_tool', 'skill_execute', 'skill_read', 'subagent_call')
    render_message_content(msg, is_thinking, is_tool_call)

    st.divider()


def render_message_content(msg: ParsedMessage, is_thinking: bool, is_tool_call: bool):
    """Render the content of a message with appropriate formatting"""
    max_content_length = 200
    content_preview = msg.content[:max_content_length] + "..." if len(msg.content) > max_content_length else msg.content

    if is_thinking:
        if len(msg.content) > max_content_length:
            st.markdown(
                f'<div style="padding: 10px; background-color: #f8f9fa; border-radius: 5px; '
                f'font-style: italic; color: #6c757d;">{content_preview}</div>',
                unsafe_allow_html=True
            )
            with st.expander("🧠 Full Thought", expanded=False):
                st.markdown(
                    f'<div style="padding: 10px; background-color: #f8f9fa; border-radius: 5px; '
                    f'font-style: italic; color: #6c757d;">{msg.content}</div>',
                    unsafe_allow_html=True
                )
        else:
            st.markdown(
                f'<div style="padding: 10px; background-color: #f8f9fa; border-radius: 5px; '
                f'font-style: italic; color: #6c757d;">{msg.content}</div>',
                unsafe_allow_html=True
            )
    elif is_tool_call:
        st.markdown(
            f'<div style="padding: 10px; background-color: #fff3cd; border-radius: 5px; '
            f'font-family: monospace; color: #856404;">{content_preview}</div>',
            unsafe_allow_html=True
        )
        
        # Show detailed tool call information
        if msg.tool_uses and 'tool_calls' in msg.tool_uses:
            for tool_call in msg.tool_uses['tool_calls']:
                tool_name = tool_call.get('name', 'unknown')
                tool_input = tool_call.get('input', {})
                
                # Special handling for Skill calls to make them more visible
                if tool_name == 'Skill':
                    skill_name = tool_input.get('skill', 'unknown')
                    st.markdown(f"**🎯 Skill Executed:** `{skill_name}`")

                with st.expander(f"🔍 Tool Details: {tool_name}", expanded=False):
                    st.json(tool_input)
    elif msg.role == 'tool':
        st.markdown(f'<div style="padding: 10px;">{content_preview}</div>', unsafe_allow_html=True)
        
        with st.expander("📦 Tool Result Details", expanded=False):            
            if msg.tool_uses:
                st.json(msg.tool_uses)
            else:
                try:
                    parsed_json = json.loads(msg.content)
                    st.json(parsed_json)
                except Exception:
                    st.code(msg.content, language='text')

    else:
        if len(msg.content) > max_content_length:
            st.markdown(f'<div style="padding: 10px;">{content_preview}</div>', unsafe_allow_html=True)
            with st.expander("💬 Full Message", expanded=False):
                st.markdown(f'<div style="padding: 10px;">{msg.content}</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div style="padding: 10px;">{msg.content}</div>', unsafe_allow_html=True)


def render_visualizations(messages: List[ParsedMessage], metadata: ConversationMetadata):
    """Render visualization section"""
    with st.expander(f"📈 Visualizations", expanded=True):
        tab1, tab2, tab3 = st.tabs(["Conversation Flow", "Tool Usage", "Timeline"])

        with tab1:
            fig = create_plotly_graph(messages, f"Conversation Flow - {metadata.session_id[:20]}...")
            st.plotly_chart(fig, width='stretch')

        with tab2:
            fig = create_tool_usage_chart(messages)
            st.plotly_chart(fig, width='stretch')

        with tab3:
            fig = create_message_timeline(messages)
            st.plotly_chart(fig, width='stretch')


def render_conversation_view(metadata: ConversationMetadata, messages: List[ParsedMessage], key_suffix: str):
    """Main function to render complete conversation view"""
    render_metadata_section(metadata, messages, key_suffix)
    render_tool_usage_section(messages)
    render_subagent_section(metadata, key_suffix)
    render_message_browser(messages, key_suffix)
    render_visualizations(messages, metadata)
