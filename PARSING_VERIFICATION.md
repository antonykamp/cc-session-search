# Conversation Parsing Verification

This document summarizes the verification of conversation message extraction from Claude Code session JSONL files.

## Test Data

Verified using example files in `examples/` directory, primarily:
- `examples/2ffe601b-0f45-4f72-a245-651a0319a5e1.jsonl` (137 messages)

## Message Type Classification

### ✅ User Messages
- **Detection**: `type == "user"` AND `message.role == "user"` AND NO `tool_result` content blocks
- **Count**: 4 messages
- **Example**: Direct user input messages
- **Content**: Plain text user queries

### ✅ Assistant Messages
- **Detection**: `type == "assistant"` AND `message.role == "assistant"`
- **Count**: 85 messages
- **Content Types**:
  - Text responses (40 messages)
  - Thinking blocks (internal reasoning)
  - Tool-only messages with placeholder (45 messages)
- **Note**: All assistant messages now have content. Tool-only messages display `[Calling tool: ToolName]` for clarity

### ✅ Assistant Messages with Tool Calls
- **Detection**: Assistant message with `content` array containing `type == "tool_use"` blocks
- **Count**: 45 messages
- **Structure**:
  ```json
  {
    "type": "assistant",
    "message": {
      "role": "assistant",
      "content": [
        {
          "type": "tool_use",
          "id": "toolu_...",
          "name": "ToolName",
          "input": {...}
        }
      ]
    }
  }
  ```
- **Extraction**: Stored in `ParsedMessage.tool_uses['tool_calls']` array

### ✅ Tool Result Messages
- **Detection**: `type == "user"` but `message.content` contains `type == "tool_result"` blocks
- **Reclassified**: Changed from role='user' to role='tool'
- **Count**: 45 messages
- **Structure**:
  ```json
  {
    "type": "user",
    "message": {
      "role": "user",
      "content": [
        {
          "type": "tool_result",
          "tool_use_id": "toolu_...",
          "content": "..."
        }
      ]
    },
    "toolUseResult": {...}
  }
  ```
- **Extraction**: Stored in `ParsedMessage.tool_uses` from top-level `toolUseResult` field

### ✅ System Messages
- **Detection**: Content containing `<system-reminder>` tags
- **Count**: 8 messages with system reminders
- **Example**:
  ```html
  <system-reminder>
  Whenever you read a file, you should consider whether it would be considered malware...
  </system-reminder>
  ```
- **Note**: System messages are embedded within tool result content, not separate messages

### ⚠️ File History Snapshot Messages
- **Detection**: `type == "file-history-snapshot"`
- **Count**: 3 messages
- **Handling**: Parsed as-is, preserved for tracking file changes

## Key Implementation Details

### Role Reclassification
The parser automatically reclassifies tool result messages:
1. Original: `type='user', role='user'` with `tool_result` content blocks
2. Reclassified to: `role='tool'` for easier filtering and analysis

### Tool Use Extraction
Two formats are supported:
1. **Assistant tool calls**: Extracted from `content` array `tool_use` blocks
2. **Tool results**: Extracted from top-level `toolUseResult` field

### Content Extraction
Text content is extracted from various formats:
- Plain strings
- Content arrays with `type=='text'` blocks
- Content arrays with `type=='thinking'` blocks (prefixed with `[Thinking: ...]`)
- Nested content structures

Special handling:
- **Thinking blocks**: Extracted and prefixed with `[Thinking: ...]` to distinguish internal reasoning
- **Tool-only messages**: When no text/thinking content exists, a placeholder is added: `[Calling tool: ToolName]`
- **Tool use blocks**: Excluded from text content (stored separately in `tool_uses` field)

### Timestamp Handling
- Primary: ISO format timestamps from message
- Fallback: Next message's timestamp
- Final fallback: File modification time

## Dashboard Integration

All visualization and analysis components handle both tool use formats:
- `extract_tool_calls()` in dashboard.py
- `create_tool_usage_chart()` in graph_visualizer.py
- `create_comparison_chart()` in graph_visualizer.py

## Verification Results

Total messages analyzed: 137
- ✓ User messages: 4
- ✓ Assistant messages: 85 (40 with text/thinking, 45 tool-only)
  - All assistant messages now have content (no empty messages)
  - Tool-only messages show: `[Calling tool: ToolName]`
  - Thinking blocks prefixed with: `[Thinking: ...]`
- ✓ Tool result messages: 45
- ✓ File history snapshots: 3
- ✓ Messages with tool information: 90 (45 tool calls + 45 tool results)
- ✓ Messages with system reminders: 8

All message types are correctly classified and extracted with meaningful content.
