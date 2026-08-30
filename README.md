# z-pinch-postproc

> **Disclaimer:** Personal research project, AI-assisted (Hermes with MiniMax M3 as the coder).
> Not a production tool. Not peer-reviewed. Not associated with Sandia National Laboratories,
> Pacific Fusion, Zap Energy, or any other fusion program.

**A small, pure-Python post-processor for Z-pinch fusion shots.** Ingests a 1D radiation-MHD
profile of the imploded fuel (from FLASH, ESTHER, HYDRA-class simulators, or a synthetic
fixture), integrates the D-T reactivity (Bosch-Hale) over the burn history, and computes
the engineering metrics that matter for a Z-pinch fusion power plant:

- **Fusion yield** E_fus [J]
- **Target gain** Q_target = E_fus / E_kinetic (liner KE)
- **Engineering gain** Q_eng = E_fus / E_stored (Marx bank / LTD)
- **Wall-plug efficiency** η_wp = E_fus / E_grid
- **Burn-weighted Lawson triple product** ⟨nTτ⟩_DT
- **Burn duration** τ_burn [ns]
- **Stagnation pressure** P_stag [GPa]
- **Convergence ratio** CR = R_initial / R_stagnation

The output JSON is a single record with all eight metrics plus the input parameter
provenance (n_live, sampler seed, simulator source) for reproducibility.

## What this is NOT

- Not a rad-MHD code. We read other simulators' output, we don't run them.
- Not a driver-circuit model. We take the driver current as input.
- Not a neutronics / blanket / BOP model. Those are separate frameworks (OpenMC,
  OpenFOAM, PROCESS) and the engineering gain chain is computed with a simple
  η_helper efficiency factor.
- Not a Z-pinch-only restricted code. The same post-processor works for any
  magnetized-fuel inertial-fusion concept (MagLIF, HED FRC, staged Z-pinch)
  provided the input profile has the right columns.

## Quick start

```bash
git clone <repo>
cd z-pinch-postproc
python -m pip install -r requirements.txt          # numpy, scipy, pandas
python code/zpp_run.py --input data/fixtures/z2960_synthetic.csv \
                       --driver-E_MJ 11.5 --driver-eff 0.15 \
                       --output outputs/z2960_first_run.json
# Inspect: cat outputs/z2960_first_run.json
# Tests:   pytest tests/
```

## Repo layout

```
z-pinch-postproc/
├── README.md                              ← you are here
├── PLAN_v0.1.md                           ← research plan + roadmap
├── MODEL_ASSUMPTIONS_AND_LIMITATIONS.md   ← single-page assumption list
├── CHANGELOG.md                           ← per-round history
├── VERSION                                ← 0.0.1-prelim
├── CITATION.cff                           ← GitHub-native citation metadata
├── requirements.txt                       ← pinned numpy, scipy, pandas
│
├── code/
│   ├── zpp_run.py                         ← CLI: ingest CSV/JSON, write report
│   ├── zpp_pipeline.py                    ← core: integrate reactivity + chain gains
│   ├── zpp_bosch_hale.py                  ← D-T reactivity <σv> parametrisation
│   ├── zpp_lawson.py                      ⟨nTτ⟩_DT integrator
│   ├── zpp_io.py                          ← CSV / JSON reader + writer
│   └── zpp_figures.py                     ← matplotlib plot helpers
│
├── data/
│   ├── fixtures/                          ← synthetic shots for testing
│   ├── external_data/                     ← published Z-shot parameters (cite source!)
│   └── runs/                              ← per-shot outputs (gitignored)
│
├── docs/
│   ├── OPEN_SOURCE_LANDSCAPE.md           ← FLASH, WarpX, Smilei, etc. (locked review)
│   ├── Z_SHOT_BENCHMARKS.md               ← published MagLIF shot parameters
│   └── TODO.md                            ← deferred items
│
├── tests/
│   ├── test_zpp_bosch_hale.py             ← reactivity parametrisation vs table
│   ├── test_zpp_pipeline.py               ← end-to-end on synthetic shot
│   ├── test_zpp_lawson.py                 ⟨nTτ⟩_DT integrator
│   └── fixtures/                          ← tiny test-only CSVs
│
└── .githooks/pre-commit                   ← py_compile + large-file block
```

## Standing version

`0.7.0` (2026-08-30) — v0.7 shipped with 609 tests. Three of four upstream
fusion engineering codes now integrated (PROCESS + OpenMC + Paramak).
Monte Carlo uncertainty quantification. FISPACT-II requires UKAEA license
(manual install only). See `docs/RELEASE_v0.7.0.md` for full release notes
and `CHANGELOG.md` for per-tier history.

## Where to start reading

1. **`PLAN_v0.1.md`** — what the project is trying to do, what's in v0.1 scope, what's deferred
2. **`MODEL_ASSUMPTIONS_AND_LIMITATIONS.md`** — every assumption and approximation in one place
3. **`docs/OPEN_SOURCE_LANDSCAPE.md`** — what already exists, what we use, what we build on
4. **`docs/Z_SHOT_BENCHMARKS.md`** — published MagLIF shot parameters we'll validate against
5. **`code/zpp_run.py`** — the CLI entry point
6. **This file** — the high-level map

## License

MIT — see `LICENSE`.

## See also

- `CONTRIBUTING.md` — branching model, commit format, version-bump policy
- `CHANGELOG.md` — per-round history (Keep a Changelog 1.1.0 format)
- `docs/TODO.md` — known deferred items
