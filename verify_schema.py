#!/usr/bin/env python3
"""
Schema Verification Script for Claude Code JSONL Files

Verifies that the JSONL conversation file format matches our expected schema.
Fails if breaking changes are detected that would prevent analysis.
"""

import json
import sys
from pathlib import Path
from typing import Dict, Any, List, Set
from datetime import datetime

# Expected schema definition
EXPECTED_SCHEMA = {
    "required_top_level_fields": {"type"},
    "optional_top_level_fields": {
        "uuid", "leafUuid", "cwd", "gitBranch", "toolUseResult", "summary",
        "message", "timestamp", "parentUuid", "isSidechain", "userType",
        "sessionId", "version", "requestId", "thinkingMetadata", "messageId",
        "snapshot", "isSnapshotUpdate"
    },
    "message_required_fields": {"role", "content"},
    "valid_message_roles": {"user", "assistant"},
    "valid_message_types": {"user", "assistant", "summary", "file-history-snapshot", "message"},
    "content_block_types": {"text", "thinking", "tool_use", "tool_result"},
    "tool_use_required_fields": {"type", "id", "name", "input"},
    "tool_result_required_fields": {"type", "tool_use_id"}
}


class SchemaValidationError(Exception):
    """Raised when schema validation fails"""
    pass


def validate_timestamp(timestamp_str: str) -> bool:
    """Validate timestamp format"""
    try:
        # Should be ISO format
        datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        return True
    except (ValueError, TypeError, AttributeError):
        return False


def validate_content_block(block: Any, block_idx: int) -> List[str]:
    """Validate a content block structure"""
    errors = []

    if not isinstance(block, dict):
        if not isinstance(block, str):
            errors.append(f"Content block {block_idx}: Expected dict or string, got {type(block)}")
        return errors

    block_type = block.get('type')
    if block_type not in EXPECTED_SCHEMA['content_block_types']:
        errors.append(f"Content block {block_idx}: Unknown block type '{block_type}'")

    # Validate specific block types
    if block_type == 'text' and 'text' not in block:
        errors.append(f"Content block {block_idx}: 'text' block missing 'text' field")

    if block_type == 'thinking' and 'thinking' not in block:
        errors.append(f"Content block {block_idx}: 'thinking' block missing 'thinking' field")

    if block_type == 'tool_use':
        for field in EXPECTED_SCHEMA['tool_use_required_fields']:
            if field not in block:
                errors.append(f"Content block {block_idx}: 'tool_use' missing required field '{field}'")

    if block_type == 'tool_result':
        for field in EXPECTED_SCHEMA['tool_result_required_fields']:
            if field not in block:
                errors.append(f"Content block {block_idx}: 'tool_result' missing required field '{field}'")

    return errors


def validate_message(msg_data: Dict[str, Any], line_num: int) -> List[str]:
    """Validate a single JSONL message"""
    errors = []

    # Check message type
    msg_type = msg_data.get('type')
    if msg_type not in EXPECTED_SCHEMA['valid_message_types']:
        errors.append(f"Line {line_num}: Unknown message type '{msg_type}'")
        # Don't continue validation if type is completely unknown
        if msg_type and not any(msg_type.startswith(prefix) for prefix in ['user', 'assistant', 'summary', 'file-history', 'message']):
            return errors

    # Handle summary messages differently
    if msg_type == 'summary':
        if 'summary' not in msg_data and 'leafUuid' not in msg_data:
            errors.append(f"Line {line_num}: Summary message missing 'summary' or 'leafUuid' field")
        return errors

    # Handle file-history-snapshot messages
    if msg_type == 'file-history-snapshot':
        # These have different structure, just check they exist
        return errors

    # Check for required top-level fields
    missing_required = EXPECTED_SCHEMA['required_top_level_fields'] - set(msg_data.keys())
    if missing_required:
        errors.append(f"Line {line_num}: Missing required field 'type'")

    # Validate timestamp if present
    if 'timestamp' in msg_data and msg_data['timestamp']:
        if not validate_timestamp(msg_data['timestamp']):
            errors.append(f"Line {line_num}: Invalid timestamp format: {msg_data['timestamp']}")

    # Validate message object (for user/assistant types)
    if msg_type in ['user', 'assistant']:
        message = msg_data.get('message', {})
        if not message:
            # Message field is optional in some cases
            return errors

        if not isinstance(message, dict):
            errors.append(f"Line {line_num}: 'message' field should be a dict, got {type(message)}")
            return errors

        # Check message role
        role = message.get('role')
        if role and role not in EXPECTED_SCHEMA['valid_message_roles']:
            errors.append(f"Line {line_num}: Unknown message role '{role}'")

        # Validate content
        content = message.get('content')
        if content is None:
            return errors

        if isinstance(content, list):
            # Content is array of blocks
            for idx, block in enumerate(content):
                block_errors = validate_content_block(block, idx)
                errors.extend([f"Line {line_num}: {err}" for err in block_errors])
        elif not isinstance(content, str) and not isinstance(content, dict):
            errors.append(f"Line {line_num}: Content should be string, dict, or array, got {type(content)}")

    # Validate tool use result if present (can be dict, list, or string)
    if 'toolUseResult' in msg_data:
        tool_result = msg_data['toolUseResult']
        # toolUseResult can be various types in the actual format
        if not isinstance(tool_result, (dict, list, str)):
            errors.append(f"Line {line_num}: 'toolUseResult' should be dict, list, or string, got {type(tool_result)}")

    return errors


