# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

`mom6-tools` is a collection of Python scripts and utilities for analyzing CESM/MOM6 ocean model output. It is built to run on NCAR HPC (Casper/Derecho) against large NetCDF history files, using `xarray` + `dask` and NCAR's PBS/dask-jobqueue cluster integration.

## Environment & install

```bash
conda env create --file environment.yml   # creates the `mom6-tools` env, installs the package editable (`pip install -e .`)
conda activate mom6-tools
```

Python 3.11. The package is `mom6_tools` (underscore); the distribution is `mom6-tools` (hyphen). Version comes from `setuptools_scm` (git tags) via `importlib.metadata`, so an editable install in a non-tagged checkout reports `__version__ = None`.

The `mom6-tools` conda env lives at `/glade/work/ajanney/conda-envs/mom6-tools` (not `~/.conda/envs`). Run its interpreter directly, e.g. `/glade/work/ajanney/conda-envs/mom6-tools/bin/python -m pytest`; the bare `python3` on PATH is the system Casper Python and lacks the project deps.

Two dependency lists must be kept in sync when adding packages: `environment.yml` (conda, authoritative for the dev env) and `requirements.txt` (used by CI and `setup.py`). Some deps install only from git: `momlevel`, `xwavelet`. HPC clusters use `dask-jobqueue` directly (conda-forge), not the former `ncar-jobqueue` wrapper.

### packages/ — in-repo subpackages

`packages/mom6-diagtables/` is a standalone, independently-installable package (its own `pyproject.toml`, `src/` layout, tests) for parsing MOM6/FMS `diag_table` files into typed objects (`parse_diag_table()` → `DiagTable`/`DiagFile`/`DiagField`). It has **no dependency on mom6-tools** and can be used on its own; `environment.yml` installs it editable (`-e ./packages/mom6-diagtables`). Test it with `python -m pytest packages/mom6-diagtables`. This is part of the ongoing object-oriented refactor (see the plan referenced in memory).

## Tests

```bash
pytest                              # all tests
pytest tests/test_horizontal_mean.py
pytest tests/test_horizontal_mean.py::test_case1   # single test
```

CI (`.github/workflows/python-tests.yml`) runs `pytest --maxfail=1 --disable-warnings -v` on push/PR to `main`. Tests are pure-numeric unit tests of reduction functions (`mom6_tools.stats.myStats_da`, `mom6_tools.drift.HorizontalMean*`) built on small hand-constructed `xarray.DataArray`s — they do **not** touch real model files, dask, or the cluster. New analysis logic should be factored so its core reduction is unit-testable the same way (operate on a `DataArray` with `yh`/`xh`/`z_l`/`time` dims and an optional `weights` area array and `basins` region mask).

## Architecture

The repo is a flat set of **standalone analysis scripts** in `mom6_tools/`, each one both an importable module and a CLI entry point (`python <script>.py <diag_config.yml> [opts]`). There is no single application — each script computes and plots one diagnostic (MOC, poleward heat transport, surface fields, T/S drift & RMS, sections/transports, ENSO, equatorial metrics, etc.). The README instructs users to put `mom6_tools/` on `$PATH` so scripts run by bare name.

### The standard script pattern

Every analysis script follows the same shape — match it when adding one:

1. `options()` (a few use `parseCommandLine()`) builds an `argparse` parser whose **first positional arg is always the path to a `diag_config.yml`**. Common flags: `-sd/--start_date`, `-ed/--end_date`, `-nw/--number_of_workers`.
2. `main()` loads the yaml, resolves the case, spins up a dask cluster if `-nw > 0`, computes, writes NetCDF to `ncfiles/` and PNGs to `PNG/<DIAG>/`, then tears the cluster down.
3. `if __name__ == '__main__':` calls `main()`.

`main()` is sometimes defined as `main(stream=False)` so the script can also be driven from a notebook.

### Config: `diag_config.yml`

The yaml is the single source of truth tying a run to its files. Structure (see `mom6_tools/.../diag_config.yml` and `docs/source/examples/diag_config.yml`):

- `Case:` — `CASEROOT` + `CIMEROOT` (CESM case dirs), `SNAME`, `OCN_DIAG_ROOT`.
- `Avg:` — default `start_date`/`end_date` for averaging (CLI flags override).
- `Fnames:` — glob suffixes per MOM6 stream (`z`, `rho2`, `native`, `sfc`, `static`, `geom`); filenames are built as `casename + suffix`.

