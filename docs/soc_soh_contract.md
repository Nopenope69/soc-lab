# SOC / SOH Interface Contract

> **Document ID**: CONTRACT-SOC-SOH-001  
> **Target Estimators**: `deliverable/bms_soc_ref.py` (`BmsSocEstimatorRef`) & `src/soh/` Estimator Suite  
> **Status**: APPROVED CONTRACT (Hardening 2 / Phase 6.3)

---

## 1. Interface Specification

The BMS State of Charge (SOC) reference estimator (`BmsSocEstimatorRef`) provides an optional coupling input `capacity_scale` in its step function:

```python
def step(
    self,
    v: float,
    i: float,
    temp_c: float,
    dt: float,
    capacity_scale: float = 1.0,
) -> SocEstimateRef:
```

### Parameters
- `v` ($V$): Measured cell terminal voltage in volts.
- `i` ($A$): Measured cell current in amperes (discharge positive per repository convention).
- `temp_c` ($^\circ\text{C}$): Cell temperature in degrees Celsius.
- `dt` ($s$): Sample interval elapsed since previous step.
- `capacity_scale` (dimensionless float): Ratio of current usable battery capacity to BOL rated capacity ($SOH_C$). Default: `1.0`.

---

## 2. Invariants and Behavioral Guarantees

1. **Bit-Identical Default**:
   When `capacity_scale == 1.0` (or omitted), the effective capacity $Q_{\text{eff}}(T)$ equals the unscaled temperature-scheduled capacity $Q(T)$ without floating-point scaling operations. This guarantees exact, bit-identical agreement ($|\Delta \text{SOC}| \le 10^{-12}$) with the frozen E7v3 baseline.

2. **Physical Capacity Scaling**:
   When `capacity_scale != 1.0`, the effective capacity utilized in Coulomb counting and process noise propagation scales as:
   $$Q_{\text{eff}}(T) = Q(T) \cdot \text{clip}(\text{capacity\_scale}, 0.10, 1.50)$$
   
   The incremental state propagation for Coulomb counting becomes:
   $$\Delta \text{SOC}_{\text{propagation}} = -\frac{\eta \cdot I \cdot \Delta t}{3600 \cdot Q_{\text{eff}}(T)}$$
   An aged cell ($SOH_C < 1.0$) experiences proportionally larger $\Delta \text{SOC}$ per ampere-hour of throughput.

3. **Safety Clamping**:
   `capacity_scale` is strictly clamped to the interval $[0.10, 1.50]$ to prevent numerical singularity or division-by-zero if an upstream estimator emits unphysical predictions.

4. **Independent SOH Resistance ($SOH_R$) Handling**:
   Impedance degradation ($SOH_R$) is tracked autonomously by the online Recursive Least Squares (RLS) filter on $R_0$ and $R_1$ inside `BmsSocEstimatorRef` during dynamic current transitions ($|\Delta I| \ge 1.0\text{ A}$), ensuring that high-frequency ohmic impedance tracking does not depend on slow-cadence external SOH updates.
