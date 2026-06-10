# Vendored FMS YAML tools — third-party, separately licensed

The files in this directory are **vendored verbatim** from the GFDL Flexible Modeling
System (FMS) YAML tools:

- `diag_table_to_yaml.py` — legacy ASCII → YAML diag_table converter
- `is_valid_diag_table_yaml.py` — YAML diag_table validator

Upstream: https://github.com/NOAA-GFDL/FMS (tools/diag_table)
Original author: Uriel Ramirez (2022).

## License — important

These files are licensed under the **GNU Lesser General Public License v3 (LGPL-3.0)**,
which is *different* from the rest of `mom6-diagtables` (Apache-2.0). They retain their
original LGPL headers and remain under LGPL-3.0; the Apache license of this package does
**not** apply to them. Keep the headers intact and preserve this notice when
redistributing.

Because of the license difference, these files are intentionally kept isolated in this
subdirectory, are **not imported** into the `mom6_diagtables` package API, and are only
invoked out-of-process (via `subprocess`) by the experimental `mom6-diagtables convert`
command. Removing this directory does not affect the parser/reader (the supported, pure
Apache-licensed functionality).

If diag_table generation becomes a first-class feature, prefer depending on an installed
`fms_yaml_tools` distribution (or a clean-room reimplementation) over vendoring.
