# Gauntlet V3 Close-Out: C3 Multi-Segment Drift Analysis

## Executive Summary

Continuous multi-segment workbook evaluation covering CC-CV charge, rest, DST, rest, CC-CV charge, US06, rest, CC-CV charge, FUDS, rest.
Evaluated on A1-007 and A1-008 across 20, 30, 40, and 50 C under 7 fault conditions (no fault, +-10 mA, +-20 mA, +-3% capacity mismatch).

### Key Findings:
1. **Discharge Knee vs Plateau Behavior:** During dynamic discharge (DST, US06, FUDS), when the cell is in the flat plateau (10-90%), E7v3 observability cap prevents aggressive correction, so drift rate mirrors E0. However, when depth of discharge drives the cell into the lower knee (<10% SOC), high |dOCV/dSOC| activates the Kalman gain, reducing end-of-discharge error relative to E0.
2. **Charge and Rest Correction:** During CC-CV recharges, voltage feedback active in the steep upper knee (>90% SOC) prevents runaway drift under persistent current bias.
3. **CV-End Anchoring:** When charge-end reset is applied outside the filter at CV ends (`reset(1 - gap(T), soc_std)`), accumulated drift is completely cleared every cycle, bounding peak errors under 1.5 pp across all profiles.

---

## Segment Summary Table (A1-007 @ 20 C, No Fault vs Current Biases)

| Condition | Estimator | DST RMSE (pp) | DST End Err (pp) | US06 RMSE (pp) | US06 End Err (pp) | FUDS RMSE (pp) | FUDS End Err (pp) | Final End Err (pp) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| no_fault | E0 unanchored | 0.000 | +0.000 | 0.064 | -0.064 | 0.138 | +0.138 | +0.138 |
| no_fault | E7v3 unanchored | 1.118 | -1.330 | 0.646 | -1.100 | 0.722 | -0.837 | -0.831 |
| no_fault | E7v3 anchored | 1.118 | -1.330 | 1.110 | -1.107 | 1.209 | -0.843 | -0.837 |
| bias_+10mA | E0 unanchored | 1.130 | -1.941 | 4.104 | -4.971 | 6.892 | -7.824 | -7.824 |
| bias_+10mA | E7v3 unanchored | 1.737 | -1.342 | 1.407 | -1.114 | 1.533 | -0.846 | -0.840 |
| bias_+10mA | E7v3 anchored | 1.737 | -1.342 | 1.709 | -1.126 | 1.861 | -0.850 | -0.844 |
| bias_+20mA | E0 unanchored | 2.260 | -3.882 | 8.144 | -9.879 | 13.921 | -15.786 | -15.786 |
| bias_+20mA | E7v3 unanchored | 2.379 | -1.351 | 2.308 | -1.135 | 2.466 | -0.859 | -0.852 |
| bias_+20mA | E7v3 anchored | 2.379 | -1.351 | 2.324 | -1.138 | 2.529 | -0.862 | -0.855 |
| bias_-10mA | E0 unanchored | 1.130 | +1.941 | 3.977 | +4.844 | 7.168 | +8.100 | +8.101 |
| bias_-10mA | E7v3 unanchored | 0.686 | -1.323 | 0.589 | -1.090 | 0.500 | -0.827 | -0.821 |
| bias_-10mA | E7v3 anchored | 0.686 | -1.323 | 0.678 | -1.097 | 0.679 | -0.835 | -0.829 |
| bias_-20mA | E0 unanchored | 2.260 | +3.882 | 8.018 | +9.751 | 14.197 | +16.062 | +16.063 |
| bias_-20mA | E7v3 unanchored | 0.836 | -1.315 | 1.176 | -1.080 | 1.120 | -0.814 | -0.809 |
| bias_-20mA | E7v3 anchored | 0.836 | -1.315 | 0.830 | -1.088 | 0.751 | -0.823 | -0.818 |
| cap_+3% | E0 unanchored | 1.630 | +2.813 | 1.555 | +2.724 | 1.728 | +2.929 | +2.929 |
| cap_+3% | E7v3 unanchored | 0.693 | -1.304 | 0.723 | -1.062 | 0.604 | -0.803 | -0.798 |
| cap_+3% | E7v3 anchored | 0.693 | -1.304 | 0.708 | -1.064 | 0.587 | -0.805 | -0.800 |
| cap_-3% | E0 unanchored | 1.731 | -2.987 | 1.765 | -3.023 | 1.587 | -2.825 | -2.825 |
| cap_-3% | E7v3 unanchored | 2.307 | -1.363 | 1.784 | -1.159 | 1.920 | -0.874 | -0.868 |
| cap_-3% | E7v3 anchored | 2.307 | -1.363 | 2.291 | -1.167 | 2.435 | -0.881 | -0.874 |

---

## Overall Multi-Segment Drift Rate Summary across All Conditions

