#!/usr/bin/env python3
"""
Claude Code Session Search CLI Tool

Debug-focused CLI for analyzing Claude Code conversation sessions.
"""

import sys
import json
import re
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import argparse

from cc_session_search.core.searcher import SessionSearcher
from cc_session_search.core.summarizer import ConversationSummarizer


# ANSI color codes
class Colors:
    RESET = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'

    # Message types
    USER = '\033[94m'      # Blue
    ASSISTANT = '\033[92m' # Green
    THINKING = '\033[96m'  # Cyan
    TOOL = '\033[93m'      # Yellow
    ERROR = '\033[91m'     # Red
    META = '\033[95m'      # Magenta

    # UI elements
    HEADER = '\033[1;36m'  # Bold Cyan
    LABEL = '\033[90m'     # Gray
    SUCCESS = '\033[92m'   # Green
    WARNING = '\033[93m'   # Yellow


def colorize(text: str, color: str, use_color: bool = True) -> str:
    """Add color to text if color is enabled"""
    if not use_color:
        return text
    return f"{color}{text}{Colors.RESET}"


class SessionResolver:
    """Resolve session shortcuts like @last, @1, @today to actual session IDs"""

    def __init__(self, searcher: SessionSearcher):
        self.searcher = searcher

    def resolve(self, session_ref: str, project_filter: Optional[str] = None) -> Dict[str, str]:
        """
        Resolve a session reference to a session ID and project name.

        Returns: {'session_id': str, 'project_name': str}
        """
        # Direct session ID (UUID format)
        if len(session_ref) >= 36 and '-' in session_ref:
            # Find which project contains this session
            sessions = self.searcher.get_recent_sessions(days_back=30, project_filter=project_filter)
            for session in sessions:
                if session['session_id'].startswith(session_ref):
                    return {
                        'session_id': session['session_id'],
                        'project_name': session['project_name']
                    }
            raise ValueError(f"Session {session_ref} not found")

        # Shortcuts
        if session_ref.startswith('@'):
            return self._resolve_shortcut(session_ref, project_filter)

        raise ValueError(f"Invalid session reference: {session_ref}")

    def _resolve_shortcut(self, shortcut: str, project_filter: Optional[str] = None) -> Dict[str, str]:
        """Resolve @ shortcuts"""
        shortcut = shortcut.lower()

        # @last or @1 = most recent
        if shortcut in ['@last', '@1']:
            sessions = self.searcher.get_recent_sessions(days_back=7, project_filter=project_filter)
            if not sessions:
                raise ValueError("No recent sessions found")
            return {
                'session_id': sessions[0]['session_id'],
                'project_name': sessions[0]['project_name']
            }

        # @2, @3, etc = nth most recent
        if shortcut.startswith('@') and shortcut[1:].isdigit():
            n = int(shortcut[1:])
            sessions = self.searcher.get_recent_sessions(days_back=7, project_filter=project_filter)
            if n > len(sessions):
                raise ValueError(f"Only {len(sessions)} recent sessions found, requested @{n}")
            return {
                'session_id': sessions[n-1]['session_id'],
                'project_name': sessions[n-1]['project_name']
            }

        # @today = most recent from today
        if shortcut == '@today':
            today = datetime.now().strftime('%Y-%m-%d')
            sessions = self.searcher.get_recent_sessions(days_back=1, project_filter=project_filter)
            if not sessions:
                raise ValueError("No sessions found today")
            return {
                'session_id': sessions[0]['session_id'],
                'project_name': sessions[0]['project_name']
            }

        # @yesterday
        if shortcut == '@yesterday':
            sessions = self.searcher.get_recent_sessions(days_back=2, project_filter=project_filter)
            yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
            for session in sessions:
                if session['last_modified'].startswith(yesterday):
                    return {
                        'session_id': session['session_id'],
                        'project_name': session['project_name']
                    }
            raise ValueError("No sessions found yesterday")

        raise ValueError(f"Unknown shortcut: {shortcut}")