def verify_file_schema(file_path: Path) -> tuple[bool, List[str]]:
    """
    Verify the schema of a single JSONL file.

    Returns:
        (is_valid, errors) tuple
    """
    errors = []

    if not file_path.exists():
        return False, [f"File not found: {file_path}"]

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except Exception as e:
        return False, [f"Failed to read file: {e}"]

    if not lines:
        return False, ["File is empty"]

    # Validate each line
    for line_num, line in enumerate(lines, 1):
        line = line.strip()
        if not line:
            continue

        try:
            msg_data = json.loads(line)
        except json.JSONDecodeError as e:
            errors.append(f"Line {line_num}: Invalid JSON - {e}")
            continue

        msg_errors = validate_message(msg_data, line_num)
        errors.extend(msg_errors)

    is_valid = len(errors) == 0
    return is_valid, errors


def verify_parser_compatibility(file_path: Path) -> tuple[bool, List[str]]:
    """
    Test that our parser can successfully parse the file.

    Returns:
        (is_compatible, errors) tuple
    """
    errors = []

    try:
        from cc_session_search.core.conversation_parser import JSONLParser

        parser = JSONLParser()
        metadata, messages = parser.parse_conversation_file(file_path)

        # Basic sanity checks
        if not messages:
            errors.append("Parser returned no messages")

        if metadata.message_count == 0:
            errors.append("Metadata reports 0 messages")

        # Check that we got expected message fields
        for idx, msg in enumerate(messages[:5]):  # Check first 5 messages
            if not hasattr(msg, 'role'):
                errors.append(f"Message {idx}: Missing 'role' attribute")
            if not hasattr(msg, 'content'):
                errors.append(f"Message {idx}: Missing 'content' attribute")
            if not hasattr(msg, 'timestamp'):
                errors.append(f"Message {idx}: Missing 'timestamp' attribute")
            if not hasattr(msg, 'tool_uses'):
                errors.append(f"Message {idx}: Missing 'tool_uses' attribute")

    except Exception as e:
        errors.append(f"Parser failed: {e}")

    is_compatible = len(errors) == 0
    return is_compatible, errors


def main():
    """Main verification script"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Verify JSONL schema compatibility for Claude Code session files"
    )
    parser.add_argument(
        "files",
        nargs="+",
        type=Path,
        help="JSONL files to verify"
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail on any warnings, not just errors"
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show detailed validation results"
    )

    args = parser.parse_args()

    total_files = len(args.files)
    failed_files = []

    print(f"Verifying {total_files} file(s)...\n")

    for file_path in args.files:
        print(f"📄 Checking: {file_path}")

        # Schema validation
        is_valid, schema_errors = verify_file_schema(file_path)

        # Parser compatibility
        is_compatible, parser_errors = verify_parser_compatibility(file_path)

        all_errors = schema_errors + parser_errors

        if is_valid and is_compatible:
            print(f"   ✅ Schema valid and parser compatible")
        else:
            print(f"   ❌ Validation failed")
            failed_files.append(file_path)

            if args.verbose or not is_valid or not is_compatible:
                for error in all_errors:
                    print(f"      - {error}")

        print()

    # Summary
    print("=" * 60)
    if failed_files:
        print(f"❌ FAILED: {len(failed_files)}/{total_files} files failed validation")
        print(f"\nFailed files:")
        for f in failed_files:
            print(f"  - {f}")
        sys.exit(1)
    else:
        print(f"✅ SUCCESS: All {total_files} file(s) passed validation")
        print("Schema is compatible with current parser implementation.")
        sys.exit(0)


if __name__ == "__main__":
    main()
