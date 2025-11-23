"""
Conversation Graph Visualizer

Creates interactive visualizations of conversation flow and structure.
"""

from typing import List, Dict, Any, Tuple
import plotly.graph_objects as go
from collections import defaultdict

from cc_session_search.core.conversation_parser import ParsedMessage


def build_conversation_graph(messages: List[ParsedMessage]) -> Dict[str, Any]:
    """
    Build a graph representation of the conversation flow.

    Returns a dictionary with nodes and edges suitable for visualization.
    """
    from cc_session_search.dashboard_utils import get_message_type

    nodes = []
    edges = []

    # Map original index to node index (accounting for filtered messages)
    original_to_node_idx = {}
    node_idx = 0

    for original_idx, msg in enumerate(messages):
        # Use unified message type detection (pass all messages for proper categorization)
        display_type = get_message_type(msg, messages)

        # Skip file history snapshots
        if display_type == 'file-history-snapshot':
            continue

        # Create node for each message
        node = {
            'id': node_idx,
            'original_idx': original_idx,
            'role': msg.role,
            'display_type': display_type,
            'timestamp': msg.timestamp.isoformat() if msg.timestamp else None,
            'content_length': len(msg.content),
            'has_tool_use': msg.tool_uses is not None,
            'label': f"{display_type}_{node_idx}"
        }
        nodes.append(node)
        original_to_node_idx[original_idx] = node_idx

        # Create edge to previous node (conversation flow)
        if node_idx > 0:
            edges.append({
                'source': node_idx - 1,
                'target': node_idx,
                'type': 'flow',
                'label': 'next'
            })

        node_idx += 1

    return {
        'nodes': nodes,
        'edges': edges,
        'original_to_node_idx': original_to_node_idx
    }


