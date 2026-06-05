"""Parse a MOM6/FMS YAML diag_table into a :class:`~mom6_diagtables.table.DiagTable`.

The YAML format is the modern alternative to the legacy ASCII diag_table, introduced in
FMS as the diag_manager was updated.  The structure is::

    title: "experiment title"
    base_date: "1 1 1 0 0 0"   # or a YAML list [1, 1, 1, 0, 0, 0]
    diag_files:
      - file_name: case.mom6.h.z
        freq: 1
        freq_units: months
        time_units: days
        unlimdim: time
        varlist:
          - var_name: thetao
            module: ocean_model
            reduction: average
            kind: r4

Key differences from ASCII:

* ``file_format`` is absent (always netCDF4); ``DiagFile.file_format`` defaults to 1.
* ``time_sampling`` is absent (removed in the modern diag_manager);
  ``DiagField.time_sampling`` defaults to ``"1"``.
* Sub-regions are defined at the *file* level (``sub_region:`` block) rather than as a
  per-field string; they are encoded into ``DiagField.regional_section`` as a
  space-separated ``"lon_min lon_max lat_min lat_max z_min z_max"`` string matching the
  ASCII convention, or ``"none"`` when absent.
* ``packing`` / ``kind``: YAML uses ``r4`` / ``r8`` string tags at the variable level
  (optionally inherited from the file level).  These are converted to the integer packing
  codes used in ASCII (``r4`` → 2, ``r8`` → 1).  When ``kind`` is absent and not
  specified at the file level, ``DiagField.packing`` is ``None``.
"""

from typing import List, Optional

import yaml

from .table import DiagField, DiagFile, DiagTable

__all__ = ["parse_diag_table_yaml"]

_KIND_TO_PACKING = {"r4": 2, "r8": 1}


def parse_diag_table_yaml(path) -> DiagTable:
    """Parse the YAML diag_table at ``path`` and return a :class:`DiagTable`."""
    with open(path) as fh:
        raw = yaml.safe_load(fh)
    return _build_table(raw)


def _build_table(raw: dict) -> DiagTable:
    title = str(raw.get("title", ""))
    base_date = _parse_base_date(raw.get("base_date", "1 1 1 0 0 0"))

    files: List[DiagFile] = []
    fields: List[DiagField] = []

    for file_entry in raw.get("diag_files", []):
        dfile = _make_file(file_entry)
        files.append(dfile)
        file_kind = file_entry.get("kind")  # file-level default for packing
        sub_region = file_entry.get("sub_region")
        regional_section = _encode_sub_region(sub_region)
        for var_entry in file_entry.get("varlist", []):
            fields.append(_make_field(var_entry, dfile.file_name,
                                      regional_section, file_kind))

    return DiagTable(title=title, base_date=base_date, files=files, fields=fields)


def _parse_base_date(value) -> List[int]:
    """Accept either a YAML list ``[1, 1, 1, 0, 0, 0]`` or a string ``"1 1 1 0 0 0"``."""
    if isinstance(value, list):
        return [int(v) for v in value]
    return [int(v) for v in str(value).split()]


def _make_file(entry: dict) -> DiagFile:
    return DiagFile(
        file_name=entry["file_name"],
        output_freq=int(entry["freq"]),
        output_freq_units=entry["freq_units"],
        time_axis_units=entry["time_units"],
        time_axis_name=entry["unlimdim"],
        new_file_freq=_opt_int(entry, "new_file_freq"),
        new_file_freq_units=entry.get("new_file_freq_units"),
        start_time=_format_start_time(entry.get("start_time")),
        file_duration=_opt_int(entry, "file_duration"),
        file_duration_units=entry.get("file_duration_units"),
    )


def _make_field(entry: dict, file_name: str,
                regional_section: str, file_kind: Optional[str]) -> DiagField:
    var_name = entry["var_name"]
    kind = entry.get("kind", file_kind)
    return DiagField(
        module_name=entry["module"],
        field_name=var_name,
        output_name=entry.get("out_name", var_name),
        file_name=file_name,
        reduction_method=entry["reduction"],
        regional_section=regional_section,
        packing=_KIND_TO_PACKING.get(kind) if kind else None,
    )


def _opt_int(d: dict, key: str) -> Optional[int]:
    val = d.get(key)
    return int(val) if val is not None else None


def _format_start_time(value) -> Optional[str]:
    """Normalise a YAML start_time (list or string) to a space-separated string."""
    if value is None:
        return None
    if isinstance(value, list):
        return " ".join(str(v) for v in value)
    return str(value)


def _encode_sub_region(sub_region) -> str:
    """Convert a YAML ``sub_region`` block to the ASCII regional_section string.

    The ASCII format is ``"lon_min lon_max lat_min lat_max z_min z_max"``
    (six space-separated numbers, with ``-1`` meaning "full extent").

    The YAML format uses four corner points (each ``[lon, lat]``) and an optional
    ``zbounds`` pair.  Corner1 and corner3 carry the opposing corners of the bounding
    box (min and max), so::

        lon_min = corner1[0],  lat_min = corner1[1]
        lon_max = corner3[0],  lat_max = corner3[1]

    Returns ``"none"`` when no sub_region is defined.
    """
    if not sub_region:
        return "none"
    region = sub_region[0] if isinstance(sub_region, list) else sub_region
    grid_type = region.get("grid_type", "none")
    if not grid_type or grid_type == "none":
        return "none"

    def _pair(val):
        if isinstance(val, (list, tuple)):
            return float(val[0]), float(val[1])
        parts = str(val).split()
        return float(parts[0]), float(parts[1])

    c1 = region.get("corner1", [-999, -999])
    c3 = region.get("corner3", [-999, -999])
    zbounds = region.get("zbounds", [-1, -1])

    lon_min, lat_min = _pair(c1)
    lon_max, lat_max = _pair(c3)
    z_min, z_max = _pair(zbounds)
    return f"{lon_min} {lon_max} {lat_min} {lat_max} {z_min} {z_max}"
