"""Generate diag_table text from :class:`~mom6_diagtables.models.DiagTable` objects.

This is a planned feature and is **not implemented yet**.  The goal is to let users build
a :class:`DiagTable` programmatically (or load, modify, and round-trip an existing one)
and write it back out in valid diag_table syntax.

The parsing side (:func:`mom6_diagtables.parse_diag_table`) already produces the data
model this writer will consume, so implementation is mostly a matter of formatting each
:class:`DiagFile` / :class:`DiagField` back into a quoted, comma-separated line.
"""

__all__ = ["write_diag_table", "diag_table_to_string"]


def diag_table_to_string(table) -> str:  # pragma: no cover - not implemented yet
    """Render a :class:`DiagTable` as diag_table text. Not implemented yet."""
    raise NotImplementedError(
        "Writing diag_tables is not implemented yet. See writer.py for the plan."
    )


def write_diag_table(table, path) -> None:  # pragma: no cover - not implemented yet
    """Write a :class:`DiagTable` to ``path`` as diag_table text. Not implemented yet."""
    raise NotImplementedError(
        "Writing diag_tables is not implemented yet. See writer.py for the plan."
    )
