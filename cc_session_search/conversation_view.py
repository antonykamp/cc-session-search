"""
Conversation view component for displaying session details
"""

import streamlit as st
import json
import urllib.parse
from typing import List

from cc_session_search.core.conversation_parser import ParsedMessage, ConversationMetadata
from cc_session_search.dashboard_utils import (
    extract_tool_calls,
    extract_system_messages,
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


def render_metadata_section(metadata: ConversationMetadata, messages: List[ParsedMessage], key_suffix: str):
    """Render session metadata section"""
    with st.expander(f"📊 Session Metadata", expanded=False):
        duration_str = format_duration(metadata.started_at, metadata.ended_at)

        # Calculate total tokens and cost
        total_tokens = sum(msg.token_count for msg in messages)
        total_cost = sum(msg.cost_usd for msg in messages)
        user_tokens = sum(msg.token_count for msg in messages if msg.role == 'user')
        assistant_tokens = sum(msg.token_count for msg in messages if msg.role == 'assistant')

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

        # Token and cost statistics
        if total_tokens > 0:
            st.divider()
            st.markdown("**💰 Token Usage & Cost:**")
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Tokens", f"{total_tokens:,}")
                st.caption(f"Input: {user_tokens:,} | Output: {assistant_tokens:,}")
            with col2:
                st.metric("Total Cost", f"${total_cost:.4f}")
            with col3:
                if total_cost > 0 and len(messages) > 0:
                    avg_cost_per_msg = total_cost / len(messages)
                    st.metric("Avg/Message", f"${avg_cost_per_msg:.6f}")

        # Copy link section
        st.divider()
        st.markdown("**📎 Share This Session:**")

        params = {
            f'project{key_suffix}': metadata.project_name,
            f'session{key_suffix}': metadata.session_id
        }
        query_string = urllib.parse.urlencode(params)
        shareable_link = f"?{query_string}"

        st.code(shareable_link, language=None)
        st.caption("📋 Copy and append to your dashboard URL to link directly to this session")

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


def render_system_messages_section(messages: List[ParsedMessage]):
    """Render system messages section"""
    system_msgs = extract_system_messages(messages)
    
    with st.expander(f"⚙️ System Messages ({len(system_msgs)})", expanded=False):
        if system_msgs:
            for msg in system_msgs:
                st.text(f"[{msg['message_index']}] {msg['content']}")
        else:
            st.info("No system messages found")


def render_message_browser(messages: List[ParsedMessage], key_suffix: str):
    """Render the interactive message browser"""
    with st.expander(f"💬 Messages Browser ({len(messages)} messages)", expanded=False):
        # Legend
        st.markdown("""
        **Message Type Legend:**
        - 👤 **User** (Blue) - User input messages
        - 🤖 **Assistant** (Green) - Regular assistant responses
        - 🧠 **Assistant Thinking** (Teal) - Internal reasoning/planning
        - 🎯 **Skill Call** (Purple) - Claude Code skill invocation
        - 🔌 **MCP Tool Call** (Deep Purple) - External MCP server tool invocation
        - ⚡ **Assistant Tool Call** (Orange) - Built-in tool invocation
        - 🔧 **Tool Result** (Amber) - Tool execution results
        - 🏷️ **Meta** (Pink) - Meta messages (caveats, system notes)
        - ⚠️ **System** - Messages with system reminders
        """)
        st.divider()

        # Get unique message types with counts
        type_counts = {}
        for msg in messages:
            msg_type = get_message_type(msg)
            type_counts[msg_type] = type_counts.get(msg_type, 0) + 1

        # Create filter labels with counts
        present_type_labels = []
        for msg_type, count in sorted(type_counts.items(), key=lambda x: x[1], reverse=True):
            if msg_type in MESSAGE_TYPE_LABELS:
                label = f"{MESSAGE_TYPE_LABELS[msg_type]} ({count})"
                present_type_labels.append(label)

        # Message type filter
        selected_type_labels = st.multiselect(
            "Filter by message type (click to select/deselect)",
            present_type_labels,
            default=present_type_labels,
            key=f"type_filter_{key_suffix}"
        )

        # Parse selected types from labels
        label_to_type = {v: k for k, v in MESSAGE_TYPE_LABELS.items()}
        selected_types = []
        for label in selected_type_labels:
            base_label = label.rsplit(' (', 1)[0]
            if base_label in label_to_type:
                selected_types.append(label_to_type[base_label])

        # Filter messages with original indices
        filtered_messages_with_idx = [
            (idx, msg) for idx, msg in enumerate(messages)
            if get_message_type(msg) in selected_types
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
    timestamp_str = msg.timestamp.strftime('%H:%M:%S') if msg.timestamp else 'N/A'

    # Determine message type
    is_thinking = '[Thinking:' in msg.content
    is_tool_call = '[Calling tool:' in msg.content or (msg.role == 'assistant' and msg.tool_uses and ('tool_calls' in msg.tool_uses or 'tool_name' in msg.tool_uses))
    has_system_reminder = '<system-reminder>' in msg.content.lower()

    # Check for tool call and result mappings
    tool_result_idx = None
    is_mcp_call = False
    is_skill_call = False
    mcp_tool_name = None
    skill_name = None

    if msg.role == 'assistant' and msg.tool_uses and 'tool_calls' in msg.tool_uses:
        for tool_call in msg.tool_uses['tool_calls']:
            tool_id = tool_call.get('id', '')
            tool_name = tool_call.get('name', '')

            if tool_name.startswith('mcp__'):
                is_mcp_call = True
                mcp_tool_name = tool_name.replace('mcp__', '').replace('__', ' → ')
            elif tool_name == 'Skill':
                is_skill_call = True
                # Extract skill name from input
                tool_input = tool_call.get('input', {})
                skill_name = tool_input.get('skill', 'unknown')

            if tool_id and tool_id in tool_id_to_result:
                tool_result_idx = tool_id_to_result[tool_id]

    # Check if tool result
    matching_call_idx = None
    matching_call_id = None
    if msg.role == 'tool' and msg.tool_uses:
        if isinstance(msg.tool_uses, dict) and 'tool_use_id' in msg.tool_uses:
            matching_call_id = msg.tool_uses['tool_use_id']
            if matching_call_id in tool_id_to_call:
                matching_call_idx = tool_id_to_call[matching_call_id]

    # Get styling based on message type
    icon, color, label = get_message_styling(
        msg, is_thinking, is_tool_call, is_mcp_call, is_skill_call,
        mcp_tool_name, skill_name, tool_result_idx, matching_call_idx,
        matching_call_id, has_system_reminder
    )

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
    render_message_content(msg, is_thinking, is_tool_call)

    st.divider()


def get_message_styling(
    msg, is_thinking, is_tool_call, is_mcp_call, is_skill_call,
    mcp_tool_name, skill_name, tool_result_idx, matching_call_idx,
    matching_call_id, has_system_reminder
):
    """Determine icon, color, and label for a message"""
    if msg.role == 'user':
        icon, color, label = "👤", "#3498db", "USER"
    elif msg.role == 'assistant':
        if is_thinking:
            icon, color, label = "🧠", "#1abc9c", "ASSISTANT (THINKING)"
        elif is_tool_call:
            if is_skill_call:
                icon = "🎯"
                color = "#9b59b6"
                label = f"SKILL CALL: {skill_name}"
            elif is_mcp_call:
                icon = "🔌"
                color = "#8e44ad"
                label = f"MCP TOOL CALL: {mcp_tool_name}"
            else:
                icon, color, label = "⚡", "#e67e22", "ASSISTANT (TOOL CALL)"
            
            if tool_result_idx is not None:
                label += f" → Result at [{tool_result_idx}]"
        else:
            icon, color, label = "🤖", "#2ecc71", "ASSISTANT"
    elif msg.role == 'tool':
        icon, color, label = "🔧", "#f39c12", "TOOL RESULT"
        if matching_call_idx is not None:
            label += f" ← Called from [{matching_call_idx}]"
        elif matching_call_id:
            label += f" (ID: {matching_call_id[:12]}...)"
    else:
        icon, color, label = "📄", "#95a5a6", msg.role.upper()

    if has_system_reminder:
        icon = "⚠️"
        label += " (SYSTEM)"

    return icon, color, label


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
            st.markdown("**Full Tool Result:**")
            try:
                parsed_json = json.loads(msg.content)
                st.json(parsed_json)
            except Exception:
                st.code(msg.content, language='text')
            
            if msg.tool_uses:
                st.markdown("**Metadata:**")
                st.json(msg.tool_uses)
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
    render_system_messages_section(messages)
    render_message_browser(messages, key_suffix)
    render_visualizations(messages, metadata)
