# mom6-tools OO refactor — status & resume notes

_Last updated: 2026-06-04. This is a working/handoff document, not part of the package.
Delete it (or move it under `docs/`) once the refactor settles._

## Known dev-time caveats (fix before any real publish)

- **`setup.py` packaging is stale for the new subpackage.** `packages=['mom6_tools']` does
  NOT include `mom6_tools.core`, so a built wheel/sdist would omit it and
  `import mom6_tools` (which imports `Case` from `mom6_tools.core`) would fail for a
  non-editable install. Editable installs (`pip install -e .`, the dev/conda path) hide
  this. There is a live `.github/workflows/pypipublish.yaml`. Fix with
  `from setuptools import find_packages; packages=find_packages(exclude=["tests*"])` before
  publishing. Deliberately deferred — still early dev.

## TL;DR

Refactoring `mom6-tools` from ~19 flat diagnostic scripts into a Case-centric,
object-oriented design **without breaking** the existing script CLIs, the
`diag_config.yml` contract, or the function imports that `cesm-mom6-diags` relies on.

- **Approved plan:** `/glade/u/home/ajanney/.claude/plans/i-want-to-refactor-tingly-lemur.md`
- **Phases 0–3: DONE and committed.** (mom6-diagtables package, DataSource data layer,
  Case + Diagnostic framework, `moc` migrated as the reference diagnostic.)
- **Phase 4: NOT STARTED** (was begun, then reverted to a clean state at user's request).
  Phase 4 = unified `mom6-diags` CLI + migrate `stats`. Detailed design is below.
- **Phase 5:** incremental migration of the remaining diagnostics (drift, surface, pht,
  transports, enso, TS_levels, …), one at a time.

Branch: `refactor-ideas`. Nothing pushed (local commits only, per the user).

## Design constraints to keep in mind (from the user)

1. **Backwards compatibility is strict.** Every `mom6_tools/<diag>.py` keeps its argparse
   signature + positional `diag_config.yml`. The reference consumer is
   `/glade/work/ajanney/Software/cesm-mom6-diags/` (its `scripts/*.sh` invoke the bare
   script names). Known invocations to preserve:
   - `moc.py diag_config.yml -nw 6`
   - `stats.py diag_config.yml -ocean_stats -time_series -nw 6`
   - `drift.py diag_config.yml thetao --drift -nw 12` (Phase 5)
2. **Three workflows:** (a) object/notebook use, (b) individual scripts/CLI,
   (c) one entry point that runs all diagnostics for a case.
3. **Primary design flavor:** *do not overcomplicate*. Prioritize readability,
   documentation, and human interaction. This is a straightforward application.
4. Prefer a **Case object that calls diagnostics and returns a mutable xarray result**;
   diagnostics auto-plot when non-interactive.

## Environment / how to run things

- Conda env is at `/glade/work/ajanney/conda-envs/mom6-tools` (NOT `~/.conda/envs`).
  - Python: `/glade/work/ajanney/conda-envs/mom6-tools/bin/python`
  - Tests: `/glade/work/ajanney/conda-envs/mom6-tools/bin/python -m pytest tests/ packages/mom6-diagtables -q`
  - The bare `python3` on PATH is the system Casper Python and lacks the deps.
- Current test status: **51 passed** (22 legacy + 7 datasource + 8 framework + 14 diagtables).
- Real carib history files (for smoke tests) live at:
  `/glade/derecho/scratch/ajanney/archive/carib12_tides_runoff_test_mom6_tools/ocn/hist`

## What exists now (Phases 0–3)

### Layer 1 — `packages/mom6-diagtables/` (standalone, no mom6-tools dep)
Parses MOM6/FMS `diag_table` files into typed objects. Installed editable via
`environment.yml`. Has its own `pyproject.toml`, `src/` layout, CLI, and 14 tests.
- `parse_diag_table(path) -> DiagTable` (+ `parse_diag_table_string`)
- `models.py`: `DiagFile`, `DiagField`, `DiagTable` (+ `.streams()`, `.fields_for()`,
  `.prefix_for_field()`, etc.)
- `prefix.py`: `stream_from_prefix`, `prefix_to_regex`, `prefix_to_glob`
- `writer.py`: stub for future diag_table *generation* (NotImplementedError)
- CLI: `mom6-diagtables inspect|validate <path>`

### Layer 2 — `mom6_tools/core/` data layer
- **`datasource.py` — `DataSource`**: resolves a source to a uniform `{stream -> dataset}`.
  Adapters: `from_config(yml)`, `from_diag_table(path, outdir=)`, `from_files(**streams)`.
  - `open(stream, variables=None, parallel=False, fill_missing=True, time_slice=False)`
    — the shared replacement for each script's `preprocess()` (select vars, fill missing
    with `zeros_like` a present requested var, optional time slice).
  - `grid(xrformat=False)` — wraps `MOM6grid(static, geom?)`.
  - Internals: `_spec`, `_abspath`, `_paths`, `_single_path`.
  - **Decision (kept):** `from_config` interprets `DOUT_S` as a real boolean
    (`TRUE/1/YES/ON`). Legacy scripts test `if DOUT_S:` on the raw xmlquery string, which
    is truthy even for `"FALSE\n"`, so they always took the archive branch. User said keep
    the corrected behavior; noted in the Phase 2 commit.
