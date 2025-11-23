"""
Comparison view component for side-by-side session analysis
"""

import streamlit as st
from typing import List

from cc_session_search.core.conversation_parser import ParsedMessage, ConversationMetadata
from cc_session_search.dashboard_utils import (
    extract_system_messages,
    get_tool_usage_stats
)
from cc_session_search.graph_visualizer import create_comparison_chart


def render_stats_comparison(messages1: List[ParsedMessage], messages2: List[ParsedMessage]):
    """Render high-level statistics comparison"""
    st.markdown("**📈 Session Comparison**")

    # Calculate statistics
    total_tokens1 = sum(msg.token_count for msg in messages1)
    total_tokens2 = sum(msg.token_count for msg in messages2)
    total_cost1 = sum(msg.cost_usd for msg in messages1)
    total_cost2 = sum(msg.cost_usd for msg in messages2)

    tool_stats1 = get_tool_usage_stats(messages1)
    tool_stats2 = get_tool_usage_stats(messages2)

    # Primary metrics - Messages and Tokens equally prominent
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        msg_delta = len(messages2) - len(messages1)
        st.metric("Session 1 Messages", len(messages1))
        st.metric("Session 2 Messages", len(messages2), delta=msg_delta)

    with col2:
        token_delta = total_tokens2 - total_tokens1
        st.metric("Session 1 Tokens", f"{total_tokens1:,}")
        st.metric("Session 2 Tokens", f"{total_tokens2:,}", delta=f"{token_delta:,}")

    with col3:
        cost_delta = total_cost2 - total_cost1
        st.metric("Session 1 Cost", f"${total_cost1:.4f}")
        st.metric("Session 2 Cost", f"${total_cost2:.4f}", delta=f"${cost_delta:.4f}")

    with col4:
        tool_delta = tool_stats2['total_calls'] - tool_stats1['total_calls']
        st.metric("Session 1 Tool Calls", tool_stats1['total_calls'])
        st.metric("Session 2 Tool Calls", tool_stats2['total_calls'], delta=tool_delta)

    return tool_stats1, tool_stats2


def render_tool_usage_comparison(tool_stats1: dict, tool_stats2: dict, messages1: List[ParsedMessage], messages2: List[ParsedMessage]):
    """Render tool usage comparison table and chart"""
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

    st.dataframe(comparison_data, width='stretch', hide_index=True)

    # Visualization
    fig = create_comparison_chart(messages1, messages2)
    st.plotly_chart(fig, width='stretch')


def render_tool_sequence_comparison(tool_stats1: dict, tool_stats2: dict):
    """Render tool call sequences comparison"""
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


def render_system_messages_comparison(messages1: List[ParsedMessage], messages2: List[ParsedMessage]):
    """Render system messages comparison"""
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


def render_comparison_view(
    metadata1: ConversationMetadata, messages1: List[ParsedMessage],
    metadata2: ConversationMetadata, messages2: List[ParsedMessage]
):
    """Main function to render complete comparison view"""
    st.header("🔄 Conversation Comparison")

    tool_stats1, tool_stats2 = render_stats_comparison(messages1, messages2)

    render_tool_usage_comparison(tool_stats1, tool_stats2, messages1, messages2)

    render_tool_sequence_comparison(tool_stats1, tool_stats2)

    render_system_messages_comparison(messages1, messages2)
