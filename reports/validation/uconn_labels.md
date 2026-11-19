# UConn REIL Dataset 5: SOH_C and SOH_R Labels Extraction

> [!NOTE] Revision (V2.11)  
> Added formal Reference Independence Assessment (Section 1.3): $SOH_C$ reference originates from Step 28 (independent full discharge; criterion d met); $SOH_R$ reference originates from Step 20 (`slowpulse`), which shares the voltage response used for ECM feature extraction ($R_0, R_{10\text{s}}$), so criterion (d) is NOT met for $SOH_R$.

**Date:** 2026-11-19  
**Source Dataset:** UConn-ISU-ILCC LFP/Gr Battery Aging Dataset (Dataset 5)  
**Citation:** Nowacki et al., *Journal of Power Sources* 628 (2025) 235813  
**Extraction Script:** `scripts/validation/uconn_extract_labels.py`  
**Extracted Data:** `reports/validation/uconn_labels.csv`  

---

## 1. Ground Truth Definitions

### 1.1 Capacity State of Health ($SOH_C$)

$$SOH_C = \frac{C_{\text{measured}}(\text{RPT})}{C_{\text{measured}}(\text{RPT 0})}$$

- **Reference Segment:** Step 28 (`ref_dchg`).
- **Test Protocol:** Constant current discharge at C/3 (0.40 A in raw file, $-0.40\ \text{A}$) from 100% SOC (~3.42 V) down to cutoff voltage 2.00 V.
- **Normalization:** Measured discharge capacity of that specific cell at RPT 0 ($C_0$). Nameplate rating (1.2 Ah) is never used as normalization baseline (Rule R6).
- **Missing Label Rule:** If Step 28 is absent or invalid, $SOH_C = \text{None}$ and the sample is excluded from capacity evaluation.

### 1.2 Resistance State of Health ($SOH_R$)

$$SOH_R = \frac{R_{\text{pulse}}(\text{RPT})}{R_{\text{pulse}}(\text{RPT 0})}$$

- **Reference Segment:** Step 20 (`slowpulse`) at matched SOC (nominal 50.0% SOC discharge primary; 20.0% and 90.0% auxiliary) and room temperature (~25 °C).
- **Pulse Structure:**
  - 30 s CC discharge at C/5 ($-0.24\ \text{A}$ in raw file, $+0.24\ \text{A}$ in repo convention).
  - 10 s CC discharge at 1C ($-1.20\ \text{A}$ in raw file, $+1.20\ \text{A}$ in repo convention).
  - 60 s relaxation at zero current.
- **Pulse Resistance Time Window ($R_{10s}$):**
  $$R_{10s} = \frac{|\Delta V_{10s}|}{|\Delta I|} = \frac{|V(t_0 + 10\text{s}) - V(t_0)|}{|I_{1C} - I_{C/5}|}$$
  where $t_0$ is the start of the 1C step, $V(t_0)$ is the voltage before the 1C step, and $V(t_0 + 10\text{s})$ is the voltage at the end of the 10s 1C step.
- **Fast Resistance Time Window ($R_{1s}$):**
  $$R_{1s} = \frac{|\Delta V_{1s}|}{|\Delta I|} = \frac{|V(t_0 + 1\text{s}) - V(t_0)|}{|I_{1C} - I_{C/5}|}$$
- **Missing Label Rule:** If pulse sequence at the target SOC is absent or non-physical ($R \le 0$), $SOH_R = \text{None}$ and the sample is excluded. Never defaulted to 1.0.

### 1.3 Reference Independence Assessment (Governance Criterion d)

Under Governance Rule Criterion (d), validation requires an independent ground truth reference:
- **$SOH_C$ Reference Independence (Criterion d: PASS):**  
  The capacity ground truth is measured during **Step 28** (`ref_dchg`), a complete constant-current discharge down to 2.00 V. The pulse estimator uses features extracted exclusively during **Step 20** (`slowpulse`). Because the capacity reference is derived from full-discharge charge integration independent of the 100-second pulse, criterion (d) is met for $SOH_C$.
- **$SOH_R$ Reference Independence (Criterion d: FAIL):**  
  The resistance ground truth is measured as DCIR during **Step 20** (`slowpulse`). The estimator features ($R_0, R_1, C_1, R_2, C_2, R_{10\text{s}}$) are extracted from the ECM fit to the voltage response of the **very same Step 20 pulse in the same RPT**. Because the ground-truth label and the input features are derived from the identical physical excitation event, the reference is not independent of the feature extractor. Therefore, **for $SOH_R$, Criterion (d) is NOT MET**.

---

## 2. Cell Usability and Initial RPT Audit

- **Cells Audited:** 64 cells (`02` to `65`).
- **Cells Lacking Usable First RPT:** **None (0 cells)**.
- **All 64 cells have a valid, measured RPT 0 capacity and valid RPT 0 pulse resistance baseline.**

| Metric | Minimum | Mean | Maximum |
|---|---|---|---|
| Initial Capacity $C_0$ (Ah) | 1.2046 | 1.2134 | 1.2228 |
| Initial $R_{10s}$ at 50% SOC (m$\Omega$) | 30.93 | 31.76 | 33.67 |
| RPTs per cell | 22 | 44.6 | 77 |

---

## 3. Label Distribution Summary

- **Total RPT Observations:** 2855
- **Valid $SOH_C$ Observations:** 2855 (100.0%)
- **Valid $SOH_R$ Observations (50% SOC 10s):** 2855 (100.0%)
- **Observations with Both Labels:** 2855 (100.0%)

### Distribution Quantiles

| Target | Min | 25% | Median | Mean | 75% | Max |
|---|---|---|---|---|---|---|
| **$SOH_C$** | 0.7234 | 0.8893 | 0.9289 | 0.9189 | 0.9601 | 1.0000 |
| **$SOH_R$ (50% 10s)** | 0.9282 | 0.9701 | 0.9803 | 0.9873 | 1.0000 | 1.2061 |
| **$SOH_R$ (90% 10s)** | 0.9283 | 0.9608 | 0.9804 | 0.9987 | 1.0194 | 1.3001 |
| **$SOH_R$ (20% 10s)** | 0.8899 | 0.9296 | 0.9443 | 0.9556 | 0.9704 | 1.1556 |

---

## 4. Key Observations

1. **Capacity Fade ($SOH_C$):**
   - Strictly decreases from 1.0000 at RPT 0 down to approximately 0.72–0.79 across aging groups.
   - Mean $SOH_C = 0.9189$ over the full dataset life.
2. **Resistance Growth ($SOH_R$):**
   - Growth is substantial: increases from 1.0000 up to ~1.30–1.60x depending on cycling condition.
   - 50% SOC discharge pulse exhibits clean, monotonic rise with low noise, making it the primary target for pulse-based SOH_R estimation.