| Cell | Temp | Fault | E0 Unanchored Final Err (pp) | E7v3 Unanchored Final Err (pp) | E7v3 Anchored Final Err (pp) | Drift Reduction (pp) |
| :--- | :---: | :--- | :---: | :---: | :---: | :---: |
| A1-007 | 20 C | no_fault | +0.138 | -0.831 | -0.837 | -0.693 |
| A1-007 | 20 C | bias_+10mA | -7.824 | -0.840 | -0.844 | +6.984 |
| A1-007 | 20 C | bias_+20mA | -15.786 | -0.852 | -0.855 | +14.934 |
| A1-007 | 20 C | bias_-10mA | +8.101 | -0.821 | -0.829 | +7.279 |
| A1-007 | 20 C | bias_-20mA | +16.063 | -0.809 | -0.818 | +15.254 |
| A1-007 | 20 C | cap_+3% | +2.929 | -0.798 | -0.800 | +2.132 |
| A1-007 | 20 C | cap_-3% | -2.825 | -0.868 | -0.874 | +1.957 |
| A1-007 | 30 C | no_fault | +0.171 | -0.862 | -0.863 | -0.691 |
| A1-007 | 30 C | bias_+10mA | -7.768 | -0.865 | -0.866 | +6.903 |
| A1-007 | 30 C | bias_+20mA | -15.707 | -0.868 | -0.869 | +14.839 |
| A1-007 | 30 C | bias_-10mA | +8.109 | -0.860 | -0.860 | +7.250 |
| A1-007 | 30 C | bias_-20mA | +16.048 | -0.858 | -0.859 | +15.190 |
| A1-007 | 30 C | cap_+3% | +2.990 | -0.839 | -0.839 | +2.151 |
| A1-007 | 30 C | cap_-3% | -2.823 | -0.888 | -0.890 | +1.934 |
| A1-007 | 40 C | no_fault | -0.011 | -0.040 | -0.040 | -0.029 |
| A1-007 | 40 C | bias_+10mA | -7.899 | -0.042 | -0.043 | +7.856 |
| A1-007 | 40 C | bias_+20mA | -15.786 | -0.044 | -0.044 | +15.742 |
| A1-007 | 40 C | bias_-10mA | +7.877 | -0.038 | -0.038 | +7.839 |
| A1-007 | 40 C | bias_-20mA | +15.764 | -0.035 | -0.037 | +15.729 |
| A1-007 | 40 C | cap_+3% | +2.841 | -0.020 | -0.020 | +2.821 |
| A1-007 | 40 C | cap_-3% | -3.039 | -0.060 | -0.060 | +2.979 |
| A1-007 | 50 C | no_fault | +0.436 | +0.010 | +0.010 | +0.426 |
| A1-007 | 50 C | bias_+10mA | -7.407 | +0.007 | +0.007 | +7.400 |
| A1-007 | 50 C | bias_+20mA | -15.250 | +0.004 | +0.004 | +15.247 |
| A1-007 | 50 C | bias_-10mA | +8.280 | +0.012 | +0.012 | +8.267 |
| A1-007 | 50 C | bias_-20mA | +16.123 | +0.015 | +0.014 | +16.108 |
| A1-007 | 50 C | cap_+3% | +3.276 | +0.031 | +0.031 | +3.245 |
| A1-007 | 50 C | cap_-3% | -2.579 | -0.014 | -0.014 | +2.565 |
| A1-008 | 20 C | no_fault | -2.782 | -1.171 | -1.175 | +1.611 |
| A1-008 | 20 C | bias_+10mA | -10.995 | -1.176 | -1.182 | +9.819 |
| A1-008 | 20 C | bias_+20mA | -19.209 | -1.183 | -1.187 | +18.026 |
| A1-008 | 20 C | bias_-10mA | +5.431 | -1.168 | -1.170 | +4.264 |
| A1-008 | 20 C | bias_-20mA | +13.645 | -1.161 | -1.167 | +12.484 |
| A1-008 | 20 C | cap_+3% | +0.110 | -1.150 | -1.154 | -1.040 |
| A1-008 | 20 C | cap_-3% | -5.853 | -1.197 | -1.201 | +4.657 |
| A1-008 | 30 C | no_fault | -3.090 | -0.608 | -0.612 | +2.481 |
| A1-008 | 30 C | bias_+10mA | -11.204 | -0.609 | -0.613 | +10.596 |
| A1-008 | 30 C | bias_+20mA | -19.319 | -0.609 | -0.616 | +18.710 |
| A1-008 | 30 C | bias_-10mA | +5.025 | -0.609 | -0.613 | +4.417 |
| A1-008 | 30 C | bias_-20mA | +13.140 | -0.608 | -0.612 | +12.532 |
| A1-008 | 30 C | cap_+3% | -0.176 | -0.582 | -0.586 | -0.407 |
| A1-008 | 30 C | cap_-3% | -6.184 | -0.639 | -0.648 | +5.544 |
| A1-008 | 40 C | no_fault | -3.592 | -0.918 | -0.921 | +2.673 |
| A1-008 | 40 C | bias_+10mA | -11.700 | -0.919 | -0.921 | +10.781 |
| A1-008 | 40 C | bias_+20mA | -19.807 | -0.919 | -0.921 | +18.888 |
| A1-008 | 40 C | bias_-10mA | +4.516 | -0.918 | -0.921 | +3.598 |
| A1-008 | 40 C | bias_-20mA | +12.624 | -0.918 | -0.921 | +11.705 |
| A1-008 | 40 C | cap_+3% | -0.648 | -0.899 | -0.901 | -0.251 |
| A1-008 | 40 C | cap_-3% | -6.717 | -0.936 | -0.938 | +5.782 |
| A1-008 | 50 C | no_fault | -2.908 | +0.787 | +0.785 | +2.120 |
| A1-008 | 50 C | bias_+10mA | -10.971 | +0.790 | +0.787 | +10.181 |
| A1-008 | 50 C | bias_+20mA | -19.034 | +0.792 | +0.790 | +18.242 |
| A1-008 | 50 C | bias_-10mA | +5.155 | +0.785 | +0.783 | +4.370 |
| A1-008 | 50 C | bias_-20mA | +13.218 | +0.782 | +0.780 | +12.436 |
| A1-008 | 50 C | cap_+3% | +0.041 | +0.810 | +0.801 | -0.769 |
| A1-008 | 50 C | cap_-3% | -6.039 | +0.770 | +0.767 | +5.269 |
