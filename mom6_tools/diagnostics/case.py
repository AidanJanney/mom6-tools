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
                        start_date=None, end_date=None, geom=None):
        """Build by parsing a MOM6 ``diag_table``.

        ``geom`` is an optional path to the ocean geometry file; pass it when
        land-block elimination is enabled (same role as ``Fnames.geom`` in a
        ``diag_config.yml``).
        """
        return cls(DataSource.from_diag_table(
            diag_table_path, outdir=outdir, casename=casename,
            start_date=start_date, end_date=end_date, geom=geom))

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

    def _missing_requirements(self, reqs):
        """Return ``(missing_streams, missing_vars)`` for a ``requires`` mapping.

        A required stream is missing if it is not defined on the source, or if its files
        cannot be opened to verify variables.  A required variable is missing if its stream
        is present but the variable is not among that stream's data variables.  ``reqs``
        values of ``None`` (or an empty list) mean "the whole stream, no specific vars".
        """
        missing_streams, missing_vars = [], []
        for stream, wanted in reqs.items():
            if not self.source.has(stream):
                missing_streams.append(stream)
                continue
            if not wanted:
                continue
            try:
                present = self.source.variables(stream)
            except Exception:
                # Can't read the stream's files to verify variables - treat as unavailable.
                missing_streams.append(stream)
                continue
            missing_vars += [f"{stream}:{v}" for v in wanted if v not in present]
        return missing_streams, missing_vars

    def available_for(self) -> list:
        """Registered diagnostics whose requirements are all satisfied by this source.

        A diagnostic is included only if every stream in its ``requires`` exists *and*
        every variable it lists for that stream is present.  Diagnostics with no
        ``requires`` are always included.
        """
        result = []
        for name in registry.available():
            cls = registry.get_diagnostic(name)
            reqs = getattr(cls, "requires", {})
            missing_streams, missing_vars = self._missing_requirements(reqs)
            if not missing_streams and not missing_vars:
                result.append(name)
        return result

    def summary(self):
        """Print a human-readable summary of this case and its runnable diagnostics."""
        print(f"Case:   {self.casename or '(unnamed)'}")
        print(f"Outdir: {self.source.outdir or '(not set)'}")
        table = self.source.diag_table
        if table is not None:
            print(f"\nDiag table: {table.title}")
            print(f"  {len(table.files)} files, {len(table.fields)} fields")
            for stream, dfile in table.streams().items():
                n = len(table.fields_for(dfile.file_name))
                print(f"  {stream:<20} {dfile.output_freq:>3} {dfile.output_freq_units:<8} {n} fields")
        streams = sorted(self.source.streams)
        print(f"\nStreams ({len(streams)}): {', '.join(streams) if streams else '(none)'}")
        runnable = self.available_for()
        all_names = registry.available()
        print(f"\nDiagnostics ({len(runnable)}/{len(all_names)} runnable):")
        for name in all_names:
            cls = registry.get_diagnostic(name)
            reqs = getattr(cls, "requires", {})
            missing_streams, missing_vars = self._missing_requirements(reqs)
            if missing_streams or missing_vars:
                parts = []
                if missing_streams:
                    parts.append(f"streams: {', '.join(sorted(missing_streams))}")
                if missing_vars:
                    parts.append(f"vars: {', '.join(sorted(missing_vars))}")
                print(f"  {name:<20} skip  (missing {'; '.join(parts)})")
            else:
                print(f"  {name:<20} ok")

    def run_all(self, only=None, exclude=None, **kwargs):
        """Run several diagnostics and collect their results.

        Parameters
        ----------
        only : list of str, optional
            Run just these diagnostics (default: every diagnostic whose required streams
            are present — see :meth:`available_for`).
        exclude : list of str, optional
            Skip these.
        **kwargs
            Passed to every diagnostic's ``run`` (e.g. ``nw``, ``plot``, ``save``).

        Returns
        -------
        dict
            Maps diagnostic name -> its result.
        """
        names = list(only) if only is not None else self.available_for()
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
