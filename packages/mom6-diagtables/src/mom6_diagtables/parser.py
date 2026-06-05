"""Parse a MOM6/FMS diag_table text file into a :class:`~mom6_diagtables.table.DiagTable`.

The diag_table is read as comma-separated values (strings are double-quoted and may
contain spaces, e.g. a regional section ``"20.1 20.1 -69.8 -34.6 -1 -1"``), so we split on
commas rather than whitespace.  The layout is:

    line 1            title (a quoted string)
    line 2            base date: six integers "YYYY MM DD HH MM SS"
    file list         one DiagFile per line, until the field list begins
    field list        one DiagField per line

A line belongs to the field list when its second column is a string (the field name)
rather than an integer (a file's output frequency).  Blank lines and ``#`` comments are
ignored everywhere.
"""

import csv
import io
from typing import List, Optional

from .table import DiagField, DiagFile, DiagTable

__all__ = ["parse_diag_table", "parse_diag_table_string"]


def parse_diag_table(path) -> DiagTable:
    """Parse the diag_table at ``path`` and return a :class:`DiagTable`.

    The format is detected automatically: files ending in ``.yaml`` or ``.yml`` are
    parsed as YAML; everything else is parsed as ASCII.
    """
    if _is_yaml_path(path):
        from .parser_yaml import parse_diag_table_yaml
        return parse_diag_table_yaml(path)
    with open(path, "r") as fh:
        return parse_diag_table_string(fh.read())


def parse_diag_table_string(text: str) -> DiagTable:
    """Parse the contents of a diag_table (as a string) into a :class:`DiagTable`."""
    rows = _content_rows(text)
    if len(rows) < 2:
        raise ValueError("diag_table is missing its title and/or base-date header lines")

    title = rows[0][0].strip()
    base_date = _parse_base_date(rows[1])

    files: List[DiagFile] = []
    fields: List[DiagField] = []
    in_field_list = False
    for cols in rows[2:]:
        # Once we see the first field line, everything after it is a field line too.
        if not in_field_list and _is_field_line(cols):
            in_field_list = True
        if in_field_list:
            fields.append(_make_field(cols))
        else:
            files.append(_make_file(cols))

    return DiagTable(title=title, base_date=base_date, files=files, fields=fields)


# -- internals -------------------------------------------------------------------


def _content_rows(text: str) -> List[List[str]]:
    """Return non-blank, non-comment lines parsed into lists of stripped CSV columns."""
    rows = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        # csv handles double-quoted fields that contain commas or spaces.
        cols = next(csv.reader(io.StringIO(line), skipinitialspace=True))
        cols = [c.strip() for c in cols]
        rows.append(cols)
    return rows


def _parse_base_date(cols: List[str]) -> List[int]:
    """The base date is six integers, sometimes space-separated within one CSV column."""
    tokens: List[str] = []
    for col in cols:
        tokens.extend(col.split())
    return [int(tok) for tok in tokens]


def _is_field_line(cols: List[str]) -> bool:
    """A field line's second column is a field name (string); a file line's second
    column is the output frequency (an integer)."""
    if len(cols) < 2:
        return False
    return not _looks_like_int(cols[1])


def _looks_like_int(value: str) -> bool:
    try:
        int(value)
        return True
    except ValueError:
        return False


def _opt_int(cols: List[str], i: int) -> Optional[int]:
    if i < len(cols) and cols[i] != "":
        return int(cols[i])
    return None


def _opt_str(cols: List[str], i: int) -> Optional[str]:
    if i < len(cols) and cols[i] != "":
        return cols[i]
    return None


def _make_file(cols: List[str]) -> DiagFile:
    if len(cols) < 6:
        raise ValueError(f"file-list line has too few columns: {cols!r}")
    return DiagFile(
        file_name=cols[0],
        output_freq=int(cols[1]),
        output_freq_units=cols[2],
        file_format=int(cols[3]),
        time_axis_units=cols[4],
        time_axis_name=cols[5],
        new_file_freq=_opt_int(cols, 6),
        new_file_freq_units=_opt_str(cols, 7),
        start_time=_opt_str(cols, 8),
        file_duration=_opt_int(cols, 9),
        file_duration_units=_opt_str(cols, 10),
    )


def _make_field(cols: List[str]) -> DiagField:
    if len(cols) < 8:
        raise ValueError(f"field-list line has too few columns: {cols!r}")
    return DiagField(
        module_name=cols[0],
        field_name=cols[1],
        output_name=cols[2],
        file_name=cols[3],
        time_sampling=cols[4],
        reduction_method=cols[5],
        regional_section=cols[6],
        packing=int(cols[7]),
    )


def _is_yaml_path(path) -> bool:
    return str(path).endswith((".yaml", ".yml"))
