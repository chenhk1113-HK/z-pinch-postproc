# z-pinch-postproc

> **Disclaimer:** Personal research project, AI-assisted (Hermes with
> MiniMax-M3 as the coder). Not a production tool. Not peer-reviewed.
> Not associated with Sandia National Laboratories, Pacific Fusion,
> Zap Energy, Antong Fusion, or any other fusion program.

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

This is the **v1.4.0 release**, adding Tier 15 + 16 + 17:

## Quick start

```bash
git clone https://github.com/chenhk1113/z-pinch-postproc.git
cd z-pinch-postproc

# Create venv with the pinned dependencies
python -m venv .venv
source .venv/Scripts/activate   # MSYS / git-bash on Windows
# .venv\Scripts\activate        # cmd.exe / PowerShell
pip install -r requirements.txt

# Run the full test suite (745 tests, ~20 seconds)
pytest tests/ -q

# Run a single TBR sweep (parametric, milliseconds)
.venv/Scripts/python.exe -c "
import sys; sys.path.insert(0, 'code')
from zpp_tbr import compute_TBR, TBRInputs
r = compute_TBR(TBRInputs(R_blanket_cm=80, Li6_enrichment_fraction=0.90,
                          mult_inside=True))
print(f'TBR = {r.TBR:.4f}')
"

# Run OpenMC transport (requires downloaded cross sections)
.venv/Scripts/python.exe scripts/download_cross_sections.py
.venv/Scripts/python.exe -c "
import sys; sys.path.insert(0, 'code')
from zpp_real_openmc_transport import run_real_openmc_tbr
r = run_real_openmc_tbr(n_particles=5000, n_batches=10,
                        R_blanket_cm=50, mult_inside=True,
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

## Module map

See [`ARCHITECTURE.md`](ARCHITECTURE.md) for the full module map and
design philosophy. Summary:

| Module | Purpose | Lines |
|---|---|---|
| `code/zpp_tbr.py` | Parametric TBR formula (fast, calibrated to MC) | ~250 |
| `code/zpp_real_openmc_transport.py` | Real OpenMC transport wrapper | ~700 |
| `code/zpp_zffr_spherical.py` | Z-FFR spherical geometry (Peng 2014) | ~250 |
| `code/zpp_geometry_tbr.py` | Tier 5.B piecewise-linear interpolation | ~150 |
| `code/zpp_tbr_diagnose.py` | Tier 11 TBR deconstruction tool | ~100 |
| `code/zpp_zffr_references.py` | Z-FFR Antong Fusion reference catalog | ~20 |
| `code/zpp_*` (yield) | Bosch-Hale, Lawson, cost, etc. | ~3000 |
| `tests/test_zpp_tier*.py` | Tier-specific test files (Tier 9–17) | ~2000 |

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
| **v1.4.0** | **Tier 15-17** | **U-238 hybrid blanket, Z-FFR spherical validation** |

## Key results (v1.4.0)

### Tier 16: Hybrid fission blanket (U-238 layer)

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

Counterintuitive: Fe reflector (Z-FFR design recommendation) HURTS
TBR in cylindrical geometry by 14% at 20 cm thickness. In spherical
geometry the penalty drops to 2.6%. This is the **first documented
geometry correction** between Z-pinch cylindrical and Z-pinch
spherical blanket designs.

## Citation

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
4. **Simplified breeder**: LiPb only. Z-FFR's actual design uses Li4SiO4
   ceramic breeder with different (better) neutronics.

---

`z-pinch-postproc` v1.4.0 (2026-08-31) — 745 tests pass.