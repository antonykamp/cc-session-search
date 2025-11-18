# Claude Code Session Search

A comprehensive tool for searching and analyzing Claude Code conversation history. Available as an MCP server, CLI tool, and interactive Streamlit dashboard.

## Features

### Core Capabilities
- **List Projects**: View all Claude Code projects with session counts
- **List Sessions**: Browse sessions for specific projects
- **List Recent Sessions**: Find recent conversations across all projects
- **Analyze Sessions**: Extract and analyze messages with role filtering
- **Search Conversations**: Search for specific terms with context windows and time ranges
- **Get Message Details**: Retrieve full content for specific messages
- **Summarize Conversations**: AI-powered summarization of daily conversations

### Interactive Dashboard
- **Visual Session Browser**: Interactive Streamlit dashboard for exploring sessions
- **Conversation Flow Graphs**: Sequence diagram visualizations with color-coded message types
- **Tool Usage Analysis**: Track and compare tool calls across sessions
- **Side-by-Side Comparison**: Compare two sessions with tool usage charts
- **Advanced Filtering**: Filter messages by type (user, assistant, thinking, tool calls, MCP calls)
- **Shareable Links**: Generate URLs to share specific sessions or comparisons
- **Full Tool Results**: View complete tool outputs including MCP server responses

## Installation

1. Install dependencies:
```bash
uv sync
```

## Usage

### Streamlit Dashboard

Launch the interactive dashboard:

```bash
uv run streamlit run cc_session_search/dashboard.py
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

See [DASHBOARD_FEATURES.md](DASHBOARD_FEATURES.md) for detailed documentation.

### CLI Tool

After installation, use the `ccsearch` command:

```bash
# List all projects
uv run ccsearch list-projects

# List recent sessions
uv run ccsearch list-recent --days-back 3

# Search for a term
uv run ccsearch search "error handling" --days-back 7

# Get specific messages
uv run ccsearch get-messages <session-id> 0 1 2

# Summarize daily conversations
uv run ccsearch summarize-daily 2025-11-18

# List sessions for a project (use --project= syntax for names starting with dash)
uv run ccsearch list-sessions --project=-Users-antonykamp-Projects-hpi-ma-byopl24-02

# Analyze sessions
uv run ccsearch analyze --days-back 2 --role-filter user
```

#### CLI Output Formats

The CLI supports multiple output formats via the `--format` flag:

- `pretty` (default): Formatted JSON with indentation
- `json`: Pretty JSON (same as pretty)
- `compact`: Single-line JSON
- `table`: Human-readable table format

Example:

```bash
uv run ccsearch list-projects --format table
```

#### CLI Commands

- `list-projects` - List all Claude Code projects
- `list-sessions <project_name>` - List sessions for a project
- `list-recent` - List recent sessions across all projects
- `analyze` - Analyze messages from sessions
- `search <query>` - Search conversations
- `get-messages <session_id> <indices...>` - Get full message content
- `summarize-daily <date>` - Summarize conversations for a date (YYYY-MM-DD)
- `summarize-range <start> <end>` - Summarize conversations for a time range

### MCP Server

Run the server:

```bash
uv run python server.py
```

Add to Claude Code MCP config (`~/.config/claude/mcp.json`):

```json
{
  "servers": {
    "cc-session-search": {
      "command": ["uv", "run", "python", "server.py"],
      "cwd": "/path/to/cc-session-search"
    }
  }
}
```

## Requirements

- Standard Claude Code installation (searches `~/.claude/projects/`)
- Python 3.13+
- MCP 1.2.0+

## MCP Server Usage

The server provides the following tools:

### list_projects()

Lists all Claude Code projects with session counts and recent activity.

### list_sessions(project_name, days_back=7)

Lists sessions for a specific project within the specified time range.

### list_recent_sessions(days_back=1, project_filter=None)

Lists recent sessions across all projects.

### analyze_sessions(days_back=1, role_filter="both", include_tools=False, project_filter=None)

Extracts and analyzes messages from sessions with filtering options.

### search_conversations(query, days_back=2, context_window=1, case_sensitive=False, project_filter=None)

Searches conversations for specific terms with context windows.

### get_message_details(session_id, message_indices)

Retrieves full content for specific messages by session ID and indices.

## Development

The server is built using the official MCP Python SDK with low-level Server class for maximum control.

Key features:

- Efficient response handling with content truncation
- Metadata-first approach to minimize token usage
- Support for date ranges and filtering
- Cross-project search capabilities

## License

MIT