def format_message_oneline(msg: Any, idx: int, use_color: bool = True) -> str:
    """Format a message as a compact one-line summary"""
    # Handle both dict and dataclass
    role = msg.role if hasattr(msg, 'role') else msg.get('role', 'unknown')
    content = msg.content if hasattr(msg, 'content') else msg.get('content', '')
    timestamp = msg.timestamp if hasattr(msg, 'timestamp') else msg.get('timestamp', '')

    # Format timestamp
    if timestamp:
        timestamp = str(timestamp)[:19]
    else:
        timestamp = ''

    # Truncate content
    if len(content) > 80:
        content = content[:77] + '...'
    content = content.replace('\n', ' ')

    # Color by role
    color = Colors.RESET
    if role == 'user':
        color = Colors.USER
    elif role == 'assistant':
        color = Colors.ASSISTANT
    elif role == 'tool':
        color = Colors.TOOL

    role_label = f"{role:10s}"
    return f"{colorize(f'[{idx}]', Colors.LABEL, use_color)} {colorize(role_label, color, use_color)} {timestamp} {content}"


def format_message_detailed(msg: Any, idx: int, use_color: bool = True) -> str:
    """Format a message with full details"""
    # Handle both dict and dataclass
    role = msg.role if hasattr(msg, 'role') else msg.get('role', 'unknown')
    content = msg.content if hasattr(msg, 'content') else msg.get('content', '')
    timestamp = msg.timestamp if hasattr(msg, 'timestamp') else msg.get('timestamp', '')

    # Format timestamp
    if timestamp:
        timestamp = str(timestamp)
    else:
        timestamp = ''

    color = Colors.RESET
    if role == 'user':
        color = Colors.USER
    elif role == 'assistant':
        color = Colors.ASSISTANT
    elif role == 'tool':
        color = Colors.TOOL

    separator = colorize('─' * 80, Colors.DIM, use_color)
    header = colorize(f"[{idx}] {role.upper()}", color, use_color) + colorize(f" @ {timestamp}", Colors.LABEL, use_color)

    return f"{separator}\n{header}\n{content}\n"


def print_session_header(metadata: Any, use_color: bool = True):
    """Print session metadata header"""
    print(colorize("═" * 80, Colors.HEADER, use_color))
    print(colorize(f"SESSION: {metadata.session_id}", Colors.HEADER, use_color))
    print(colorize("═" * 80, Colors.HEADER, use_color))
    print(f"Project:    {metadata.project_name}")
    if metadata.git_branch:
        print(f"Branch:     {metadata.git_branch}")
    if metadata.is_subagent:
        print(colorize(f"Subagent:   {metadata.agent_type} (parent: {metadata.parent_session_id})", Colors.WARNING, use_color))
    print(colorize("─" * 80, Colors.DIM, use_color))


# ============================================================================
# COMMANDS
# ============================================================================

def cmd_show(args):
    """Show session overview with metadata and message summary"""
    resolver = SessionResolver(SessionSearcher())
    ref = resolver.resolve(args.session, args.project)

    searcher = SessionSearcher()
    result = searcher.get_session_with_subagents(ref['session_id'], ref['project_name'])

    if not result:
        print(colorize(f"✗ Session not found", Colors.ERROR, args.color), file=sys.stderr)
        sys.exit(1)

    metadata = result['metadata']
    messages = result['messages']
    agg = result['aggregate_metrics']

    print_session_header(metadata, args.color)

    # Message stats
    print(f"\nMessages:   {len(messages)}")
    user_msgs = sum(1 for m in messages if (m.role if hasattr(m, 'role') else m.get('role')) == 'user')
    asst_msgs = sum(1 for m in messages if (m.role if hasattr(m, 'role') else m.get('role')) == 'assistant')
    tool_msgs = sum(1 for m in messages if (m.role if hasattr(m, 'role') else m.get('role')) == 'tool')
    print(f"  User:     {user_msgs}")
    print(f"  Assistant: {asst_msgs}")
    print(f"  Tool:     {tool_msgs}")

    # Cost stats
    print(f"\nTokens:     {agg['total_tokens']:,}")
    print(f"Cost:       ${agg['total_cost_usd']:.4f}")
    if agg['session_count'] > 1:
        print(colorize(f"  (includes {agg['session_count'] - 1} subagents)", Colors.DIM, args.color))

    # Subagents
    if result['subagents']:
        print(f"\nSubagents:  {len(result['subagents'])}")
        for sub in result['subagents'][:5]:
            agent_type = sub.get('agent_type', 'unknown')
            msg_count = sub.get('message_count', 0)
            print(f"  • {agent_type}: {msg_count} messages")

    # Recent messages preview
    if not args.no_preview:
        print(colorize("\n─── Last 5 messages ───", Colors.HEADER, args.color))
        for idx, msg in enumerate(messages[-5:], start=len(messages)-5):
            print(format_message_oneline(msg, idx, args.color))


