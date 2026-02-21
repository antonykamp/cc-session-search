#!/usr/bin/env python3
"""
Claude Code Session Explorer CLI Tool
"""

import sys
import argparse
import subprocess

from cc_session_explorer.experiment_collector import ExperimentCollector


# ANSI color codes
class Colors:
    RESET = '\033[0m'
    DIM = '\033[2m'
    ERROR = '\033[91m'     # Red
    SUCCESS = '\033[92m'   # Green


def colorize(text: str, color: str, use_color: bool = True) -> str:
    """Add color to text if color is enabled"""
    if not use_color:
        return text
    return f"{color}{text}{Colors.RESET}"


def cmd_collect_experiment(args):
    """Collect experiment metrics to CSV"""

    use_color = args.color if hasattr(args, 'color') else True
    collector = ExperimentCollector(args.directory, args.experiment_id)

    print(colorize(f"Collecting sessions for experiment '{args.experiment_id}' from {args.directory}...",
                    Colors.DIM, use_color))

    rows = collector.collect()
    output_path = collector.write_csv(rows, args.output)

    main_count = sum(1 for r in rows if not r['is_sub_agent'])
    sub_count = sum(1 for r in rows if r['is_sub_agent'])
    print(colorize(f"Wrote {len(rows)} rows ({main_count} main + {sub_count} sub-agent) to {output_path}",
                    Colors.SUCCESS, use_color))


def main():
    """CLI entry point for collecting experiment data"""
    parser = argparse.ArgumentParser(
        prog='cc-collect',
        description='Collect experiment metrics from Claude Code sessions to CSV',
    )
    parser.add_argument('directory', help='Path to directory with session JSONL files')
    parser.add_argument('experiment_id', help='Experiment ID to filter by (e.g. 2026-02-01--6)')
    parser.add_argument('--output', '-o', help='Output CSV path (default: <experiment-id>--summary.csv)')
    parser.add_argument('--no-color', dest='color', action='store_false', default=True,
                        help='Disable colored output')

    args = parser.parse_args()

    try:
        cmd_collect_experiment(args)
    except ValueError as e:
        print(colorize(f"Error: {str(e)}", Colors.ERROR, args.color), file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(colorize(f"Error: {str(e)}", Colors.ERROR, args.color), file=sys.stderr)
        if '--debug' in sys.argv:
            raise
        sys.exit(1)


def run_dashboard():
    """Launch the Streamlit dashboard"""
    from pathlib import Path
    dashboard_path = Path(__file__).parent / "dashboard.py"
    sys.exit(subprocess.call([sys.executable, "-m", "streamlit", "run", str(dashboard_path), *sys.argv[1:]]))


if __name__ == "__main__":
    main()
