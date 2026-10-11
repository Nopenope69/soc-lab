"""Pydantic schemas for the central assumptions engine."""

from typing import Any, Dict, List, Literal, Optional, Tuple, Union
from pydantic import BaseModel, ConfigDict, Field, model_validator


class AssumptionEntry(BaseModel):
    """Single assumption container with provenance, units, bounds, and note."""

    model_config = ConfigDict(extra="forbid")

    value: Any
    unit: str
    status: Literal["placeholder", "assumed", "measured", "fitted"]
    bounds: Optional[Tuple[float, float]] = None
    note: str

    @model_validator(mode="after")
    def validate_bounds(self) -> "AssumptionEntry":
        """Verify numeric values fall within declared bounds."""
        if self.bounds is not None:
            min_bound, max_bound = self.bounds
            if min_bound > max_bound:
                raise ValueError(
                    f"Invalid bounds [{min_bound}, {max_bound}]: lower bound exceeds upper bound"
                )

            self._check_value_recursive(self.value, min_bound, max_bound)
        return self

    def _check_value_recursive(self, val: Any, min_b: float, max_b: float) -> None:
        """Recursively check scalar, list, or dictionary numeric items against bounds."""
        if isinstance(val, bool):
            return
        if isinstance(val, (int, float)):
            if not (min_b <= val <= max_b):
                raise ValueError(
                    f"Assumption value {val} is outside declared bounds [{min_b}, {max_b}] ({self.note})"
                )
        elif isinstance(val, list):
            for item in val:
                self._check_value_recursive(item, min_b, max_b)
        elif isinstance(val, dict):
            for sub_val in val.values():
                self._check_value_recursive(sub_val, min_b, max_b)


class PlantAssumptions(BaseModel):
    """True cell electrochemistry and physical parameters."""

    model_config = ConfigDict(extra="forbid")

    nominal_capacity_Ah: AssumptionEntry
    initial_soc: AssumptionEntry
    coulombic_efficiency: AssumptionEntry
    temperatures_c: AssumptionEntry
    soc_grid: AssumptionEntry
    ocv_table_v: AssumptionEntry
    r0_table_ohm: AssumptionEntry
    r1_table_ohm: AssumptionEntry
    tau1_table_s: AssumptionEntry
    r2_table_ohm: AssumptionEntry
    tau2_table_s: AssumptionEntry
    hysteresis_amplitude_v: AssumptionEntry
    hysteresis_gamma: AssumptionEntry

    @model_validator(mode="after")
    def validate_ocv_monotonicity_and_grid(self) -> "PlantAssumptions":
        """Validate that SOC grid is sorted and OCV table is strictly increasing in SOC."""
        soc_list = self.soc_grid.value
        if not isinstance(soc_list, list) or len(soc_list) < 2:
            raise ValueError("soc_grid must be a list with at least 2 points")

        for idx in range(len(soc_list) - 1):
            if soc_list[idx + 1] <= soc_list[idx]:
                raise ValueError("soc_grid values must be strictly increasing")

        ocv_dict = self.ocv_table_v.value
        if not isinstance(ocv_dict, dict):
            raise ValueError("ocv_table_v must be a dictionary keyed by temperature string")

        for temp_key, voltages in ocv_dict.items():
            if not isinstance(voltages, list):
                raise ValueError(f"ocv_table_v values for temp '{temp_key}' must be a list")
            if len(voltages) != len(soc_list):
                raise ValueError(
                    f"ocv_table_v length ({len(voltages)}) for temp '{temp_key}' does not match soc_grid ({len(soc_list)})"
                )
            for idx in range(len(voltages) - 1):
                if voltages[idx + 1] <= voltages[idx]:
                    raise ValueError(
                        f"OCV table at temperature {temp_key} is not strictly increasing: "
                        f"V[{idx}]={voltages[idx]} >= V[{idx+1}]={voltages[idx+1]} "
                        f"at SOC {soc_list[idx]} and {soc_list[idx+1]}"
                    )
        return self


class DutyAssumptions(BaseModel):
    """Synthetic duty cycle parameters driving test profile generators."""

    model_config = ConfigDict(extra="forbid")

    initial_soc: AssumptionEntry
    ambient_temperature_c: AssumptionEntry
    pulse_c_rate: AssumptionEntry
    pulse_duration_s: AssumptionEntry
    rest_duration_s: AssumptionEntry
    total_duration_s: AssumptionEntry
    cycle_type: AssumptionEntry
    charge_discharge_ratio: AssumptionEntry
    soc_min_limit: AssumptionEntry
    soc_max_limit: AssumptionEntry
    allow_extremes: Optional[AssumptionEntry] = None


class EstimatorMismatch(BaseModel):
    """Relative parameter deviations for robustness and mismatch testing."""

    model_config = ConfigDict(extra="forbid")

    capacity_pct: AssumptionEntry
    r0_pct: AssumptionEntry
    r1_pct: AssumptionEntry
    tau1_pct: AssumptionEntry
    r2_pct: AssumptionEntry
    tau2_pct: AssumptionEntry
    ocv_offset_mv: AssumptionEntry
    hysteresis_amplitude_pct: AssumptionEntry
    hysteresis_gamma_pct: AssumptionEntry


