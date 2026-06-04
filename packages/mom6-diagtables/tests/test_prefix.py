"""Tests for stream-name and regex derivation from diag_table file prefixes."""

from mom6_diagtables import prefix_to_glob, prefix_to_regex, stream_from_prefix


def test_stream_from_prefix_with_date_placeholders():
    assert stream_from_prefix("case.mom6.h.z%4yr-%2mo") == "z"
    assert stream_from_prefix("case.mom6.h.native%4yr-%2mo") == "native"


def test_stream_from_prefix_static_has_no_placeholders():
    assert stream_from_prefix("case.mom6.h.static") == "static"


def test_stream_from_prefix_section_name_kept_whole():
    assert stream_from_prefix("case.mom6.h.Agulhas_Section%4yr-%2mo") == "Agulhas_Section"


def test_stream_from_prefix_without_marker_returns_prefix():
    assert stream_from_prefix("weird_name%4yr") == "weird_name"


def test_prefix_to_regex_year_month():
    assert prefix_to_regex("case.mom6.h.z%4yr-%2mo") == r"case.mom6.h.z_\d{4}_\d{2}.nc"


def test_prefix_to_regex_no_placeholders():
    assert prefix_to_regex("case.mom6.h.static") == "case.mom6.h.static.nc"


def test_prefix_to_glob_year_month():
    assert prefix_to_glob("case.mom6.h.z%4yr-%2mo") == "case.mom6.h.z*.nc"


def test_prefix_to_glob_no_placeholders():
    assert prefix_to_glob("case.mom6.h.static") == "case.mom6.h.static.nc"
