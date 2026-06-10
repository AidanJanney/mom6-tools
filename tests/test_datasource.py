"""Tests for the DataSource data layer.

These avoid CESM/HPC and dask: ``from_config`` shells out to ``xmlquery`` and needs a
real case, so it is exercised indirectly via path-resolution helpers here, while
``from_files`` and ``from_diag_table`` are tested with in-memory datasets and the real
diag_table fixtures shipped with mom6-diagtables.
"""

from pathlib import Path

import numpy as np
import pytest
import xarray as xr

from mom6_tools.core import DataSource

DIAGTABLES = Path(__file__).resolve().parents[1] / "packages" / "mom6-diagtables" / "tests" / "data"


def _toy_dataset():
    """A tiny dataset with a couple of v-point variables (like a native/z stream)."""
    dims = ("time", "yh", "xh")
    shape = (2, 3, 4)
    data = np.arange(np.prod(shape), dtype=float).reshape(shape)
    return xr.Dataset(
        {"vmo": (dims, data), "vo": (dims, data + 1)},
        coords={"time": [0, 1]},
    )


def test_from_files_open_selects_variables():
    src = DataSource.from_files(native=_toy_dataset())
    ds = src.open("native", variables=["vmo"])
    assert list(ds.data_vars) == ["vmo"]


def test_from_files_open_fills_missing_with_zeros():
    src = DataSource.from_files(native=_toy_dataset())
    ds = src.open("native", variables=["vmo", "vhml", "vhGM"])
    assert set(ds.data_vars) == {"vmo", "vhml", "vhGM"}
    # filled variables are zeros, shaped like the present template (vmo)
    assert float(ds["vhml"].sum()) == 0.0
    assert ds["vhGM"].dims == ds["vmo"].dims


def test_open_without_fill_raises_on_missing():
    src = DataSource.from_files(native=_toy_dataset())
    with pytest.raises(KeyError):
        src.open("native", variables=["not_a_var"], fill_missing=False)


def test_unknown_stream_raises():
    src = DataSource.from_files(native=_toy_dataset())
    with pytest.raises(KeyError):
        src.open("z")


def test_relative_paths_resolved_against_outdir():
    src = DataSource.from_files(outdir="/data/run", z="case.mom6.h.z*.nc")
    assert src._paths("z") == "/data/run/case.mom6.h.z*.nc"


def test_absolute_paths_left_untouched():
    src = DataSource.from_files(outdir="/data/run", z="/elsewhere/foo.nc")
    assert src._paths("z") == "/elsewhere/foo.nc"


def test_from_diag_table_resolves_streams_to_globs():
    table = DIAGTABLES / "diag_table_regional_carib"
    src = DataSource.from_diag_table(table, outdir="/run")
    # the carib table has these streams; each becomes a *.nc glob under outdir
    assert src.has("native") and src.has("static")
    assert src._paths("static").startswith("/run/")
    assert src._paths("static").endswith(".nc")
    assert "*" in src._paths("native")
