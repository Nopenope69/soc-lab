"""Tests for the assumptions schema validation, bounds checks, and OCV monotonicity."""

import pytest
from pydantic import ValidationError

from soc.assumptions.loader import load_assumptions
from soc.assumptions.schema import (
    AssumptionEntry,
    Assumptions,
    PlantAssumptions,
)


def test_base_yaml_validates_cleanly():
    """Verify that base.yaml passes schema validation without warnings or errors."""
    assumptions, raw_dict, config_hash = load_assumptions()
    assert isinstance(assumptions, Assumptions)
    assert assumptions.plant.nominal_capacity_Ah.value == 100.0
    assert assumptions.soc_definition.basis.value == "present_capacity"
    assert config_hash is not None and len(config_hash) == 64


def test_out_of_bounds_rejection():
    """Verify that values outside declared bounds raise ValueError."""
    # Valid entry
    entry = AssumptionEntry(
        value=50.0,
        unit="Ah",
        status="placeholder",
        bounds=(1.0, 500.0),
        note="Valid test entry",
    )
    assert entry.value == 50.0

    # Below lower bound
    with pytest.raises(ValidationError, match="outside declared bounds"):
        AssumptionEntry(
            value=0.5,
            unit="Ah",
            status="placeholder",
            bounds=(1.0, 500.0),
            note="Too low",
        )

    # Above upper bound
    with pytest.raises(ValidationError, match="outside declared bounds"):
        AssumptionEntry(
            value=600.0,
            unit="Ah",
            status="placeholder",
            bounds=(1.0, 500.0),
            note="Too high",
        )


def test_unknown_key_rejection():
    """Verify that extra keys in configuration are strictly forbidden."""
    _, raw_dict, _ = load_assumptions()
    raw_dict["unknown_top_level_group"] = {"fake": 123}

    with pytest.raises(ValueError, match="Extra inputs are not permitted"):
        Assumptions.model_validate(raw_dict)


def test_ocv_table_must_be_strictly_increasing():
    """Verify that an OCV curve with flat or decreasing points fails schema validation."""
    _, raw_dict, _ = load_assumptions()

    # Create a non-monotonic OCV table at 25.0 C (two identical consecutive values)
    flat_ocv = list(raw_dict["plant"]["ocv_table_v"]["value"]["25.0"])
    flat_ocv[4] = flat_ocv[3]  # flat spot!
    raw_dict["plant"]["ocv_table_v"]["value"]["25.0"] = flat_ocv

    with pytest.raises(ValueError, match="not strictly increasing"):
        Assumptions.model_validate(raw_dict)

    # Decreasing point
    decreasing_ocv = list(raw_dict["plant"]["ocv_table_v"]["value"]["25.0"])
    decreasing_ocv[5] = decreasing_ocv[4] - 0.01  # decreasing!
    raw_dict["plant"]["ocv_table_v"]["value"]["25.0"] = decreasing_ocv

    with pytest.raises(ValueError, match="not strictly increasing"):
        Assumptions.model_validate(raw_dict)