- **`cluster.py` — `Cluster`**: context manager wrapping `m6toolbox.request_workers`
  (`with Cluster(nw) as cl: ... cl.parallel`).

### Layer 3 — `mom6_tools/core/` diagnostic framework
- **`base.py` — `Diagnostic`**: `compute`/`plot`/`save` + default `run(plot, save, **kw)`
  that applies the policy and returns the result. Declares `name` and `requires`.
- **`registry.py`**: lazy `name -> "module:Class"`. Currently `{"moc": "mom6_tools.moc:MOC"}`.
  `register`, `get_diagnostic`, `is_registered`, `available`.
- **`interactive.py`**: `is_interactive()` + `resolve(value)` for `True/False/"auto"/None`
  (`"auto"` -> `not is_interactive()`).
- **`case.py` — `Case`**: `from_config`/`from_diag_table`/`from_files`, properties
  `casename`/`config`, `diagnostic(name)`, `run_all(only=, exclude=, **kw)`, and
  `__getattr__` so `case.<registered_name>(...)` dispatches to that diagnostic's `run`.
- `from mom6_tools import Case` works (added to `mom6_tools/__init__.py`).

### Reference migration — `moc.py`
- `class MOC(Diagnostic)` + module-level engine `_compute_moc(case, sd, ed, parallel,
  savefigs, outdir, debug)` = the **original body verbatim**, with two changes only:
  data access goes through `case.source.grid()` / `case.source.open('z', [...])`, and the
  matplotlib + intake-catalog blocks are gated by `if savefigs:`. The numeric/streamfunction
  code (`MOCpsi`, `findExtrema*`, `plotPsi`) is untouched.
- `main()` is now a thin shim: `Case.from_config(...).moc(plot=True, save=True)`. CLI is
  byte-identical (`options()` unchanged).
- `MOC.run(start_date, end_date, nw, plot, save, outdir, ncdir, debug)` does cluster +
  engine + NetCDF write. `MOC.compute(...)` = `run(plot=False, save=False)`.
- **Verified:** imports clean, `moc.py -h` unchanged, registry resolves `moc -> MOC`,
  51 tests pass. Compute-only smoke test on real carib data ran through grid/open/annual-
  mean/time-mean/MOCpsi and stopped at the **verbatim** line
  `yyg = grd.geolat_c.max(-1)+0*zg` — a *pre-existing* moc.py assumption that grids are
  NON-symmetric (corner J == center J); carib is symmetric (J+1). Not a regression
  (original never ran on carib). Left unchanged (fixing would change global-grid behavior).

### Known minor behavior deltas introduced (all output-neutral), documented in commits
- `Cluster` uses `request_workers`: a dask cluster is created for `nw>0` (old `moc` used
  `nw>1`) and the project is hardcoded `NCGD0011` (old `moc` used `NCARCluster()` with the
  default project). Same NetCDF/PNG output; only the worker threshold and charged account
  differ.

### Commits on `refactor-ideas` (local only)
- `e029fff` Add mom6-diagtables standalone package (phase 0/1) — also contains the
  `prefix_to_glob` addition (it was staged with `packages/`).
- `ba00c6e` Add DataSource data layer and Cluster helper (phase 2).
- `e7ff5e0` Add Case facade + Diagnostic base; migrate moc (phase 3).

