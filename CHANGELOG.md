# Changelog — z-pinch-postproc

> **Date 2026-08-29**: project initialised.
> All notable changes to this project are documented here. Format follows
> [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Planned for v0.1
- Replace synthetic fixture with a profile derived from Gomez et al. 2024 PRL (Z-shot 2960)
- Tune the synthetic profile to be more MagLIF-realistic (T_peak ~ 3-5 keV, ρ_peak ~ 1-2 g/cc)
- Update Z-shot benchmarks doc with the new profile

### Planned for v0.2
- Replace static η_helper with a PROCESS call (Brayton/Rankine cycle)
- Add an OpenMC call for tritium breeding ratio on the liquid-Pb first wall
- Add a Paramak geometry generator for the Z-IFE concept

### Planned for v0.3
- Slutz 2021 ice-burner scaling for burn-wave propagation
- α-heating bootstrap model

See `docs/TODO.md` for the full list.

## [0.0.1-prelim] — 2026-08-29

### Added
- Initial scaffold. Standing docs (README, PLAN_v0.1, MODEL_ASSUMPTIONS_AND_LIMITATIONS, CHANGELOG, CITATION.cff, LICENSE, CONTRIBUTING.md).
- `code/zpp_bosch_hale.py` — D-T reactivity parametrisation (Hively 1983, valid 0.2-30 keV, matches Bosch-Hale 1992 to within 30%).
- `code/zpp_lawson.py` — Burn-weighted Lawson triple product ⟨nTτ⟩_DT with 3-tier classification.
- `code/zpp_pipeline.py` — Core pipeline: 1D burn integration, gain chain, stagnation pressure, convergence ratio.
- `code/zpp_io.py` — CSV / JSON input, JSON output.
- `code/zpp_run.py` — CLI entry point.
- `data/fixtures/z2960_synthetic.csv` — Synthetic near-ignition scenario (peak T=2.9 keV, peak ρ=1.85 g/cc, R_initial=0.5 cm, R_stag=0.16 cm).
- `tests/test_zpp_bosch_hale.py` — 6 tests, all pass.
- `tests/test_zpp_lawson.py` — 4 tests, all pass.
- `tests/test_zpp_io.py` — 4 tests, all pass.
- `tests/test_zpp_pipeline.py` — 4 tests, all pass.
- `docs/OPEN_SOURCE_LANDSCAPE.md` — Catalog of OSS frameworks (FLASH, WarpX, Smilei, ESTHER, OpenMC, OpenFOAM, PROCESS) we use vs don't reimplement.
- `docs/Z_SHOT_BENCHMARKS.md` — Published Z-machine + MagLIF parameters.
- `docs/TODO.md` — Deferred items for v0.1+.
- `requirements.txt` — numpy, scipy, pandas, pytest, matplotlib.
- Version-control framework files (.gitignore, .gitattributes, .githooks/pre-commit, CONTRIBUTING.md, CHANGELOG.md, VERSION) from `C:\Users\lamkuenai\tools\version-control-framework\`.

### Test summary
- 19 tests, all pass (0.31 s on Windows)
- Pipeline: synthetic shot → 46 MJ fusion yield, Q_eng=4.04, Q_target=26.9, eta_wallplug=1.62, τ_burn=7 ns, ⟨nTτ⟩=5.7e21 keV s/m³ (ignition-class), P_stag=2.07e5 GPa, CR=3.1.

### Known limitations (per MODEL_ASSUMPTIONS_AND_LIMITATIONS.md)
- Hively 1983 fit is ~30% vs Bosch-Hale 1992 in 0.2-30 keV; drifts above 30 keV (not tested).
- Synthetic fixture is a *design* scenario, not a current-MagLIF shot. Q_eng~4 here vs Q_eng<0.001 for Z 2960 real data. Real data in v0.1.
- η_helper is a static scalar (0.40 Brayton); v0.2 replaces with PROCESS.
- No alpha-heating bootstrap (v0.3).
- No TBR coupling to OpenMC (v0.2).
- 1D-only; 2D/3D effects (sausage, kink, mix) not modeled.