class EstimatorModelAssumptions(BaseModel):
    """Parameters believed by the estimator, with mismatch support."""

    model_config = ConfigDict(extra="forbid")

    mismatch: EstimatorMismatch
    nominal_capacity_Ah: Optional[AssumptionEntry] = None
    coulombic_efficiency: Optional[AssumptionEntry] = None
    r0_table_ohm: Optional[AssumptionEntry] = None
    r1_table_ohm: Optional[AssumptionEntry] = None
    tau1_table_s: Optional[AssumptionEntry] = None
    r2_table_ohm: Optional[AssumptionEntry] = None
    tau2_table_s: Optional[AssumptionEntry] = None
    hysteresis_amplitude_v: Optional[AssumptionEntry] = None
    hysteresis_gamma: Optional[AssumptionEntry] = None


class SensorsAssumptions(BaseModel):
    """Sensor accuracy, ADC resolution, and noise parameters."""

    model_config = ConfigDict(extra="forbid")

    current_offset_a: AssumptionEntry
    current_gain_error: AssumptionEntry
    current_noise_sigma_a: AssumptionEntry
    voltage_noise_sigma_v: AssumptionEntry
    voltage_quantisation_v: AssumptionEntry
    sample_period_s: AssumptionEntry
    dropout_rate: AssumptionEntry
    temperature_noise_sigma_c: AssumptionEntry


class FilterAssumptions(BaseModel):
    """Filter state covariances, process noise, and algorithmic thresholds."""

    model_config = ConfigDict(extra="forbid")

    initial_soc_offset: AssumptionEntry
    initial_soc_std: AssumptionEntry
    initial_rc_current_std_a: AssumptionEntry
    initial_hysteresis_std: AssumptionEntry
    process_noise_q_soc: AssumptionEntry
    process_noise_q_rc: AssumptionEntry
    process_noise_q_hysteresis: AssumptionEntry
    measurement_noise_r_v: AssumptionEntry
    ocv_slope_weighting_gain: AssumptionEntry
    convergence_threshold_2pct: AssumptionEntry
    convergence_threshold_5pct: AssumptionEntry
    reversal_min_current_a: AssumptionEntry


class SocDefinitionAssumptions(BaseModel):
    """Ground-truth SOC reference basis and recalibration anchor policies."""

    model_config = ConfigDict(extra="forbid")

    basis: AssumptionEntry
    anchor_enabled: AssumptionEntry
    rest_anchor_enabled: AssumptionEntry
    rest_current_threshold_a: AssumptionEntry
    rest_duration_threshold_s: AssumptionEntry
    full_charge_voltage_threshold_v: AssumptionEntry
    full_charge_current_threshold_a: AssumptionEntry
    full_charge_anchor_soc: AssumptionEntry
    full_charge_anchor_enabled: Optional[AssumptionEntry] = None

    @model_validator(mode="after")
    def validate_basis(self) -> "SocDefinitionAssumptions":
        """Enforce present_capacity basis."""
        if self.basis.value != "present_capacity":
            raise ValueError(
                f"Invalid basis '{self.basis.value}': reference SOC basis must be 'present_capacity'"
            )
        return self


class BarsAssumptions(BaseModel):
    """Test matrix pass/fail bar thresholds."""

    model_config = ConfigDict(extra="forbid")

    t1_ocv_error_max_mv: AssumptionEntry
    t2_dynamic_rmse_max: AssumptionEntry
    t2_dynamic_max_error: AssumptionEntry
    t3_bess_rmse_24h_max: AssumptionEntry
    t4_plateau_p95_max: AssumptionEntry
    t5_converge_time_s: AssumptionEntry
    t6_drift_bess_per_day_max: AssumptionEntry
    t7_error_rise_max: AssumptionEntry
    t9_post_rest_step_error_max: AssumptionEntry
    t10_reversal_spike_max: AssumptionEntry
    t12_mismatch_rmse_rise_max: AssumptionEntry
    t14_auto_max_ms_per_step: AssumptionEntry


class RunAssumptions(BaseModel):
    """Operational run settings: random seeds, data splits, and dataset IDs."""

    model_config = ConfigDict(extra="forbid")

    random_seed: AssumptionEntry
    splits_file: AssumptionEntry
    dataset_names: AssumptionEntry
    warmup_steps: Optional[AssumptionEntry] = None
    num_seeds: Optional[AssumptionEntry] = None
    tie_band_pp: Optional[AssumptionEntry] = None
    metric_warmup_s: Optional[AssumptionEntry] = None
    full_charge_hold_s: Optional[AssumptionEntry] = None


class MetricsAssumptions(BaseModel):
    """Evaluation metric configuration and duration thresholds."""

    model_config = ConfigDict(extra="forbid")

    drift_min_run_s: AssumptionEntry


class Assumptions(BaseModel):
    """Complete root configuration container."""

    model_config = ConfigDict(extra="forbid")

    plant: PlantAssumptions
    duty: DutyAssumptions
    estimator_model: EstimatorModelAssumptions
    sensors: SensorsAssumptions
    filter: FilterAssumptions
    soc_definition: SocDefinitionAssumptions
    bars: BarsAssumptions
    run: RunAssumptions
    metrics: Optional[MetricsAssumptions] = None

