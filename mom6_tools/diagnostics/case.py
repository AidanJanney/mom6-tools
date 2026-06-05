"""The :class:`Case` facade - the central object users interact with.

A ``Case`` wraps a :class:`~mom6_tools.diagnostics.datasource.DataSource` and exposes each
registered diagnostic as a method that returns a mutable ``xarray`` result::

    from mom6_tools import Case

    case = Case.from_config("diag_config.yml")     # or from_diag_table / from_files
    moc  = case.moc(start_date="0052-01-01", end_date="0073-01-01", nw=6)
    results = case.run_all(only=["moc"])           # run several at once

Diagnostic methods are dispatched through the registry (:mod:`registry`), so
``case.<name>(...)`` works for any registered diagnostic without ``Case`` needing to know
about it.  Each call accepts that diagnostic's keyword arguments plus the shared
``plot``/``save`` policy.
"""

from . import registry
from .datasource import DataSource

__all__ = ["Case"]


class Case:
    """User-facing handle to one model run and its diagnostics."""

    def __init__(self, source: DataSource):
        self.source = source

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        return f"Case({self.source!r})"

    # -- construction ------------------------------------------------------------

    @classmethod
    def from_config(cls, yml_path, start_date=None, end_date=None):
        """Build from a ``diag_config.yml`` (the current CESM workflow)."""
        return cls(DataSource.from_config(yml_path, start_date=start_date, end_date=end_date))

    @classmethod
    def from_diag_table(cls, diag_table_path, outdir=None, casename=None,
                        start_date=None, end_date=None):
        """Build by parsing a MOM6 ``diag_table``."""
        return cls(DataSource.from_diag_table(
            diag_table_path, outdir=outdir, casename=casename,
            start_date=start_date, end_date=end_date))

    @classmethod
    def from_files(cls, **kwargs):
        """Build from explicit per-stream files, globs, or open datasets."""
        return cls(DataSource.from_files(**kwargs))

    # -- convenience -------------------------------------------------------------

    @property
    def casename(self):
        return self.source.casename

    @property
    def config(self):
        """The parsed ``diag_config.yml`` dict, or ``None`` for other sources."""
        return self.source.config

    # -- diagnostics -------------------------------------------------------------

    def diagnostic(self, name):
        """Return an instantiated Diagnostic for ``name`` (bound to this case)."""
        return registry.get_diagnostic(name)(self)

    def run_all(self, only=None, exclude=None, **kwargs):
        """Run several diagnostics and collect their results.

        Parameters
        ----------
        only : list of str, optional
            Run just these diagnostics (default: every registered one).
        exclude : list of str, optional
            Skip these.
        **kwargs
            Passed to every diagnostic's ``run`` (e.g. ``nw``, ``plot``, ``save``).

        Returns
        -------
        dict
            Maps diagnostic name -> its result.
        """
        names = list(only) if only is not None else registry.available()
        if exclude:
            names = [n for n in names if n not in exclude]
        results = {}
        for name in names:
            results[name] = self.diagnostic(name).run(**kwargs)
        return results

    def __getattr__(self, name):
        """Dispatch ``case.<diagnostic>(...)`` to the registered diagnostic's ``run``."""
        # __getattr__ runs only when normal attribute lookup fails, so this never
        # shadows real attributes/methods.  Ignore dunder/private lookups.
        if name.startswith("_"):
            raise AttributeError(name)
        if registry.is_registered(name):
            return self.diagnostic(name).run
        raise AttributeError(
            f"{type(self).__name__!r} object has no attribute {name!r} and no "
            f"diagnostic is registered under that name (known: {registry.available()})"
        )
