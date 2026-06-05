"""Tests for stream-name and regex derivation from diag_table file prefixes."""

from mom6_diagtables import infer_stream_names, prefix_to_glob, prefix_to_regex, stream_from_prefix


def test_stream_from_prefix_with_date_placeholders():
    assert stream_from_prefix("case.mom6.h.z%4yr-%2mo") == "z"
    assert stream_from_prefix("case.mom6.h.native%4yr-%2mo") == "native"


def test_stream_from_prefix_static_has_no_placeholders():
    assert stream_from_prefix("case.mom6.h.static") == "static"


def test_stream_from_prefix_section_name_kept_whole():
    assert stream_from_prefix("case.mom6.h.Agulhas_Section%4yr-%2mo") == "Agulhas_Section"


def test_stream_from_prefix_without_marker_returns_prefix():
    assert stream_from_prefix("weird_name%4yr") == "weird_name"


def test_stream_from_prefix_custom_pattern():
    # Different model convention: extract stream after ".ocn.h."
    pattern = r"\.ocn\.h\.(?P<stream>[^%]+)"
    assert stream_from_prefix("case.ocn.h.z%4yr-%2mo", pattern=pattern) == "z"
    assert stream_from_prefix("case.ocn.h.static", pattern=pattern) == "static"


def test_stream_from_prefix_custom_pattern_no_match_falls_back():
    # Pattern does not match; fallback strips date placeholders from the whole prefix.
    pattern = r"\.ocn\.h\.(?P<stream>[^%]+)"
    assert stream_from_prefix("case.mom6.h.z%4yr-%2mo", pattern=pattern) == "case.mom6.h.z"


# -- infer_stream_names ----------------------------------------------------------

def test_infer_stream_names_cobalt_style():
    prefixes = [
        "ocean_cobalt_sfc",
        "ocean_cobalt_btm",
        "ocean_cobalt_tracers_int",
        "ocean_cobalt_fluxes_int",
        "ocean_cobalt_fdet_100",
        "ocean_cobalt_tracers_month_z",
        "ocean_cobalt_tracers_instant",
        "ocean_cobalt_daily_2d",
    ]
    result = infer_stream_names(prefixes)
    assert result == {
        "sfc": "ocean_cobalt_sfc",
        "btm": "ocean_cobalt_btm",
        "tracers_int": "ocean_cobalt_tracers_int",
        "fluxes_int": "ocean_cobalt_fluxes_int",
        "fdet_100": "ocean_cobalt_fdet_100",
        "tracers_month_z": "ocean_cobalt_tracers_month_z",
        "tracers_instant": "ocean_cobalt_tracers_instant",
        "daily_2d": "ocean_cobalt_daily_2d",
    }


def test_infer_stream_names_cesm_style_with_date_placeholders():
    prefixes = [
        "case.mom6.h.z%4yr-%2mo",
        "case.mom6.h.native%4yr-%2mo",
        "case.mom6.h.static",
    ]
    result = infer_stream_names(prefixes)
    assert result == {
        "z": "case.mom6.h.z%4yr-%2mo",
        "native": "case.mom6.h.native%4yr-%2mo",
        "static": "case.mom6.h.static",
    }


def test_infer_stream_names_single_prefix():
    # Single file: no peers to compare; base name is returned as-is.
    result = infer_stream_names(["ocean_cobalt_sfc"])
    assert result == {"ocean_cobalt_sfc": "ocean_cobalt_sfc"}


def test_infer_stream_names_empty():
    assert infer_stream_names([]) == {}


def test_prefix_to_regex_year_month():
    assert prefix_to_regex("case.mom6.h.z%4yr-%2mo") == r"case.mom6.h.z_\d{4}_\d{2}.nc"


def test_prefix_to_regex_no_placeholders():
    assert prefix_to_regex("case.mom6.h.static") == "case.mom6.h.static.nc"


def test_prefix_to_glob_year_month():
    assert prefix_to_glob("case.mom6.h.z%4yr-%2mo") == "case.mom6.h.z*.nc"


def test_prefix_to_glob_no_placeholders():
    assert prefix_to_glob("case.mom6.h.static") == "case.mom6.h.static.nc"
