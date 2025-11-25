# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

This is a Python-based tool for searching and analyzing Claude Code conversation history. It provides both an MCP server for integration with Claude Code and a standalone CLI tool. The project reads JSONL conversation files from `~/.claude/projects/` and provides search, analysis, and AI-powered summarization capabilities.

## Development Commands

### Setup
```bash
# Install dependencies using uv
uv sync
```

### Running the MCP Server
```bash
# Start the MCP server (for integration with Claude Code)
uv run python cc_session_search/server.py
```

### Running the CLI Tool
```bash
# The CLI is accessed via the 'ccsearch' command
uv run ccsearch <command> [options]

# Examples:
uv run ccsearch list-projects
uv run ccsearch list-recent --days-back 3
uv run ccsearch search "error handling" --days-back 7
uv run ccsearch summarize-daily 2025-11-18
```

### Running the Streamlit Dashboard
```bash
# Start the interactive web dashboard
uv run streamlit run cc_session_search/dashboard.py

# The dashboard will open in your browser at http://localhost:8501
```

**Dashboard Features:**
- **Single Session View**: Explore individual conversations with metadata, tool usage stats, system messages, and interactive visualizations
- **Compare Sessions Mode**: Side-by-side comparison of two conversations with:
  - Tool usage comparison (counts, sequences, and charts)
  - System messages comparison
  - Individual session details in columns
- **Interactive Visualizations**:
  - Conversation flow graph (sequence diagram with temporal flow, top-to-bottom)
  - Separate columns for User, Assistant, Tool Calls, Skills, MCP Tools, Tool Results, Meta, and File History
  - Color-coded message types: Blue (User), Green (Assistant Text), Teal (Thinking), Purple (Skills), Deep Purple (MCP), Orange (Tool Calls), Amber (Tool Results), Pink (Meta)
  - Tool call → result connections visualized with arrows
  - Tool usage distribution charts
  - Message timeline
  - Comparison bar charts
- **Message Browser**:
  - Paginated view with advanced type filtering
  - Filter by: User, Assistant (Text), Assistant (Thinking), Skill Calls, MCP Calls, Tool Calls, Tool Results, Meta, System, File History
  - Message counts shown for each filter type
  - Bidirectional tool call ↔ result links (click to jump)
  - Full tool result expansion (complete output including MCP responses)
  - Meta message highlighting for system caveats and context injection
- **Shareable Links**:
  - Generate URL parameters for any session or comparison
  - Auto-load sessions from URL parameters
  - Copy query strings to share with team
- **Project/Session Selection**: Browse all projects and sessions with counts and timestamps
- **MCP Tool Highlighting**: MCP server tools visually distinguished with plugin icon (🔌) and deep purple color

## Architecture

### Core Components