def cmd_tail(args):
    """Show last N messages from a session"""
    resolver = SessionResolver(SessionSearcher())
    ref = resolver.resolve(args.session, args.project)

    searcher = SessionSearcher()
    result = searcher.get_session_with_subagents(ref['session_id'], ref['project_name'])

    if not result:
        print(colorize(f"✗ Session not found", Colors.ERROR, args.color), file=sys.stderr)
        sys.exit(1)

    messages = result['messages']
    n = args.n or 20

    if not args.no_header:
        print_session_header(result['metadata'], args.color)
        print(f"\nShowing last {min(n, len(messages))} of {len(messages)} messages\n")

    for idx, msg in enumerate(messages[-n:], start=max(0, len(messages)-n)):
        if args.oneline:
            print(format_message_oneline(msg, idx, args.color))
        else:
            print(format_message_detailed(msg, idx, args.color))


def cmd_head(args):
    """Show first N messages from a session"""
    resolver = SessionResolver(SessionSearcher())
    ref = resolver.resolve(args.session, args.project)

    searcher = SessionSearcher()
    result = searcher.get_session_with_subagents(ref['session_id'], ref['project_name'])

    if not result:
        print(colorize(f"✗ Session not found", Colors.ERROR, args.color), file=sys.stderr)
        sys.exit(1)

    messages = result['messages']
    n = args.n or 20

    if not args.no_header:
        print_session_header(result['metadata'], args.color)
        print(f"\nShowing first {min(n, len(messages))} of {len(messages)} messages\n")

    for idx, msg in enumerate(messages[:n]):
        if args.oneline:
            print(format_message_oneline(msg, idx, args.color))
        else:
            print(format_message_detailed(msg, idx, args.color))


def cmd_dump(args):
    """Dump entire conversation"""
    resolver = SessionResolver(SessionSearcher())
    ref = resolver.resolve(args.session, args.project)

    searcher = SessionSearcher()
    result = searcher.get_session_with_subagents(ref['session_id'], ref['project_name'])

    if not result:
        print(colorize(f"✗ Session not found", Colors.ERROR, args.color), file=sys.stderr)
        sys.exit(1)

    messages = result['messages']

    if args.format == 'json':
        print(json.dumps(messages, indent=2))
        return

    if not args.no_header:
        print_session_header(result['metadata'], args.color)
        print(f"\nTotal messages: {len(messages)}\n")

    for idx, msg in enumerate(messages):
        print(format_message_detailed(msg, idx, args.color))


