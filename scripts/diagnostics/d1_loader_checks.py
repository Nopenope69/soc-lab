"""Diagnostic D1: Loader and leakage checks.

Verifies:
a) 20 C file selection, exclusion of 20120809 .xls files, and step vs schedule labeling.
b) Sheet selection by prefix Channel_1-, 25 C OCV sheet swap handling, cell specimen isolation.
c) Current sign convention (I_repo = -I_raw), mean current during Step 8 and C/20 discharge.
d) Identification profile isolation (DST-only vs US06/FUDS) and E5 variant selection audit.
e) Label audit: "ANR26650M1-A", search for 2.5 Ah, 2500, 26650, 2.4 defaults across repo.
"""

from pathlib import Path
import re
import openpyxl
import pandas as pd
import numpy as np

from soc.data.calce_loader import load_ocv_file, load_dynamic_cycle, get_raw_dir
from scripts.evaluate_calce import get_file_paths

def run_d1():
    raw_dir = get_raw_dir()
    print("=== D1. Loader and Leakage Checks ===\n")

    # a) 20 C files
    print("--- D1(a). 20 C File Resolution ---")
    ocv_20_007, dyn_20_007 = get_file_paths(raw_dir, 20, "A1-007")
    ocv_20_008, dyn_20_008 = get_file_paths(raw_dir, 20, "A1-008")
    print(f"20 C A1-007 OCV file: {ocv_20_007.name}")
    print(f"20 C A1-007 Dynamic file: {dyn_20_007.name}")
    print(f"20 C A1-008 OCV file: {ocv_20_008.name}")
    print(f"20 C A1-008 Dynamic file: {dyn_20_008.name}")

    # Check all files in 20 C directory
    dir_20 = [p for p in raw_dir.glob("*DST-US06-FUDS-20*") if p.is_dir()][0]
    all_20_files = [p.name for p in dir_20.glob("*") if not p.name.startswith("~$")]
    print(f"All files in 20 C dynamic directory: {all_20_files}")
    is_xls_excluded = not any("20120809.xls" in f for f in [dyn_20_007.name, dyn_20_008.name])
    is_20120817_used = "20120817.xlsx" in dyn_20_007.name and "20120817.xlsx" in dyn_20_008.name
    print(f"20120809 .xls files excluded: {is_xls_excluded}")
    print(f"20120817.xlsx files used: {is_20120817_used}")

    # Check how profiles are labeled in load_dynamic_cycle
    # Step target mapping from calce_loader.py:
    # "DST": 8, "US06": 16, "FUDS": 24
    print("Step target mapping in calce_loader.py: DST -> Step 8, US06 -> Step 16, FUDS -> Step 24.")

    # b) Sheet selection and 25 C OCV sheet swap
    print("\n--- D1(b). Sheet Selection & 25 C OCV Sheet Swap ---")
    ocv_25_dir = [p for p in raw_dir.glob("*OCV25*") if p.is_dir()][0]
    ocv_25_files = [p for p in ocv_25_dir.glob("*.xlsx") if not p.name.startswith("~$")]
    for f in ocv_25_files:
        wb = openpyxl.load_workbook(f, read_only=True)
        print(f"File: {f.name} -> Sheets: {wb.sheetnames}")
        wb.close()

    ocv_25_007, dyn_25_007 = get_file_paths(raw_dir, 25, "A1-007")
    ocv_25_008, dyn_25_008 = get_file_paths(raw_dir, 25, "A1-008")
    print(f"Loader selected 25 C A1-007 OCV: {ocv_25_007.name}")
    print(f"Loader selected 25 C A1-008 OCV: {ocv_25_008.name}")

    # Inspect Channel sheet chosen by calce_loader
    wb_007 = openpyxl.load_workbook(ocv_25_007, read_only=True)
    ch_sheet_007 = [s for s in wb_007.sheetnames if s.startswith("Channel_1-")][0]
    wb_007.close()
    wb_008 = openpyxl.load_workbook(ocv_25_008, read_only=True)
    ch_sheet_008 = [s for s in wb_008.sheetnames if s.startswith("Channel_1-")][0]
    wb_008.close()
    print(f"A1-007 OCV25 sheet parsed: {ch_sheet_007}")
    print(f"A1-008 OCV25 sheet parsed: {ch_sheet_008}")

    # c) Current sign convention
    print("\n--- D1(c). Current Sign Convention ---")
    ocv_25_data = load_ocv_file(ocv_25_007, 25.0, "A1-007")
    dyn_25_dst = load_dynamic_cycle(dyn_25_007, 25.0, "A1-007", "DST", ocv_25_data.c20_capacity_ah)
    mean_i_dst = float(np.mean(dyn_25_dst.current_a))
    print(f"DST (Step 8) parsed current: mean = {mean_i_dst:+.4f} A (positive = discharge in repo convention)")
    
    # Check C/20 discharge step
    # Step 5 is C/20 discharge
    df_ocv_raw = pd.read_excel(ocv_25_007, sheet_name=ch_sheet_007)
    sub_dis = df_ocv_raw[df_ocv_raw["Step_Index"] == 5]
    raw_dis_i_mean = float(np.mean(sub_dis["Current(A)"]))
    print(f"Raw C/20 discharge (Step 5) current mean in Excel: {raw_dis_i_mean:+.4f} A")
    print(f"Inverted C/20 discharge current (-I_raw): {-raw_dis_i_mean:+.4f} A (positive = discharge)")

    # d) Profile leakage / Variant selection
    print("\n--- D1(d). Profile Leakage & Variant Selection Audit ---")
    print("In identify_calce_params.py: only OCV and DST are ingested. US06 and FUDS are not imported.")
    print("In evaluate_calce.py: variant selection lines 327-330:")
    print("   better_e5 = 'E5 v1' if e5v1_med < e5v2_med else 'E5 v2'")
    print("   where e5v1_med and e5v2_med were computed from df_gate_base (US06 and FUDS baseline results!)")

    # e) Label audit & grep
    print("\n--- D1(e). Cell Part Number & Capacity Label Audit ---")
    repo_root = Path(__file__).resolve().parent.parent.parent
    patterns = ["ANR26650", "APR18650", "26650", "2.5 Ah", "2.5Ah", "2500", "2.4"]
    for pat in patterns:
        hits = []
        for p in repo_root.rglob("*"):
            if p.is_file() and not any(part.startswith(".") for part in p.parts) and "data/raw" not in str(p) and "__pycache__" not in str(p):
                try:
                    text = p.read_text(encoding="utf-8", errors="ignore")
                    matches = [m.start() for m in re.finditer(re.escape(pat), text, re.IGNORECASE)]
                    if matches:
                        hits.append((p.relative_to(repo_root), len(matches)))
                except Exception:
                    pass
        print(f"Matches for '{pat}': {hits}")

if __name__ == "__main__":
    run_d1()