Scripts resolve the actual run directory and casename from CESM at runtime via `cime_xmlquery(caseroot, varname)` in `m6toolbox.py` (shells out to CESM's `xmlquery`) — querying `CASE`, `DOUT_S`, `DOUT_S_ROOT`, `RUNDIR`. When short-term archiving (`DOUT_S`) is on, data lives in `DOUT_S_ROOT/ocn/hist/`, otherwise in `RUNDIR`. New scripts should use this same resolution rather than hardcoding paths.

`DiagsCase.py` is the older, richer case manager: it parses the CESM `diag_table` directly (`_parse_diag_table`), maps fields→file prefixes, and builds datasets with `stage_dset(fields)`. Newer scripts lean on `cime_xmlquery` + yaml `Fnames` globs instead, but `DiagsCase` is still used (e.g. by `create_cesm_diagnostic.py`).

### Cluster / parallelism

dask parallelism is gated by `-nw`. `m6toolbox.get_cluster(scheduler='pbs', account=..., ...)` is the single factory that builds a `dask_jobqueue` cluster (PBS by default; `'slurm'`/`'sge'`/`'lsf'` also supported via the `scheduler=` arg). `account` is **required** — pass it explicitly or set the `PBS_ACCOUNT` env var; there is no default (jobs bill a real allocation), and a missing account raises `ValueError`. `m6toolbox.request_workers(nw, scheduler='pbs', **kw)` is the shared helper: for `nw > 0` it calls `get_cluster`, scales it, and returns `(parallel, cluster, client)`; for `nw == 0` (or if dask/dask_jobqueue can't be imported) it runs serially. The standalone scripts construct a cluster inline via `get_cluster()` (replacing the former bare `NCARCluster()`); the OO path uses `diagnostics.Cluster(nw, scheduler=..., **kw)`. Worker-job defaults target NCAR Casper PBS (`cores=1, memory='25GB', queue='casper'`); override as needed. `interface` is unset by default (login nodes may lack `ib0`, and the interface is also bound by the local scheduler) — pass `interface='ib0'` when running where InfiniBand exists. This replaces the former `ncar-jobqueue`/`NCARCluster` dependency — no `~/.config/dask/ncar-jobqueue.yaml` is required, though `dask_jobqueue` still honours `~/.config/dask/jobqueue.yaml` for any unset options.

### Shared utility modules (not CLI scripts)

- `m6toolbox.py` — the grab-bag toolbox: CESM/xml helpers (`cime_xmlquery`), dataset filtering (`filter_vars`), time-weighted means (`weighted_temporal_mean*`), basin masks (`genBasinMasks`), grid/section geometry (`section2quadmesh`, `geoslice`, `mom6_latlon2ij`), MOC math (`MOCpsi`), EOS (`rho_Wright97`).
- `MOM6grid.py` — `MOM6grid(grd_file, geom_file, xrformat)` loads the static/geometry grid; `xrformat=True` returns an xarray Dataset, otherwise a numpy-attribute object.
- `stats.py` — weighted `*_da` reductions (`min/max/mean/std/rms`), `myStats_da`, plus its own `main()` for ocean stats / time series.
- `m6plot.py` — plotting helpers used across scripts.
- `MOM6grid`/`stats`/`drift` reductions take `dims=('yh','xh')`, optional `weights` (cell area), and optional `basins` (region mask DataArray with a `region` coord) — this signature is the common contract for horizontal reductions.

### Orchestration / batch generation

`create_cesm_diagnostic.py <caseroot> <shortname>` scaffolds a per-case directory containing `diag_config.yml`, one PBS batch script per diagnostic under `scripts/`, and a `run_scripts.sh` that `qsub`s them all. The generated `scripts/*.sh` activate a conda env, `cd` into `mom6_tools/`, and run the analysis scripts — this is the intended production workflow on HPC. `create_mom6_tools.py` is a related generator. The committed `mom6_tools/carib12_tides_runoff_test_mom6_tools/` directory is an example of this generated output (a regional test case).

### Docs & notebooks

`docs/source/examples/*.ipynb` are the user-facing usage examples (also rendered on readthedocs via `jupyter-book`/`nbsphinx`). `mom6_tools/nb_templates/{climo,ts}.ipynb` are parameterized notebook templates. `ClimoGenerator.py` generates climatologies and is consumed by `drift.py`, `diff_rms.py`, `compute_basin_reductions.py`.

## Conventions

- Style is configured in `setup.cfg`: `flake8` max-line-length 100 (with a permissive ignore list), `isort` with `mom6_tools` as first-party. There is no pre-commit hook wired up; formatting is not enforced in CI.
- Indentation in this codebase is inconsistent (mix of 2-space and 4-space across files). Match the surrounding file rather than imposing a global style.
- Scripts write outputs relative to the current working directory (`PNG/`, `ncfiles/`, `output/`) and `os.makedirs(..., exist_ok=True)` them in `main()`.