### Deliberately uncommitted / excluded
- `test.py` (repo root) — the user's scratch sketch of a *future* API
  (`init_domain(...)`, `case.surface(...)`). Aspirational, not implemented.
- `mom6_tools/carib12_tides_runoff_test_mom6_tools/` — generated batch output (job logs).

---

## Phase 4 — detailed plan (resume here)

**Goal:** (A) a unified `mom6-diags` CLI; (B) migrate `stats` as the second reference,
demonstrating the feature-flag / basin-mask shape — *conservatively*, by reusing
`stats.py`'s existing engine functions rather than rewriting them.

### Why conservative for stats
`stats.py` already has clean engine functions and unit-tested reductions, and its CLI is
heavily used by `cesm-mom6-diags`. So: **do NOT touch `stats.py`'s `main()`, `options()`,
the reduction functions, or the engines' internals.** Add a thin OO layer over them and
register it. (This differs from `moc`, where `main()` became a shim — that's fine and
should be noted; backwards-compat safety wins for the busiest script.)

### Step A — `mom6_tools/cli.py` (the `mom6-diags` entry point)
A small argparse CLI dispatching through the registry → Case → diagnostic.

Subcommands:
- `mom6-diags list` — print `registry.available()`.
- `mom6-diags run <name> <diag_config.yml> [-sd -ed -nw --no-plot --no-save]` —
  `Case.from_config(config, sd, ed).<name>(nw=, plot=, save=)`.
- `mom6-diags run-all <diag_config.yml> [--only a,b] [--exclude c] [-sd -ed -nw ...]` —
  `case.run_all(only=, exclude=, nw=, plot=, save=)`.

