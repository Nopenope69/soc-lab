"""Canonical units and polarity conventions for the SOH subsystem.

All estimators, features, data loaders, and plant interfaces in this module
strictly adhere to these definitions.

Current Sign Convention:
- Discharge current is positive (i > 0 discharges the cell).
- Charge current is negative (i < 0 charges the cell).
- Zero current is rest (i == 0).
This precisely matches `src/soc/models/cell_2rc.py`.

Canonical Units:
- Voltage: Volts (V)
- Current: Amperes (A)
- Time: Seconds (s)
- Temperature: Degrees Celsius (°C)
- Capacity: Ampere-hours (Ah)
- Resistance: Ohms (Ω)
- Energy: Watt-hours (Wh)
"""

# Polarity constants
CURRENT_POLARITY_DISCHARGE = 1.0
CURRENT_POLARITY_CHARGE = -1.0


def celsius_to_kelvin(temp_c: float) -> float:
    """Convert degrees Celsius to Kelvin."""
    return temp_c + 273.15


def kelvin_to_celsius(temp_k: float) -> float:
    """Convert Kelvin to degrees Celsius."""
    return temp_k - 273.15


def ah_to_as(capacity_ah: float) -> float:
    """Convert Ampere-hours (Ah) to Ampere-seconds / Coulombs (As)."""
    return capacity_ah * 3600.0


def as_to_ah(capacity_as: float) -> float:
    """Convert Coulombs (As) to Ampere-hours (Ah)."""
    return capacity_as / 3600.0


def is_charging(current_a: float, threshold_a: float = 1e-4) -> bool:
    """Check if current is charging (< 0)."""
    return current_a < -abs(threshold_a)


def is_discharging(current_a: float, threshold_a: float = 1e-4) -> bool:
    """Check if current is discharging (> 0)."""
    return current_a > abs(threshold_a)


def is_resting(current_a: float, threshold_a: float = 1e-4) -> bool:
    """Check if cell is at rest (|current| <= threshold)."""
    return abs(current_a) <= abs(threshold_a)
