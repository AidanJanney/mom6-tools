# mom6-tools refactor — usage & testing guide

A hands-on guide to try out what's been built so far (Phases 0–3). Everything here is on
the `refactor-ideas` branch. **The legacy scripts are unchanged in behavior** — the new
object-oriented layer sits alongside them.

> What's available now: the `mom6-diagtables` package, the `Case` object with three
> constructors, and the **`moc`** diagnostic through `Case`.
> **Not yet built:** the unified `mom6-diags` CLI and the `stats` OO wrappers (Phase 4).

## 0. Setup

Use the project's conda Python directly (don't rely on the system `python3`):

```bash
PY=/glade/work/ajanney/conda-envs/mom6-tools/bin/python
```

## 1. Run the test suite

```bash
$PY -m pytest tests/ packages/mom6-diagtables -q
```
Expected: **51 passed**. (Legacy reductions, the data layer, the diagnostic framework,
and the diag_table parser.)

## 2. The standalone `mom6-diagtables` package

Works on its own, no mom6-tools needed. Two example tables live in `diag_tables/`.

CLI:
```bash
# summarize files / fields / streams
$PY -m mom6_diagtables.cli inspect diag_tables/diag_table_global
# or, if the console script is on PATH:
mom6-diagtables inspect diag_tables/diag_table_global
mom6-diagtables validate diag_tables/diag_table_regional_carib
```

Python:
```python
from mom6_diagtables import parse_diag_table
t = parse_diag_table("diag_tables/diag_table_global")
print(t.title, t.base_date)
print(t.streams().keys())              # z, native, rho2, sfc, static, ...
print(t.prefix_for_field("soga"))      # file prefix that holds 'soga'
```

## 3. The `Case` object — three ways to point at data

```python
from mom6_tools import Case

# (a) the current CESM workflow: a diag_config.yml (resolves the run dir via xmlquery)
case = Case.from_config("path/to/diag_config.yml")

# (b) parse a MOM6 diag_table; outdir defaults to the table's directory
case = Case.from_diag_table("diag_tables/diag_table_global",
                            outdir="/glade/.../ocn/hist")

# (c) point directly at files / globs / already-open datasets
case = Case.from_files(
    casename="mycase",
    outdir="/glade/.../ocn/hist",
    z="mycase.mom6.h.z.*.nc",
    static="mycase.mom6.h.static.nc",
    geom="mycase.mom6.h.ocean_geometry.nc",
    start_date="2000-01-01", end_date="2000-12-31",
)

print(case.casename)
case.source.streams            # dict of stream -> glob/list/Dataset
ds = case.source.open("z", variables=["vmo"])   # lazy xarray.Dataset
grd = case.source.grid()                         # MOM6 grid object
```

## 4. Run the `moc` diagnostic through `Case`

```python
# returns a mutable xarray.Dataset (sections + AMOC/ACC time series)
moc = case.moc(start_date="0052-01-01", end_date="0073-01-01", nw=6)

# notebook-friendly: data only, no figures / NetCDF
moc = case.moc(nw=0, plot=False, save=False)

# force file output even in a notebook
moc = case.moc(nw=6, plot=True, save=True)
```

Policy: `plot`/`save` accept `True` / `False` / `"auto"` (default). `"auto"` = act when
run **non-interactively** (script/CLI), skip when interactive (notebook/REPL). Outputs,
when enabled, are `PNG/MOC/*.png` and `ncfiles/<case>_MOC.nc` — same as before.

### Quick real-data smoke test (compute-only, no cluster/catalog)
The carib history files are at
`/glade/derecho/scratch/ajanney/archive/carib12_tides_runoff_test_mom6_tools/ocn/hist`.

```python
from mom6_tools import Case
H = "/glade/derecho/scratch/ajanney/archive/carib12_tides_runoff_test_mom6_tools/ocn/hist"
c = Case.from_files(
    casename="carib12_tides_runoff_test_mom6_tools", outdir=H,
    z="carib12_tides_runoff_test_mom6_tools.mom6.h.z.2000-??.nc",
    static="carib12_tides_runoff_test_mom6_tools.mom6.h.static.nc",
    geom="carib12_tides_runoff_test_mom6_tools.mom6.h.ocean_geometry.nc",
    start_date="2000-01-01", end_date="2000-12-31",
)
moc = c.moc(nw=0, plot=False, save=False)   # see note below
```
**Heads-up:** on the carib *regional* case this currently stops at
`yyg = grd.geolat_c.max(-1)+0*zg` (shape mismatch). That's a **pre-existing `moc.py`
limitation** — `moc.py` assumes non-symmetric grids (used by global CESM runs), while
carib uses symmetric memory (corner dim is one larger). It is **not** introduced by the
refactor (the same line exists verbatim in the original). On a global case it runs as
before. If you want, I can add symmetric-grid support as a separate, opt-in change.

## 5. The legacy CLIs still work unchanged

```bash
$PY mom6_tools/moc.py diag_config.yml -nw 6
$PY mom6_tools/stats.py diag_config.yml -ocean_stats -time_series -nw 6
```
`moc.py` now runs through the new engine internally but the command line, flags, and
output files are identical. `stats.py` is entirely untouched.

## 6. What to look for / how you can sanity-check

- **Parity of `moc`:** run `moc.py diag_config.yml -nw N` on a *global* case you've run
  before and diff `ncfiles/<case>_MOC.nc` against a previous run
  (`python -c "import xarray as xr; xr.testing.assert_allclose(xr.open_dataset(a), xr.open_dataset(b))"`).
- **Notebook ergonomics:** in Jupyter, `case.moc(plot=False, save=False)` should return a
  Dataset you can inspect/plot yourself; `"auto"` should *not* spray files.
- **Two minor, output-neutral deltas** vs. old `moc.py`: the shared cluster helper makes a
  dask cluster for `nw>0` (old moc: `nw>1`) and hardcodes project `NCGD0011` (old moc used
  the default project). Same NetCDF/PNG; only the worker threshold and the charged account
  differ. Tell me if you'd rather `moc` keep its old cluster behavior exactly.

## 7. Coming next (Phase 4, not yet built)

- `mom6-diags list` / `mom6-diags run <name> <config>` / `mom6-diags run-all <config>`
  (one entry point for all diagnostics).
- `case.surface(...)`, `case.forcing(...)`, `case.ocean_stats(...)`,
  `case.time_series(...)` reusing `stats.py`'s existing engines.

Feedback welcome on the `Case` API shape and the `plot/save="auto"` behavior before I wire
up the CLI and migrate more diagnostics.
