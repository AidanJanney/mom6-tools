"""Tests for the diag_table parser, run against the two real tables in tests/data/."""

from pathlib import Path

import pytest

from mom6_diagtables import DiagField, DiagFile, parse_diag_table
from mom6_diagtables.parser import parse_diag_table_string
from mom6_diagtables.parser_yaml import parse_diag_table_yaml

DATA = Path(__file__).parent / "data"
GLOBAL = DATA / "diag_table_global"
CARIB = DATA / "diag_table_regional_carib"
GLOBAL_YAML = DATA / "diag_table_global.yaml"


def test_header_is_parsed():
    table = parse_diag_table(GLOBAL)
    assert table.title.startswith("MOM6 diagnostic fields table")
    assert table.base_date == [1, 1, 1, 0, 0, 0]


def test_global_file_and_field_counts():
    table = parse_diag_table(GLOBAL)
    assert len(table.files) == 24
    assert len(table.fields) == 266


def test_carib_file_and_field_counts():
    table = parse_diag_table(CARIB)
    assert len(table.files) == 7
    assert len(table.fields) == 139


def test_streams_include_expected_names():
    table = parse_diag_table(GLOBAL)
    streams = table.streams()
    for expected in ("z", "native", "rho2", "sfc", "static"):
        assert expected in streams


def test_static_file_has_negative_frequency_and_no_optional_columns():
    # The static file line is "...static", -1, "days", 1, "days", "time"  (6 columns).
    table = parse_diag_table(GLOBAL)
    static = table.streams()["static"]
    assert isinstance(static, DiagFile)
    assert static.output_freq == -1
    assert static.new_file_freq is None  # optional columns absent


def test_monthly_file_has_optional_columns():
    table = parse_diag_table(GLOBAL)
    z = table.streams()["z"]
    assert z.output_freq == 1
    assert z.output_freq_units == "months"
    assert z.new_file_freq == 1
    assert z.new_file_freq_units == "months"


def test_regional_section_field_is_parsed_as_one_token():
    """A regional section is a single quoted token with internal spaces.

    This is the case that breaks a naive whitespace split, so it is the key regression
    test for the CSV-based parser.
    """
    table = parse_diag_table(GLOBAL)
    agulhas = [f for f in table.fields if "Agulhas_Section" in f.file_name]
    assert agulhas, "expected Agulhas_Section fields in the global table"
    f = agulhas[0]
    assert isinstance(f, DiagField)
    assert f.regional_section == "20.1 20.1 -69.8 -34.6 -1 -1"
    assert f.reduction_method == ".true."
    assert f.packing == 2


def test_fields_for_returns_only_that_files_fields():
    table = parse_diag_table(CARIB)
    native_name = table.streams()["native"].file_name
    fields = table.fields_for(native_name)
    assert fields
    assert all(f.file_name == native_name for f in fields)


def test_prefix_for_field_unique():
    table = parse_diag_table(CARIB)
    # 'soga' (global mean salinity) is written once, to the native stream.
    prefix = table.prefix_for_field("soga")
    assert prefix == table.streams()["native"].file_name


def test_prefix_for_field_raises_when_ambiguous():
    table = parse_diag_table(GLOBAL)
    # 'thetao' is written to several streams (rho2, z, native, sections ...).
    assert len(table.files_for_field("thetao")) > 1
    with pytest.raises(KeyError):
        table.prefix_for_field("thetao")


def test_prefix_for_field_raises_when_missing():
    table = parse_diag_table(CARIB)
    with pytest.raises(KeyError):
        table.prefix_for_field("not_a_real_field")


# -- YAML parser -----------------------------------------------------------------

def test_yaml_header():
    table = parse_diag_table_yaml(GLOBAL_YAML)
    assert "MOM6" in table.title
    assert table.base_date == [1, 1, 1, 0, 0, 0]