def cmd_sessions(args):
    """List sessions with smart filtering"""
    searcher = SessionSearcher()

    # Determine time range
    if args.today:
        days_back = 1
    elif args.days:
        days_back = args.days
    else:
        days_back = 1  # Default to today

    sessions = searcher.get_recent_sessions(days_back=days_back, project_filter=args.project)

    # Apply filters
    if args.has_errors:
        # TODO: implement error detection
        pass

    if args.min_cost:
        # TODO: filter by cost
        pass

    # Sort
    if args.sort_by == 'cost':
        # TODO: sort by cost
        pass

    # Output
    if args.format == 'oneline':
        for session in sessions:
            project = session['project_name'][:30]
            sid = session['session_id'][:8]
            msgs = session['message_count']
            modified = (session.get('started_at') or session.get('ended_at') or '')[: 16]
            print(f"{colorize(sid, Colors.LABEL, args.color)} {modified} {project:30s} {msgs:3d} msgs")
    elif args.format == 'json':
        print(json.dumps(sessions, indent=2))
    else:  # table
        print(colorize(f"{'Session':<10} {'Started':<17} {'Project':<30} {'Msgs':<6}", Colors.HEADER, args.color))
        print(colorize("─" * 70, Colors.DIM, args.color))
        for session in sessions:
            sid = session['session_id'][:8]
            modified = (session.get('started_at') or session.get('ended_at') or '')[:16]
            project = session['project_name'][:28]
            msgs = session['message_count']
            print(f"{sid:<10} {modified:<17} {project:<30} {msgs:<6}")

    print(colorize(f"\nTotal: {len(sessions)} sessions", Colors.DIM, args.color))


def cmd_projects(args):
    """List all projects"""
    searcher = SessionSearcher()
    projects = searcher.discover_projects()

    if args.format == 'json':
        print(json.dumps(projects, indent=2))
        return

    print(colorize(f"{'Project':<50} {'Sessions':<10} {'Latest':<20}", Colors.HEADER, args.color))
    print(colorize("─" * 80, Colors.DIM, args.color))

    for project in projects:
        name = project['decoded_name'][:48]
        count = project['session_count']
        latest = project['latest_activity'][:19]
        print(f"{name:<50} {count:<10} {latest:<20}")

    print(colorize(f"\nTotal: {len(projects)} projects", Colors.DIM, args.color))


def cmd_msg(args):
    """Get specific messages by index"""
    resolver = SessionResolver(SessionSearcher())
    ref = resolver.resolve(args.session, args.project)

    searcher = SessionSearcher()
    result = searcher.get_session_with_subagents(ref['session_id'], ref['project_name'])

    if not result:
        print(colorize(f"✗ Session not found", Colors.ERROR, args.color), file=sys.stderr)
        sys.exit(1)

    messages = result['messages']

    if args.format == 'json':
        selected = [messages[i] for i in args.indices if i < len(messages)]
        print(json.dumps(selected, indent=2))
        return

    if not args.no_header:
        print_session_header(result['metadata'], args.color)

    for idx in args.indices:
        if idx >= len(messages):
            print(colorize(f"✗ Message {idx} not found (max: {len(messages)-1})", Colors.ERROR, args.color))
            continue
        print(format_message_detailed(messages[idx], idx, args.color))


def cmd_errors(args):
    """Extract and show errors from a session"""
    resolver = SessionResolver(SessionSearcher())
    ref = resolver.resolve(args.session, args.project)

    searcher = SessionSearcher()
    result = searcher.get_session_with_subagents(ref['session_id'], ref['project_name'])

    if not result:
        print(colorize(f"✗ Session not found", Colors.ERROR, args.color), file=sys.stderr)
        sys.exit(1)

    messages = result['messages']

    # Find errors (heuristic: messages containing error keywords)
    error_keywords = ['error', 'exception', 'failed', 'failure', 'traceback', 'errno']
    errors = []

    for idx, msg in enumerate(messages):
        content = (msg.content if hasattr(msg, 'content') else msg.get('content', '')).lower()
        if any(keyword in content for keyword in error_keywords):
            errors.append((idx, msg))

    if not errors:
        print(colorize(f"✓ No errors found in session", Colors.SUCCESS, args.color))
        return

    if not args.no_header:
        print_session_header(result['metadata'], args.color)
        print(colorize(f"\nFound {len(errors)} potential errors\n", Colors.WARNING, args.color))

    for idx, msg in errors:
        print(format_message_detailed(msg, idx, args.color))


