# Claude Code Session Search

A comprehensive tool for searching and analyzing Claude Code conversation history. Available as an MCP server, CLI tool, and interactive Streamlit dashboard.

## Features

### Core Capabilities
- **Debug-Focused CLI**: Fast conversation debugging with session shortcuts (@last, @1, @today)
- **Session Shortcuts**: Quick access to recent sessions without remembering UUIDs
- **Error Extraction**: Automatically find and display errors from conversations
- **Cost Tracking**: Detailed token and cost breakdown including subagents
- **Tool Analysis**: Analyze tool usage patterns and statistics
- **Search**: Search across conversations with context windows
- **AI Summarization**: Generate intelligent summaries of conversations
- **MCP Server**: Integration with Claude Code via MCP protocol

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

### CLI Tool (Recommended for Debugging)

The CLI provides a fast, terminal-friendly interface for debugging conversations.

#### Quick Start

```bash
# Show overview of most recent session
uv run ccsearch show @last

# View last 10 messages
uv run ccsearch tail @last -n 10

# Extract errors from last session
uv run ccsearch errors @last

# Cost breakdown for 2nd most recent session
uv run ccsearch cost @2

# List today's sessions
uv run ccsearch sessions --today

# Search for a term
uv run ccsearch search "error handling"
```

#### Session Shortcuts

Instead of typing full UUIDs, use convenient shortcuts:

- `@last` or `@1` - Most recent session
- `@2`, `@3`, etc. - 2nd, 3rd most recent session
- `@today` - Most recent session from today
- `@yesterday` - Most recent session from yesterday
- Or use partial UUID: `89930f19`

#### Core Commands

**Session Inspection:**
```bash
ccsearch show @last              # Overview with metadata and stats
ccsearch tail @1 -n 20          # Last 20 messages (default)
ccsearch head @1 -n 20          # First 20 messages
ccsearch dump @last             # Full conversation dump
ccsearch msg @last 5 10 15      # Specific messages by index
```

**Session Discovery:**
```bash
ccsearch sessions               # Today's sessions (default)
ccsearch sessions --today       # Today's sessions
ccsearch sessions --days 7      # Last 7 days
ccsearch projects               # List all projects
```

**Analysis:**
```bash
ccsearch errors @last           # Extract error messages
ccsearch tools @last            # Tool usage analysis
ccsearch tools @last --stats    # Tool usage statistics only
ccsearch cost @last             # Detailed cost breakdown
```

**Search:**
```bash
ccsearch search "bug fix"                    # Search last 7 days
ccsearch search "error" --days 14            # Search last 14 days
ccsearch search "config" --role assistant    # Search in assistant messages
ccsearch search "test" --limit 20            # Show up to 20 results
```

**Summarization:**
```bash
ccsearch summarize 2025-11-23              # Summarize a specific date
ccsearch summarize @last                   # Summarize a session (coming soon)
ccsearch summarize 2025-11-23 --style insights
```

#### Output Options

Most commands support these flags:

- `--no-color` - Disable colored output (for piping or logging)
- `--no-header` - Skip header (for `tail`, `head`, etc.)
- `--oneline` - Compact one-line format (for `tail`, `head`)
- `--format json` - JSON output
- `--project PROJECT` - Filter to specific project

#### Color-Coded Output

The CLI uses colors to make output easier to scan:

- **Blue** - User messages
- **Green** - Assistant messages
- **Cyan** - Thinking blocks
- **Yellow** - Tool calls/results
- **Red** - Errors
- **Magenta** - Meta information
- **Gray** - Labels and secondary info

Use `--no-color` to disable colors for scripting.

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

### MCP Server

Run the server:

```bash
uv run python cc_session_search/server.py
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

## CLI Examples

### Common Debugging Workflows

**Just finished a conversation and want to review:**
```bash
# Quick overview
ccsearch show @last

# See what happened at the end
ccsearch tail @last

# Check if there were errors
ccsearch errors @last

# How much did it cost?
ccsearch cost @last
```

**Investigating an issue from yesterday:**
```bash
# List yesterday's sessions
ccsearch sessions --days 2

# Look at specific session (use session ID from list)
ccsearch show 89930f19

# Find the error
ccsearch errors 89930f19

# See context around message 42
ccsearch msg 89930f19 40 41 42 43 44
```

**Comparing today vs yesterday:**
```bash
# Today's sessions
ccsearch sessions --today

# Cost summary
ccsearch cost @1  # Most recent
ccsearch cost @2  # Second most recent

# Tool usage comparison
ccsearch tools @1 --stats
ccsearch tools @2 --stats
```

**Search across all recent work:**
```bash
# Find where you discussed a specific topic
ccsearch search "database migration" --days 7

# Find tool failures
ccsearch search "failed" --role tool

# Find your questions
ccsearch search "how do I" --role user
```

## Requirements

- Standard Claude Code installation (searches `~/.claude/projects/`)
- Python 3.13+
- MCP 1.2.0+ (for server functionality)

## MCP Server Tools

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
- Session shortcuts for fast debugging
- Color-coded terminal output
- Cost and token tracking

## License

MIT
