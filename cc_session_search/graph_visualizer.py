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
    nodes = []
    edges = []

    # Track tool call relationships
    tool_call_map = {}  # message_index -> tool_result_index

    for idx, msg in enumerate(messages):
        # Determine message subtype for better visualization
        is_thinking = '[Thinking:' in msg.content
        is_tool_call = '[Calling tool:' in msg.content
        is_mcp_call = False
        is_skill_call = False
        skill_name = None
        mcp_tool_name = None

        # Check if this is an MCP tool call or skill call
        if msg.role == 'assistant' and msg.tool_uses and 'tool_calls' in msg.tool_uses:
            is_tool_call = True  # Ensure flag is set even if text marker is missing
            for tool_call in msg.tool_uses['tool_calls']:
                tool_name = tool_call.get('name', '')
                if tool_name.startswith('mcp__'):
                    is_mcp_call = True
                    mcp_tool_name = tool_name.replace('mcp__', '').replace('__', ' → ')
                elif tool_name == 'Skill':
                    is_skill_call = True
                    tool_input = tool_call.get('input', {})
                    skill_name = tool_input.get('skill', 'unknown')

        # Determine display type for coloring
        if msg.role == 'assistant':
            if is_thinking:
                display_type = 'assistant_thinking'
            elif is_skill_call:
                display_type = 'assistant_skill_call'
            elif is_mcp_call:
                display_type = 'assistant_mcp_call'
            elif is_tool_call:
                display_type = 'assistant_tool_call'
            else:
                display_type = 'assistant_text'
        else:
            display_type = msg.role

        # Create node for each message
        node = {
            'id': idx,
            'role': msg.role,
            'display_type': display_type,
            'timestamp': msg.timestamp.isoformat() if msg.timestamp else None,
            'content_length': len(msg.content),
            'has_tool_use': msg.tool_uses is not None,
            'label': f"{msg.role}_{idx}",
            'is_thinking': is_thinking,
            'is_tool_call': is_tool_call,
            'skill_name': skill_name,
            'mcp_tool_name': mcp_tool_name
        }
        nodes.append(node)

        # Create edge to previous message (conversation flow)
        if idx > 0:
            edges.append({
                'source': idx - 1,
                'target': idx,
                'type': 'flow',
                'label': 'next'
            })

    return {
        'nodes': nodes,
        'edges': edges
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

    # Horizontal lanes for different message types
    x_positions = {
        'user': 50,
        'assistant_text': 150,
        'assistant_thinking': 150,
        'assistant_tool_call': 250,
        'assistant_skill_call': 300,
        'assistant_mcp_call': 350,
        'tool': 450,
        'file-history-snapshot': 550
    }

    # Position nodes chronologically (top to bottom)
    for idx, node in enumerate(nodes):
        display_type = node.get('display_type', node['role'])

        # Get x position based on type
        x = x_positions.get(display_type, 200)

        # Y position is just the index (temporal order)
        y = -idx * y_spacing  # Negative for top-to-bottom

        positions[node['id']] = (x, y)

    # Build tool call to tool result mapping
    tool_call_map = {}  # tool_use_id -> (tool_call_idx, tool_result_idx)

    for idx, node in enumerate(nodes):
        msg = messages[idx]

        # If this is a tool call, record it
        if msg.role == 'assistant' and msg.tool_uses and 'tool_calls' in msg.tool_uses:
            for tool_call in msg.tool_uses['tool_calls']:
                tool_id = tool_call.get('id')
                if tool_id:
                    tool_call_map[tool_id] = {'call_idx': idx, 'result_idx': None}

        # If this is a tool result, match it by tool_use_id
        elif msg.role == 'tool' and msg.tool_uses:
            # Check if we have the tool_use_id directly
            if isinstance(msg.tool_uses, dict) and 'tool_use_id' in msg.tool_uses:
                tool_id = msg.tool_uses['tool_use_id']
                if tool_id in tool_call_map:
                    tool_call_map[tool_id]['result_idx'] = idx

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

    # Create node traces (one per display type for coloring)
    display_type_colors = {
        'user': ('#3498db', 'User'),
        'assistant_text': ('#2ecc71', 'Assistant (Text)'),
        'assistant_thinking': ('#1abc9c', 'Assistant (Thinking)'),
        'assistant_skill_call': ('#9b59b6', 'Skill Call'),
        'assistant_mcp_call': ('#8e44ad', 'MCP Tool Call'),
        'assistant_tool_call': ('#e67e22', 'Assistant (Tool Call)'),
        'tool': ('#f39c12', 'Tool Result'),
        'system': ('#e74c3c', 'System'),
        'file-history-snapshot': ('#95a5a6', 'File History')
    }

    node_traces = []

    for display_type, (color, label) in display_type_colors.items():
        type_nodes = [n for n in nodes if n.get('display_type', n['role']) == display_type]

        if not type_nodes:
            continue

        node_x = [positions[n['id']][0] for n in type_nodes]
        node_y = [positions[n['id']][1] for n in type_nodes]
        
        node_text = []
        for n in type_nodes:
            text = f"[{n['id']}] {label}<br>Length: {n['content_length']} chars"
            if n.get('skill_name'):
                text += f"<br><b>Skill: {n['skill_name']}</b>"
            if n.get('mcp_tool_name'):
                text += f"<br><b>MCP Tool: {n['mcp_tool_name']}</b>"
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
    axis_ticks = [
        (50, 'User'),
        (150, 'Assistant'),
        (250, 'Tool Call'),
        (300, 'Skill'),
        (350, 'MCP'),
        (450, 'Tool Result'),
        (550, 'File History')
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
