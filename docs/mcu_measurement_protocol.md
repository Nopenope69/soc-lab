# MCU Measurement Protocol: Edge SOH & SOC Inference

> **Document ID**: DOC-MCU-001  
> **Status**: APPROVED PROTOCOL  
> **Target Architectures**: 
> - ARM Cortex-M4 @ 170 MHz (e.g. STMicroelectronics STM32G474)
> - ARM Cortex-M7 @ 480 MHz (e.g. STMicroelectronics STM32H743)

---

## 1. Purpose and Scope

This protocol establishes the standardized, reproducible procedure for physically measuring the execution latency, Worst-Case Execution Time (WCET), stack memory consumption, static RAM allocation, and Flash memory footprint of edge inference algorithms (`soh_pulse_elasticnet` and `bms_soc_ref`).

Analytical approximations or cycle-count estimates derived on workstation CPUs must **never** be cited as measured hardware WCET without following this protocol.

---

## 2. Clock Configurations and Assumptions

To harmonize across all evaluation reports and simulation models:

| Target Platform | Core Architecture | Core Clock Frequency | Cache Configuration | FPU Configuration |
| :--- | :--- | :--- | :--- | :--- |
| **STM32G474** | ARM Cortex-M4 | **170.0 MHz** | ART Accelerator ON, 0-wait-state equivalent | Single-precision hardware FPv4-SP-D16 |
| **STM32H743** | ARM Cortex-M7 | **480.0 MHz** | 16 KB I-Cache ON, 16 KB D-Cache ON | Double/single-precision FPv5-D16-M |

Compiler specification: `arm-none-eabi-gcc` version 12.3.rel1 or newer, optimization level `-O2` with `-mthumb -mcpu=cortex-m4 -mfpu=fpv4-sp-d16 -mfloat-abi=hard`.

---

## 3. Physical Latency & WCET Measurement

Two complementary physical measurement channels are required:

### Method A: DWT Cycle Counter (Internal Microsecond Timing)
The ARM Data Watchpoint and Trace (DWT) unit provides cycle-accurate elapsed core clock cycles.

```c
// Initialization (run once at system startup):
CoreDebug->DEMCR |= CoreDebug_DEMCR_TRCENA_Msk;
DWT->CTRL |= DWT_CTRL_CYCCNTENA_Msk;

// Measurement harness:
uint32_t t_start = DWT->CYCCNT;
soh_pulse_predict(&pulse_features, &result);
uint32_t t_end = DWT->CYCCNT;

uint32_t elapsed_cycles = t_end - t_start - DWT_OVERHEAD_CYCLES;
float elapsed_us = ((float)elapsed_cycles / 170.0f); // for 170 MHz clock
```

### Method B: High-Speed GPIO Pin Toggling (Oscilloscope / Logic Analyzer)
A dedicated, unshared GPIO pin on an isolated I/O bank (e.g. `GPIOB_PIN_5`) is configured for maximum slew rate (Very High Speed).

```c
// Toggle pin HIGH immediately before function call, LOW immediately after
GPIOB->BSRR = (1 << 5);             // Set PB5 HIGH
soh_pulse_predict(&pulse_features, &result);
GPIOB->BSRR = (1 << (5 + 16));      // Set PB5 LOW
```

- Connect an active probe to an oscilloscope with at least 500 MHz analog bandwidth and 2.5 GSa/s sampling rate.
- Measure pulse width $\tau$ across 10,000 randomized pulse iterations.
- Record:
  - $\bar{\tau}$ (Mean latency)
  - $\tau_{\text{p99}}$ (99th percentile)
  - $\tau_{\text{max}}$ (Absolute Worst-Case Execution Time, WCET)

---

## 4. Stack and Memory Footprint Measurement

### Stack High-Water Mark (Stack Coloring)
Prior to running the inference loop:
1. Paint the entire stack memory region with a known pattern (`0xA5A5A5A5`).
2. Execute 10,000 inference steps with worst-case bounding condition inputs.
3. Inspect memory backwards from the top of the stack to identify the lowest address where the `0xA5A5A5A5` pattern was overwritten.
4. Calculate peak stack consumption:
   $$\text{Stack}_{\text{peak}} = \text{Stack}_{\text{base}} - \text{Address}_{\text{lowest\_written}}$$

### Flash and Static RAM
Extract exact section sizes from the compiled ELF artifact:
```bash
arm-none-eabi-size -A deliverable/edge_pkg/build/libsoh_edge.a
```
- **Flash (ROM)**: Sum of `.text` + `.rodata`
- **Static RAM**: Sum of `.data` + `.bss` (must be zero for pure reentrant functions).

---

## 5. Standard Output Format (`mcu_timings.json`)

When physical MCU measurements are captured, store results at `data/measurements/mcu_timings.json`:

```json
{
  "target_mcu_cortex_m4_170mhz": {
    "clock_mhz": 170.0,
    "status": "MEASURED",
    "pulse_inference_wcet_us": 0.035,
    "empirical_inference_wcet_us": 0.028,
    "tracker_step_wcet_us": 0.045,
    "complete_pipeline_inference_wcet_us": 0.108,
    "ecm_2rc_fitting_wcet_ms": 0.420,
    "inference_flash_bytes": 4096,
    "fitting_flash_bytes": 8192,
    "inference_ram_stack_bytes": 512,
    "fitting_ram_stack_bytes": 3200,
    "ram_static_bytes": 0
  },
  "target_mcu_cortex_m7_480mhz": {
    "clock_mhz": 480.0,
    "status": "MEASURED",
    "pulse_inference_wcet_us": 0.012,
    "empirical_inference_wcet_us": 0.009,
    "tracker_step_wcet_us": 0.016,
    "complete_pipeline_inference_wcet_us": 0.037,
    "ecm_2rc_fitting_wcet_ms": 0.145,
    "inference_flash_bytes": 4096,
    "fitting_flash_bytes": 8192,
    "inference_ram_stack_bytes": 512,
    "fitting_ram_stack_bytes": 3200,
    "ram_static_bytes": 0
  }
}
```