**cc_session_search/core/**
- `conversation_parser.py`: JSONL parser for Claude Code conversation files
  - `JSONLParser`: Main parser class that handles JSONL conversation files
  - `ParsedMessage`: Dataclass representing a parsed message with role, content, timestamp, tool usage, token count, and cost
  - `ConversationMetadata`: Metadata extracted from conversations (project info, session ID, git branch, timestamps)
  - Handles different message types: user, assistant, tool results, and summary messages
  - Auto-detects and reclassifies tool responses (originally role='user' with tool_result content blocks)
  - Fixes missing timestamps using subsequent message timestamps or file modification time
  - Extracts actual token usage from API responses (input_tokens, output_tokens, cache_creation_tokens, cache_read_tokens)
  - Calculates accurate USD cost using actual API token counts and Claude pricing
  - Properly accounts for prompt caching costs (cache reads at 90% discount)
  - Only assistant messages have usage data; user message tokens are included in the next assistant's input_tokens

- `searcher.py`: Core search and session analysis functionality
  - `SessionSearcher`: Main search class
  - Discovers projects by scanning `~/.claude/projects/` directory structure
  - Provides session listing, filtering by date ranges, and cross-project search
  - Implements conversation search with context windows and role filtering

- `summarizer.py`: AI-powered conversation summarization
  - `ConversationSummarizer`: Generates intelligent summaries using headless Claude
  - Supports multiple summary styles: 'journal', 'insights', 'stories'
  - Can summarize by specific date or time range

- `models.py`: Data models used across the codebase
  - `Message`: Represents a conversation message
  - `SearchResult`: Search result with context
  - `ConversationSummary`: Summarized conversation view

**cc_session_search/server.py**
- MCP server implementation using the low-level MCP Server class
- Exposes 8 tools for Claude Code integration
- All tools return JSON responses via `types.TextContent`

**cc_session_search/cli.py**
- Standalone CLI tool with multiple output formats (pretty, json, compact, table)
- Mirrors MCP server functionality for direct command-line usage
- Entry point defined in pyproject.toml as `ccsearch` command

**cc_session_search/dashboard.py**
- Interactive Streamlit web dashboard for conversation analysis
- Provides single session view and side-by-side comparison mode
- Integrates all visualization components
- Uses Streamlit caching for performance with `@st.cache_resource`
- URL parameter support for shareable links (found in Session Metadata expander)
- Message type filtering with counts and bidirectional tool call linking
- Full tool result display in expandable sections
- Token counting and cost calculation for each message and conversation
- Displays input/output tokens, total cost, and average cost per message

**cc_session_search/graph_visualizer.py**
- Conversation graph visualization using Plotly
- `create_plotly_graph()`: Interactive conversation flow visualization with role-based node coloring
- `create_tool_usage_chart()`: Bar chart of tool usage distribution
- `create_message_timeline()`: Timeline scatter plot of messages
- `create_comparison_chart()`: Side-by-side tool usage comparison

### Project Structure Conventions

- **Project Names**: Claude Code encodes project directory paths as dash-separated names
  - Example: `/Users/name/Projects/foo` becomes `-Users-name-Projects-foo`
  - Use `--project=-Users-...` syntax when project names start with dash
  - The `_decode_project_name()` method converts dashes back to slashes for display

- **Session Files**: Stored as `conversation-{uuid}.jsonl` in project directories
  - Each line is a JSON object representing a message or event
  - Messages have `type` field ('summary' or regular) and `message` field with role and content
  - Timestamps in ISO format, may be missing for first message
  - Assistant messages include `usage` field with actual API token counts

- **Message Roles**:
  - `user`: Human input (tokens counted in next assistant message's input_tokens)
  - `assistant`: Claude's responses (includes usage data with input/output tokens)
  - `tool`: Tool execution results (auto-detected from tool_result content blocks or toolUseResult data)
  - `summary`: Conversation summaries

- **Token Counting**:
  - Only assistant messages have `usage` field from API responses
  - `usage.input_tokens`: Includes the user's prompt + conversation context
  - `usage.output_tokens`: The assistant's response tokens
  - `usage.cache_creation_input_tokens`: Tokens written to prompt cache
  - `usage.cache_read_input_tokens`: Tokens read from prompt cache (90% cheaper)
  - User messages don't have usage data - their tokens are included in the next assistant's input_tokens

### Key Design Patterns

1. **Metadata-First Approach**: Extracts metadata before processing messages to minimize token usage
2. **Content Truncation**: Limits output to prevent token overflow (e.g., 500 char message previews)
3. **Role Detection**: Automatically reclassifies user messages containing tool results as 'tool' role
4. **Timestamp Inference**: Fills missing timestamps using next message's timestamp or file modification time
5. **Max Limits**: Days back limited to 7, message indices limited to 10, context window limited to 5
6. **API-Based Token Counting**: Uses actual usage data from Claude API responses, not estimation
7. **Cache-Aware Pricing**: Properly calculates costs for prompt caching with 90% discount on cache reads

## Testing

No formal test suite currently exists. Manual testing is done via CLI commands.

## Dependencies

- Python 3.13+ (specified in .python-version)
- MCP SDK 1.2.0+ for server functionality
- Streamlit 1.28.0+ for interactive dashboard
- Plotly 5.17.0+ for interactive visualizations
- Pandas 2.1.0+ for data manipulation
- `uv` package manager for dependency management

Note: Token counting uses actual API usage data from conversation files, not estimation libraries.
