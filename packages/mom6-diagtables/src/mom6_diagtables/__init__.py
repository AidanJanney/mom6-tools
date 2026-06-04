"""mom6-diagtables: a lightweight reader for MOM6/FMS diag_table files.

Typical use::

    from mom6_diagtables import parse_diag_table
    table = parse_diag_table("diag_table")
    print(table.streams())
"""

from .models import DiagField, DiagFile, DiagTable
from .parser import parse_diag_table, parse_diag_table_string
from .prefix import prefix_to_glob, prefix_to_regex, stream_from_prefix

__version__ = "0.1.0"

__all__ = [
    "parse_diag_table",
    "parse_diag_table_string",
    "DiagTable",
    "DiagFile",
    "DiagField",
    "stream_from_prefix",
    "prefix_to_regex",
    "prefix_to_glob",
]
