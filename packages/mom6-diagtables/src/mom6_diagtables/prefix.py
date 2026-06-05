"""Helpers for interpreting diag_table file prefixes.

A diag_table file name (the first column of a file-list line) looks like::

    case.mom6.h.z%4yr-%2mo
    case.mom6.h.static

The ``%Nxx`` tokens are date placeholders (``%4yr`` = a 4-digit year, ``%2mo`` = a
2-digit month, etc.) that MOM6/FMS expands when it writes the history files.  These
helpers turn a prefix into (a) a short *stream* name and (b) a regular expression that
matches the expanded netCDF file names on disk.
"""

import os
import re
from typing import Dict, Iterable

__all__ = ["stream_from_prefix", "infer_stream_names", "prefix_to_regex", "prefix_to_glob"]

# Default pattern for the CESM/MOM6 ``<case>.mom6.h.<stream>[%...]`` convention.
# The named group ``stream`` captures everything between ``.mom6.h.`` and the first
# date placeholder (or end of string).  Adapt this for other model conventions by
# supplying a different regex with the same ``(?P<stream>...)`` group.
_CESM_STREAM_PATTERN = r"\.mom6\.h\.(?P<stream>[^%]+)"


def stream_from_prefix(prefix: str, pattern: str = _CESM_STREAM_PATTERN) -> str:
    """Return the short stream name embedded in a diag_table file prefix.

    Parameters
    ----------
    prefix : str
        A diag_table file prefix, e.g. ``"case.mom6.h.z%4yr-%2mo"``.
    pattern : str, optional
        A regular expression with a ``(?P<stream>...)`` named group that captures the
        stream name.  Defaults to the CESM/MOM6 ``<case>.mom6.h.<stream>`` convention.

        To adapt for a different naming convention, supply a custom regex.  For
        example, to extract the stream after ``.ocn.h.`` instead of ``.mom6.h.``::

            pattern = r"\\.ocn\\.h\\.(?P<stream>[^%]+)"
            stream_from_prefix("case.ocn.h.z%4yr", pattern=pattern)  # -> "z"

        Any regex understood by :func:`re.search` is accepted.  The ``(?P<stream>...)``
        group name is required.

    Returns
    -------
    str
        The stream name, or (if the pattern does not match) the prefix with any date
        placeholders stripped — so callers always receive a usable fallback string.

    Examples
    --------
    >>> stream_from_prefix("case.mom6.h.z%4yr-%2mo")
    'z'
    >>> stream_from_prefix("case.mom6.h.static")
    'static'
    >>> stream_from_prefix("case.mom6.h.Agulhas_Section%4yr-%2mo")
    'Agulhas_Section'
    """
    match = re.search(pattern, prefix)
    if match:
        return match.group("stream")
    # Fallback: strip date placeholders from the whole prefix.
    return prefix.split("%", 1)[0]


def infer_stream_names(prefixes: Iterable[str]) -> Dict[str, str]:
    """Infer stream names from a collection of file prefixes without a known convention.

    Finds the longest common prefix shared by all names (after stripping date
    placeholders), snaps it back to the last word separator (``_`` or ``.``), and uses
    what remains as the stream name.  Works for both the CESM convention
    (``<case>.mom6.h.<stream>``) and non-standard conventions like BGC output
    (``ocean_cobalt_<stream>``):

    >>> infer_stream_names(["ocean_cobalt_sfc", "ocean_cobalt_btm"])
    {'sfc': 'ocean_cobalt_sfc', 'btm': 'ocean_cobalt_btm'}
    >>> infer_stream_names(["case.mom6.h.z%4yr-%2mo", "case.mom6.h.native%4yr-%2mo"])
    {'z': 'case.mom6.h.z%4yr-%2mo', 'native': 'case.mom6.h.native%4yr-%2mo'}

    Parameters
    ----------
    prefixes : iterable of str
        Diag_table file prefixes.  Date placeholders (``%Nxx`` tokens) are stripped
        before comparison.

    Returns
    -------
    dict
        ``{stream_name: original_prefix}`` — the keys are short stream identifiers;
        the values are the original prefix strings (with date placeholders intact).
    """
    prefixes = list(prefixes)
    if not prefixes:
        return {}

    # Strip date placeholders to get comparable base names.
    bases = [p.split("%", 1)[0] for p in prefixes]

    if len(bases) == 1:
        # Single file: no peers to compare against; stream name is the bare base name.
        return {bases[0]: prefixes[0]}

    common = os.path.commonprefix(bases)

    if common:
        # Snap back to the last separator so we don't cut in the middle of a word.
        sep_idx = max(common.rfind("_"), common.rfind("."))
        if sep_idx >= 0:
            common = common[:sep_idx + 1]

    if common:
        return {base[len(common):]: prefix for base, prefix in zip(bases, prefixes)}
    # No common prefix at all — return full base names as stream keys.
    return {base: prefix for base, prefix in zip(bases, prefixes)}


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