def create_plotly_graph(messages: List[ParsedMessage], title: str = "Conversation Flow") -> go.Figure:
    """
    Create an interactive Plotly visualization of the conversation graph.
    Similar to a sequence diagram with temporal flow from top to bottom.
    """
    graph_data = build_conversation_graph(messages)
    nodes = graph_data['nodes']
    edges = graph_data['edges']

    # Sequence diagram style: each message in chronological order vertically
    positions = {}
    y_spacing = 30  # Tighter vertical spacing for sequence diagram

    # Horizontal lanes for different message types (columns)
    # Columns: User | Assistant | Basic Tools | Tool Results | Meta | MCP | Skill | Subagent
    x_positions = {
        # User column
        'user': 0,

        # Assistant column (thinking and text same position)
        'assistant_text': 100,
        'assistant_thinking': 100,

        # Basic tool calls column
        'basic_tool_call': 200,

        # Tool results column (next to basic tools, all results here, colored by executor)
        'basic_tool_result': 300,
        'mcp_result': 300,
        'skill_result': 300,
        'subagent_result': 300,

        # Meta column
        'meta': 400,

        # MCP calls column (list, read, tool all same color/position)
        'mcp_list': 500,
        'mcp_read': 500,
        'mcp_tool': 500,

        # Skill calls column (execute and read same position)
        'skill_execute': 600,
        'skill_read': 600,

        # Subagent calls column
        'subagent_call': 700
    }

    # Position nodes chronologically (top to bottom)
    for idx, node in enumerate(nodes):
        display_type = node.get('display_type', node['role'])

        # Get x position based on type
        x = x_positions.get(display_type, 200)

        # Y position is just the index (temporal order)
        y = -idx * y_spacing  # Negative for top-to-bottom

        positions[node['id']] = (x, y)

    # Build tool call to tool result mapping using original indices
    tool_call_map = {}  # tool_use_id -> (tool_call_node_idx, tool_result_node_idx)
    original_to_node_idx = graph_data['original_to_node_idx']

    for node in nodes:
        original_idx = node['original_idx']
        msg = messages[original_idx]

        # If this is a tool call, record it
        if msg.role == 'assistant' and msg.tool_uses and 'tool_calls' in msg.tool_uses:
            for tool_call in msg.tool_uses['tool_calls']:
                tool_id = tool_call.get('id')
                if tool_id:
                    tool_call_map[tool_id] = {'call_idx': node['id'], 'result_idx': None}

        # If this is a tool result, match it by tool_use_id
        elif msg.role == 'tool' and msg.tool_uses:
            # Check if we have the tool_use_id directly
            if isinstance(msg.tool_uses, dict) and 'tool_use_id' in msg.tool_uses:
                tool_id = msg.tool_uses['tool_use_id']
                if tool_id in tool_call_map:
                    tool_call_map[tool_id]['result_idx'] = node['id']

    # Create edge traces - temporal flow
    flow_edge_x = []
    flow_edge_y = []

    for edge in edges:
        source_pos = positions[edge['source']]
        target_pos = positions[edge['target']]

        # Only draw if target is below source (temporal flow)
        if target_pos[1] < source_pos[1]:
            flow_edge_x.extend([source_pos[0], target_pos[0], None])
            flow_edge_y.extend([source_pos[1], target_pos[1], None])

    flow_edge_trace = go.Scatter(
        x=flow_edge_x,
        y=flow_edge_y,
        mode='lines',
        line=dict(width=0.5, color='#e0e0e0', dash='dot'),
        hoverinfo='none',
        showlegend=False,
        name='Flow'
    )

    # Create tool call -> result connections
    tool_edge_x = []
    tool_edge_y = []

    for tool_id, mapping in tool_call_map.items():
        call_idx = mapping['call_idx']
        result_idx = mapping['result_idx']

        if result_idx is not None:
            call_pos = positions[call_idx]
            result_pos = positions[result_idx]

            tool_edge_x.extend([call_pos[0], result_pos[0], None])
            tool_edge_y.extend([call_pos[1], result_pos[1], None])

    tool_edge_trace = go.Scatter(
        x=tool_edge_x,
        y=tool_edge_y,
        mode='lines',
        line=dict(width=2, color='#ff9800', dash='solid'),
        hoverinfo='none',
        showlegend=True,
        name='Tool Call → Result'
    )

    # Import color mapping
    from cc_session_search.dashboard_utils import MESSAGE_TYPE_INFO, MESSAGE_TYPE_LABELS

    # Create node traces (one per display type for coloring)
    node_traces = []

    # Get unique display types from nodes
    unique_types = set(n.get('display_type') for n in nodes)

    # Order legend by connecting related nodes (calls with their results)
    legend_order = [
        'user',
        'assistant_text',
        'assistant_thinking',
        'basic_tool_call',
        'basic_tool_result',
        'mcp_list',
        'mcp_read',
        'mcp_tool',
        'mcp_result',
        'skill_execute',
        'skill_read',
        'skill_result',
        'subagent_call',
        'subagent_result',
        'meta'
    ]

    # Process types in legend order
    for display_type in legend_order:
        if display_type not in unique_types:
            continue

        # Get color and label from MESSAGE_TYPE_INFO
        if display_type in MESSAGE_TYPE_INFO:
            icon, color, base_label = MESSAGE_TYPE_INFO[display_type]
            label = MESSAGE_TYPE_LABELS.get(display_type, base_label)
        else:
            color, label = '#95a5a6', display_type.upper()

        type_nodes = [n for n in nodes if n.get('display_type') == display_type]

        if not type_nodes:
            continue

        node_x = [positions[n['id']][0] for n in type_nodes]
        node_y = [positions[n['id']][1] for n in type_nodes]

        node_text = []
        for n in type_nodes:
            text = f"[{n['id']}] {label}<br>Length: {n['content_length']} chars"
            node_text.append(text)

        trace = go.Scatter(
            x=node_x,
            y=node_y,
            mode='markers',
            marker=dict(
                size=12,
                color=color,
                line=dict(width=1, color='white'),
                symbol='circle'
            ),
            hovertext=node_text,
            hoverinfo='text',
            name=label,
            showlegend=True
        )
        node_traces.append(trace)

    # Add vertical lane lines for sequence diagram effect
    lane_lines_x = []
    lane_lines_y = []

    min_y = min(positions[n['id']][1] for n in nodes)
    max_y = 0

    # Define axis ticks explicitly to ensure correct ordering
    # Columns: User | Assistant | Basic Tools | Tool Results | Meta | MCP | Skill | Subagent
    axis_ticks = [
        (0, 'User'),
        (100, 'Assistant'),
        (200, 'Basic Tools'),
        (300, 'Tool Results'),
        (400, 'Meta'),
        (500, 'MCP'),
        (600, 'Skill'),
        (700, 'Subagent')
    ]
    tick_vals = [t[0] for t in axis_ticks]
    tick_text = [t[1] for t in axis_ticks]

    for x_pos in tick_vals:
        lane_lines_x.extend([x_pos, x_pos, None])
        lane_lines_y.extend([max_y, min_y - 50, None])

    lane_trace = go.Scatter(
        x=lane_lines_x,
        y=lane_lines_y,
        mode='lines',
        line=dict(width=0.5, color='#e0e0e0', dash='dash'),
        hoverinfo='none',
        showlegend=False
    )

    # Create figure with all traces
    fig = go.Figure(data=[lane_trace, flow_edge_trace, tool_edge_trace] + node_traces)

    fig.update_layout(
        title=dict(
            text=title,
            x=0.5,
            xanchor='center'
        ),
        showlegend=True,
        hovermode='closest',
        margin=dict(b=40, l=60, r=60, t=60),
        xaxis=dict(
            showgrid=False,
            zeroline=False,
            showticklabels=True,
            fixedrange=False,
            tickmode='array',
            tickvals=tick_vals,
            ticktext=tick_text,
            range=[-20, max(tick_vals) + 100]
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor='rgba(200,200,200,0.2)',
            zeroline=False,
            showticklabels=False,
            fixedrange=False
        ),
        plot_bgcolor='rgba(250,250,250,0.3)',
        paper_bgcolor='rgba(0,0,0,0)',
        height=800,
        legend=dict(
            yanchor="top",
            y=0.99,
            xanchor="right",
            x=0.99,
            bgcolor='rgba(128,128,128,0.15)',
            bordercolor='rgba(128,128,128,0.4)',
            borderwidth=1,
            font=dict(
                size=11
            )
        ),
        dragmode='pan'
    )

    return fig