def cmd_tools(args):
    """Analyze tool usage in a session"""
    resolver = SessionResolver(SessionSearcher())
    ref = resolver.resolve(args.session, args.project)

    searcher = SessionSearcher()
    result = searcher.get_session_with_subagents(ref['session_id'], ref['project_name'])

    if not result:
        print(colorize(f"✗ Session not found", Colors.ERROR, args.color), file=sys.stderr)
        sys.exit(1)

    messages = result['messages']

    # Extract tool calls
    tool_calls = []
    for idx, msg in enumerate(messages):
        role = msg.role if hasattr(msg, 'role') else msg.get('role')
        content = str(msg.content if hasattr(msg, 'content') else msg.get('content', ''))
        if role == 'tool' or 'tool_use' in content:
            tool_calls.append((idx, msg))

    if not tool_calls:
        print(colorize(f"✓ No tool calls found", Colors.SUCCESS, args.color))
        return

    if not args.no_header:
        print_session_header(result['metadata'], args.color)
        print(colorize(f"\nFound {len(tool_calls)} tool calls\n", Colors.HEADER, args.color))

    if args.stats:
        # Show statistics
        tool_names = {}
        for idx, msg in tool_calls:
            # Try to extract tool name (simplified)
            content = str(msg.get('content', ''))
            # This is a simplified extraction - would need proper parsing
            tool_names['tool'] = tool_names.get('tool', 0) + 1

        for tool, count in sorted(tool_names.items(), key=lambda x: x[1], reverse=True):
            print(f"{tool:20s} {count:4d} calls")
    else:
        # Show all tool calls
        for idx, msg in tool_calls:
            print(format_message_oneline(msg, idx, args.color))


def cmd_cost(args):
    """Show cost breakdown for a session"""
    resolver = SessionResolver(SessionSearcher())
    ref = resolver.resolve(args.session, args.project)

    searcher = SessionSearcher()
    result = searcher.get_session_with_subagents(ref['session_id'], ref['project_name'])

    if not result:
        print(colorize(f"✗ Session not found", Colors.ERROR, args.color), file=sys.stderr)
        sys.exit(1)

    metadata = result['metadata']
    messages = result['messages']
    agg = result['aggregate_metrics']

    print_session_header(metadata, args.color)

    print(colorize("\n=== Cost Breakdown ===", Colors.HEADER, args.color))
    print(f"\nMain Session:")
    print(f"  Tokens: {agg['main_session_tokens']:,}")
    print(f"  Cost:   ${agg['main_session_cost']:.4f}")

    if result['subagents']:
        print(f"\nSubagents ({len(result['subagents'])}):")
        print(f"  Tokens: {agg['subagent_tokens']:,}")
        print(f"  Cost:   ${agg['subagent_cost']:.4f}")

        for sub in result['subagents']:
            agent_type = sub.get('agent_type', 'unknown')
            tokens = sub.get('token_count', 0)
            cost = sub.get('cost_usd', 0)
            print(f"    • {agent_type}: {tokens:,} tokens, ${cost:.4f}")

    print(f"\n{colorize('TOTAL:', Colors.BOLD, args.color)}")
    print(f"  Tokens: {agg['total_tokens']:,}")
    print(f"  Cost:   ${agg['total_cost_usd']:.4f}")
    print(f"  Avg:    ${agg['total_cost_usd']/len(messages):.4f} per message")


def cmd_search(args):
    """Search conversations with enhanced filtering"""
    searcher = SessionSearcher()

    # Build search parameters
    kwargs = {
        'query': args.query,
        'days_back': args.days or 7,
        'context_window': args.context or 1,
        'case_sensitive': args.case_sensitive,
        'project_filter': args.project,
    }

    if args.role:
        kwargs['role_filter'] = args.role

    result = searcher.search_conversations(**kwargs)

    if not result.get('matches'):
        print(colorize("✓ No matches found", Colors.WARNING, args.color))
        return

    print(colorize(f"Found {result['total_matches']} matches in {result['sessions_searched']} sessions\n", Colors.HEADER, args.color))

    limit = args.limit or 10
    for match in result['matches'][:limit]:
        project = match['project_name'][:30]
        sid = match['session_id'][:8]
        idx = match['message_index']
        role = match['role']
        timestamp = match['timestamp'][:16]
        content = match['content'][:100].replace('\n', ' ')

        print(colorize(f"{sid} [{idx}]", Colors.LABEL, args.color), end=" ")
        print(f"{timestamp} {project:30s}")
        print(f"  {content}...")
        print()


