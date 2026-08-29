# TODO — Deferred Items

> Tracked explicitly so the next session can pick up where this one left off.
> Format: each item has a target version, a status, and a one-line description.
> Cross-references: see `PLAN_v0.1.md` for the research plan and `MODEL_ASSUMPTIONS_AND_LIMITATIONS.md` for the limits.

## v0.1 — Real-data validation (Z-shot 2960)

- [ ] Replace `data/fixtures/z2960_synthetic.csv` with a profile derived from Gomez et al. 2024 PRL
- [ ] Tune the CLI to accept a MagLIF-style profile (1D time-series of T, ρ, ρR)
- [ ] Add a `data/external_data/` directory for published-shot data with citation
- [ ] Update the synthetic-shot fixture to be more MagLIF-realistic (T_peak ~ 3-5 keV, ρ_peak ~ 1-2 g/cc)
- [ ] Add a CSV unit test for the v0.1 real-data profile
- [ ] Add a `data/fixtures/README.md` documenting the fixture provenance

## v0.2 — Neutronics + BOP coupling

- [ ] Replace static `eta_helper` with a PROCESS call (Brayton/Rankine cycle)
- [ ] Add an OpenMC call for tritium breeding ratio on the liquid-Pb first wall
- [ ] Add a Paramak geometry generator for the Z-IFE concept (replace the doc's RTL schematic)
- [ ] Add ALARA activation calculation for the first wall
- [ ] Add a wall-plug efficiency chain that threads driver → coupling → thermal → electrical

## v0.3 — Alpha-heating + burn-wave propagation

- [ ] Implement Slutz 2021 ice-burner scaling for burn-wave propagation
- [ ] Add an alpha-heating bootstrap model (parametric, not full rad-hydro)
- [ ] Add a "fuel layer" parameter (DT ice vs DT gas) to the input contract
- [ ] Add a v0.3 validation against the Gomez 2024 scaling at 65 MA (projected)

## v0.4 — 2D effects (if needed)

- [ ] Accept a 2D profile (R, Z, t) and integrate over the burn volume
- [ ] Add a sausage/kink mix correction (empirical, from MACH2 validation)
- [ ] Add a wall-mode correction (parametric, from Sandia internal data — likely not public)

## Research roadmap (v0.5+)

- [ ] Compare Q_eng for the Z-IFE concept vs Zap Energy sheared-flow Z-pinch vs General Fusion MTF
- [ ] Compare to the published ARPA-E milestone targets (DOE Milestone Program)
- [ ] Couple to Pacific Fusion's published fast-pulser design when their technical paper is public
- [ ] Add a ZN (Z Neutron) extrapolation module for the 20-30 MJ / 65 MA class
- [ ] Add a representative-day LCOE estimate from PROCESS + the post-processor

## Standing cross-cuts

- [ ] Keep MODEL_ASSUMPTIONS_AND_LIMITATIONS.md synced with each new feature
- [ ] Keep CHANGELOG.md in Keep-a-Changelog 1.1.0 format
- [ ] Use Conventional Commits for all commit messages
- [ ] Run `pytest tests/ -v` before every commit; never commit with red tests
- [ ] Pre-commit hook (`py_compile` + 5 MB block) is intact; never skip
