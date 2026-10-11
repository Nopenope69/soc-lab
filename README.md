# SOC Estimation Lab

A rigorous benchmark harness for battery State-of-Charge (SOC) estimation algorithms (E0 through E7) on Lithium Iron Phosphate (LFP) cells.

## Timing Convention
- **Sample $k$ measurement:** At sample $k$, the plant applies current $i_k$ to state $x_k$. The measurement carries $v_k$ (terminal voltage at $x_k$ under $i_k$), $i_k$, temperature $T_k$, and time step $\Delta t$.
- **Truth state $k$:** Truth recorded at sample $k$ is the state after the step, $x_{k+1}$.
- **Estimator step:** `Estimator.step(measurement)` must return the estimate of $x_{k+1}$. It first updates on $v_k$ using its prior for $x_k$, then propagates forward with $i_k$ over $\Delta t$.
- **Evaluation:** Metrics compare estimate $k$ with truth $k$, which both refer to the identical post-step instant $x_{k+1}$.

## Dropped Samples
When `Measurement.dropout` is True, measurement values (`v`, `i`, `temp_c`) are NaN. Estimators execute only the time-update (predict) step and skip the measurement correction (update) step. The evaluation harness holds the last estimate across dropouts and excludes dropped steps from metric calculations.

## Assumptions System
All configurable parameters live in YAML under `configs/assumptions/`. Layered resolution order:
`base.yaml` $\to$ `profiles/{automotive,bess}.yaml` $\to$ `scenarios/*.yaml` $\to$ CLI `--set path.to.key=value`.
Every parameter is strictly validated via Pydantic with explicit bounds, units, notes, and statuses (`placeholder`, `assumed`, `measured`, `fitted`).
Derived quantities (e.g. $C_j = \tau_j / R_j$) are computed in exactly one place dynamically.

## Quick Start
```bash
make test     # Run all unit and analytic tests
make smoke    # Run smoke scenario (<60s) for E0, E1, E2
```
