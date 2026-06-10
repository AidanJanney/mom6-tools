"""Placeholder for diag_table *generation* (not implemented yet).

The parser side (:func:`mom6_diagtables.parse_diag_table`) already produces the
:class:`~mom6_diagtables.table.DiagTable` data model that a writer would consume, so the
remaining work is formatting each :class:`~mom6_diagtables.table.DiagFile` /
:class:`~mom6_diagtables.table.DiagField` back into valid diag_table syntax.  This module
is intentionally a stub until that feature is needed; it is not exported from the package.
"""


def diag_table_to_string(table) -> str:  # pragma: no cover - not implemented yet
    """Render a :class:`DiagTable` as diag_table text. Not implemented yet."""
    raise NotImplementedError(
        "Writing diag_tables is not implemented yet (see writer.py)."
    )
