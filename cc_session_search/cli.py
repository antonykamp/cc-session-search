#!/usr/bin/env python3
"""
Claude Code Session Search CLI Tool

Command-line interface for analyzing Claude Code conversation sessions across all projects.
"""

import sys
import json
import argparse

from cc_session_search.core.searcher import SessionSearcher
from cc_session_search.core.summarizer import ConversationSummarizer


def format_output(data, output_format='pretty'):
    """Format output based on user preference"""
    if output_format == 'json':
        return json.dumps(data, indent=2)
    elif output_format == 'compact':
        return json.dumps(data)
    else:  # pretty
        return json.dumps(data, indent=2)


def list_projects(args):
    """List all Claude Code projects with session counts and activity"""
    searcher = SessionSearcher()
    projects = searcher.discover_projects()
    
    if args.format == 'table':
        print(f"{'Project Name':<50} {'Sessions':<10} {'Latest Activity':<25}")
        print("-" * 85)
        for project in projects:
            decoded = project['decoded_name']
            count = project['session_count']
            latest = project['latest_activity'][:19]  # Trim to datetime only
            print(f"{decoded:<50} {count:<10} {latest:<25}")
    else:
        print(format_output(projects, args.format))


def list_sessions(args):
    """List sessions for a specific project"""
    # Support both positional and --project flag
    project_name = args.project_name or args.project_name_opt
    if not project_name:
        print("Error: project_name is required. Use either 'ccsearch list-sessions PROJECT' or 'ccsearch list-sessions --project PROJECT'", file=sys.stderr)
        sys.exit(1)
    
    searcher = SessionSearcher()
    sessions = searcher.get_sessions_for_project(project_name, args.days_back)
    
    if args.format == 'table':
        print(f"{'Session ID':<40} {'Messages':<10} {'Last Modified':<25}")
        print("-" * 75)
        for session in sessions:
            session_id = session['session_id'][:38]
            count = session['message_count']
            modified = session['last_modified'][:19]
            print(f"{session_id:<40} {count:<10} {modified:<25}")
    else:
        print(format_output(sessions, args.format))


def list_recent_sessions(args):
    """List recent sessions across all projects"""
    searcher = SessionSearcher()
    sessions = searcher.get_recent_sessions(args.days_back, args.project_filter)
    
    if args.format == 'table':
        print(f"{'Project':<30} {'Session ID':<25} {'Messages':<10} {'Modified':<20}")
        print("-" * 85)
        for session in sessions:
            project = session['project_name'][:28]
            session_id = session['session_id'][:23]
            count = session['message_count']
            modified = session['last_modified'][:19]
            print(f"{project:<30} {session_id:<25} {count:<10} {modified:<20}")
    else:
        print(format_output(sessions, args.format))


def analyze_sessions(args):
    """Extract and analyze messages from sessions with filtering"""
    searcher = SessionSearcher()
    result = searcher.analyze_sessions(
        days_back=args.days_back,
        role_filter=args.role_filter,
        project_filter=args.project_filter,
        include_tools=args.include_tools
    )
    print(format_output(result, args.format))


def search_conversations(args):
    """Search conversations for specific terms"""
    searcher = SessionSearcher()
    result = searcher.search_conversations(
        query=args.query,
        context_window=args.context_window,
        days_back=args.days_back,
        project_filter=args.project_filter,
        case_sensitive=args.case_sensitive,
        role_filter=args.role_filter,
        start_time=args.start_time,
        end_time=args.end_time
    )
    
    if args.format == 'table' and result.get('matches'):
        print(f"\nFound {result['total_matches']} matches across {result['sessions_searched']} sessions\n")
        for match in result['matches'][:10]:  # Show first 10
            print(f"Project: {match['project_name']}")
            print(f"Session: {match['session_id']}")
            print(f"Message #{match['message_index']} at {match['timestamp']}")
            print(f"Role: {match['role']}")
            print(f"Content preview: {match['content'][:100]}...")
            print("-" * 80)
    else:
        print(format_output(result, args.format))


def get_message_details(args):
    """Get full content for specific messages"""
    searcher = SessionSearcher()
    result = searcher.get_message_details(args.session_id, args.message_indices)
    print(format_output(result, args.format))


def summarize_daily(args):
    """Generate intelligent summary of conversations for a specific date"""
    summarizer = ConversationSummarizer()
    result = summarizer.summarize_daily_conversations(
        date=args.date,
        style=args.style,
        project_filter=args.project_filter
    )
    
    if args.format == 'table' or args.format == 'pretty':
        print(f"\n=== Daily Summary for {result['date']} ===")
        print(f"Style: {result['summary_style']}")
        print(f"Sessions: {result['total_sessions']}, Messages: {result['total_messages']}")
        print(f"\nSummary:\n{result['summary']}")
        if result.get('key_topics'):
            print(f"\nKey Topics: {', '.join(result['key_topics'])}")
        if result.get('projects_mentioned'):
            print(f"Projects: {', '.join(result['projects_mentioned'])}")
    else:
        print(format_output(result, args.format))


