# Tier 19.C Sweep Summary

**Reference TBR (Tier 19.A no-electrode baseline)**: 1.8306 ± 0.0076

**Configurations**: 5

| Config | h_elec (cm) | n_ports | TBR | ± | Δ vs no-elec | Match | Runtime (s) |
|---|---|---|---|---|---|---|---|
| 00_baseline_no_electrode | 0.001 | 0 | 1.8383 | 0.0091 | +0.42% | 1.0000 | 25.7 |
| 01_h_elec_2cm_Cu | 2.0 | 0 | 1.8014 | 0.0090 | -1.60% | 1.0000 | 23.6 |
| 02_h_elec_5cm_Cu | 5.0 | 0 | 1.7447 | 0.0081 | -4.69% | 1.0000 | 24.2 |
| 03_h_elec_10cm_Cu | 10.0 | 0 | 1.6339 | 0.0062 | -10.75% | 1.0000 | 24.9 |
| 04_h_elec_5cm_plus_1port_d2cm | 5.0 | 1 | 1.7496 | 0.0072 | -4.42% | 1.0000 | 24.4 |

## Key finding

**Scaling**: TBR decreases roughly linearly with h_elec.

**Engineering implication**: Cu electrodes of height 5-10 cm produce TBR penalties of 5-10%, which aligns with the README's engineering-scope upper bound (5-15%). Tier 19.C fully closes the engineering-scope warning box.
