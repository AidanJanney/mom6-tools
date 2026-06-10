"""A name -> Diagnostic-class registry, resolved lazily.

The registry maps a short name (``"moc"``) to a ``"module:Class"`` string and imports the
module only when that diagnostic is first used.  This keeps ``import mom6_tools`` light:
the heavy per-diagnostic imports (dask, intake, plotting, the cluster modules) are not
pulled in until a diagnostic actually runs.

As diagnostics are migrated in later phases, add a line to ``_REGISTRY`` (or call
:func:`register`).
"""

import importlib

__all__ = ["register", "get_diagnostic", "is_registered", "available"]

# name -> "module:ClassName"
_REGISTRY = {
    "moc": "mom6_tools.moc:MOC",
    "surface": "mom6_tools.surface:Surface",
}


def register(name: str, target: str) -> None:
    """Register ``name`` -> ``"module:ClassName"`` (overwrites an existing entry)."""
    _REGISTRY[name] = target


def is_registered(name: str) -> bool:
    """Whether ``name`` is a known diagnostic."""
    return name in _REGISTRY


def available() -> list:
    """All registered diagnostic names, in registration order."""
    return list(_REGISTRY)


def get_diagnostic(name: str):
    """Import and return the Diagnostic class registered under ``name``.

    Raises ``KeyError`` if ``name`` is unknown.
    """
    try:
        target = _REGISTRY[name]
    except KeyError:
        raise KeyError(
            f"No diagnostic named {name!r}; known diagnostics: {available()}"
        )
    module_name, class_name = target.split(":")
    module = importlib.import_module(module_name)
    return getattr(module, class_name)