def test_yaml_file_and_field_counts():
    table = parse_diag_table_yaml(GLOBAL_YAML)
    assert len(table.files) == 5
    assert len(table.fields) == 8


def test_yaml_streams():
    table = parse_diag_table_yaml(GLOBAL_YAML)
    streams = table.streams()
    for expected in ("z", "native", "sfc", "static"):
        assert expected in streams


def test_yaml_file_attributes():
    table = parse_diag_table_yaml(GLOBAL_YAML)
    z = table.streams()["z"]
    assert isinstance(z, DiagFile)
    assert z.output_freq == 1
    assert z.output_freq_units == "months"
    assert z.time_axis_units == "days"
    assert z.time_axis_name == "time"
    assert z.new_file_freq == 1
    assert z.new_file_freq_units == "months"
    assert z.file_format == 1       # YAML default


def test_yaml_field_attributes():
    table = parse_diag_table_yaml(GLOBAL_YAML)
    thetao = next(f for f in table.fields if f.field_name == "thetao")
    assert isinstance(thetao, DiagField)
    assert thetao.module_name == "ocean_model"
    assert thetao.reduction_method == "average"
    assert thetao.packing == 2      # r4 -> 2
    assert thetao.time_sampling == "1"  # YAML default


def test_yaml_out_name_override():
    table = parse_diag_table_yaml(GLOBAL_YAML)
    uo = next(f for f in table.fields if f.field_name == "uo")
    assert uo.output_name == "u"


def test_yaml_sub_region_encoded():
    table = parse_diag_table_yaml(GLOBAL_YAML)
    agulhas = next(f for f in table.fields if "Agulhas" in f.file_name)
    assert agulhas.regional_section != "none"
    parts = agulhas.regional_section.split()
    assert len(parts) == 6


def test_yaml_no_sub_region_is_none_string():
    table = parse_diag_table_yaml(GLOBAL_YAML)
    thetao = next(f for f in table.fields if f.field_name == "thetao")
    assert thetao.regional_section == "none"


def test_parse_diag_table_auto_detects_yaml():
    # The public parse_diag_table() function should dispatch by extension.
    table = parse_diag_table(GLOBAL_YAML)
    assert len(table.files) == 5


def test_parse_diag_table_auto_detects_ascii():
    table = parse_diag_table(GLOBAL)
    assert len(table.files) == 24


# -- ASCII tests (existing) -------------------------------------------------------

def test_comments_and_blank_lines_are_ignored():
    text = (
        '"my title"\n'
        "1 1 1 0 0 0\n"
        "### a comment\n"
        "\n"
        '"case.mom6.h.z%4yr-%2mo", 1, "months", 1, "days", "time", 1, "months"\n'
        '# another comment\n'
        '"ocean_model", "thetao", "thetao", "case.mom6.h.z%4yr-%2mo", "all", "mean", "none", 2\n'
    )
    table = parse_diag_table_string(text)
    assert table.title == "my title"
    assert len(table.files) == 1
    assert len(table.fields) == 1
    assert table.fields[0].output_name == "thetao"


# -- streams() overrides ----------------------------------------------------------

def test_streams_default_heuristic():
    # Default (no args) uses the common-prefix heuristic.
    table = parse_diag_table(GLOBAL)
    streams = table.streams()
    for expected in ("z", "native", "rho2", "sfc", "static"):
        assert expected in streams


def test_streams_pattern_override():
    table = parse_diag_table(GLOBAL)
    streams = table.streams(pattern=r"\.mom6\.h\.(?P<stream>[^%]+)")
    assert "z" in streams and "native" in streams
    assert streams["z"].file_name.endswith("z%4yr-%2mo")


def test_streams_mapping_override():
    table = parse_diag_table(GLOBAL)
    first = table.files[0].file_name
    streams = table.streams(mapping={first: "CUSTOM"})
    assert "CUSTOM" in streams
    assert streams["CUSTOM"].file_name == first
