"""Command-line interface for mom6-diagtables.

    mom6-diagtables inspect  <path>   # summarize files, fields, and streams
    mom6-diagtables validate <path>   # exit non-zero if it cannot be parsed (ASCII or YAML)
    mom6-diagtables convert  <path>   # [experimental] convert legacy ASCII diag_table to YAML
"""

import argparse
import subprocess
import sys
from pathlib import Path

from .parser import parse_diag_table

_FMS_TOOLS = Path(__file__).parent / "fms_yaml_tools"


def _inspect(path: str) -> int:
    table = parse_diag_table(path)
    streams = table.streams()  # default common-prefix heuristic
    file_to_stream = {f.file_name: name for name, f in streams.items()}
    print(f"Title:     {table.title}")
    print(f"Base date: {table.base_date}")
    print(f"\nFiles ({len(table.files)}):")
    for f in table.files:
        n = len(table.fields_for(f.file_name))
        stream = file_to_stream.get(f.file_name, "")
        print(f"  {stream:<20} {f.file_name}  ({f.output_freq} {f.output_freq_units}, {n} fields)")
    print(f"\nStreams ({len(streams)}): {', '.join(sorted(streams))}")
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


def _convert(path: str) -> int:
    """Convert a legacy ASCII diag_table to YAML (experimental).

    Shells out to the vendored, LGPL-licensed FMS converter (see
    ``fms_yaml_tools/NOTICE.md``); not part of the supported pure-Python API.
    """
    script = _FMS_TOOLS / "diag_table_to_yaml.py"
    result = subprocess.run([sys.executable, str(script), "-f", path])
    return result.returncode


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="mom6-diagtables", description="Read and inspect MOM6 diag_table files."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_inspect = sub.add_parser("inspect", help="Summarize a diag_table (ASCII or YAML).")
    p_inspect.add_argument("path", help="Path to a diag_table file.")

    p_validate = sub.add_parser("validate", help="Check that a diag_table parses (ASCII or YAML).")
    p_validate.add_argument("path", help="Path to a diag_table file.")

    p_convert = sub.add_parser(
        "convert",
        help="[experimental] Convert a legacy ASCII diag_table to YAML (uses vendored "
             "LGPL FMS tool; see fms_yaml_tools/NOTICE.md).")
    p_convert.add_argument("path", help="Path to the ASCII diag_table to convert.")

    args = parser.parse_args(argv)
    if args.command == "inspect":
        return _inspect(args.path)
    if args.command == "validate":
        return _validate(args.path)
    if args.command == "convert":
        return _convert(args.path)
    return 2  # unreachable: subcommand is required


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