def cmd_summarize(args):
    """AI-powered conversation summary"""
    summarizer = ConversationSummarizer()

    # Determine what to summarize
    if args.target.startswith('@') or len(args.target) >= 36:
        # Session reference
        resolver = SessionResolver(SessionSearcher())
        ref = resolver.resolve(args.target, args.project)
        # TODO: implement session-specific summarization
        print(colorize("✗ Session summarization not yet implemented", Colors.ERROR, args.color))
        return
    else:
        # Assume it's a date
        result = summarizer.summarize_daily_conversations(
            date=args.target,
            style=args.style,
            project_filter=args.project
        )

        print(colorize(f"=== Summary for {result['date']} ===", Colors.HEADER, args.color))
        print(colorize(f"Style: {result['summary_style']}", Colors.DIM, args.color))
        print(colorize(f"Sessions: {result['total_sessions']}, Messages: {result['total_messages']}", Colors.DIM, args.color))
        print()
        print(result['summary'])

        if result.get('key_topics'):
            print(colorize("\nKey Topics:", Colors.LABEL, args.color))
            for topic in result['key_topics']:
                print(f"  • {topic}")


# ============================================================================
# MAIN
# ============================================================================

def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        prog='ccsearch',
        description='Claude Code Session Search - Fast conversation debugging',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  ccsearch show @last              Show overview of most recent session
  ccsearch tail @1 -n 10          Show last 10 messages
  ccsearch sessions --today        List today's sessions
  ccsearch errors @last            Extract errors from last session
  ccsearch cost @2                 Cost breakdown for 2nd most recent
  ccsearch search "bug fix"        Search for term across sessions
        """
    )

    subparsers = parser.add_subparsers(dest='command', help='Command to run')

    # Common arguments for all commands
    def add_common_args(p):
        p.add_argument('--project', '-p', help='Filter to specific project')
        p.add_argument('--no-color', dest='color', action='store_false', default=True,
                      help='Disable colored output')

    # show command
    show_parser = subparsers.add_parser('show', help='Show session overview')
    show_parser.add_argument('session', help='Session ID or @shortcut (@last, @1, @today, etc.)')
    show_parser.add_argument('--no-preview', action='store_true', help='Skip message preview')
    add_common_args(show_parser)

    # tail command
    tail_parser = subparsers.add_parser('tail', help='Show last N messages')
    tail_parser.add_argument('session', help='Session ID or @shortcut')
    tail_parser.add_argument('-n', type=int, help='Number of messages (default: 20)')
    tail_parser.add_argument('--oneline', action='store_true', help='Compact one-line format')
    tail_parser.add_argument('--no-header', action='store_true', help='Skip header')
    add_common_args(tail_parser)

    # head command
    head_parser = subparsers.add_parser('head', help='Show first N messages')
    head_parser.add_argument('session', help='Session ID or @shortcut')
    head_parser.add_argument('-n', type=int, help='Number of messages (default: 20)')
    head_parser.add_argument('--oneline', action='store_true', help='Compact one-line format')
    head_parser.add_argument('--no-header', action='store_true', help='Skip header')
    add_common_args(head_parser)

    # dump command
    dump_parser = subparsers.add_parser('dump', help='Dump entire conversation')
    dump_parser.add_argument('session', help='Session ID or @shortcut')
    dump_parser.add_argument('--format', choices=['text', 'json'], default='text')
    dump_parser.add_argument('--no-header', action='store_true', help='Skip header')
    add_common_args(dump_parser)

    # sessions command
    sessions_parser = subparsers.add_parser('sessions', help='List sessions')
    sessions_parser.add_argument('--today', action='store_true', help='Show only today')
    sessions_parser.add_argument('--days', type=int, help='Days back to search')
    sessions_parser.add_argument('--has-errors', action='store_true', help='Only sessions with errors')
    sessions_parser.add_argument('--min-cost', type=float, help='Minimum cost threshold')
    sessions_parser.add_argument('--sort-by', choices=['time', 'cost'], default='time')
    sessions_parser.add_argument('--format', choices=['table', 'oneline', 'json'], default='table')
    add_common_args(sessions_parser)

    # projects command
    projects_parser = subparsers.add_parser('projects', help='List all projects')
    projects_parser.add_argument('--format', choices=['table', 'json'], default='table')
    add_common_args(projects_parser)

    # msg command
    msg_parser = subparsers.add_parser('msg', help='Get specific messages by index')
    msg_parser.add_argument('session', help='Session ID or @shortcut')
    msg_parser.add_argument('indices', type=int, nargs='+', help='Message indices')
    msg_parser.add_argument('--format', choices=['text', 'json'], default='text')
    msg_parser.add_argument('--no-header', action='store_true', help='Skip header')
    add_common_args(msg_parser)

    # errors command
    errors_parser = subparsers.add_parser('errors', help='Extract errors from session')
    errors_parser.add_argument('session', help='Session ID or @shortcut')
    errors_parser.add_argument('--no-header', action='store_true', help='Skip header')
    add_common_args(errors_parser)

    # tools command
    tools_parser = subparsers.add_parser('tools', help='Analyze tool usage')
    tools_parser.add_argument('session', help='Session ID or @shortcut')
    tools_parser.add_argument('--stats', action='store_true', help='Show statistics only')
    tools_parser.add_argument('--no-header', action='store_true', help='Skip header')
    add_common_args(tools_parser)

    # cost command
    cost_parser = subparsers.add_parser('cost', help='Show cost breakdown')
    cost_parser.add_argument('session', help='Session ID or @shortcut')
    add_common_args(cost_parser)

    # search command
    search_parser = subparsers.add_parser('search', help='Search conversations')
    search_parser.add_argument('query', help='Search term')
    search_parser.add_argument('--days', type=int, help='Days back to search (default: 7)')
    search_parser.add_argument('--context', '-C', type=int, help='Context window size')
    search_parser.add_argument('--case-sensitive', '-i', action='store_true')
    search_parser.add_argument('--role', choices=['user', 'assistant', 'tool'])
    search_parser.add_argument('--limit', '-n', type=int, help='Limit results (default: 10)')
    add_common_args(search_parser)

    # summarize command
    summarize_parser = subparsers.add_parser('summarize', help='AI-powered summary')
    summarize_parser.add_argument('target', help='Date (YYYY-MM-DD), session ID, or @shortcut')
    summarize_parser.add_argument('--style', choices=['journal', 'insights', 'stories'],
                                  default='journal')
    add_common_args(summarize_parser)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    # Route to command handlers
    try:
        if args.command == 'show':
            cmd_show(args)
        elif args.command == 'tail':
            cmd_tail(args)
        elif args.command == 'head':
            cmd_head(args)
        elif args.command == 'dump':
            cmd_dump(args)
        elif args.command == 'sessions':
            cmd_sessions(args)
        elif args.command == 'projects':
            cmd_projects(args)
        elif args.command == 'msg':
            cmd_msg(args)
        elif args.command == 'errors':
            cmd_errors(args)
        elif args.command == 'tools':
            cmd_tools(args)
        elif args.command == 'cost':
            cmd_cost(args)
        elif args.command == 'search':
            cmd_search(args)
        elif args.command == 'summarize':
            cmd_summarize(args)
    except ValueError as e:
        print(colorize(f"✗ {str(e)}", Colors.ERROR, args.color if hasattr(args, 'color') else True), file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(colorize(f"✗ Error: {str(e)}", Colors.ERROR, args.color if hasattr(args, 'color') else True), file=sys.stderr)
        if '--debug' in sys.argv:
            raise
        sys.exit(1)


if __name__ == "__main__":
    main()
