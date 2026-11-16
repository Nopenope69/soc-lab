"""CALCE aging cycle data loader.

Parses CALCE A123 (1.11 Ah LFP) and CS2 cycle test files, converts raw Arbin
sign conventions to canonical repository polarity (discharge positive), extracts
cycle records, and applies qualified Reference Measurement Protocols to determine
BOL and rated ground-truth SOH labels.
"""

from pathlib import Path
from typing import Dict, List, Optional
import numpy as np

try:
    import pandas as pd
except ImportError:
    pd = None

from soh.common.contracts import CycleRecord
from soh.common.protocols import CellReferenceSpec
from soh.data.base_loader import AbstractAgingDataLoader, SohBatteryData, SohDataset


class CalceAgingDataLoader(AbstractAgingDataLoader):
    """Loader for CALCE battery aging cycle experiments."""

    def __init__(self, spec: Optional[CellReferenceSpec] = None):
        if spec is None:
            # Default reference spec for A123 LiFePO4, measured capacity about 1.06 Ah (A1-007) and about 1.09 Ah (A1-008) at 25 C, format unverified
            self.spec = CellReferenceSpec(
                cell_id="CALCE_A123_UNVERIFIED",
                chemistry="LFP",
                nominal_capacity_ah=1.11,
                v_max=3.65,
                v_min=2.00,
                t_ref_c=25.0,
                c_rate_ref_discharge=0.5,
                nominal_resistance_ohm=0.015,
            )
        else:
            self.spec = spec

    def parse_excel_file(
        self,
        file_path: Path,
        cell_id: str,
        max_rows: Optional[int] = None,
    ) -> SohBatteryData:
        """Parse single CALCE Arbin Excel file into an SohBatteryData object."""
        if pd is None:
            raise ImportError(
                "pandas and openpyxl are required to parse CALCE Excel files. "
                "Install with 'pip install .[research]'"
            )
        xl = pd.ExcelFile(file_path)
        # Select data channel sheet (typically Channel_1-006 or second sheet)
        sheet = None
        for s in xl.sheet_names:
            if "channel" in s.lower():
                sheet = s
                break
        if sheet is None:
            sheet = xl.sheet_names[1] if len(xl.sheet_names) > 1 else xl.sheet_names[0]

        df = pd.read_excel(file_path, sheet_name=sheet, nrows=max_rows)

        # Standard column names
        time_col = "Test_Time(s)"
        curr_col = "Current(A)"
        volt_col = "Voltage(V)"
        cycle_col = "Cycle_Index"
        dis_cap_col = "Discharge_Capacity(Ah)"
        ir_col = "Internal_Resistance(Ohm)"
        temp_col = "Temperature (C)_1" if "Temperature (C)_1" in df.columns else None

        battery = SohBatteryData(
            cell_id=cell_id,
            spec=self.spec.model_copy(update={"cell_id": cell_id}),
        )

        if cycle_col not in df.columns:
            # Single cycle or continuous test
            cycle_indices = [1]
            groups = [(1, df)]
        else:
            groups = df.groupby(cycle_col)

        cum_throughput_ah = 0.0

        for cycle_idx, sub in groups:
            if len(sub) < 10:
                continue

            raw_time = sub[time_col].values.astype(float)
            raw_curr = sub[curr_col].values.astype(float)
            raw_volt = sub[volt_col].values.astype(float)
            raw_temp = (
                sub[temp_col].values.astype(float)
                if temp_col
                else np.full(len(sub), self.spec.t_ref_c)
            )

            # Polarity inversion: Arbin records charge as positive, discharge as negative.
            # Repository canonical polarity: discharge is positive, charge is negative.
            curr_canonical = -raw_curr
            time_rel = raw_time - raw_time[0]
            dt = np.diff(time_rel, prepend=time_rel[0])

            # Ah throughput for this cycle
            cycle_ah = np.sum(np.abs(curr_canonical) * dt) / 3600.0
            cum_throughput_ah += cycle_ah

            # Ground truth capacity
            meas_cap = None
            if dis_cap_col in sub.columns:
                max_dis = float(np.nanmax(sub[dis_cap_col].values))
                if max_dis > 0.05:
                    meas_cap = max_dis

            if meas_cap is None:
                # Approximate from CC discharge integration
                dis_mask = curr_canonical > 0.1
                if np.any(dis_mask):
                    meas_cap = float(np.sum(curr_canonical[dis_mask] * dt[dis_mask]) / 3600.0)

            # Ground truth resistance if measured by Arbin
            meas_res = None
            if ir_col in sub.columns:
                valid_ir = sub[ir_col].dropna()
                valid_ir = valid_ir[valid_ir > 0]
                if not valid_ir.empty:
                    meas_res = float(valid_ir.mean())

            cycle_rec = CycleRecord(
                cycle_index=int(cycle_idx),
                time_s=time_rel,
                voltage_v=raw_volt,
                current_a=curr_canonical,
                temp_c=raw_temp,
                ah_throughput=cum_throughput_ah,
                measured_capacity_ah=meas_cap,
                measured_resistance_ohm=meas_res,
            )
            battery.cycles.append(cycle_rec)

        battery.compute_ground_truths()
        return battery

    def load_battery(self, cell_id: str, data_dir: Path) -> SohBatteryData:
        """Find matching file and load battery."""
        candidates = list(data_dir.glob(f"**/*{cell_id}*.xlsx"))
        if not candidates:
            raise FileNotFoundError(f"No CALCE file found for cell_id {cell_id} under {data_dir}")
        return self.parse_excel_file(candidates[0], cell_id=cell_id)

    def load_dataset(self, data_dir: Path) -> SohDataset:
        """Scan directory and build cohort dataset."""
        dataset = SohDataset()
        files = [f for f in data_dir.glob("**/*.xlsx") if not f.name.startswith("~$")]
        for f in files[:5]:  # Load representative sample
            cid = f.stem.split("-")[0] + "_" + f.parent.name
            try:
                bdata = self.parse_excel_file(f, cell_id=cid)
                if bdata.cycles:
                    dataset.add_battery(bdata)
            except Exception:
                continue
        return dataset