def create_tool_usage_chart(messages: List[ParsedMessage]) -> go.Figure:
    """Create a bar chart of tool usage."""
    from collections import Counter

    # Extract tool calls
    tool_calls = []
    for msg in messages:
        if msg.role == 'assistant' and msg.tool_uses:
            # Handle new format: tool_calls array
            if 'tool_calls' in msg.tool_uses:
                for tool_block in msg.tool_uses['tool_calls']:
                    tool_name = tool_block.get('name', 'unknown')
                    
                    # Enhance tool names for better visibility
                    if tool_name == 'Skill':
                        skill = tool_block.get('input', {}).get('skill', 'unknown')
                        tool_name = f"Skill: {skill}"
                    elif tool_name.startswith('mcp__'):
                        mcp_name = tool_name.replace('mcp__', '').replace('__', ' → ')
                        tool_name = f"MCP: {mcp_name}"
                        
                    tool_calls.append(tool_name)
            # Handle old format: direct tool_name field
            elif 'tool_name' in msg.tool_uses:
                tool_name = msg.tool_uses.get('tool_name', 'unknown')
                tool_calls.append(tool_name)

    if not tool_calls:
        # Return empty figure
        fig = go.Figure()
        fig.add_annotation(
            text="No tool calls in this conversation",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=16)
        )
        fig.update_layout(height=300)
        return fig

    # Count tools
    tool_counts = Counter(tool_calls)

    # Create bar chart
    fig = go.Figure(data=[
        go.Bar(
            x=list(tool_counts.keys()),
            y=list(tool_counts.values()),
            marker_color='#3498db',
            text=list(tool_counts.values()),
            textposition='auto',
        )
    ])

    fig.update_layout(
        title="Tool Usage Distribution",
        xaxis_title="Tool Name",
        yaxis_title="Number of Calls",
        height=400,
        showlegend=False
    )

    return fig


