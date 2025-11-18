# Dashboard Features Guide

## Quick Start

**To copy a link to a session:**
1. Expand **"📊 Session Metadata"** at the top of any session view
2. Look for **"📎 Share This Session"** section
3. Copy the query string shown
4. Append to your dashboard URL

**To view full tool results:**
1. Find any tool result message (amber/🔧)
2. Click **"📦 Tool Result Details"** to expand
3. View complete output (no truncation)

**To filter messages:**
1. Open **"💬 Messages Browser"**
2. Use the multiselect dropdown to choose message types
3. See count for each type in parentheses

---

## Shareable Links

### How to Copy a Link to a Session

**For Single Sessions:**
1. Open a session in the dashboard
2. Click to expand **"📊 Session Metadata"** section (at the top of the session view)
3. Find the **"📎 Share This Session"** section
4. Copy the query string shown (e.g., `?project1=myproject&session1=conversation-abc123`)
5. Append it to your dashboard URL: `http://localhost:8501/?project1=...&session1=...`
6. Share the complete URL

**For Comparison Mode:**
1. Open two sessions in comparison mode
2. At the top of the comparison view, expand **"📎 Share This Comparison"**
3. Copy the query string with both sessions
4. Append to dashboard URL and share

**Auto-Loading:**
When someone opens a shareable link, the dashboard automatically:
- Detects the URL parameters
- Pre-selects the specified project(s) and session(s)
- Shows a "📎 Session loaded from shareable link" notification

---

## Message Type Highlighting

The dashboard uses distinct icons and colors to differentiate message types for better visual navigation.

### Message Types and Visual Indicators

