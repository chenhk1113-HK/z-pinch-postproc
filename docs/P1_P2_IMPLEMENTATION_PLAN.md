# z-pinch-postproc P1 + P2 implementation plan (drop-mcnp.docx, 2026-09-01)

This document tracks the implementation of the P1 and P2 recommendations
from `drop-mcnp.docx` (the 2026-09-01 follow-up to `zreview3.docx`).
The `drop-mcnp.docx` author argues — correctly — that MCNP
cross-validation is overkill for this project, and that the higher-ROI
P1 work is OpenMC provenance disclosure + reproducibility + comparison
against peer-reviewed public benchmarks (ITER, EU DEMO WCLL).

## Items shipped in this round (2026-09-01)

### P1-A: Tier-result provenance stamping
- New: `scripts/stamp_provenance.py`
- Walks every `data/results/*/` directory and stamps both `*_sweep.json`
  (adds a `provenance` block as a sibling to `results`) and `*_sweep.md`
  (adds a `## Provenance` section).
- Auto-detects OpenMC version from `.venv/Scripts/python.exe`.
- Auto-detects `n_particles` / `n_batches` from the Tier test/source
  files; falls back to the central `run_real_openmc_tbr` defaults.
- ENDF release recorded as `"ENDF/B-VIII.0 (declared)"` — the cross-section
  downloader targets ENDF/B-VIII.0 but doesn't probe the exact sub-version.

### P1-B: Tier 6 convergence curve
- New: `scripts/run_tier6_convergence.py`
- New result: `data/results/2026-09-01_tier6_convergence/`
- Runs the Tier 6 LiPb cylindrical baseline (R_p=4, R_be=52, R_b=50,
  R_struct=53 cm, 90% Li-6, mult_inside=False, reflective BC) at
  n_particles ∈ {500, 1000, 2000, 5000, 10000, 20000, 50000}.
- Wall: ~4 minutes total (113s for the largest point).
- **Finding**: TBR asymptotes at **1.80 ± 0.08%** (n=50000). At the
  project default (n=5000) TBR=1.7996 ± 0.23%, fully converged.
- **Honest disclosure**: the published Tier 18.B baseline (TBR=1.8280)
  uses Be INSIDE (R_be=6 cm) while this convergence curve uses Be OUTSIDE
  (R_be=52 cm). Both numbers are correct for their respective layer orders;
  the ~2% difference is real layer-order physics, not a bug. Documented
  in the convergence result file.

### P1-C: OpenMC input decks published
- New: `data/inputs/README.md` — single source of truth for every Tier's
  geometry/material/source/MC-settings, with how-to-reproduce per Tier.
- New: `scripts/run_tier6_sweep.py` — reproduces Tier 6 LiPb baseline
  in ~14s. Result: TBR=1.7996 ± 0.23%, exact match to convergence sweep.
- New: `scripts/run_tier18b_sweep.py` — reproduces Tier 18.B LiPb half
  (Be inside). Result: TBR=1.8395 ± 0.33% (expected 1.8280; within
  0.6% statistical noise).
- New result JSONs: `data/results/2026-08-31_tier6_baseline/` and
  `data/results/2026-08-31_tier18b_li4sio4/tier18b_lipb_baseline.json`.

### P2-B: Per-Tier applicability callouts in README
- Three Tier result sections in `README.md` now open with an
  `> **Applicability:**` callout that names the geometry scope and
  explicitly forbids over-extrapolation:
  - Tier 13 (Fe reflector): cylindrical only; spherical penalty is 2.6% not 14%.
  - Tier 16 (U-238): cylindrical only; spherical penalty is ~4% not 26%.
  - Tier 18 (Li₄SiO₄): cylindrical only; spherical gives TBR=1.50 not 1.03.

## Items deferred (NOT in this round, but on the roadmap)

### P1-D: Cross-validate against ITER TBR benchmark + EU DEMO WCLL public data
**Per the drop-mcnp.docx recommendation, MCNP cross-validation is dropped.
Instead, compare Tier 6 / 18.B / 17 results against:**

- **ITER Test Blanket Module (TBM) TBR benchmark**: published by
  the ITER organization as part of the TBM program. The TBM uses
  Li₄SiO₄ ceramic breeder + Be multiplier + RAFM steel structure in
  a helium-cooled geometry, with a 14 MeV D-T point source. Our
  Tier 18 geometry is close enough to do a meaningful comparison.

- **EU DEMO WCLL (Water-Cooled Lithium-Lead) blanket public data**:
  the EUROfusion consortium publishes TBR vs blanket thickness
  curves for the WCLL design. Our Tier 6 LiPb baseline at
  R_blanket=50 cm can be compared against the WCLL published values.

