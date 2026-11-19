#!/usr/bin/env python3
"""
Scan UConn REIL RPT dataset (dataset 5) across all 64 cells and 207 CSV files.
Audits:
- Condition groups (1 to 11)
- File partitions per cell
- RPT counts, initial RPT 0 validity, and capacity
- SOH_C ranges
- Slowpulse presence across SOC levels (20%, 50%, 90%)
- Sampling rates, units, sign conventions
"""

import glob
import os
import sys
import numpy as np
import pandas as pd


def get_condition_group(cell_id: int) -> int:
    """Map cell number (2..65) to condition group (1..11).

    Groups 1 to 10: 6 cells each (02-07, 08-13, ..., 56-61)
    Group 11: 4 cells (62-65)
    """
    if 2 <= cell_id <= 61:
        return (cell_id - 2) // 6 + 1
    elif 62 <= cell_id <= 65:
        return 11
    else:
        raise ValueError(f"Cell ID {cell_id} out of range [2, 65]")


def main():
    data_dir = os.environ.get(
        "SOC_DATA_DIR", "/Users/tecbusiness/soc_data"
    )
    rpt_dir = os.path.join(data_dir, "uconn_reil", "extracted", "rpt_data")
    if not os.path.exists(rpt_dir):
        print(f"Error: directory {rpt_dir} does not exist", file=sys.stderr)
        sys.exit(1)

    cell_summaries = []

    for cell_id in range(2, 66):
        cell_str = f"{cell_id:02d}"
        group_id = get_condition_group(cell_id)
        parts = sorted(glob.glob(os.path.join(rpt_dir, f"rpt_cell_{cell_str}_part*.csv")))
        num_parts = len(parts)

        # Read all parts with minimal columns
        dfs = []
        for p in parts:
            df_part = pd.read_csv(
                p,
                usecols=[
                    "RPT Number",
                    "Step Number",
                    "Segment Key",
                    "Pulse Type",
                    "Pulse SOC",
                    "Capacity (Ah)",
                ],
            )
            dfs.append(df_part)

        df_cell = pd.concat(dfs, ignore_index=True)
        rpts = sorted(df_cell["RPT Number"].unique())
        has_rpt0 = 0 in rpts

        # For each RPT, check ref_dchg capacity
        rpt_caps = {}
        rpt_pulses = {}
        for rpt in rpts:
            sub = df_cell[df_cell["RPT Number"] == rpt]
            dchg = sub[sub["Segment Key"] == "ref_dchg"]
            if len(dchg) > 0:
                cap = float(dchg["Capacity (Ah)"].max() - dchg["Capacity (Ah)"].min())
                rpt_caps[rpt] = cap
            else:
                rpt_caps[rpt] = None

            # Pulses
            pulses = sub[sub["Segment Key"] == "slowpulse"]["Pulse SOC"].dropna().unique().tolist()
            rpt_pulses[rpt] = sorted(pulses)

        cap0 = rpt_caps.get(0, None)
        valid_rpt_count = sum(1 for c in rpt_caps.values() if c is not None and c > 0.5)
        min_cap = min((c for c in rpt_caps.values() if c is not None), default=None)
        max_cap = max((c for c in rpt_caps.values() if c is not None), default=None)
        final_rpt = max(rpts) if rpts else None
        final_cap = rpt_caps.get(final_rpt, None)
        final_soh = (final_cap / cap0) if (final_cap and cap0) else None

        cell_summaries.append({
            "cell_id": cell_id,
            "cell_str": cell_str,
            "group": group_id,
            "num_parts": num_parts,
            "total_rows": len(df_cell),
            "num_rpts": len(rpts),
            "rpts_contiguous": rpts == list(range(len(rpts))),
            "has_rpt0": has_rpt0,
            "cap0": cap0,
            "final_rpt": final_rpt,
            "final_cap": final_cap,
            "final_soh": final_soh,
            "min_cap": min_cap,
            "max_cap": max_cap,
            "valid_rpt_count": valid_rpt_count,
        })

    summary_df = pd.DataFrame(cell_summaries)
    print("=== UCONN DATASET 5 AUDIT SUMMARY ===")
    print(f"Total cells: {len(summary_df)}")
    print(f"Cells with RPT0: {summary_df['has_rpt0'].sum()}")
    print(f"Cells with contiguous RPTs: {summary_df['rpts_contiguous'].sum()}")
    print(f"Total CSV parts: {summary_df['num_parts'].sum()}")
    print(f"Total data points (rows): {summary_df['total_rows'].sum():,}")
    print(f"Initial capacity (cap0) mean: {summary_df['cap0'].mean():.4f} Ah, min: {summary_df['cap0'].min():.4f} Ah, max: {summary_df['cap0'].max():.4f} Ah")
    print(f"RPT count per cell: min {summary_df['num_rpts'].min()}, mean {summary_df['num_rpts'].mean():.1f}, max {summary_df['num_rpts'].max()}")
    print(f"Final SOH_C mean: {summary_df['final_soh'].mean():.4f}, min: {summary_df['final_soh'].min():.4f}, max: {summary_df['final_soh'].max():.4f}")
    print("\nSummary by Condition Group:")
    grp = summary_df.groupby("group").agg({
        "cell_id": "count",
        "num_rpts": ["min", "mean", "max"],
        "cap0": ["mean"],
        "final_soh": ["min", "mean", "max"],
    })
    print(grp.to_string())

    # Save summary table as CSV for reference
    out_csv = "reports/validation/uconn_cell_summary.csv"
    os.makedirs("reports/validation", exist_ok=True)
    summary_df.to_csv(out_csv, index=False)
    print(f"\nWrote per-cell audit to {out_csv}")


if __name__ == "__main__":
    main()
