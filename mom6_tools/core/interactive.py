"""Decide whether a diagnostic should plot/save automatically.

The diagnostics support a ``plot``/``save`` policy that can be ``True``, ``False`` or
``"auto"`` (the default).  ``"auto"`` means *do the side effect when running
non-interactively* (a script or the CLI) and *skip it when interactive* (a notebook or
REPL), so that ``case.moc()`` in a notebook just returns the data for inspection while
``moc.py`` from the command line writes its PNGs and NetCDF as before.
"""

import sys

__all__ = ["is_interactive", "resolve"]


def is_interactive() -> bool:
    """Best-effort detection of an interactive Python session.

    True for a plain REPL (``sys.ps1`` is set), IPython/Jupyter (``get_ipython`` is
    available), or ``python -i``.  False for a normal script or the CLI.
    """
    if hasattr(sys, "ps1"):
        return True
    try:  # IPython/Jupyter inject get_ipython into builtins
        get_ipython  # type: ignore  # noqa: F821
        return True
    except NameError:
        pass
    return bool(getattr(sys.flags, "interactive", 0))


def resolve(value) -> bool:
    """Turn a ``True``/``False``/``"auto"``/``None`` policy into a boolean.

    ``"auto"`` (and ``None``) resolve to ``not is_interactive()``.
    """
    if value is True or value is False:
        return value
    if value in ("auto", None):
        return not is_interactive()
    raise ValueError(f"Expected True, False, 'auto' or None; got {value!r}")
