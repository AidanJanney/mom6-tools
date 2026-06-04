"""Command-line interface for mom6-diagtables.

    mom6-diagtables inspect <diag_table>     # summarize files, fields, and streams
    mom6-diagtables validate <diag_table>    # exit non-zero if it cannot be parsed
"""

import argparse
import sys

from .parser import parse_diag_table


def _inspect(path: str) -> int:
    table = parse_diag_table(path)
    print(f"Title:     {table.title}")
    print(f"Base date: {table.base_date}")
    print(f"\nFiles ({len(table.files)}):")
    for f in table.files:
        n = len(table.fields_for(f.file_name))
        print(f"  {f.stream:<20} {f.file_name}  ({f.output_freq} {f.output_freq_units}, {n} fields)")
    streams = sorted(table.streams())
    print(f"\nStreams ({len(streams)}): {', '.join(streams)}")
    print(f"Total fields: {len(table.fields)}")
    return 0


def _validate(path: str) -> int:
    try:
        table = parse_diag_table(path)
    except Exception as exc:  # noqa: BLE001 - report any parse failure to the user
        print(f"INVALID: {path}: {exc}", file=sys.stderr)
        return 1
    print(f"OK: {path} ({len(table.files)} files, {len(table.fields)} fields)")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="mom6-diagtables", description="Read and inspect MOM6 diag_table files."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_inspect = sub.add_parser("inspect", help="Summarize a diag_table.")
    p_inspect.add_argument("path", help="Path to a diag_table file.")

    p_validate = sub.add_parser("validate", help="Check that a diag_table parses.")
    p_validate.add_argument("path", help="Path to a diag_table file.")

    args = parser.parse_args(argv)
    if args.command == "inspect":
        return _inspect(args.path)
    if args.command == "validate":
        return _validate(args.path)
    return 2  # unreachable: subcommand is required


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
