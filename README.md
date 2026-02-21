# Claude Code Session Explorer

A tool for analyzing Claude Code conversation history. Available as an interactive Streamlit dashboard and a CLI tool for experiment data collection.

## Features

### Interactive Dashboard
- **Visual Session Browser**: Interactive Streamlit dashboard for exploring sessions
- **Conversation Flow Graphs**: Sequence diagram visualizations with color-coded message types
- **Tool Usage Analysis**: Track and compare tool calls across sessions
- **Side-by-Side Comparison**: Compare two sessions with tool usage charts
- **Advanced Filtering**: Filter messages by type (user, assistant, thinking, tool calls, MCP calls)
- **Shareable Links**: Generate URLs to share specific sessions or comparisons
- **Full Tool Results**: View complete tool outputs including MCP server responses

### CLI Tool
- **Experiment Collection**: Gather experiment metrics from session files into CSV format

## Installation

```bash
uv sync
```

## Usage

### Dashboard (`cc-dashboard`)

Launch the interactive dashboard:

```bash
uv run cc-dashboard
```

The dashboard will open in your browser at `http://localhost:8501`.

**Features:**
- **Single Session View**: Explore individual sessions with detailed message browsers, tool usage stats, and visualizations
- **Compare Mode**: Side-by-side comparison of two sessions with tool usage analysis
- **Message Filtering**: Filter by message type (user, assistant text, thinking, tool calls, MCP calls, tool results)
- **Conversation Flow Graph**: Interactive sequence diagram showing message flow and tool call connections
- **Shareable Links**: Copy URL parameters to share sessions with others
- **Full Tool Results**: Expand any tool result to see complete output (including MCP responses)

**Shareable Links:**
The dashboard supports URL parameters for direct linking:
- Single session: `?project1=PROJECT&session1=SESSION_ID`
- Comparison: `?project1=PROJECT1&session1=SESSION1&project2=PROJECT2&session2=SESSION2`

### Experiment Collection (`cc-collect`)

```bash
uv run cc-collect <directory> <experiment-id> [--output path.csv]
```

Options:
- `--output, -o` - Output CSV path (default: `<experiment-id>--summary.csv`)
- `--no-color` - Disable colored output

## Requirements

- Standard Claude Code installation (searches `~/.claude/projects/`)
- Python 3.13+

## License

MIT
