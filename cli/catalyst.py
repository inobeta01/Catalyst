#!/usr/bin/env python3
"""Catalyst CLI entrypoint."""
import sys
import argparse
from cli.commands.run import cmd_run
from cli.commands.reset import cmd_reset
from cli.commands.eval import cmd_eval


def main():
    parser = argparse.ArgumentParser(description="Catalyst: synthetic agent evaluation harness")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("run", help="Run the agent stack")
    subparsers.add_parser("reset", help="Reset state")
    subparsers.add_parser("eval", help="Run evaluation suite")

    args = parser.parse_args()

    if args.command == "run":
        cmd_run()
    elif args.command == "reset":
        cmd_reset()
    elif args.command == "eval":
        cmd_eval()


if __name__ == "__main__":
    main()
