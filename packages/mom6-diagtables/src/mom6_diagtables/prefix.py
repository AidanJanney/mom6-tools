"""Helpers for interpreting diag_table file prefixes.

A diag_table file name (the first column of a file-list line) looks like::

    case.mom6.h.z%4yr-%2mo
    case.mom6.h.static

The ``%Nxx`` tokens are date placeholders (``%4yr`` = a 4-digit year, ``%2mo`` = a
2-digit month, etc.) that MOM6/FMS expands when it writes the history files.  These
helpers turn a prefix into (a) a short *stream* name and (b) a regular expression that
matches the expanded netCDF file names on disk.
"""

import re

__all__ = ["stream_from_prefix", "prefix_to_regex", "prefix_to_glob"]


def stream_from_prefix(prefix: str) -> str:
    """Return the short stream name embedded in a diag_table file prefix.

    The CESM/MOM6 convention is ``<case>.mom6.h.<stream>[%<date placeholders>]`` so the
    stream is the text after ``.mom6.h.`` and before the first ``%``.

    Examples
    --------
    >>> stream_from_prefix("case.mom6.h.z%4yr-%2mo")
    'z'
    >>> stream_from_prefix("case.mom6.h.static")
    'static'
    >>> stream_from_prefix("case.mom6.h.Agulhas_Section%4yr-%2mo")
    'Agulhas_Section'

    If the ``.mom6.h.`` marker is absent, the whole prefix (minus any date
    placeholders) is returned, so callers always get a usable string.
    """
    marker = ".mom6.h."
    tail = prefix.split(marker, 1)[1] if marker in prefix else prefix
    # Drop date placeholders such as %4yr-%2mo.
    return tail.split("%", 1)[0]


def prefix_to_regex(prefix: str) -> str:
    """Convert a diag_table file prefix into a regex matching its netCDF files.

    Each ``%N...`` date placeholder becomes ``_\\d{N}`` (N digits), mirroring the
    long-standing convention in mom6-tools' ``DiagsCase.convert_prefix_to_regex``.  The
    returned pattern ends in ``.nc`` and is intended for use with :func:`re.search`.

    >>> prefix_to_regex("case.mom6.h.z%4yr-%2mo")
    'case.mom6.h.z_\\\\d{4}_\\\\d{2}.nc'
    """
    parts = prefix.split("%")
    regex = parts[0]
    for date_token in parts[1:]:
        ndigits = int(date_token[0])
        regex += rf"_\d{{{ndigits}}}"
    regex += ".nc"
    return regex


def prefix_to_glob(prefix: str) -> str:
    """Convert a diag_table file prefix into a shell glob matching its netCDF files.

    Everything from the first date placeholder onward is collapsed to ``*``, so the
    glob matches any expanded history file for that stream.  A prefix with no date
    placeholders simply gains a ``.nc`` suffix.  This mirrors how the existing scripts
    glob history files (e.g. ``casename + ".mom6.h.z*.nc"``).

    >>> prefix_to_glob("case.mom6.h.z%4yr-%2mo")
    'case.mom6.h.z*.nc'
    >>> prefix_to_glob("case.mom6.h.static")
    'case.mom6.h.static.nc'
    """
    head = prefix.split("%", 1)[0]
    return head + "*.nc" if "%" in prefix else head + ".nc"
