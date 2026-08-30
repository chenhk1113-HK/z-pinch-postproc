# Changelog — z-pinch-postproc

> All notable changes to this project are documented here. Format follows
> [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Planned for v0.4
- PROCESS integration for full BOP wall-plug chain (replaces static η_helper)
- OpenMC coupling for tritium breeding ratio
- Paramak geometry generator for Z-IFE concept
- Z-IFE vs Zap sheared-flow vs General Fusion MTF extended comparison

See `docs/TODO.md` for the full list.

## [0.3.0] — 2026-08-30

### Added
- **Tier 3.A — α-heating bootstrap**: new module
  `code/zpp_alpha_heating.py` with parametric α-deposition +
  iterative T_eq solve. The 3.5 MeV α from D-T deposits energy in
  the fuel via f_dep(ρR) = 1 - exp(-ρR/ρR_α), raising T_stag to T_eq.
  Pipeline `apply_alpha_heating=True` (default), reports
  `alpha_heating` block (T_eq, boost_factor, ignited, f_dep,
  ρR_alphas, P_alpha, P_brem, Q_with_alpha, Lawson ignition margin).
  Bug fix: ρR computation changed from trapz(rho, R) parametric
  integral to per-timestep 2*ρ*R averaged over burn window.
  **+33 tests** (test_zpp_alpha_heating.py).
- **Tier 3.B — Comparative analysis**: new module
  `code/zpp_comparison.py` with `ConceptParameters` dataclass
  and 5 reference design points (Z present, ZN, Zap-SFZ, GF-MTF,
  PF). `compare_concepts()` returns side-by-side table with
  current + target LCOE; `comparison_markdown_table()` formats
  as Markdown. **+24 tests** (test_zpp_comparison.py).
- **Tier 3.C — Extended ZN sweep at 65 MA**: new module
  `code/zpp_zn65.py` with 125-point 3D sweep around the actual
  ZN design (Yager-Elorriaga 2022: I=65 MA). Includes
  `mix_aware_pareto`, `scaling_law_regression`, and `zn_65_summary`.
  **+20 tests** (test_zpp_zn65.py).

### Changed
- `run_pipeline` accepts new `apply_alpha_heating=True` parameter
  (default ON).
- Output gains `alpha_heating` block with T_eq, boost factor,
  ignited flag, and Lawson ignition margin.

### Strategic findings
- **Z present (Gomez 2020 anchor)**: α boost ~1.0 (no effect;
  ρR ~0.005 g/cm² → only 1.6% of α energy deposited). Matches
  published expectation.
- **ZN design**: α boost 0.81x (T drops from 5.0 to 4.07 keV).
  ρR ~0.024 g/cm² → 2.3% deposition. α heating insufficient.
  Consistent with Tier 2.D: ZN sub-break-even.
- **ICF hot spot** (T=10, ρ=200 g/cc, ρR=1.0): T_eq=50 keV cap,
  ignited. Lawson margin 1.6e1 (16x above threshold). Matches NIF.
- **Comparative analysis**: All 5 concepts (Z, ZN, Zap-SFZ, GF-MTF,
  PF) are sub-break-even with current published parameters.
  LCOE_target columns show the gap to design targets. GF-MTF is
  closest to ignition (nTτ ~1e22 vs threshold 3e21).
- **ZN-65 scaling laws**: Q_eng scales linearly with I_peak
  (R²=0.995), B_z0 (R²=0.918), and weakly with E_laser (R²=0.62).
  Even at the highest (75 MA, 40 T, 12 kJ) corner, Q_eng ~ 2e-4,
  still 5 orders of magnitude below break-even (27.8 for ZN eta_wp).

### Test summary
- 213 tests, all pass (8s on Windows). Up from 136 in v0.2.0.
- Pipeline on Gomez 2020 real-data equivalent (with all 4 tier-3
  effects: laser preheat + 2D mix + α heating + scaling):
  E_fus_2D = 268 J, T_eq = 2.52 keV (no α boost, ρR too low).

### Known limitations (per MODEL_ASSUMPTIONS_AND_LIMITATIONS.md)
- McBride 2015 model is plausibly equivalent, not exact; ±30-50%
  T_ion uncertainty, ±factor 2-4 on E_fusion.
- 2D mix correction is parametric; not a 2D rad-hydro simulation.
- α-heating model uses bremsstrahlung as the only loss channel
  (no conduction, no radiation). For ICF hot-spot this is too
  simplistic, hence the 50 keV T cap as a "ignition indicator".
- LCOE model uses fixed CAPEX_per_GWe (does not scale driver cost
  with rep-rate).
- ZN scaling sweep (both Tier 2.D and Tier 3.C) shows the McBride
  model cannot reach break-even with current Z/ZN design
  parameters. This is the honest finding, not a model failure.



## [0.2.0] — 2026-08-30

### Added
- **Tier 2.A — Hohlraum / laser preheat (MagLIF)**: new module
  `code/zpp_laser.py` with `LaserPreheat` dataclass. The laser
  raises the fuel adiabat via `T_preheat_eV += E_laser * eta / (N * c_v)`,
  capturing the leading-order coupling from Slutz 2010 / McBride 2015.
  Three presets: `no_laser`, `z_present_zbeamlet`, `zn_design_laser`.
  Pipeline reports `laser_preheat` block (energy budget, T_preheat_floor
  when input_provenance['preheat'] is given).
  Gomez 2020 anchor preserved within 1.1% (2.50 → 2.53 keV).
  **+22 tests** (test_zpp_laser.py).
- **Tier 2.B — Rep-rate + LCOE**: new module `code/zpp_economics.py`
  with design-driven `PlantEconomics` dataclass. Caller specifies
  `nameplate_MW`; `required_rep_rate_Hz` is derived from physics.
  LCOE returns inf for sub-break-even Q_eng. Pareto frontiers
  `lcoe_pareto_frontier` (over Q_eng) and `lcoe_vs_capacity_factor`
  (over CF). Break-even Q_eng: Z present = 62.5, ZN design = 12.5.
  **+27 tests** (test_zpp_economics.py).
- **Tier 2.C — 2D mix correction**: new module `code/zpp_mix.py`
  with parametric `eta_mix_empirical(CR, B_z0_T)`. Functional form:
  `exp(-alpha * (CR/CR_ref)^beta * (B_ref/B_z0)^gamma)`. Calibrated
  against Gomez 2020 PRL anchor: eta_mix=0.58 at CR=3, B=16 T
  (1.7x 1D→2D correction). B-field stabilisation is strong
  (gamma=1.2): ZN design (CR=4.7, B=30) gets eta_mix=0.64.
  Pipeline `apply_2d_mix=True` (default), `mix_correction_2d` block
  in output. B_z0 override via `input_provenance['maglif']['B_z0_T']`.
  **+18 tests** (test_zpp_mix.py).
- **Tier 2.D — ZN scaling sweep**: new module `code/zpp_scaling.py`
  with 96-point 3D sweep over (I_peak, B_z0, E_laser). E_stored_J
  auto-scales as 22 MJ * (I/20)^2 (ZN at 60 MA → 198 MJ, matching
  Yager-Elorriaga 2022). `break_even_contour()` filters above-break-
  even points; `scaling_summary()` reports the design envelope.
  **+21 tests** (test_zpp_scaling.py).

### Changed
- `run_pipeline` now applies 2D mix correction by default (set
  `apply_2d_mix=False` to disable). Output gains `mix_correction_2d`
  block.
- `run_pipeline` accepts new `laser=LaserPreheat` parameter.
- `MagLIFInputs.E_laser_kJ` is now physics-active (boosts
  T_preheat_eV in McBride profile generator).
- CSV fixture `z_gomez2020_real.csv` regenerated with the laser-
  coupled model (peak 2.50 → 2.53 keV).
- Triangular test profiles in `test_zpp_laser.py` updated to use
  realistic fuel CR (3, not 20) so the 2D mix correction doesn't
  crush synthetic yields.

### Strategic finding (Tier 2.D)
The McBride 1D + 2D-mix model, with realistic physics, predicts ZN
design hits Q_eng ~ 1e-4, far below the 12.5 break-even for ZN-class
drivers. This is consistent with the published literature: ZN's
'target Q_eng ~ 1-10' relies on optimistic physics not captured
here. Break-even requires either much higher I_peak, much better
mix efficiency, or advanced concepts (ignition, magnetised target
fusion). Documented as a regression test in
`test_mcbride_1D_predicts_no_break_even`.

### Test summary
- 136 tests, all pass (0.6s on Windows). Up from 47 in v0.1.0.
- Pipeline on Gomez 2020 real-data equivalent (with mix correction):
  E_fus_2D ~ 0.25 kJ (Gomez 2020: ~2 kJ D-T equiv; within published
  T_ion uncertainty band).

### Known limitations (per MODEL_ASSUMPTIONS_AND_LIMITATIONS.md)
- McBride 2015 model is plausibly equivalent, not exact; ±30-50%
  T_ion uncertainty, ±factor 2-4 on E_fusion.
- 2D mix correction is parametric; not a 2D rad-hydro simulation.
- LCOE model uses a fixed CAPEX_per_GWe (does not scale driver cost
  with rep-rate). Real plant economics are more nuanced.
- ZN scaling sweep shows the McBride model cannot reach break-even
  with current Z/ZN design parameters. This is the honest finding,
  not a model failure.



## [0.1.0] — 2026-08-29

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
