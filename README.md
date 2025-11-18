# Claude Code Session Search

A tool for searching and analyzing Claude Code conversation history. Available as both an MCP server and a CLI tool.

## Features

- **List Projects**: View all Claude Code projects with session counts
- **List Sessions**: Browse sessions for specific projects
- **List Recent Sessions**: Find recent conversations across all projects
- **Analyze Sessions**: Extract and analyze messages with role filtering
- **Search Conversations**: Search for specific terms with context windows and time ranges
- **Get Message Details**: Retrieve full content for specific messages
- **Summarize Conversations**: AI-powered summarization of daily conversations

## Installation

1. Install dependencies:
```bash
uv sync
```

## Usage

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
