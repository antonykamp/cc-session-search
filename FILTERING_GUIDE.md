# Message Filtering Guide

## Overview

The dashboard now supports granular filtering by message subtype, allowing you to focus on specific aspects of conversations.

## Available Filters

### Message Types

| Filter | Icon | Description | Use Case |
|--------|------|-------------|----------|
| **User** | 👤 | User input messages | See what the user asked for |
| **Assistant (Text)** | 🤖 | Regular responses | Read plain text answers |
| **Assistant (Thinking)** | 🧠 | Extended thinking | Understand reasoning process |
| **MCP Tool Call** | 🔌 | MCP server tool invocations | See external MCP tool usage |
| **Assistant (Tool Call)** | ⚡ | Built-in tool invocations | See which built-in tools were called |
| **Tool Result** | 🔧 | Tool outputs | See tool execution results |
| **System** | ⚠️ | System reminders | Find system messages |
| **File History** | 📄 | File snapshots | Track file changes |

### Filter Features

**Message Counts**: Each filter shows how many messages of that type exist
```
🤖 Assistant (Text) (12)
🧠 Assistant (Thinking) (28)
⚡ Assistant (Tool Call) (45)
🔌 MCP Tool Call (8)
```

**Multi-Select**: Click multiple types to view them together

**Sorted by Frequency**: Most common types appear first in the list

**Dynamic**: Only message types present in the conversation are shown

**Bidirectional Links**: Tool calls and results show navigation links to each other

## Example Workflows

### 1. Debug Tool Execution Flow

**Goal**: Understand which tools were called and why

**Steps**:
1. Use multiselect filter to select "⚡ Assistant (Tool Call)" and "🔧 Tool Result"
2. See tool invocations (orange) and results (amber) together
3. Click "→ Result at [N]" links to jump between calls and results
4. Expand "🔍 Tool Details" to see exact parameters
5. Expand "📦 Tool Result Details" to see complete output (no truncation)

**Result**: Clear view of all tool activity with full execution details

### 2. Trace User Intent

**Goal**: Understand what the user wanted

**Steps**:
1. Use multiselect filter to select only "👤 User"
2. Read through all user messages sequentially
3. See the conversation from user perspective

**Result**: Clear understanding of user requirements without responses

### 3. Analyze Reasoning Process

**Goal**: See how Claude approached the problem

**Steps**:
1. Use multiselect filter to deselect all types
2. Select only "🧠 Assistant (Thinking)"
3. Read through thinking messages chronologically

**Result**: Complete view of internal reasoning and planning

### 4. Analyze MCP Tool Usage

**Goal**: Track external MCP server tool interactions

**Steps**:
1. Use multiselect filter to select "🔌 MCP Tool Call" and "🔧 Tool Result"
2. See all MCP server invocations
3. Expand tool details to see MCP request parameters
4. Expand tool results to see complete MCP server responses

**Result**: Full visibility into MCP server integration and data flow

### 5. Compare Input vs Output

**Goal**: Match user requests to tool actions

**Steps**:
1. Use multiselect filter to deselect all types
2. Select "👤 User" and "⚡ Assistant (Tool Call)"
3. See cause-and-effect relationship

**Result**: Clear mapping of requests to actions

### 6. Focus on Final Answers

**Goal**: Read only the text responses

**Steps**:
1. Use multiselect filter to select only "🤖 Assistant (Text)"
2. Skip all thinking, tools, and other noise
3. Read just the final answers

**Result**: Clean view of what was communicated to user

## Filter Summary

When filters are active, a blue info box shows:
```
📊 Showing 45 of 137 messages
```

This helps you understand how much you've filtered.

## Tips

1. **Start broad, narrow down**: Begin with all types, then remove what you don't need
2. **Combine complementary types**: User + Tool Calls shows request-action pairs
3. **Check the counts**: High tool call counts may indicate automation
4. **Toggle thinking on/off**: Helps distinguish between planning and execution
5. **Use bidirectional links**: Click message indices to jump between related tool calls and results
6. **Expand tool results**: View complete output including MCP responses (no truncation)
7. **MCP vs Built-in**: Filter separately to compare external vs built-in tool usage

## Keyboard Workflow

For power users:
1. Click message browser to expand
2. Click in the multiselect filter dropdown
3. Type to search for specific filter types
4. Use arrow keys to navigate options
5. Click or press Enter to select/deselect
6. Click outside dropdown to close

## Comparison Mode

In comparison mode, filters work independently on each session:
- Filter session 1 to show tool calls
- Filter session 2 to show thinking
- Compare different aspects side-by-side

## Recent Enhancements

**Implemented:**
- ✅ MCP tool call highlighting and filtering
- ✅ Bidirectional tool call ↔ result linking
- ✅ Full tool result expansion (complete output)
- ✅ Shareable links for sessions and comparisons
- ✅ Teal color for thinking messages (distinct from MCP purple)
- ✅ Separate MCP column in conversation flow graph

**Future Enhancements:**
- Save filter presets
- Search within filtered messages
- Export filtered view
- Filter by specific tool name
- Filter by timestamp range
- Bookmark specific messages
