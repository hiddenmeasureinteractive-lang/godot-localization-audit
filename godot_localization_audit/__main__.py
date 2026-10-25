"""Command line interface. Stdout is data; stderr carries input errors."""
from __future__ import annotations

import argparse
import json
import sys

from . import __version__, scan_path, proposed_patch, check_catalog


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit Godot localization without executing or changing project files.")
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("scan", "patch", "check-catalog"):
        child = commands.add_parser(command)
        child.add_argument("path")
        if command != "patch":
            child.add_argument("--format", choices=("text", "json"), default="text")
        if command != "check-catalog":
            child.add_argument("--display-function", action="append", default=[], metavar="NAME",
                               help="Trust a bare function as a one-argument display sink; repeatable.")
    args = parser.parse_args(argv)
    # Unicode source strings must survive Windows redirected output.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", newline="")
    if args.command == "patch":
        if not args.display_function:
            print("No display functions allowlisted; no patch proposed.", file=sys.stderr)
            return 0
        try:
            sys.stdout.write(proposed_patch(args.path, args.display_function))
            return 0
        except (OSError, ValueError) as exc:
            print(str(exc), file=sys.stderr)
            return 2
    report = scan_path(args.path, args.display_function) if args.command == "scan" else check_catalog(args.path)
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    elif args.command == "scan":
        for finding in report["findings"]:
            print(f"{finding['path']}:{finding['line']}:{finding['column']} [{finding['category']}] "
                  f"{finding['text']!r} — {finding['reason']}")
        print(f"Scanned {report['files_scanned']} file(s); {len(report['findings'])} literal(s). "
              "This is a lexical audit, not proof of complete localization.")
    else:
        for issue in report["issues"]:
            print(f"{args.path}:{issue['row']} [{issue['locale']}/{issue['kind']}] {issue['message']}")
        print(f"Checked {report['rows_checked']} source-string row(s); {len(report['issues'])} issue(s).")
    if report["errors"]:
        if args.format != "json":
            for error in report["errors"]:
                print(error, file=sys.stderr)
        return 2
    return 1 if args.command == "check-catalog" and report["issues"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
