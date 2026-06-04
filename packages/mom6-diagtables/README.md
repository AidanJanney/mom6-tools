# mom6-diagtables

A small, dependency-free Python package for reading [MOM6](https://github.com/mom-ocean/MOM6)
/ FMS `diag_table` files into typed Python objects.

It is developed as part of [mom6-tools](https://github.com/NCAR/mom6-tools) but has **no
dependency on mom6-tools** (or xarray, or CESM) and can be installed and used on its own.

## Install

```bash
pip install -e packages/mom6-diagtables      # from a mom6-tools checkout
# or, once published / split into its own repo:
pip install mom6-diagtables
```

## Usage

```python
from mom6_diagtables import parse_diag_table

table = parse_diag_table("diag_table")

table.title                       # the title string from line 1
table.base_date                   # [1, 1, 1, 0, 0, 0]

for f in table.files:
    print(f.file_name, f.output_freq, f.output_freq_units, f.stream)

# Look things up:
table.streams()                   # {"z": DiagFile, "native": DiagFile, ...}
table.fields_for(some_file_name)  # [DiagField, ...]
table.prefix_for_field("thetao")  # the file prefix that contains 'thetao'
```

## Command line

```bash
mom6-diagtables inspect diag_table     # summarize files, fields, and streams
mom6-diagtables validate diag_table    # exit non-zero if the file cannot be parsed
```

## The diag_table format

A `diag_table` is a small text file with two header lines (a title and a base date),
followed by two comma-separated sections:

1. **File list** — one line per output file (prefix, frequency, units, format, ...).
2. **Field list** — one line per field (module, field name, output name, file prefix,
   time sampling, reduction method, regional section, packing).

Strings are double-quoted and may contain spaces (e.g. a regional section
`"20.1 20.1 -69.8 -34.6 -1 -1"`), so the file is parsed as comma-separated values rather
than by splitting on whitespace.

## Status

- [x] Parse `diag_table` files into `DiagTable` / `DiagFile` / `DiagField` objects.
- [ ] Generate / write `diag_table` files (see `writer.py` — not yet implemented).
