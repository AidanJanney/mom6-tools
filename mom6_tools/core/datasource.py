"""A uniform interface to MOM6 history output, regardless of where it comes from.

Every diagnostic script today re-implements the same handful of steps: figure out the
run directory and case name, build per-stream file globs, load the static grid, and open
each stream with ``xr.open_mfdataset`` plus a little ``preprocess`` that selects the
needed variables and fills any that are missing with zeros.  :class:`DataSource` collects
that logic in one place so a diagnostic only has to say *which stream and which variables*
it wants.

A ``DataSource`` knows three things:

* ``casename`` - the run name (used to build output file names),
* ``outdir``   - the directory holding the history files,
* ``streams``  - a mapping of stream name -> where its files live, where the value may be
  a glob string (``"case.mom6.h.z*.nc"``), a list of paths, or an already-open
  ``xarray.Dataset``.

Build one with whichever adapter matches how the user described their data:

>>> DataSource.from_config("diag_config.yml")          # the current CESM yaml workflow
>>> DataSource.from_diag_table("diag_table")           # parse a MOM6 diag_table
>>> DataSource.from_files(z="run/*.z.nc", static=...)  # explicit paths or datasets

Everything downstream (the future ``Case`` and ``Diagnostic`` classes) talks to a
``DataSource`` and never has to know which adapter built it.
"""

import glob
import os

import xarray as xr
import yaml

from mom6_tools.m6toolbox import cime_xmlquery
from mom6_tools.MOM6grid import MOM6grid

__all__ = ["DataSource"]


def _resolve_outdir(caseroot: str) -> str:
    """Return the history-file directory for a CESM case (mirrors the scripts).

    When short-term archiving (``DOUT_S``) is on, history files live under
    ``DOUT_S_ROOT/ocn/hist/``; otherwise they are still in the run directory.

    Note: the legacy scripts test ``if DOUT_S:`` on the raw ``xmlquery`` string, which is
    truthy even when it reads ``"FALSE"``.  Here we interpret it as a proper boolean so
    the ``RUNDIR`` branch is actually reachable, matching the documented behaviour.
    """
    dout_s = cime_xmlquery(caseroot, "DOUT_S").strip()
    if dout_s.upper() in ("TRUE", "1", "YES", "ON"):
        return cime_xmlquery(caseroot, "DOUT_S_ROOT").strip() + "/ocn/hist/"
    return cime_xmlquery(caseroot, "RUNDIR").strip()


def _prepare(ds: xr.Dataset, variables, fill_missing: bool) -> xr.Dataset:
    """Select ``variables`` from ``ds``, optionally filling absent ones with zeros.

    This is the shared replacement for the per-script ``preprocess()`` helpers.  When a
    requested variable is missing and ``fill_missing`` is true, it is created as
    ``zeros_like`` an existing requested variable (the same trick the scripts use so a run
    that didn't output, say, ``vhGM`` still computes).  With ``fill_missing`` false a
    missing variable raises ``KeyError``.
    """
    if variables is None:
        return ds
    if fill_missing:
        present = [v for v in variables if v in ds.variables]
        template = ds[present[0]] if present else None
        for v in variables:
            if v not in ds.variables:
                if template is None:
                    raise KeyError(
                        f"Cannot fill missing variable {v!r}: none of {variables} are "
                        f"present to use as a template."
                    )
                ds[v] = xr.zeros_like(template)
    return ds[list(variables)]