def summarize_time_range(args):
    """Generate intelligent summary for a time range"""
    summarizer = ConversationSummarizer()
    result = summarizer.summarize_time_range(
        start_time=args.start_time,
        end_time=args.end_time,
        style=args.style,
        project_filter=args.project_filter
    )
    
    if args.format == 'table' or args.format == 'pretty':
        print(f"\n=== Time Range Summary ===")
        print(f"From: {args.start_time} To: {args.end_time}")
        print(f"Style: {result['summary_style']}")
        print(f"Sessions: {result['total_sessions']}, Messages: {result['total_messages']}")
        print(f"\nSummary:\n{result['summary']}")
        if result.get('key_topics'):
            print(f"\nKey Topics: {', '.join(result['key_topics'])}")
    else:
        print(format_output(result, args.format))


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description='Claude Code Session Search - Analyze conversation sessions',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    # Global options
    parser.add_argument('--format', choices=['pretty', 'json', 'compact', 'table'],
                       default='pretty', help='Output format (default: pretty)')
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # list-projects command
    projects_parser = subparsers.add_parser('list-projects',
                                           help='List all Claude Code projects')
    
    # list-sessions command
    sessions_parser = subparsers.add_parser('list-sessions',
                                           help='List sessions for a specific project')
    sessions_parser.add_argument('project_name', nargs='?', help='Encoded project directory name')
    sessions_parser.add_argument('--project', dest='project_name_opt', help='Encoded project directory name (alternative to positional)')
    sessions_parser.add_argument('--days-back', type=int, default=7,
                                help='Days back to search (max 7, default: 7)')
    
    # list-recent-sessions command
    recent_parser = subparsers.add_parser('list-recent',
                                         help='List recent sessions across all projects')
    recent_parser.add_argument('--days-back', type=int, default=1,
                              help='Days back to search (max 7, default: 1)')
    recent_parser.add_argument('--project-filter', help='Filter to specific project')
    
    # analyze-sessions command
    analyze_parser = subparsers.add_parser('analyze',
                                          help='Analyze messages from sessions')
    analyze_parser.add_argument('--days-back', type=int, default=1,
                               help='Days back to analyze (max 7, default: 1)')
    analyze_parser.add_argument('--role-filter', choices=['user', 'assistant', 'both', 'tool'],
                               default='both', help='Filter by message role')
    analyze_parser.add_argument('--project-filter', help='Filter to specific project')
    analyze_parser.add_argument('--include-tools', action='store_true',
                               help='Include tool usage messages')
    
    # search command
    search_parser = subparsers.add_parser('search',
                                         help='Search conversations for terms')
    search_parser.add_argument('query', help='Search term or phrase')
    search_parser.add_argument('--context-window', type=int, default=1,
                              help='Messages before/after match (max 5, default: 1)')
    search_parser.add_argument('--days-back', type=int, default=2,
                              help='Days back to search (max 7, default: 2)')
    search_parser.add_argument('--project-filter', help='Filter to specific project')
    search_parser.add_argument('--case-sensitive', action='store_true',
                              help='Case sensitive search')
    search_parser.add_argument('--role-filter', choices=['user', 'assistant', 'both', 'tool'],
                              default='both', help='Filter by message role')
    search_parser.add_argument('--start-time', help='Start time (ISO format)')
    search_parser.add_argument('--end-time', help='End time (ISO format)')
    search_parser.add_argument('--include-tools', action='store_true',
                              help='Include tool usage messages')
    
    # get-messages command
    messages_parser = subparsers.add_parser('get-messages',
                                           help='Get full content for specific messages')
    messages_parser.add_argument('session_id', help='Session ID')
    messages_parser.add_argument('message_indices', type=int, nargs='+',
                                help='Message indices to retrieve (max 10)')
    
    # summarize-daily command
    daily_parser = subparsers.add_parser('summarize-daily',
                                        help='Summarize conversations for a date')
    daily_parser.add_argument('date', help='Date in YYYY-MM-DD format')
    daily_parser.add_argument('--style', choices=['journal', 'insights', 'stories'],
                             default='journal', help='Summary style')
    daily_parser.add_argument('--project-filter', help='Filter to specific project')
    
    # summarize-range command
    range_parser = subparsers.add_parser('summarize-range',
                                        help='Summarize conversations for a time range')
    range_parser.add_argument('start_time', help='Start time (ISO format)')
    range_parser.add_argument('end_time', help='End time (ISO format)')
    range_parser.add_argument('--style', choices=['journal', 'insights', 'stories'],
                             default='journal', help='Summary style')
    range_parser.add_argument('--project-filter', help='Filter to specific project')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # Route to appropriate handler
    try:
        if args.command == 'list-projects':
            list_projects(args)
        elif args.command == 'list-sessions':
            list_sessions(args)
        elif args.command == 'list-recent':
            list_recent_sessions(args)
        elif args.command == 'analyze':
            analyze_sessions(args)
        elif args.command == 'search':
            search_conversations(args)
        elif args.command == 'get-messages':
            args.message_indices = args.message_indices[:10]  # Limit to 10
            get_message_details(args)
        elif args.command == 'summarize-daily':
            summarize_daily(args)
        elif args.command == 'summarize-range':
            summarize_time_range(args)
        else:
            parser.print_help()
            sys.exit(1)
    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
