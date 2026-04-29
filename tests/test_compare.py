"""
Tests for configuration comparison utilities.

Validates:
- normalization behavior
- compare / diff / describe modes
- flat vs nested outputs
- metadata inclusion
- filtering behavior

Copyright (C) 2026
"""

import pytest

from owlplanner.config.defaults import default_config
from owlplanner.config.compare import compare_configs


# ---------------------------------------------------------
# Fixtures
# ---------------------------------------------------------

@pytest.fixture
def base_config():
    return default_config(ni=2)


@pytest.fixture
def modified_config(base_config):
    cfg = dict(base_config)

    # shallow copy is fine for controlled mutation
    cfg = {k: v.copy() if isinstance(v, dict) else v for k, v in cfg.items()}

    cfg["rates_selection"]["dividend_rate"] = 2.0
    cfg["optimization_parameters"]["objective"] = "maxBequest"

    return cfg


# ---------------------------------------------------------
# Basic behavior
# ---------------------------------------------------------

def test_compare_identical_configs(base_config):
    result = compare_configs(base_config, base_config)

    # Should contain no differences
    flat = compare_configs(base_config, base_config, flat=True)
    assert all(not v["different"] for v in flat.values())


def test_compare_detects_changes(base_config, modified_config):
    result = compare_configs(base_config, modified_config, flat=True)

    assert "rates_selection.dividend_rate" in result
    assert result["rates_selection.dividend_rate"]["different"] is True

    assert "optimization_parameters.objective" in result
    assert result["optimization_parameters.objective"]["different"] is True


# ---------------------------------------------------------
# Diff mode
# ---------------------------------------------------------

def test_diff_mode_only_returns_changes(base_config, modified_config):
    result = compare_configs(base_config, modified_config, mode="diff", flat=True)

    # Should only include changed fields
    assert all(v["different"] for v in result.values())
    assert "rates_selection.dividend_rate" in result
    assert "optimization_parameters.objective" in result


def test_diff_mode_empty_for_identical(base_config):
    result = compare_configs(base_config, base_config, mode="diff", flat=True)

    assert result == {}


# ---------------------------------------------------------
# Describe mode
# ---------------------------------------------------------

def test_describe_mode_contains_value_and_default(base_config):
    result = compare_configs(base_config, None, mode="describe", flat=True)

    sample = result["rates_selection.dividend_rate"]

    assert "value" in sample
    assert "default" in sample
    assert sample["value"] == sample["default"]


def test_describe_mode_diff_against_default(base_config):
    modified = default_config(ni=2)
    modified["rates_selection"]["dividend_rate"] = 2.0

    result = compare_configs(modified, None, mode="diff", flat=True)

    assert "rates_selection.dividend_rate" in result
    assert result["rates_selection.dividend_rate"]["different"] is True


# ---------------------------------------------------------
# Metadata behavior
# ---------------------------------------------------------

def test_include_metadata(base_config):
    result = compare_configs(base_config, None, mode="describe", include_metadata=True, flat=True)

    sample = result["rates_selection.dividend_rate"]

    assert "description" in sample


def test_exclude_metadata(base_config):
    result = compare_configs(base_config, None, mode="describe", include_metadata=False, flat=True)

    sample = result["rates_selection.dividend_rate"]

    assert "description" not in sample


# ---------------------------------------------------------
# Flat vs nested
# ---------------------------------------------------------

def test_flat_output_keys(base_config, modified_config):
    result = compare_configs(base_config, modified_config, flat=True)

    assert isinstance(result, dict)
    assert any("." in k for k in result.keys())


def test_nested_output_structure(base_config, modified_config):
    result = compare_configs(base_config, modified_config, flat=False)

    assert "rates_selection" in result
    assert "dividend_rate" in result["rates_selection"]


# ---------------------------------------------------------
# include_equal behavior
# ---------------------------------------------------------

def test_exclude_equal_fields(base_config, modified_config):
    result = compare_configs(
        base_config,
        modified_config,
        include_equal=False,
        flat=True,
    )

    assert all(v["different"] for v in result.values())


# ---------------------------------------------------------
# Path filtering
# ---------------------------------------------------------

def test_path_filter(base_config, modified_config):
    result = compare_configs(
        base_config,
        modified_config,
        flat=True,
        path_filter=["rates_selection"],
    )

    assert all(k.startswith("rates_selection") for k in result.keys())


# ---------------------------------------------------------
# Reference behavior
# ---------------------------------------------------------

def test_reference_default(base_config):
    result = compare_configs(base_config, None, mode="describe", reference="default", flat=True)

    sample = result["rates_selection.dividend_rate"]

    assert sample["default"] == sample["value"]


# ---------------------------------------------------------
# Normalization behavior (critical)
# ---------------------------------------------------------

def test_missing_fields_equal_after_normalization():
    a = {}
    b = default_config(ni=1)

    result = compare_configs(a, b, flat=True)

    # Should be equal after normalization
    assert all(not v["different"] for v in result.values())


# ---------------------------------------------------------
# Error handling
# ---------------------------------------------------------

def test_invalid_mode_raises(base_config):
    with pytest.raises(ValueError):
        compare_configs(base_config, base_config, mode="invalid")

