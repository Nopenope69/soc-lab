# Gustave Eiffel 105 Ah Evaluation Specification & Sealed Run Provenance

> [!NOTE] Revision (V1.12 Run Count Reconciliation)  
> Expanded evaluation attempt forensic log to include every invocation in session history (both inline python attempts and scratch script invocations), reconciling Definition A (6 scratch script attempts) and Definition B (10 total invocations prior to success).

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

## 2. Evaluation Script Forensic History & Complete Invocation Table

Forensic review of the agent session log (`transcript_full.jsonl`) between steps 5590 and 5685 reveals every invocation of sealed-test evaluation commands:

### Run Count Definitions & Reconciliation:
- **Definition A (File-based Invocations of `scratch/eval_test_cells.py`):** Exactly **6 failed attempts** (steps 5607, 5635, 5641, 5651, 5657, 5661), followed by 2 successful executions (steps 5667 and 5681).
- **Definition B (All Sealed Evaluation Invocations):** Exactly **10 failed attempts** (steps 5591, 5593, 5595, 5603, 5607, 5635, 5641, 5651, 5657, 5661), including initial inline-python execution attempts and temporary file `/tmp/eval_test_cells.py`, followed by 2 successful executions (steps 5667 and 5681).

### Complete Table of Sealed Test Evaluation Invocations:

| Invocation # | Step ID | Command Executed | Exit Code | Error Text / Output | Edit Made Before Next Run |
|:---:|:---:|:---|:---:|:---|:---|
| 1 | **5591** | `.venv/bin/python -c 'import numpy as np...'` | `1` | `SyntaxError: unexpected character after line continuation character` | Switched from inline script to writing script file `/tmp/eval_test_cells.py`. |
| 2 | **5593** | `.venv/bin/python -c 'code="""..."""...'` (write to `/tmp`) | `1` | `ModuleNotFoundError: No module named 'src'` | Added `PYTHONPATH=.` to execution command. |
| 3 | **5595** | `PYTHONPATH=. .venv/bin/python /tmp/eval_test_cells.py` | `1` | `ImportError: cannot import name 'resample_dynamic_segment' from 'src.soc.data.ge105_loader'` | Realized resampling is internal to `extract_wltc_segments`; prepared scratch script. |
| 4 | **5603** | `.venv/bin/python -c 'code="""..."""...'` (write to scratch) | `1` | `SyntaxError: unterminated string literal (detected at line 109)` | Switched from shell string echo to direct `write_file` tool call (step 5605) to write `scratch/eval_test_cells.py`. |
| 5 (Run 1) | **5607** | `PYTHONPATH=. .venv/bin/python .../scratch/eval_test_cells.py` | `1` | `ImportError: cannot import name 'E7v3' from 'src.soc.estimators.e7v3'` | Changed import name to `E7V3CompositeFilter` (step 5633). |
| 6 (Run 2) | **5635** | `PYTHONPATH=. .venv/bin/python .../scratch/eval_test_cells.py` | `1` | `TypeError: ParamSet.__init__() got an unexpected keyword argument 'rbc_gain_soc'` | Corrected `calib_to_paramset` helper to remove extraneous parameters and match `ParamSet` dataclass fields (step 5639). |
| 7 (Run 3) | **5641** | `PYTHONPATH=. .venv/bin/python .../scratch/eval_test_cells.py` | `1` | `FileNotFoundError: Gustave Eiffel file missing at: .../BUGE390/20230717_1537_full_40C_buge390_dattes.mat` | Inspected filesystem via `ls` (steps 5643, 5645) and replaced guessed filenames with exact disk filenames (`20230721_2113` for 390, `20240201_1650` for 391) (step 5649). |
| 8 (Run 4) | **5651** | `PYTHONPATH=. .venv/bin/python .../scratch/eval_test_cells.py` | `1` | `AttributeError: 'Ge105DynamicSegment' object has no attribute 't'` | Renamed shorthand attributes (`.t`, `.v`, `.i`, `.soc`, `.temp_c`) to canonical dataclass field names (`.time_s`, `.voltage_v`, `.current_a`, `.truth_soc`, `.temperature_c_array`) (step 5655). |
| 9 (Run 5) | **5657** | `PYTHONPATH=. .venv/bin/python .../scratch/eval_test_cells.py` | `1` | `TypeError: Measurement.__init__() missing 1 required positional argument: 'dropout'` | Added required positional argument `dropout=False` to `Measurement` instantiation (step 5659). |
| 10 (Run 6) | **5661** | `PYTHONPATH=. .venv/bin/python .../scratch/eval_test_cells.py` | `1` | `AttributeError: 'SocEstimateRef' object has no attribute 'flags'` | Changed attribute access from `.flags` to `.status_flags` (step 5665). |
| 11 (Run 7) | **5667** | `PYTHONPATH=. .venv/bin/python .../scratch/eval_test_cells.py` | `0` | **SUCCESS**. Processed all 24 scenarios across BUGE390 and BUGE391; printed metrics matrix to stdout. | Execution succeeded without error. Staged output tables for report drafting. |
| 12 (Run 8) | **5681** | `.venv/bin/python -c 'exec(open(...eval_test_cells.py).read())'` | `0` | **SUCCESS**. Re-executed exact script from Python wrapper to extract markdown table formatting. | Results identical to Run 7. Committed to repository in `847843c`. |

### Nature of Modifications:
- **Syntax and Interface Corrections Only:** Every single modification across the 10 failed attempts was strictly a mechanical fix for shell escaping, Python import names, actual disk filenames, or dataclass attributes.
- **Zero Algorithmic, Spec, or Tuning Changes:** At no point across any invocation were any calibration parameters (`ge105_v1.json`), estimator equations (`src/soc/estimators/e7v3.py`), noise covariances, acceptance thresholds, or scenario perturbations modified.
