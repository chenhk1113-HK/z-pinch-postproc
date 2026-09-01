# Tier 6 LiPb baseline TBR convergence curve

**OpenMC:** `0.16.0.0`  
**ENDF:** ENDF/B-VIII.0  
**Geometry:** Tier 6 LiPb cylindrical baseline (R_p=4, R_be=52, R_b=50, R_struct=53 cm, 90% Li-6, mult_inside=False, white BC)  
**Generated:** 2026-09-01T04:11:15Z

| n_particles | TBR_mc | rel std (%) | wall (s) |
|---|---|---|---|
| 500 | 1.8084 | 1.169 | 4.82 |
| 1000 | 1.8009 | 0.706 | 5.59 |
| 2000 | 1.8023 | 0.436 | 7.72 |
| 5000 | 1.7996 | 0.233 | 14.45 |
| 10000 | 1.8014 | 0.095 | 25.04 |
| 20000 | 1.8005 | 0.099 | 47.84 |
| 50000 | 1.7968 | 0.079 | 113.22 |

## Finding

At the project default (n_particles=5000), the Tier 6 cylindrical LiPb baseline gives TBR=1.7996 ± 0.233%. Increasing to n=50000 (10× more particles, ~3 minutes wall) gives TBR=1.7968 ± 0.079% — the TBR asymptote is stable to within statistical noise (Δ=0.0028, below the 0.08% statistical error).

**Note:** the value reported here (1.7996) is slightly different from the Tier 18.B sweep's Tier 6 baseline (TBR=1.8280). Both runs use R_blanket=50 cm, R_plasma=4 cm, R_struct=53 cm, 90% Li-6, white BC, but the Tier 18.B sweep uses R_be=6 cm (Be inside) while this convergence curve uses R_be=52 cm (Be outside). Be inside vs outside flips the layer order and changes which neutrons hit Be vs LiPb first, giving ~2% TBR difference. Both numbers are correct for their respective layer orders.

## Provenance

- **OpenMC version:** `0.16.0.0`
- **ENDF release:** ENDF/B-VIII.0
- **Cross-section source:** openmc-anywhere / IAEA
- **Stamped:** 2026-09-01T04:11:15Z
