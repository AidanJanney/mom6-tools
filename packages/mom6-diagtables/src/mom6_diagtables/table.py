"""Typed representations of the contents of a MOM6/FMS diag_table.

A diag_table has two header lines (a title and a base date) followed by two sections:
a *file list* and a *field list*.  Those map onto :class:`DiagFile` and :class:`DiagField`
here, and the whole table is held by :class:`DiagTable`.

See the MOM6 documentation for the authoritative format description:
https://mom6.readthedocs.io/en/main/api/generated/pages/Diagnostics.html
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .prefix import stream_from_prefix

__all__ = ["DiagFile", "DiagField", "DiagTable"]


@dataclass
class DiagFile:
    """One output-file definition from the file-list section.

    ``file_name``, ``output_freq``, ``output_freq_units``, ``time_axis_units``, and
    ``time_axis_name`` are required.  ``file_format`` has a default of 1 (netCDF) because
    the YAML format does not include it.  The remaining attributes are optional and control
    when a new physical file is started.
    """

    file_name: str
    output_freq: int
    output_freq_units: str
    time_axis_units: str
    time_axis_name: str
    file_format: int = 1
    new_file_freq: Optional[int] = None
    new_file_freq_units: Optional[str] = None
    start_time: Optional[str] = None
    file_duration: Optional[int] = None
    file_duration_units: Optional[str] = None

    @property
    def stream(self) -> str:
        """Short stream name (e.g. ``z``, ``native``, ``static``) from the file name."""
        return stream_from_prefix(self.file_name)


@dataclass
class DiagField:
    """One field definition from the field-list section.

    ``regional_section`` is ``"none"`` for global output or six space-separated numbers
    (``lon_min lon_max lat_min lat_max vert_min vert_max``) for a sub-domain.  Values are
    stored verbatim as strings; this class does not validate or restrict them.

    ``time_sampling`` and ``packing`` are optional because the YAML format omits them
    (``time_sampling`` was removed in the modern diag_manager; ``packing``/``kind`` may be
    inherited from the file level).
    """

    module_name: str
    field_name: str
    output_name: str
    file_name: str
    reduction_method: str
    regional_section: str = "none"
    time_sampling: str = "1"
    packing: Optional[int] = None


@dataclass
class DiagTable:
    """A parsed diag_table: the two header lines plus the file and field lists."""

    title: str
    base_date: List[int]
    files: List[DiagFile] = field(default_factory=list)
    fields: List[DiagField] = field(default_factory=list)

    # -- lookups -----------------------------------------------------------------

    def file_names(self) -> List[str]:
        """All output-file names, in table order."""
        return [f.file_name for f in self.files]

    def get_file(self, file_name: str) -> Optional[DiagFile]:
        """Return the :class:`DiagFile` with ``file_name``, or ``None`` if not present."""
        for f in self.files:
            if f.file_name == file_name:
                return f
        return None

    def streams(self) -> Dict[str, "DiagFile"]:
        """Map each stream name to its :class:`DiagFile` using :func:`stream_from_prefix`.

        Stream names are derived from the CESM ``<case>.mom6.h.<stream>`` convention.
        For non-standard naming conventions use :meth:`infer_streams` instead.

        If two files share a stream name (unusual) the last one wins.
        """
        return {f.stream: f for f in self.files}

    def infer_streams(self) -> Dict[str, "DiagFile"]:
        """Map each stream name to its :class:`DiagFile` using auto-detection.

        Finds the longest common prefix shared by all file names and strips it to
        produce stream names.  Works for both the CESM convention and non-standard
        conventions such as BGC output (e.g. ``ocean_cobalt_sfc``, ``ocean_cobalt_btm``
        → streams ``sfc``, ``btm``).  Falls back gracefully to the full base name when
        no common prefix is found.

        Use this instead of :meth:`streams` when the diag_table does not follow the
        ``.mom6.h.<stream>`` pattern.
        """
        from .prefix import infer_stream_names
        name_to_prefix = infer_stream_names([f.file_name for f in self.files])
        prefix_to_file = {f.file_name: f for f in self.files}
        return {stream: prefix_to_file[prefix] for stream, prefix in name_to_prefix.items()}

    def fields_for(self, file_name: str) -> List[DiagField]:
        """All fields written to ``file_name``."""
        return [fld for fld in self.fields if fld.file_name == file_name]

    def files_for_field(self, field_name: str) -> List[str]:
        """File names that contain ``field_name`` (matched against ``field_name`` or
        ``output_name``)."""
        names = []
        for fld in self.fields:
            if field_name in (fld.field_name, fld.output_name):
                names.append(fld.file_name)
        # Preserve order but drop duplicates.
        return list(dict.fromkeys(names))

    def prefix_for_field(self, field_name: str) -> str:
        """Return the single file prefix containing ``field_name``.

        Raises
        ------
        KeyError
            If the field is in no file, or in more than one file.
        """
        matches = self.files_for_field(field_name)
        if not matches:
            raise KeyError(f"Field {field_name!r} not found in diag_table")
        if len(matches) > 1:
            raise KeyError(
                f"Field {field_name!r} appears in multiple files: {matches}"
            )
        return matches[0]