def create_message_timeline(messages: List[ParsedMessage]) -> go.Figure:
    """Create a timeline visualization of messages."""
    # Filter messages with timestamps
    timestamped_messages = [msg for msg in messages if msg.timestamp]

    if not timestamped_messages:
        fig = go.Figure()
        fig.add_annotation(
            text="No timestamp information available",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=16)
        )
        fig.update_layout(height=300)
        return fig

    # Prepare data
    role_colors = {
        'user': '#3498db',
        'assistant': '#2ecc71',
        'tool': '#f39c12',
        'system': '#e74c3c'
    }

    # Create scatter plot
    traces = []

    for role, color in role_colors.items():
        role_msgs = [msg for msg in timestamped_messages if msg.role == role]

        if not role_msgs:
            continue

        timestamps = [msg.timestamp for msg in role_msgs]
        indices = [timestamped_messages.index(msg) for msg in role_msgs]
        hover_text = [
            f"[{timestamped_messages.index(msg)}] {msg.role}<br>"
            f"{msg.timestamp.strftime('%Y-%m-%d %H:%M:%S')}<br>"
            f"{len(msg.content)} chars"
            for msg in role_msgs
        ]

        trace = go.Scatter(
            x=timestamps,
            y=indices,
            mode='markers',
            marker=dict(size=10, color=color),
            name=role.capitalize(),
            hovertext=hover_text,
            hoverinfo='text'
        )
        traces.append(trace)

    fig = go.Figure(data=traces)

    fig.update_layout(
        title="Message Timeline",
        xaxis_title="Time",
        yaxis_title="Message Index",
        height=400,
        hovermode='closest'
    )

    return fig


def create_comparison_chart(
    messages1: List[ParsedMessage],
    messages2: List[ParsedMessage],
    title: str = "Tool Usage Comparison"
) -> go.Figure:
    """Create a side-by-side comparison chart of tool usage."""
    from collections import Counter

    # Extract tool calls from both sessions
    def get_tool_counts(messages):
        tool_calls = []
        for msg in messages:
            if msg.role == 'assistant' and msg.tool_uses:
                # Handle new format: tool_calls array
                if 'tool_calls' in msg.tool_uses:
                    for tool_block in msg.tool_uses['tool_calls']:
                        tool_name = tool_block.get('name', 'unknown')
                        
                        # Enhance tool names
                        if tool_name == 'Skill':
                            skill = tool_block.get('input', {}).get('skill', 'unknown')
                            tool_name = f"Skill: {skill}"
                        elif tool_name.startswith('mcp__'):
                            mcp_name = tool_name.replace('mcp__', '').replace('__', ' → ')
                            tool_name = f"MCP: {mcp_name}"
                            
                        tool_calls.append(tool_name)
                # Handle old format: direct tool_name field
                elif 'tool_name' in msg.tool_uses:
                    tool_name = msg.tool_uses.get('tool_name', 'unknown')
                    tool_calls.append(tool_name)
        return Counter(tool_calls)

    counts1 = get_tool_counts(messages1)
    counts2 = get_tool_counts(messages2)

    # Get all unique tools
    all_tools = sorted(set(counts1.keys()) | set(counts2.keys()))

    if not all_tools:
        fig = go.Figure()
        fig.add_annotation(
            text="No tool calls in either conversation",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=16)
        )
        fig.update_layout(height=400)
        return fig

    # Create grouped bar chart
    fig = go.Figure(data=[
        go.Bar(
            name='Session 1',
            x=all_tools,
            y=[counts1.get(tool, 0) for tool in all_tools],
            marker_color='#3498db'
        ),
        go.Bar(
            name='Session 2',
            x=all_tools,
            y=[counts2.get(tool, 0) for tool in all_tools],
            marker_color='#2ecc71'
        )
    ])

    fig.update_layout(
        title=title,
        xaxis_title="Tool Name",
        yaxis_title="Number of Calls",
        barmode='group',
        height=400
    )

    return fig
