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

    The first six attributes are required by the diag_table format; the rest are optional
    and control when a new physical file is started.
    """

    file_name: str
    output_freq: int
    output_freq_units: str
    file_format: int
    time_axis_units: str
    time_axis_name: str
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
    """

    module_name: str
    field_name: str
    output_name: str
    file_name: str
    time_sampling: str
    reduction_method: str
    regional_section: str
    packing: int


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

    def streams(self) -> Dict[str, DiagFile]:
        """Map each stream name to its :class:`DiagFile`.

        If two files share a stream name (unusual) the last one wins.
        """
        return {f.stream: f for f in self.files}

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
