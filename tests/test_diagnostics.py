"""Tests for the Case facade, Diagnostic base class, registry, and plot/save policy.

These use a dummy diagnostic and a toy DataSource so they exercise the framework wiring
without real model data, dask, or plotting.  The real MOC migration is checked only for
import/registration here (it needs HPC data + a cluster to run end to end).
"""

import numpy as np
import pytest
import xarray as xr

from mom6_tools.diagnostics import Case, Diagnostic
from mom6_tools.diagnostics import interactive, registry


class _Dummy(Diagnostic):
    name = "dummy"
    requires = {"native": ["foo"]}

    def compute(self, *, scale=1.0):
        ds = self.case.source.open("native", variables=["foo"])
        return (ds["foo"] * scale).rename("result")

    def plot(self, result):
        self.case._plotted = True

    def save(self, result):
        self.case._saved = True


@pytest.fixture
def case():
    foo = xr.DataArray(np.arange(4.0), dims=["x"], name="foo")
    c = Case.from_files(native=xr.Dataset({"foo": foo}))
    c._plotted = c._saved = False
    return c


def test_resolve_policy_explicit():
    assert interactive.resolve(True) is True
    assert interactive.resolve(False) is False


def test_resolve_policy_auto_matches_non_interactive():
    # The test runner is non-interactive, so 'auto' should be True here.
    assert interactive.resolve("auto") is (not interactive.is_interactive())


def test_resolve_policy_rejects_garbage():
    with pytest.raises(ValueError):
        interactive.resolve("sometimes")


def test_registry_resolves_moc_lazily():
    assert "moc" in registry.available()
    from mom6_tools.moc import MOC
    assert registry.get_diagnostic("moc") is MOC


def test_registry_unknown_raises():
    with pytest.raises(KeyError):
        registry.get_diagnostic("does_not_exist")


def test_diagnostic_run_returns_result(case):
    registry.register("dummy", f"{__name__}:_Dummy")
    result = case.dummy(plot=False, save=False, scale=2.0)
    np.testing.assert_array_equal(result.values, np.arange(4.0) * 2.0)


def test_run_applies_plot_and_save_policy(case):
    registry.register("dummy", f"{__name__}:_Dummy")
    case.dummy(plot=True, save=False)
    assert case._plotted and not case._saved


def test_run_all_collects_results(case):
    registry.register("dummy", f"{__name__}:_Dummy")
    results = case.run_all(only=["dummy"], plot=False, save=False, scale=3.0)
    assert set(results) == {"dummy"}
    np.testing.assert_array_equal(results["dummy"].values, np.arange(4.0) * 3.0)


def test_unknown_diagnostic_attribute_raises(case):
    with pytest.raises(AttributeError):
        case.no_such_diagnostic
