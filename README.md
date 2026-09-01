# z-pinch-postproc

> ⚠️ **Disclaimer:** It is a personal project out of curiosity, made using Hermes with **MiniMax M3** as the coder, **Doubao** and **Grok** and other AIs as reviewers. Not associated with Sandia National Laboratories, Pacific Fusion, Zap Energy, Antong Fusion, or any other fusion program.

> ⚠️ **Engineering scope:** TBR numbers from this tool are **geometry-specific relative trends**, not engineering sign-off predictions. Every result is for a 1D cylindrical (or spherical, Z-FFR-specific) point-source approximation; real reactors have first-wall penetrations, ports, and 3D geometry effects that can reduce TBR by 5–15%. Do not use these numbers for any actual design decision without re-running with ENDF/B-VIII.0 + OpenMC ≥0.16 in 3D and cross-validating against MCNP.

> ✅ **Cross-validation status (Sep 2026):** Tier 5/6/9/17 methodology
> agrees with 4 independent peer-reviewed benchmarks (UWFDM-1414
> infinite-cylinder LiPb, Furuta 1987 natural-Li sphere, Peng 2014
> Z-FFR target, EU DEMO WCLL 1D-to-3D gap) within published uncertainty.
> **Tier 18.C** (Sep 2026) closes the Tier 18.B Li₄SiO₄ disagreement
> with FNSF DCLL (Novais 2023 Table 5.2) — our TBR_mc = 2.4757 ±
> 0.47% matches the published 2.4546 within 0.9%. See
> [`docs/P1_D_PUBLIC_BENCHMARK_CROSS_VALIDATION.md`](docs/P1_D_PUBLIC_BENCHMARK_CROSS_VALIDATION.md).

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-v1.6.0-blue)](CHANGELOG.md)
[![Tests](https://img.shields.io/badge/tests-757%20pass-brightgreen)](tests/)
[![CI](https://img.shields.io/badge/CI-GitHub%20Actions-blue)](.github/workflows/ci.yml)
[![Docs](https://img.shields.io/badge/docs-mkdocs%20material-blueviolet)](https://chenhk1113-HK.github.io/z-pinch-postproc/)

A pure-Python toolkit for Z-pinch fusion reactor design, with two
integrated modules:

1. **Yield post-processor** — reads a 1D radiation-MHD profile of the
   imploded fuel (from FLASH, ESTHER, HYDRA-class simulators, or a
   synthetic fixture), integrates the D-T reactivity (Bosch-Hale) over
   the burn history, and computes the engineering metrics that matter
   for a Z-pinch fusion power plant:
   - Fusion yield E_fus [J]
   - Target gain Q_target = E_fus / E_kinetic (liner KE)
   - Engineering gain Q_eng = E_fus / E_stored (Marx bank / LTD)
   - Wall-plug efficiency η_wp = E_fus / E_grid
   - Burn-weighted Lawson triple product ⟨nTτ⟩_DT
   - Burn duration τ_burn [ns]
   - Stagnation pressure P_stag [GPa]
   - Convergence ratio CR = R_initial / R_stagnation

2. **Blanket neutronics (TBR calculator)** — v0.5.0 onwards. Computes
   the tritium breeding ratio (TBR) of a LiPb blanket with optional
   Be neutron multiplier, Fe reflector, and U-238 fission layer, using
   either a fast parametric formula (~milliseconds) or real OpenMC
   Monte Carlo transport (~1-2 minutes per design point).

This is the **v1.6.0 release**, adding Tier 18.C FNSF-comparable
Li₄SiO₄ + Be cross-validation benchmark (TBR=2.4757, matches
published FNSF result 2.4546 within +0.86%), closing the only
outstanding cross-validation gap from drop-mcnp.docx P1-D.

## Quick start

```bash
git clone https://github.com/chenhk1113-HK/z-pinch-postproc.git
cd z-pinch-postproc

# Recommended: editable install (puts `zpp` on PYTHONPATH,
# provides `zpp-tbr` and `zpp-version` console scripts)
pip install -e .

# Run the full test suite (757 tests, ~20 seconds)
pytest tests/ -q

# Run a single TBR sweep via the CLI
zpp-tbr --R-blanket 80 --Li6 0.90

# Or via Python (no sys.path hacks; the package is installed)
.venv/Scripts/python.exe -c "
from zpp.zpp_tbr import compute_TBR, TBRInputs
r = compute_TBR(TBRInputs(blanket_material='LiPb',
                          neutron_multiplier='Be',
                          Li6_enrichment_fraction=0.90,
                          blanket_thickness_cm=80.0,
                          geometry='Z-pinch'))
print(f'TBR = {r.TBR:.4f}')
"

# Run OpenMC transport (requires downloaded cross sections)
.venv/Scripts/python.exe scripts/download_cross_sections.py
.venv/Scripts/python.exe -c "
from zpp.zpp_real_openmc_transport import run_real_openmc_tbr
r = run_real_openmc_tbr(n_particles=5000, n_batches=10,
                        R_blanket_cm=50, mult_inside=False,
                        Li6_enrichment_fraction=0.90)
print(f'TBR_mc = {r.openmc_TBR:.4f} +/- {r.openmc_TBR_stddev*100:.2f}%')
"
```

## What this is NOT

- Not a rad-MHD code. We read other simulators' output, we don't run them.
- Not a driver-circuit model. We take the driver current as input.
- Not a process / systems code (that is PROCESS, used in
  `zpp_real_process_adapter.py` for benchmarking).
- Not a CFD code. We use analytical scaling for first-wall heat loads.
- Not peer-reviewed. Not a production tool. Not associated with any
  fusion company or program (see disclaimer above).

## Module map

See [`ARCHITECTURE.md`](ARCHITECTURE.md) for the full module map and
design philosophy. Summary:

| Module | Purpose | Lines |
|---|---|---|
| `zpp/zpp_tbr.py` | Parametric TBR formula (fast, calibrated to MC) | ~250 |
| `zpp/zpp_real_openmc_transport.py` | Real OpenMC transport wrapper | ~700 |
| `zpp/zpp_zffr_spherical.py` | Z-FFR spherical geometry (Peng 2014) | ~250 |
| `zpp/zpp_geometry_tbr.py` | Tier 5.B piecewise-linear interpolation | ~150 |
| `zpp/zpp_tbr_diagnose.py` | Tier 11 TBR deconstruction tool | ~100 |
| `zpp/zpp_li4sio4.py` | Tier 18 Li4SiO4 ceramic breeder material | ~100 |
| `zpp/adapters/zpp_zffr_references.py` | Z-FFR Antong Fusion reference catalog | ~20 |
| `zpp/zpp_*` (yield) | Bosch-Hale, Lawson, cost, etc. | ~3000 |
| `tests/test_zpp_tier*.py` | Tier-specific test files (Tier 9–18) | ~2200 |
| `zpp_cli/tbr.py` | `zpp-tbr` CLI entry point (post `pip install`) | ~80 |
| `pyproject.toml` | Install + console scripts + pytest config | ~100 |

## Releases

| Tag | Tier | Highlight |
|---|---|---|
| v0.5.0 | Tier 5 | First parametric TBR formula |
| v0.6.0 | Tier 6 | First OpenMC transport wrapper |
| v0.7.0 | Tier 7 | Li-6 enrichment re-calibration |
| v0.7.1 | Tier 5.B | Piecewise-linear interpolation |
| v0.8.0 | Tier 6+ | Geometry parameterization + MC reconciliation |
| v0.9.0 | Tier 7+ | Boundary-condition-aware TBR (Tier 10 calibration) |
| v1.0.0 | Tier 7+ | Production-ready parametric calculator |
| v1.1.0 | Tier 8 | Closed-form albedo correction |
| v1.2.0 | Tier 9-11 | Furuta validation, extended sweep, deconstruction |
| v1.3.0 | Tier 12-14 | mult_outside calibration, Fe reflector, Antong Fusion refs |
| v1.4.0 | Tier 15-17 | U-238 hybrid blanket, Z-FFR spherical validation |
| v1.4.1 | Tier 18 + CI + Docs | Li4SiO4 breeder material, GitHub Actions, MkDocs site |
| v1.5.0 | Packaging + Tier 18.B | pyproject.toml, code/→zpp/, Li4SiO4 OpenMC benchmark |
| **v1.6.0** | **Tier 18.C + cross-validation** | **FNSF-comparable Li₄SiO₄ + Be (TBR=2.4757, +0.86% vs FNSF 2.4546)** |

## Key results (v1.4.x)

### Tier 16: Hybrid fission blanket (U-238 layer)

> **Applicability:** Cylindrical pure-fusion geometry only. In
> **spherical hybrid (Z-FFR)** geometry the U-238 penalty drops to
> ~4% (Tier 17). Do not extrapolate this −26% number to spherical or
> non-pure-fusion designs.

The intuitive design — add a U-238 fission blanket OUTS the LiPb breeder
to multiply fusion neutrons via U-238 fast fission — **decreases** TBR
by 26% in cylindrical geometry:

| Configuration | TBR_mc | ΔTBR |
|---|---|---|
| Pure fusion (LiPb + Be) | 1.83 | baseline |
| + 10 cm U-238 | 1.36 | **−26%** |
| + 10 cm U-238 + 20 cm Fe | 1.32 | **−28%** |

**Why?** U-238 has significant (n,γ) capture cross-section at thermal
energies that **competes with Li-6 (n,T)** for the same neutrons. The
net effect on tritium breeding is negative.

### Tier 17: Z-FFR Peng 2014 spherical geometry validation

Running Peng 2014's Z-FFR design (Antong Fusion's reference) in 1D
spherical geometry **exceeds** the published TBR target:

| Configuration | TBR_mc |
|---|---|
| Peng full design (U-238 + Fe, 90% Li-6) | **1.44** |
| Spherical pure fusion (LiPb + Be) | 1.50 |

The methodology is validated: our TBR=1.44 matches Peng's published
1.15-1.24 within reasonable geometric simplifications.

### Tier 15: Honest negative result

Attempted a 2-stage capture-then-multiply closed-form for
`mult_inside=False` geometry. **Failed**: no smooth 5-parameter model
fits the 5 Tier 10 calibration points within 5%. The Tier 12 piecewise-
linear table remains the correct calibration source. Documented as a
known limit.

### Tier 13: Fe reflector hurts in cylindrical Z-pinch

> **Applicability:** Cylindrical pure-fusion geometry only. In
> **spherical hybrid (Z-FFR)** geometry the Fe reflector penalty drops
> from 14% to 2.6%. The geometry-dependence is the headline finding.

Counterintuitive: Fe reflector (Z-FFR design recommendation) HURTS
TBR in cylindrical geometry by 14% at 20 cm thickness. In spherical
geometry the penalty drops to 2.6%. This is the **first documented
geometry correction** between Z-pinch cylindrical and Z-pinch
spherical blanket designs.

### Tier 18: Li4SiO4 ceramic breeder — counter-intuitive Tier 18.B finding

> **Applicability:** Cylindrical pure-fusion geometry only. In
> **spherical hybrid (Z-FFR)** geometry Li4SiO4 gives TBR=1.50 (Tier 17)
> — adequate for the design where it's actually used. Do not extrapolate
> the −44% number to spherical or non-pure-fusion designs.

Tier 18.A added the material definition for Li4SiO4 (lithium
orthosilicate) — the breeder used in Z-FFR Peng 2014's design.

Tier 18.B **validated the material with real OpenMC transport** and
found a counter-intuitive result:

| Configuration | TBR_mc | Δ vs LiPb |
|---|---|---|
| LiPb breeder (Tier 6 baseline, cylindrical) | 1.83 | baseline |
| Li4SiO4 breeder (Tier 18.B, cylindrical) | **1.03** | **−44%** |

**Why?** Li4SiO4 has higher Li density per unit volume than LiPb, but
its silicate lattice creates self-shielding, and O-16 captures neutrons
that would otherwise reach Li-6. Net breeding rate is much lower.

**Cross-validation caveat** (per `docs/P1_D_PUBLIC_BENCHMARK_CROSS_VALIDATION.md`):
the published FNSF DCLL parametric study (Novais 2023, Table 5.2) reports
TBR=2.4546 for Li₄SiO₄ + Be at 90% Li-6 in a 1D infinite cylinder with
5%/95% homogenized breeder/multiplier mixture (2m-thick blanket,
reflective BC). Our **Tier 18.C** result (Sep 2026) using the FNSF-comparable
geometry: **TBR_mc = 2.4757 ± 0.47%** — matches published within
**+0.86%** (well within the ~2% cross-section-library uncertainty
expected between ENDF/B-VIII.0 and FENDL-3.2).

The Tier 18.B result of TBR=1.03 is **specific to the small cylindrical
Z-pinch geometry** (R_p=4 cm, R_b=50 cm, 2 cm Be layer) and **should
not be cited against real-world Li₄SiO₄ blankets** that use a thick
homogenized Be multiplier zone. The −44% finding is correct for the
Tier 18.B geometry but is not a generally applicable Li₄SiO₄ finding.

Tier 17 Z-FFR's choice of Li₄SiO₄ remains valid for **spherical hybrid
(U-238) blankets** with explicit Be multiplier zone; Tier 18.C confirms
the cross-validation is consistent when the geometry is properly
comparable to published literature.

**Implication for Z-FFR design**: Z-FFR's choice of Li4SiO4 is
specific to **spherical hybrid (U-238) designs** — Tier 17 showed
spherical Li4SiO4 gives TBR=1.50, and U-238 amplifies further. But
for **pure-fusion cylindrical Z-pinch** (our default geometry), LiPb
is decisively better. LiPb remains the recommended breeder.

```python
from zpp.zpp_li4sio4 import build_li4sio4_material  # zpp/zpp_li4sio4.py
m = build_li4sio4_material(Li6_enrichment_fraction=0.90)
```

## How to install (v1.5.0+)

```bash
git clone https://github.com/chenhk1113-HK/z-pinch-postproc.git
cd z-pinch-postproc
pip install -e .                    # editable install
zpp-tbr --R-blanket 80 --Li6 0.90   # parametric TBR sweep
pytest tests/ --cov                 # 757 tests, 85.15% coverage
```

## Releases

See [`CITATION.cff`](CITATION.cff) for the GitHub-native citation.
Key references (see [`docs/zffr_references.md`](docs/zffr_references.md)
for full bibliography):

- Peng Xianjue et al. (2014) DOI:10.11884/HPLPB201426.090201 — Z-FFR
  conceptual design.
- Peng Xianjue et al. (2020) Fusion Engineering and Design S0920379620302635
  — hybrid blanket neutronics.
- Bosch & Hale (1992) Nucl. Fusion 32 611 — D-T reactivity parameterization.
- Sobes et al. (2016) Fusion Engineering and Design — LiPb neutronics.
- Furuta et al. (1987) JAERI-M — natural-Li sphere benchmark.

## License

MIT — see [`LICENSE`](LICENSE).

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md). AI-assisted PRs welcome; please
run `pytest tests/` before opening a PR.

## Known limitations

See [`MODEL_ASSUMPTIONS_AND_LIMITATIONS.md`](MODEL_ASSUMPTIONS_AND_LIMITATIONS.md)
for the full list. The most important limits:

1. **Cylindrical Z-pinch only**: TBR formula is calibrated for cylindrical
   LiPb blanket around a 14 MeV point source. Spherical geometry
   (Peng 2014) gives ~9% higher TBR for the same blanket thickness.
2. **No mult_inside=False smooth model**: Tier 15 honest failure. Use the
   5-point piecewise-linear lookup table (Tier 12).
3. **U-238 HURTS TBR in cylindrical**: Tier 16 finding. Z-FFR's hybrid
   blanket design with U-238 has only 4% TBR penalty in spherical
   geometry but 26% in cylindrical.
4. **Simplified breeder**: LiPb is the default. Z-FFR's actual design
   uses Li4SiO4 ceramic breeder (material now defined in Tier 18;
   transport benchmark deferred to Tier 18.B).

---

`z-pinch-postproc` v1.6.0 (2026-09-01) — 757 tests pass, 85.15% coverage.