class DataSource:
    """Resolves a model-output source to a uniform ``{stream -> dataset}`` interface.

    Construct via :meth:`from_config`, :meth:`from_diag_table`, or :meth:`from_files`
    rather than calling the initializer directly.
    """

    def __init__(
        self,
        *,
        casename=None,
        outdir="",
        streams=None,
        start_date=None,
        end_date=None,
        config=None,
        diag_table=None,
    ):
        self.casename = casename
        self.outdir = outdir or ""
        self.streams = dict(streams or {})
        self.start_date = start_date
        self.end_date = end_date
        #: the parsed ``diag_config.yml`` dict, if built by :meth:`from_config`
        self.config = config
        #: the parsed ``DiagTable``, if built by :meth:`from_diag_table`
        self.diag_table = diag_table

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        return (
            f"DataSource(casename={self.casename!r}, outdir={self.outdir!r}, "
            f"streams={sorted(self.streams)})"
        )

    # -- adapters ----------------------------------------------------------------

    @classmethod
    def from_config(cls, yml_path, start_date=None, end_date=None):
        """Build from a ``diag_config.yml`` (the current CESM workflow).

        Resolves the case name and history directory via CESM's ``xmlquery`` exactly as
        the scripts do, and builds one glob per ``Fnames`` stream as
        ``casename + suffix``.  ``start_date``/``end_date`` override the ``Avg`` block.
        """
        with open(yml_path) as fh:
            config = yaml.safe_load(fh)
        caseroot = config["Case"]["CASEROOT"]
        casename = cime_xmlquery(caseroot, "CASE").strip()
        outdir = _resolve_outdir(caseroot)
        fnames = config.get("Fnames", {})
        streams = {name: casename + suffix for name, suffix in fnames.items()}
        avg = config.get("Avg", {})
        return cls(
            casename=casename,
            outdir=outdir,
            streams=streams,
            start_date=start_date or avg.get("start_date"),
            end_date=end_date or avg.get("end_date"),
            config=config,
        )

    @classmethod
    def from_diag_table(cls, diag_table_path, outdir=None, casename=None,
                        start_date=None, end_date=None, geom=None,
                        stream_pattern=None, stream_mapping=None):
        """Build by parsing a MOM6 ``diag_table``.

        Each stream in the table becomes a file glob (``prefix_to_glob``).  ``outdir``
        defaults to the directory containing the diag_table; pass it explicitly if the
        history files live elsewhere.

        Stream names come from :meth:`DiagTable.streams`, which by default uses the
        convention-agnostic common-prefix heuristic.  Override per-table with
        ``stream_pattern`` (a regex with a ``(?P<stream>...)`` group, e.g. the CESM
        ``\\.mom6\\.h\\.(?P<stream>[^%]+)``) or ``stream_mapping``
        (an explicit ``{file_name: stream_name}`` dict).

        ``geom`` is an optional path to the ocean geometry file
        (``ocean_geometry.nc``).  Required only when land-block elimination is enabled;
        if omitted, ``grid()`` uses the static file alone.
        """
        from mom6_diagtables import parse_diag_table, prefix_to_glob

        table = parse_diag_table(diag_table_path)
        if outdir is None:
            outdir = os.path.dirname(os.path.abspath(diag_table_path))
        streams = {
            stream: prefix_to_glob(dfile.file_name)
            for stream, dfile in table.streams(pattern=stream_pattern,
                                               mapping=stream_mapping).items()
        }
        if geom is not None:
            streams["geom"] = str(geom)
        return cls(
            casename=casename,
            outdir=outdir,
            streams=streams,
            start_date=start_date,
            end_date=end_date,
            diag_table=table,
        )

    @classmethod
    def from_files(cls, *, casename=None, outdir="", start_date=None, end_date=None,
                   **streams):
        """Build from explicit per-stream files, globs, or open datasets.

        Each keyword names a stream; its value is a path/glob, a list of paths, or an
        ``xarray.Dataset`` (already opened).  Relative paths are resolved against
        ``outdir``.  Example::

            DataSource.from_files(z="run/*.z.nc", static="run/static.nc")
        """
        return cls(
            casename=casename,
            outdir=outdir,
            streams=streams,
            start_date=start_date,
            end_date=end_date,
        )

    # -- access ------------------------------------------------------------------

    def has(self, stream: str) -> bool:
        """Whether ``stream`` is defined on this source."""
        return stream in self.streams

    def variables(self, stream: str) -> set:
        """Return the data-variable names available in ``stream``.

        For an in-memory ``Dataset`` this reads its ``data_vars`` directly; for files it
        opens only the FIRST matching file (not the whole ``open_mfdataset`` set), so it is
        cheap enough to call from :meth:`Case.available_for`.  Raises if the stream is
        undefined or its files cannot be opened - callers that want a soft check should
        catch the exception.
        """
        spec = self._spec(stream)
        if isinstance(spec, xr.Dataset):
            return set(spec.data_vars)
        with xr.open_dataset(self._single_path(stream), decode_times=False) as ds:
            return set(ds.data_vars)

    def open(self, stream, variables=None, parallel=False, fill_missing=True,
             time_slice=False, **open_kwargs):
        """Open ``stream`` as a lazy :class:`xarray.Dataset`.

        Parameters
        ----------
        stream : str
            Stream name, e.g. ``"z"``, ``"native"``, ``"static"``.
        variables : list of str, optional
            Restrict to these variables.  With ``fill_missing`` (default), any that are
            absent are added as zeros; without it, a missing variable raises ``KeyError``.
        parallel : bool
            Passed to ``xr.open_mfdataset`` (set ``True`` when a dask cluster is up).
        time_slice : bool
            If true, slice ``time`` to ``[start_date, end_date]``.  Off by default because
            most diagnostics slice after their own temporal averaging.
        **open_kwargs
            Forwarded to ``xr.open_mfdataset``.
        """
        spec = self._spec(stream)
        if isinstance(spec, xr.Dataset):
            ds = _prepare(spec, variables, fill_missing)
        else:
            preprocess = None
            if variables is not None:
                preprocess = lambda d: _prepare(d, variables, fill_missing)  # noqa: E731
            ds = xr.open_mfdataset(
                self._paths(stream), parallel=parallel, preprocess=preprocess,
                **open_kwargs,
            )
        if time_slice:
            ds = ds.sel(time=slice(self.start_date, self.end_date))
        return ds

    def grid(self, xrformat=False):
        """Load the static grid via :func:`mom6_tools.MOM6grid.MOM6grid`.

        Uses the ``static`` stream, and the ``geom`` stream as an override when present
        (needed when land-block elimination leaves NaNs in the static file).
        """
        static_path = self._single_path("static")
        if self.has("geom"):
            geom_path = self._single_path("geom")
            if os.path.exists(geom_path):
                return MOM6grid(static_path, geom_path, xrformat=xrformat)
        return MOM6grid(static_path, xrformat=xrformat)

    # -- internals ---------------------------------------------------------------

    def _spec(self, stream):
        if stream not in self.streams:
            raise KeyError(
                f"Stream {stream!r} is not defined on this DataSource "
                f"(have: {sorted(self.streams)})"
            )
        return self.streams[stream]

    def _abspath(self, path):
        if os.path.isabs(path) or not self.outdir:
            return path
        return os.path.join(self.outdir, path)

    def _paths(self, stream):
        """Return a glob string or list of paths suitable for ``open_mfdataset``."""
        spec = self._spec(stream)
        if isinstance(spec, (list, tuple)):
            return [self._abspath(p) for p in spec]
        return self._abspath(spec)

    def _single_path(self, stream):
        """Resolve ``stream`` to a single existing file path (for grid loading)."""
        spec = self._spec(stream)
        if isinstance(spec, xr.Dataset):
            raise ValueError(
                f"Stream {stream!r} is an in-memory Dataset; grid() needs a file path."
            )
        if isinstance(spec, (list, tuple)):
            return self._abspath(spec[0])
        path = self._abspath(spec)
        if any(ch in path for ch in "*?["):
            matches = sorted(glob.glob(path))
            if not matches:
                raise FileNotFoundError(f"No files match {path!r}")
            return matches[0]
        return path
