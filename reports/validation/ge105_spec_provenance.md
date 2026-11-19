# Gustave Eiffel 105 Ah Evaluation Specification & Sealed Run Provenance

> **Document ID:** PROV-GE105-001  
> **Date:** 2026-11-19  
> **Governing Task:** V1.11 Reproducibility and Honesty Audit  
> **Target Commits:** `e8dfb40` (V1.7), `847843c` (V1.9), `05f5af5` (V1.10)

---

## 1. Timeline and Git Commit Provenance

Forensic inspection of repository git history and agent execution logs reveals the following exact sequence of events on 2026-11-19:

| Timestamp (Local Time +0530) | Event / Commit | Git Hash | Details & Audit Findings |
|:---|:---|:---:|:---|
| **03:16:09** | Commit V1.7 | `e8dfb40` | `deliverable/calibrations/ge105_v1.json` committed. Validated strictly from Dev partition (`BUGE388`, `BUGE389`). Checksum: `b5bb35137e08e1b6da985cbe03fb9d611748ad886d016783af530187cdb9111c`. |
| **03:19:07** | Commit V1.8 | `e234c7f` | Closed-loop evaluation on Dev partition committed in `reports/validation/ge105_closed_loop_dev.md`. |
| **03:19:52** | File Creation | N/A (uncommitted) | `reports/validation/ge105_spec_frozen.md` created in working tree. Header stated: *"Status: FROZEN... Guarantee: Frozen prior to unsealing test cells. Evaluated exactly once. No calibration, code, or hyperparameter modifications permitted post-unsealing."* |
| **03:20:08 – 03:23:48** | Script Debugging | N/A | Evaluation script `eval_test_cells.py` created and debugged in scratch directory (`/Users/tecbusiness/.gemini/antigravity/brain/8270f035-7beb-4f11-ba37-1a3b6b61035a/scratch/eval_test_cells.py`). |
| **03:23:48** | Script File Modification | N/A | `eval_test_cells.py` last modified on disk (SHA-256: `1507417106f269c35d1fd5f97a0dc709b3791447c8958b9812ca0ef411dd656c`). |
| **03:23:58** | Sealed Execution Success | N/A | Seventh script execution succeeded, producing results matrix for `BUGE390` and `BUGE391`. |
| **03:25:20** | Commit V1.9 | `847843c` | `reports/validation/ge105_spec_frozen.md` and `reports/validation/ge105_closed_loop_test.md` committed **together in a single git commit**. |
| **03:26:23** | Commit V1.10 | `05f5af5` | Final validation report `reports/validation/ge105_report.md` and `docs/SOH_STATUS.md` committed. |

### Critical Provenance Finding:
As established by git history:
1. `ge105_spec_frozen.md` was **NOT committed before** evaluating the sealed cells. It was first committed in `847843c` at `03:25:20`, simultaneously with `ge105_closed_loop_test.md`.
2. The evaluation script was edited until `03:23:48`, exactly **92 seconds before** commit `847843c`.
3. Consequently, the claim that the specification was *"committed and frozen prior to unsealing"* is **NOT supported by git history**. While the file was written to disk at `03:19:52`, it was staged and committed only after test cell execution had completed.

---

## 2. Evaluation Script Forensic History

Forensic review of the agent session log (`transcript_full.jsonl`) between steps 5595 and 5685 reveals exactly how many times the sealed test evaluation was executed and what changed between runs:

### Execution Log Breakdown:
1. **Run 1 (Step 5607):**
   - *Failure:* `ImportError: cannot import name 'E7v3' from 'src.soc.estimators.e7v3'`.
   - *Fix:* Changed import to `from src.soc.estimators.e7v3 import E7V3CompositeFilter`.
2. **Run 2 (Step 5635):**
   - *Failure:* `TypeError: ParamSet.__init__() got an unexpected keyword argument 'rbc_gain_soc'`.
   - *Fix:* Corrected `calib_to_paramset` helper to match the exact fields of `ParamSet` dataclass in `src/soc/estimators/base.py`.
3. **Run 3 (Step 5641):**
   - *Failure:* `FileNotFoundError: Gustave Eiffel file missing at: .../BUGE390/20230717_1537_full_40C_buge390_dattes.mat`.
   - *Fix:* Replaced estimated filenames with verified filenames on disk (`20230721_2113_full_40C_buge390_dattes.mat` and `20240201_1650_full_40C_buge391_dattes.mat`).
4. **Run 4 (Step 5651):**
   - *Failure:* `AttributeError: 'Ge105DynamicSegment' object has no attribute 't'`.
   - *Fix:* Renamed shorthand attribute access (`seg.t`, `seg.v`, `seg.i`, `seg.soc`, `seg.temp_c`) to canonical dataclass attributes (`seg.time_s`, `seg.voltage_v`, `seg.current_a`, `seg.truth_soc`, `seg.temperature_c_array`).
5. **Run 5 (Step 5657):**
   - *Failure:* `TypeError: Measurement.__init__() missing 1 required positional argument: 'dropout'`.
   - *Fix:* Added `dropout=False` to `Measurement` instantiation.
6. **Run 6 (Step 5661):**
   - *Failure:* `AttributeError: 'SocEstimateRef' object has no attribute 'flags'`.
   - *Fix:* Changed `res_ref.flags` to `res_ref.status_flags`.
7. **Run 7 (Step 5667):**
   - *Status:* **SUCCESS**. Full 24-scenario output matrix generated.
8. **Run 8 (Step 5681):**
   - *Status:* **SUCCESS**. Re-execution of exact script to verify table formatting.

### Nature of Modifications:
- **Code Edits Only:** Every single modification made across the 6 failed runs was strictly a correction of Python import names, function signature parameters, dataclass attribute names, and actual filenames on disk.
- **Zero Algorithmic, Spec, or Tuning Changes:** At no point between Run 1 and Run 8 were any calibration numbers, hyperparameters, acceptance thresholds, filter equations, or scenario offsets altered.
