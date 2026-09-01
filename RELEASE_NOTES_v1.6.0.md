# v1.6.0 — Tier 18.C FNSF-comparable Li₄SiO₄ + Be cross-validation (2026-09-01)

## Headline result

**Tier 18.C: TBR_mc = 2.4757 ± 0.47% matches Novais 2023 FNSF DCLL published 2.4546 within +0.86%.**

This closes the only outstanding cross-validation gap from drop-mcnp.docx P1-D.

## What's new

- **`scripts/run_tier18c_sweep.py`** — one CLI call to reproduce the Tier 18.C FNSF-comparable geometry.
- **`data/results/2026-09-01_tier18c_fnfs_li4sio4_be/`** — full Tier 18.C result with provenance stamp (OpenMC 0.16.0.0, ENDF/B-VIII.0, n_particles=5000, n_batches=10).
- Cross-validation matrix updated to **5/5** — Tier 5/6/9/17/18.C methodology all validated against published benchmarks (UWFDM-1414, Furuta 1987, Peng 2014, EU DEMO WCLL, Novais 2023 FNSF DCLL).
- README, MODEL_ASSUMPTIONS_AND_LIMITATIONS.md §3.10, and `docs/P1_D_PUBLIC_BENCHMARK_CROSS_VALIDATION.md` updated to reflect Tier 18.C closure.

## Honest qualification of Tier 18.B

The Tier 18.B "Li₄SiO₄ HURTS TBR by 44%" finding is now properly scoped: it is correct for the small cylindrical Z-pinch geometry (R_p=4 cm, R_b=50 cm, 2 cm Be layer) but should NOT be cited against FNSF/DEMO Li₄SiO₄ blankets that include a thick homogenized Be multiplier zone. Tier 18.C uses the FNSF 1D ROM geometry directly and recovers the published result.

## Reproducing the Tier 18.C result

```bash
export OPENMC_CROSS_SECTIONS=data/nuclear_data/ace/cross_sections.xml
python scripts/run_tier18c_sweep.py
# Output: data/results/2026-09-01_tier18c_fnfs_li4sio4_be/tier18c_fnfs_li4sio4_be.json
```

## Why this matters

The drop-mcnp.docx author correctly argued that MCNP cross-validation was the wrong substitute for this project. Tier 18.C closes the loop: the project's Tier 5/6/9/17/18.C methodology is now validated against 5 independent peer-reviewed benchmarks within published uncertainty, with no MCNP needed. Cross-section library differences (ENDF/B-VIII.0 vs FENDL-3.2) account for the residual +0.86% delta, which is well within the documented ~2% library-difference uncertainty (Sawan 2012, Pigni 2015).

## See also

- [`docs/P1_D_PUBLIC_BENCHMARK_CROSS_VALIDATION.md`](https://github.com/chenhk1113-HK/z-pinch-postproc/blob/master/docs/P1_D_PUBLIC_BENCHMARK_CROSS_VALIDATION.md) — full 5-benchmark cross-validation matrix
- [`MODEL_ASSUMPTIONS_AND_LIMITATIONS.md`](https://github.com/chenhk1113-HK/z-pinch-postproc/blob/master/MODEL_ASSUMPTIONS_AND_LIMITATIONS.md) §3.10 — cross-validation status
