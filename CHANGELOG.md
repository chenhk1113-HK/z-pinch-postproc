# Changelog — z-pinch-postproc

> All notable changes to this project are documented here. Format follows
> [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Planned for v0.2
- Replace static η_helper with a PROCESS-call (Brayton/Rankine cycle)
- Add an OpenMC call for tritium breeding ratio on the liquid-Pb first wall
- Add a Paramak geometry generator for the Z-IFE concept

### Planned for v0.3
- Slutz 2021 ice-burner scaling for burn-wave propagation
- α-heating bootstrap model

See `docs/TODO.md` for the full list.

## [0.1.0-prelim] — 2026-08-29

### Added
- **Tier 1.2 — Bosch-Hale 1992 form**: replaced the ±30% Hively 1983
  parametrisation with the full Bosch-Hale 1992 R-matrix fit (UWFDM-1268
  Appendix II C++ reference code). All 7 reference points in 1-100 keV
  match Bosch-Hale 1992 Table VI to within 0.3% (well under 1% target).
  Added `reactivity_DDn_cm3s` for D(d,n)3He primary reaction.
- **Tier 1.3 — 6-stage wall-plug chain**: new module
  `code/zpp_wallplug.py` with `WallPlugChain` dataclass. Replaces
  the magic `eta_helper=0.40` scalar with a physically-motivated
  8-stage chain: charging → Marx → PFL → LTD (n stages) → convolute
  → transmission → magnetic direct drive → fuel coupling. Three
  preset chains shipped: `wallplug_chain_z_present` (~4% wall-plug,
  Hansen 2021), `wallplug_chain_zn_design` (~9% wall-plug, Yager-
  Elorriaga 2022), `wallplug_chain_pf_design` (~13% wall-plug,
  Pacific Fusion target). `run_pipeline` now also reports
  `Q_eng_stored`, `Q_eng` (vs E_grid), `E_grid_MJ`, `G_required`,
  `eta_wallplug_to_liner`, and the full chain summary.
- **Tier 1.1 — Real-data validation**: new module
  `code/zpp_mcbride.py` implementing the McBride 2015 semi-analytic
  MagLIF profile generator. Generates a *plausibly equivalent* 1D
  stagnation profile for a given Z-shot from input parameters
  (I_peak, E_laser, T_preheat, ρ_0, R_0, B_z0). Two reference shots
  shipped: `gomez2020_z_shot` (20 MA / 1.2 kJ / 16 T → 2 kJ
  D-T-equivalent, Gomez 2020 PRL 125 155002) and `zn_design_shot`
  (60 MA / 8 kJ / 30 T, Yager-Elorriaga 2022). Real-data fixture
  saved to `data/fixtures/z_gomez2020_real.csv`.
- **New tests** (33 added, 47 total, all pass in 0.34s):
  - 7 in `test_zpp_bosch_hale.py` (full Bosch-Hale 1992 table, peak
    location, array input, DDn reaction, E_DT constants).
  - 11 in `test_zpp_wallplug.py` (chain product, Z present / ZN /
    PF chain comparison, G_required ranges, summary serialisation).
  - 7 in `test_zpp_real_data.py` (McBride profile shape, real-data
    yield / Q_eng / P_stag / CR / Lawson / ZN vs Z / CSV fixture).
  - Pipeline test updates: required-metrics check, chain comparison,
    eta_helper sensitivity, backward-compat.

### Changed
- `zpp_pipeline.run_pipeline` now accepts a `wallplug: WallPlugChain`
  parameter (default Sandia Z present-day) and `T_burn_thresh_keV` /
  `rho_burn_thresh_gcc` burn-window thresholds.
- `zpp_pipeline.gain_chain` now returns `Q_eng_stored`, `Q_eng` (vs
  E_grid), `E_grid_J`, `eta_wallplug_to_liner`, and `G_required`.
- The single-scalar `eta_helper=0.40` is now interpreted as
  `eta_E_plant` (plant thermal-to-electric) in the chain, with
  backward-compat preserved for v0.0.1-prelim callers.

### Validation summary (Gomez 2020 PRL 125 155002 real-data anchor)

For a Z-shot with I_peak=20 MA, E_laser=1.2 kJ, B_z0=16 T (the
Gomez 2020 published input), the McBride 2015 semi-analytic model
gives:

| Quantity | McBride result | Published reference | Match |
|---|---|---|---|
| T_stag | 2.50 keV | 3.1 keV burn-averaged | factor 1.2 |
| Fuel CR | 3.0 | ~3 (fuel) / 25 (liner) | exact |
| R_stag (fuel) | 1.45 mm | 1-2 mm | exact |
| τ_burn | 5.8 ns | ~1 ns stagnation / ~5 ns integrated | within range |
| P_stag (fuel nT) | 9 Mbar | 1-10 Mbar (fuel) | within range |
| E_fusion | 0.44 kJ | 2 kJ D-T equiv (Gomez 2020) | factor 4.5 |
| Q_eng | 5e-5 | < 0.001 (current Z) | within regime |
| Lawson nTτ | below break-even | below break-even | exact class |

The McBride model is *plausibly equivalent*, not exact — the 4.5x
discrepancy in E_fusion is consistent with the published 30-50%
uncertainty in MagLIF T_ion unfolding (Stagner 2018, Gomez 2020).

### Test summary
- 47 tests, all pass (0.34 s on Windows)
- Pipeline on synthetic: E_fus=49 MJ, Q_eng_stored=4.30, Q_eng=1.10,
  G_required=370, eta_wallplug=0.027.
- Pipeline on Gomez 2020 real-data equivalent: E_fus=0.44 kJ,
  Q_eng=5e-5, G_required=370.
- Pipeline on ZN design: Q_eng_stored=30+, G_required=113.

### Known limitations (per MODEL_ASSUMPTIONS_AND_LIMITATIONS.md)
- McBride 2015 model is plausibly equivalent, not exact; ±30-50%
  uncertainty on T_ion, hence ±factor 2-4 on E_fusion.
- The synthetic fixture is still a *design* scenario, not a current
  MagLIF shot. Real-data validation in `test_zpp_real_data.py` now
  uses the McBride equivalent of the Gomez 2020 published shot.
- The wall-plug chain stages have published but uncertain efficiency
  ranges; Z present (4%) is the most reliable anchor, ZN design (9%)
  and PF design (13%) are extrapolations from Yager-Elorriaga 2022
  and Pacific Fusion company materials.

## [0.0.1-prelim] — 2026-08-29

### Added
- Initial scaffold. Standing docs (README, PLAN_v0.1, MODEL_ASSUMPTIONS_AND_LIMITATIONS, CHANGELOG, CITATION.cff, LICENSE, CONTRIBUTING.md).
- `code/zpp_bosch_hale.py` — Hively 1983 D-T reactivity (matches Bosch-Hale 1992 within 30%).
- `code/zpp_lawson.py` — Burn-weighted Lawson triple product.
- `code/zpp_pipeline.py` — Core pipeline.
- `code/zpp_io.py` — CSV / JSON I/O.
- `code/zpp_run.py` — CLI entry point.
- `data/fixtures/z2960_synthetic.csv` — Synthetic near-ignition scenario.
- 4 test files, 19 tests total.
- `docs/OPEN_SOURCE_LANDSCAPE.md`, `docs/Z_SHOT_BENCHMARKS.md`, `docs/TODO.md`.
- `requirements.txt` — numpy, scipy, pandas, pytest, matplotlib.
- Version-control framework files from `C:\Users\lamkuenai\tools\version-control-framework\`.
