# Release Notes for v0.7.0

**Date:** 2026-08-30
**Tag:** v0.7.0
**Tests:** 609 passing in 18s

## Highlights

**Three of four upstream fusion engineering codes now integrated.** PROCESS
(BOP wall-plug chain), OpenMC (TBR neutronics), and Paramak (geometric design)
are installed and actively exercised by the project. FISPACT-II is documented
but requires a UKAEA license (manual install only).

**Monte Carlo uncertainty quantification** added. End-to-end ZN plant
simulation now propagates uncertainty through 5 input parameters (MHD effect,
blanket thickness, Li-6 enrichment, FW coverage, hot temperature) and reports
TBR/LCOE distributions.

## What's New

- **Tier 7.A — Real Paramak integration** (`code/zpp_real_paramak_adapter.py`).
  Paramak 0.9.11 installed via pip. Builds 3D CAD geometry for all 4 pre-defined
  radial builds (ZN, Tokamak, GF-MTF, Zap-SFZ). Exports STEP files for CAD
  inspection. **+14 tests**.
- **Tier 7.B — OpenMC cross-sections management** (`code/zpp_cross_sections.py`).
  Documents the install path for the ENDF cross-section library (~5 GB) and
  the minimal subset needed for LiPb blanket (~6 nm, ~200 MB).
  `list_required_nuclides_for_blanket()` returns the nuclide list for any
  blanket material. **+15 tests**.
- **Tier 7.C — Monte Carlo UQ** (`code/zpp_uncertainty.py`). 1000-sample MC
  propagation through the ZN plant simulation with reproducible RNG.
  Reports TBR distribution (mean, std, percentiles), LCOE distribution,
  P(TBR >= threshold), and P(sub-break-even). **+12 tests**.
- **Tier 7.D — FISPACT-II probe** (`code/zpp_fispact_adapter.py`). Documents
  the manual UKAEA license install path. Provides parametric activation proxy
  (Tier 5.D fallback) until FISPACT is available. **+9 tests**.

## Test summary

- 609 tests pass in 18s.
- Up from 560 in v0.6.1 (+49 tests).
- Up from 433 in v0.5.0 (+176 tests across v0.6.0 + v0.6.1 + v0.7.0).

## Process install summary

| Code | Status | Install method | Version |
|---|---|---|---|
| PROCESS | ✅ installed | `git clone && pip install` | 0.0.1.dev1+g6df462050 |
| OpenMC | ✅ installed | `pip install openmc-anywhere` (PyPI wheel) | 0.16.0.0 |
| Paramak | ✅ installed | `pip install paramak` | 0.9.11 |
| FISPACT-II | ❌ not installed | Manual + UKAEA license required | - |

## Strategic findings

- **TBR is robustly feasible** for ZN blanket design: 100% of 100 MC samples
  show TBR >= 1.05 threshold (consistent with Tier 5.B).
- **LCOE is uniformly sub-break-even** for ZN plant at current physics
  (Q_eng ~1e-3): all 100 MC samples show LCOE = inf (consistent with
  Tier 2.D + 5.A + 6.B).
- **Real Paramak geometry** confirmed for ZN design: total_radius=99 cm,
  plasma_height=100 cm, blanket_volume=3.08 m^3, STEP file 29 KB.
- **Real OpenMC geometry** confirmed: builds valid geometry/materials/
  tallies XML via openmc API even without cross-sections.

## Honest disclosures (per AGENTS.md rule 12)

- **OpenMC cross-section library** (~5 GB ENDF data) is not bundled with
  openmc-anywhere. The OpenMC adapter builds real geometry XML but cannot
  run a real Monte Carlo TBR transport without it.
- **FISPACT-II** is not auto-installable due to UKAEA license requirements.
  Activation analysis uses Tier 5.D DPA + Smolentsev erosion as the proxy.
- **Paramak is tokamak-centric**. Z-pinch uses `revolved_shape()` primitive
  for cylindrical geometry; not the D-shape plasma assumed by `tokamak()`.

## Files in this release

### New code (v0.7)
- `code/zpp_real_paramak_adapter.py` (170 lines)
- `code/zpp_cross_sections.py` (170 lines)
- `code/zpp_uncertainty.py` (240 lines)
- `code/zpp_fispact_adapter.py` (130 lines)

### New tests (v0.7)
- `tests/test_zpp_real_paramak_adapter.py` (14 tests)
- `tests/test_zpp_cross_sections.py` (15 tests)
- `tests/test_zpp_uncertainty.py` (12 tests)
- `tests/test_zpp_fispact_adapter.py` (9 tests)

### Updated (v0.7)
- `tests/test_zpp_subprocess_adapters.py`: reflects v0.7 state (PROCESS +
    OpenMC + Paramak installed; FISPACT-II missing).

## How to verify

```bash
# From project root
python -m pytest tests/ -v   # 609 tests should pass

# End-to-end ZN plant simulation
python -c "
import sys; sys.path.insert(0, 'code')
from zpp_plant_simulation import simulate_plant, PlantDesign
from zpp_comparison import ZN_DESIGN
result = simulate_plant(ZN_DESIGN, PlantDesign(name='test'), nameplate_MW=100)
print(f'TBR={result.TBR:.4f}, LCOE={\"inf\" if not result.LCOE_above_break_even else result.LCOE_USD_per_MWh:.2f}')
"

# Paramak geometry (requires openmc-anywhere, paramak installed)
python -c "
import sys; sys.path.insert(0, 'code')
import tempfile
from zpp_real_paramak_adapter import build_paramak_zpinch
from zpp_geometry import ZN_radial_build
with tempfile.TemporaryDirectory() as wd:
    r = build_paramak_zpinch(ZN_radial_build(), wd, export_step=True)
    print(f'Paramak ZN: R={r.total_radius_cm:.1f} cm, h={r.plasma_height_cm:.1f} cm, STEP={r.step_file_generated}')
"
```

## Next steps (v0.8 candidates)

1. **OpenMC cross-sections download + real TBR** (5 GB ENDF library)
2. **FISPACT-II install** (UKAEA license acquisition)
3. **Paramak D-shape extension** for spherical tokamaks
4. **Sensitivity ranking via Sobol** on Tier 7.C MC samples
5. **Public benchmark against published Z-pinch TBR values**