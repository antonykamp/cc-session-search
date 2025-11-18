#!/usr/bin/env python3
"""
Verification script to test conversation parsing against example files
"""

from pathlib import Path
from cc_session_search.core.conversation_parser import JSONLParser

def main():
    parser = JSONLParser()
    examples_dir = Path("examples")

    # Test with one of the example files
    example_file = examples_dir / "2ffe601b-0f45-4f72-a245-651a0319a5e1.jsonl"

    print(f"Testing parser with: {example_file}")
    print("=" * 80)

    try:
        metadata, messages = parser.parse_conversation_file(example_file)

        print(f"\n📊 METADATA:")
        print(f"  Session ID: {metadata.session_id}")
        print(f"  Project: {metadata.project_name}")
        print(f"  Messages: {len(messages)}")
        print(f"  Started: {metadata.started_at}")
        print(f"  Ended: {metadata.ended_at}")
        print(f"  Git Branch: {metadata.git_branch}")

        # Count messages by role
        role_counts = {}
        tool_uses_count = 0
        system_msg_count = 0

        for msg in messages:
            role_counts[msg.role] = role_counts.get(msg.role, 0) + 1
            if msg.tool_uses:
                tool_uses_count += 1
            if 'system-reminder' in msg.content.lower():
                system_msg_count += 1

        print(f"\n📈 MESSAGE BREAKDOWN:")
        for role, count in sorted(role_counts.items()):
            print(f"  {role:12s}: {count:4d} messages")

        print(f"\n🔧 TOOL INFORMATION:")
        print(f"  Messages with tool uses: {tool_uses_count}")
        print(f"  Messages with system reminders: {system_msg_count}")

        # Show first few messages of each role
        print(f"\n📝 SAMPLE MESSAGES:")
        print("-" * 80)

        for role in sorted(set(msg.role for msg in messages)):
            role_messages = [msg for msg in messages if msg.role == role]
            print(f"\n{role.upper()} (first message):")
            if role_messages:
                msg = role_messages[0]
                content_preview = msg.content[:150].replace('\n', ' ')
                print(f"  Content: {content_preview}...")
                print(f"  Timestamp: {msg.timestamp}")
                print(f"  Has tool uses: {msg.tool_uses is not None}")

        # Check specific message types
        print(f"\n🔍 VERIFICATION CHECKS:")
        print("-" * 80)

        # Check for tool results being classified as 'tool' role
        tool_role_messages = [msg for msg in messages if msg.role == 'tool']
        print(f"✓ Tool results classified as 'tool' role: {len(tool_role_messages)} messages")

        # Check for assistant messages with tool_use
        assistant_with_tools = [msg for msg in messages if msg.role == 'assistant' and msg.tool_uses]
        print(f"✓ Assistant messages with tool uses: {len(assistant_with_tools)} messages")

        # Check for user messages (should NOT include tool results)
        user_messages = [msg for msg in messages if msg.role == 'user']
        print(f"✓ Pure user messages: {len(user_messages)} messages")

        # Show a sample tool result message
        if tool_role_messages:
            print(f"\n📦 SAMPLE TOOL RESULT MESSAGE:")
            msg = tool_role_messages[0]
            print(f"  Role: {msg.role}")
            print(f"  Content preview: {msg.content[:100].replace(chr(10), ' ')}...")
            print(f"  Tool uses data: {msg.tool_uses is not None}")

        # Show a sample assistant message with tool use
        if assistant_with_tools:
            print(f"\n🤖 SAMPLE ASSISTANT WITH TOOL USE:")
            msg = assistant_with_tools[0]
            print(f"  Role: {msg.role}")
            print(f"  Content preview: {msg.content[:100].replace(chr(10), ' ')}...")
            print(f"  Tool uses: {msg.tool_uses}")

        print(f"\n✅ Parsing verification complete!")

    except Exception as e:
        print(f"❌ Error during parsing: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
