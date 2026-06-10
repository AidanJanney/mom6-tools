# Migration: ncar-jobqueue → dask-jobqueue

_Date: 2026-06-10. Records the removal of `ncar-jobqueue`/`NCARCluster` and its
replacement with `dask-jobqueue`._

## Why

`ncar-jobqueue` wrapped `dask-jobqueue`, auto-detecting the NCAR machine and pulling
worker-job defaults from `~/.config/dask/ncar-jobqueue.yaml`. We removed that layer of
indirection and now build a `dask-jobqueue` cluster directly, with PBS as the default and
an explicit option to select another scheduler.

## The new entry point — `m6toolbox.get_cluster`

A single factory replaces every `NCARCluster()` construction
(`mom6_tools/m6toolbox.py`):

```python
def get_cluster(scheduler='pbs', account='NCGD0011', cores=1, processes=1,
                memory='25GB', walltime='01:00:00', queue='casper',
                interface=None, **kwargs):
    ...
    import dask_jobqueue
    cluster_cls = getattr(dask_jobqueue, _SCHEDULERS[scheduler.lower()])
    return cluster_cls(account=account, cores=cores, processes=processes, memory=memory,
                       walltime=walltime, queue=queue, interface=interface, **kwargs)
```

- **PBS is the default.** `scheduler=` selects the cluster type via the module-level map
  `_SCHEDULERS = {'pbs': 'PBSCluster', 'slurm': 'SLURMCluster', 'sge': 'SGECluster',
  'lsf': 'LSFCluster'}`. An unknown scheduler raises `ValueError`.
- **Defaults mirror the old NCAR Casper PBS config** (`cores=1`, `memory='25GB'`,
  `queue='casper'`, `walltime='01:00:00'`, `account='NCGD0011'`).
- **`interface` defaults to `None`, not `'ib0'`.** `dask-jobqueue` binds the interface on
  the *local scheduler* as well as the workers, and login nodes may not expose `ib0`
  (observed: a Casper login node only had `lo`/`mgt`/`ext`). Pass `interface='ib0'`
  explicitly when running where InfiniBand exists.
- `**kwargs` pass straight through to the underlying `dask-jobqueue` constructor.

## Specific code changes

### Core helper — `mom6_tools/m6toolbox.py`
- Added `_SCHEDULERS` map and the `get_cluster(...)` factory.
- `request_workers(nw)` → `request_workers(nw, scheduler='pbs', **cluster_kwargs)`:
  - Removed `from ncar_jobqueue import NCARCluster`.
  - Removed `cluster = NCARCluster(project='NCGD0011')`; now `cluster =
    get_cluster(scheduler=scheduler, **cluster_kwargs)`.
  - Narrowed the import guard from `except:` to `except ImportError:` and dropped
    `ncar_jobqueue` from the warning text.

### OO path — `mom6_tools/diagnostics/cluster.py`
- `Cluster.__init__(self, nw=0)` → `Cluster.__init__(self, nw=0, scheduler='pbs',
  **cluster_kwargs)`; `start()` forwards them to `request_workers`.
- Docstrings updated from `NCARCluster` to dask-jobqueue wording.

### Standalone scripts (inline `cluster = NCARCluster()`)
Each had its import line `from ncar_jobqueue import NCARCluster` replaced with
`from mom6_tools.m6toolbox import get_cluster`, and `NCARCluster()` replaced with
`get_cluster()` (the surrounding `cluster.scale(...)`, `Client(cluster)`, and
`client.close(); cluster.close()` lines are unchanged):

`stats.py` (×2), `surface.py`, `drift.py`, `enso.py`, `forcing.py`,
`tao_mooring_comparison.py`, `moc_sigma2.py`, `bouyancy_flux.py`, `wind_stress.py`,
`aaiw_pv.py`, `section_transports.py`, `diff_rms.py`, `poleward_heat_transport.py`,
`equatorial_comparison.py`, `TS_levels.py`.

### Scripts with a dangling import only (no construction)
Removed the unused `from ncar_jobqueue import NCARCluster` line:
`moc.py`, `compute_basin_reductions.py`, `create_climatology.py`.

### Example notebooks (`docs/source/examples/*.ipynb`)
Source-cell replacements:
- `from ncar_jobqueue import NCARCluster` → `from mom6_tools.m6toolbox import get_cluster`
- `import ncar_jobqueue` → `from mom6_tools import m6toolbox`
- `ncar_jobqueue.NCARCluster(` → `m6toolbox.get_cluster(`
- `NCARCluster(` → `get_cluster(`

Affected: `EquatorialOceanMetrics`, `Equatorial_comparison`, `TS_drift`, `TS_levels`,
`aaiw_pv`, `close_tracer_budgets`, `combining-tiles`, `diags_case`, `enso`,
`meridional_overturning`, `poleward_heat_transport`, `seaice`, `surface`,
`velocity_levels`. In `case_workflow_demo.ipynb` a stale traceback output that referenced
`NCARCluster` was cleared.

### Dependency manifests
- `requirements.txt`: `ncar_jobqueue @ git+https://github.com/NCAR/ncar-jobqueue` →
  `dask-jobqueue`.
- `environment.yml`: added conda dep `- dask-jobqueue`; removed the pip
  `ncar-jobqueue @ git+...` line.
- `ci/travis-conda-environment.yml`: added conda `- dask-jobqueue`; removed pip
  `ncar_jobqueue`.
- `CLAUDE.md`: updated the "Cluster / parallelism" and dependency sections.

## Caveats / behavior changes

- The standalone scripts previously called the bare `NCARCluster()`, which read the
  account from `ncar-jobqueue.yaml` (often `P93300012`). They now use `get_cluster()`'s
  default `account='NCGD0011'` — the same account the central `request_workers` already
  hardcoded. Override `account=` if you charge to a different project.
- No `~/.config/dask/ncar-jobqueue.yaml` is needed anymore. `dask-jobqueue` still honours
  `~/.config/dask/jobqueue.yaml` for any options left unset.

## Verification

```bash
/glade/work/ajanney/conda-envs/mom6-tools/bin/python -m pytest tests/ packages/mom6-diagtables -q
```

- 72 passed (the two `ncar_jobqueue` pkg_resources deprecation warnings are gone).
- `get_cluster()` constructs a real `PBSCluster`; its `job_script()` contains the expected
  directives: `#PBS -q casper`, `#PBS -A NCGD0011`,
  `#PBS -l select=1:ncpus=1:mem=24GB`, `#PBS -l walltime=01:00:00`.
- `grep -rn "ncar_jobqueue\|NCARCluster"` across the tree returns only documentation
  references (this file, `CLAUDE.md`, the explanatory comments in `m6toolbox.py`, and a
  historical note in `REFACTOR_STATUS.md`) — no live code uses remain.