`--no-plot`/`--no-save` map to `plot=False`/`save=False`; default leave as `"auto"`
(which resolves to True under the CLI since it's non-interactive). Add
`def main(argv=None)` and `if __name__ == "__main__": sys.exit(main())`.

**Packaging:** add to `setup.py` (currently has NO entry_points):
```python
entry_points={"console_scripts": ["mom6-diags = mom6_tools.cli:main"]},
```
Then re-install so the script appears:
`/glade/work/ajanney/conda-envs/mom6-tools/bin/python -m pip install -e . --no-deps`
(Until reinstalled, test via `python -m mom6_tools.cli ...`.)

### Step B — migrate `stats` (reuse engines)

1. **Re-apply the two reverted prep edits** (they were clean; reverted only to keep the
   tree tidy while pausing):
   - `DataSource`: add `caseroot=None, rundir=None` params in `__init__` (store as
     `self.caseroot`, `self.rundir`), and in `from_config` compute
     `rundir = cime_xmlquery(caseroot, "RUNDIR").strip()` and pass both through.
     (The stats `ocean_stats` engine reads `args.rundir/ocean.stats` and re-queries
     `RUN_STARTDATE` from `args.caseroot`.)
   - `stats.py::xystats`: add `results = {}` before the var loop, `results[var] = stats`
     inside it, and `return results` at the end (replacing the bare `return`). `main()`
     ignores the return, so this is behavior-neutral; it lets `case.surface(...)` return
     data.

2. **Add an args adapter** in `stats.py` so the engines (which expect an `args` object)
   can be driven from a `Case`:
   ```python
   from types import SimpleNamespace
   from mom6_tools.core import Diagnostic

   def _legacy_args(case, *, nw=0, start_date=None, end_date=None, debug=False):
       src, cfg = case.source, (case.config or {})
       return SimpleNamespace(
           casename = src.casename or "",
           OUTDIR   = src.outdir,
           rundir   = src.rundir,
           caseroot = src.caseroot,
           nw       = nw,
           start_date = start_date or src.start_date,
           end_date   = end_date or src.end_date,
           native = src.streams.get("native"),
           static = src.streams.get("static"),
           geom   = src.streams.get("geom"),
           debug  = debug,
       )

   def _grid_and_basins(case):
       # mirrors stats.main() lines ~417-440
       grd = case.source.grid(xrformat=True)
       try:    area = grd.area_t.where(grd.wet > 0)
       except: area = grd.areacello.where(grd.wet > 0)
       try:    depth = grd.depth_ocean.values
       except: depth = grd.deptho.values
       depth[np.isnan(depth)] = 0.0
       basin_code = genBasinMasks(grd.geolon.values, grd.geolat.values, depth, xda=True)
       basins = basin_code.isel(region=[0,4,5,6,7,8,9,10,11,12,13])
       return grd, area, basins
   ```

3. **Add four diagnostic wrappers** in `stats.py`, each overriding `run` (engines do
   compute+plot+save together, like MOC). Ensure `PNG/` and `ncfiles/` exist
   (`os.makedirs(..., exist_ok=True)`), build `args`, call the engine, return its result.
   - `OceanStats(name="ocean_stats")` → `return ocean_stats(args)` (needs no grid).
   - `TimeSeries(name="time_series")` → `grd, area, _ = _grid_and_basins(case);
     return extract_time_series(args.native, ["thetaoga","soga","opottempmint","somint"], area, args)`
   - `Surface(name="surface")` → `grd, _, basins = _grid_and_basins(case);
     return xystats(args.native, ["SSH","tos","sos","mlotst","oml","speed"], grd, basins, args)`
   - `Forcing(name="forcing")` → `grd, _, basins = _grid_and_basins(case);
     return xystats(args.native, ["friver","ficeberg","fsitherm","hfsnthermds","sfdsi",
     "hflso","seaice_melt_heat","wfo","hfds","Heat_PmE"], grd, basins, args)`

   Variable lists are copied verbatim from `stats.main()` (lines ~447, ~451, ~456).
   Each `run` signature: `run(self, *, nw=0, start_date=None, end_date=None, debug=False,
   plot="auto", save="auto")`. The stats engines always write outputs; `plot`/`save` are
   accepted for API uniformity — note this in the docstring (a future deeper refactor can
   make them honor the policy; keep it simple now).

4. **Register** in `registry.py`:
   ```python
   "ocean_stats": "mom6_tools.stats:OceanStats",
   "time_series": "mom6_tools.stats:TimeSeries",
   "surface":     "mom6_tools.stats:Surface",
   "forcing":     "mom6_tools.stats:Forcing",
   ```

5. **Leave `stats.py::main()` untouched.** Two code paths (legacy CLI vs OO) will share
   the engines — acceptable and intentional for the busiest script. Note this in the
   commit. (Optional later: make `main()` a shim once confident.)

### Caveats for Phase 4 / things to verify
- The stats engines use `args.OUTDIR + '/' + fname` + `open_mfdataset`, so the OO wrappers
  only work for **path-based sources (`from_config`)**, not `from_files(...=Dataset)` or
  `from_diag_table`. Document this; it's fine for the primary workflow.
- `surface`/`forcing` need an `sfc`/`native` stream with 2D fields; on the carib case the
  native stream exists, so a compute-only smoke test should be possible. `ocean_stats`
  needs `RUNDIR/ocean.stats` (a text file) + `ocean.stats.nc` — may not exist for carib;
  check before smoke-testing.
- `run_all` will now include moc + the 4 stats features; on a regional case moc will hit
  the symmetric-grid issue — consider `case.run_all(exclude=["moc"])` for carib testing.

### Tests to add (Phase 4)
`tests/test_cli.py` and extend `tests/test_diagnostics.py`:
- `mom6-diags list` includes the registered names.
- CLI arg parsing maps `--no-plot/--no-save` correctly (can monkeypatch
  `Case.from_config` to a fake returning a dummy case, asserting dispatch + kwargs).
- registry resolves the 4 stats names to their classes (lazy import).
- These stay pure-python (no HPC/dask), like the existing framework tests.

---

## Phase 5 — remaining diagnostics (later)
Migrate one per PR, each keeping its CLI as a shim (moc pattern) or reusing engines (stats
pattern), registering in `registry.py`. Candidates and their streams:
`drift` (z), `surface.py`, `poleward_heat_transport` (z + static), `section_transports`
(native/sections), `enso`, `TS_levels`, `aaiw_pv`, `equatorial_*`. Keep
notebook-imported functions importable at their current paths.

## Pointers
- Memory: `/glade/u/home/ajanney/.claude/projects/-glade-work-ajanney-Software-mom6-tools/memory/oo-refactor.md`
- Usage/testing guide for the user: `REFACTOR_USAGE.md` (same dir as this file).