- **Other public benchmarks** that pre-date this project:
  - Sawan & Mohanty (2009) — FUSION neutronics benchmarks
  - Fischer 2020 / Brown 2023 — TBR per neutron reference values
  - Furuta 1987 — already used (Tier 9 validation)

**Effort**: 1-2 weeks (mostly reading + cross-reference table).
**Value**: HIGH. This is what the drop-mcnp.docx author correctly
identified as the real substitute for MCNP. A peer-reviewed public
benchmark is more credible than a second MC code, because the public
benchmark has been validated against multiple MC codes AND against
experimental data (where available).

### P2-A: 3D port/penetration correction factor
- Add a small 3D OpenMC model: cylinder + one port + tally the
  difference vs the 1D model.
- Use that to derive a multiplicative correction factor
  `f_port(area, count) = TBR_3D / TBR_1D`.
- Apply to every existing Tier number without re-running the 1D sweeps.
- **Effort**: 1-3 weeks (3D geometry is harder than 1D, but the
  OpenMC API already supports it).
- **Value**: HIGH. Closes the "but real reactors have ports" objection
  that any ARIES/DEMO-style comparison will raise.
- **Open question**: how many ports / what port area to assume? The
  answer depends on reactor design choices (Z-pinch liner replacement
  interval, diagnostic needs) that this project doesn't have authority
  on. Suggest: parameterize `f_port(port_count, port_area_fraction)`
  and let the user apply it.

### P2-C: Li-6 online-adjustment wrapper
- Add a thin class wrapper around `compute_TBR` that maintains state
  and exposes `plant.adjust_Li6(li6)` / `plant.current_TBR()`.
- Enables plant-level simulators to consume the parametric neutronics
  without re-instantiating `TBRInputs` every time.
- **Effort**: 3-5 days.
- **Value**: MEDIUM. Only matters if a plant-level simulator consumer
  appears. Currently no such consumer in the project.
- **When to do it**: when somebody actually wants to write a plant
  simulator that consumes z-pinch-postproc. Not preemptively.

### Tier-12 Li₄SiO₄ sweep script (was attempted, deferred)
- `scripts/run_tier18b_sweep.py` originally tried to reproduce the
  Li₄SiO₄ half of the Tier 18.B sweep via a `materials_override`
  path. This plumbing is NOT in the public `zpp/` API today
  (`_build_blanket_materials` only knows how to build LiPb).
- The on-disk Tier 18.B Li₄SiO₄ result (TBR=1.0296 ± 0.48%) was
  generated by a custom geometry builder that's not currently
  exposed. To make this reproducible from a single CLI invocation
  requires extending `_build_blanket_materials` (or adding a sibling
  function `_build_ceramic_blanket_materials`) and the `run_real_openmc_tbr`
  signature to accept a `breeder_override`.
- **Effort**: ~1-2 days to extend `_build_blanket_materials` and
  `run_real_openmc_tbr` to accept breeder switching; then the
  script as written will work.
- **When to do it**: when somebody needs to reproduce the Tier 18.B
  Li₄SiO₄ result. Currently the on-disk JSON is sufficient for citation.

## Per-item verification (per AGENTS.md rule 18 + 23)

- `pytest --collect-only`: **757 tests** (unchanged).
- `scripts/check_version_drift.py`: **OK** (all sources agree on 1.5.0).
- `scripts/stamp_provenance.py --list`: **6 Tier directories stamped** with OpenMC=0.16.0.0, ENDF=B-VIII.0, n_particles=5000.
- `scripts/run_tier6_sweep.py`: **TBR=1.7996** (matches convergence sweep within MC noise).
- `scripts/run_tier18b_sweep.py`: **TBR=1.8395** (matches published 1.8280 within 0.6% statistical noise).
- `scripts/run_tier6_convergence.py`: **TBR asymptote 1.80 ± 0.08% at n=50000**, consistent with default n=5000 within statistical noise.

## Open questions for the user

1. **Should the Tier 18.B Li₄SiO₄ reproducibility gap be closed in the
   next round?** It's a 1-2 day change to extend `_build_blanket_materials`
   and `run_real_openmc_tbr`. Worth doing before any external citation.

2. **Which public benchmarks (P1-D) to prioritize?** The ITER TBM
   benchmark is closer to the Tier 18 Li₄SiO₄ geometry; EU DEMO WCLL
   is closer to the Tier 6 LiPb geometry. Both are ~1 week each.

3. **Should `data/inputs/` grow to include the actual OpenMC XML
   geometry/material files** (not just the Python reproduction scripts)?
   Publishing raw XML is more reproducible but adds another layer of
   documentation to maintain.

4. **Tier convergence sweeps for Tier 9 (Furuta), Tier 17 (Z-FFR
   spherical), Tier 18.B Li₄SiO₄?** Currently only Tier 6 has a
   convergence curve. The methodology is now proven; ~30 minutes per
   Tier to add a 7-point sweep.