| Message Type | Icon | Color | Description |
|-------------|------|-------|-------------|
| **User** | 👤 | Blue (#3498db) | User input messages |
| **Assistant (Text)** | 🤖 | Green (#2ecc71) | Regular assistant text responses |
| **Assistant (Thinking)** | 🧠 | Teal (#1abc9c) | Internal reasoning/planning (extended thinking) |
| **MCP Tool Call** | 🔌 | Deep Purple (#8e44ad) | External MCP server tool invocations |
| **Assistant (Tool Call)** | ⚡ | Orange (#e67e22) | Built-in tool invocation messages |
| **Tool Result** | 🔧 | Amber (#f39c12) | Tool execution results |
| **System** | ⚠️ | Red (#e74c3c) | Messages with system reminders |
| **File History** | 📄 | Gray (#95a5a6) | File snapshot messages |

### Visual Features

#### 1. Message Headers
Each message has a colored header bar with:
- Colored left border (4px solid)
- Light tinted background
- Bold colored icon and label
- Message index and timestamp
- Message type indicator

#### 2. Content Styling
Different content types have distinct backgrounds:
- **Thinking messages**: Gray background, italic text
- **Tool calls**: Yellow background, monospace font
- **Regular content**: Plain white background

#### 3. Expandable Tool Details
- **Tool Call Details**: Click to expand and see full JSON parameters
  - Bash commands shown with syntax highlighting
  - File paths highlighted for Read/Write/Edit
  - Search patterns shown for Grep
  - Full JSON for other tools (including MCP tool calls)
- **Tool Result Details**: Full tool execution results
  - **Full Tool Result**: Complete output in code block (no truncation)
  - **Metadata**: tool_use_id and other metadata in JSON format
  - Works for all tools including MCP server responses

### Detailed Tool Call Information

The dashboard now shows comprehensive tool usage information:

#### Tool Usage Summary
- **Tool Call Counts**: Table showing frequency of each tool
- **Tool Call Sequence**: Visual flow of tool usage (first 20 calls)

#### Detailed Tool Calls Section
Expandable section showing:
- **Bash commands**: Full command with syntax highlighting
  ```bash
  uv run python verify_parsing.py
  ```
- **File operations**: File paths for Read/Write/Edit tools
  ```
  📄 File: /path/to/file.py
  ```
- **Search operations**: Patterns for Grep tool
  ```
  🔍 Pattern: TODO
  ```
- **Other tools**: Full JSON input parameters

### Conversation Graph Visualization

The Plotly conversation flow graph displays messages in a sequence diagram format:

**Layout:**
- **Vertical flow**: Messages flow top-to-bottom chronologically
- **Horizontal lanes**: Separate columns for each message type
  - User (leftmost)
  - Assistant (text, thinking, tool calls)
  - MCP Tools (dedicated column)
  - Built-in Tool Results
  - File History (rightmost)
- **Tool connections**: Orange arrows connect tool calls to their results

**Color Scheme:**
- **User nodes**: Blue (#3498db)
- **Assistant (Text) nodes**: Green (#2ecc71)
- **Assistant (Thinking) nodes**: Teal (#1abc9c)
- **MCP Tool Call nodes**: Deep Purple (#8e44ad)
- **Assistant (Tool Call) nodes**: Orange (#e67e22)
- **Tool Result nodes**: Amber (#f39c12)
- **System nodes**: Red (#e74c3c)
- **File History nodes**: Gray (#95a5a6)

### Message Browser Legend

A legend is displayed at the top of the message browser explaining all icons and colors for easy reference.

## Advanced Message Filtering

### Granular Type Filters

The message browser now includes advanced filtering by message subtype:

**Available Filters:**
- 👤 **User** - User input messages only
- 🤖 **Assistant (Text)** - Regular text responses
- 🧠 **Assistant (Thinking)** - Extended thinking/planning
- 🔌 **MCP Tool Call** - External MCP server tool invocations
- ⚡ **Assistant (Tool Call)** - Built-in tool invocations
- 🔧 **Tool Result** - Tool execution results
- ⚠️ **System** - System reminder messages
- 📄 **File History** - File snapshot messages

**Filter Features:**
- **Message counts**: Each filter shows the count of that type `(N)`
- **Multi-select**: Select multiple types to view simultaneously
- **Sorted by frequency**: Most common types appear first
- **Dynamic**: Only shows types present in current conversation

### Filter Summary

When filters are active, a summary shows: `📊 Showing X of Y messages`

### Bidirectional Tool Call Links

Messages now show connections between tool calls and their results:
- **Tool Call Messages**: Display "→ Result at [N]" when a result exists
- **Tool Result Messages**: Display "← Called from [N]" linking back to the call
- Click the message index to jump directly to the linked message

## Usage

### Viewing Messages
1. Open the **Messages Browser** expander
2. Reference the legend for message type meanings
3. Use the message type multiselect filter to show/hide specific types
4. Expand tool details sections to see full parameters and results
5. Use bidirectional links to navigate between tool calls and results

**Example Workflows:**

*Debugging tool execution:*
1. Use multiselect filter to select "⚡ Assistant (Tool Call)" and "🔧 Tool Result"
2. See all tool invocations and their results together
3. Click "→ Result at [N]" links to jump to tool outputs
4. Expand "📦 Tool Result Details" to see complete output

*Understanding user intent:*
1. Use multiselect filter to select only "👤 User"
2. Read through conversation from user perspective
3. No assistant responses or tool clutter

*Analyzing reasoning:*
1. Use multiselect filter to select only "🧠 Assistant (Thinking)"
2. See Claude's internal thought process
3. Understand decision-making flow

*Analyzing MCP tool usage:*
1. Use multiselect filter to select only "🔌 MCP Tool Call"
2. See all external MCP server tool invocations
3. Expand tool details to see full MCP request parameters
4. Follow links to see MCP response results

*Finding specific interactions:*
1. Use multiselect filter to deselect all types
2. Select only the types you want (e.g., User + Tool Results)
3. See cause-and-effect of user requests

### Analyzing Tool Usage
1. Check **Tool Usage** section for summary statistics
2. Expand **Detailed Tool Calls** to see parameters
3. For Bash commands, see the exact command executed
4. For file operations, see which files were accessed

### Comparing Sessions
In comparison mode, tool usage is shown side-by-side with visual charts highlighting differences in tool usage patterns between sessions.

## Benefits

1. **Faster Navigation**: Quickly identify message types at a glance
2. **Better Understanding**: See exactly what tools were called and with what parameters
3. **Debugging Aid**: Trace tool execution flow and parameters
4. **Visual Analysis**: Color-coded graphs make conversation flow patterns obvious
5. **Detailed Inspection**: Expand sections to see full tool details when needed
