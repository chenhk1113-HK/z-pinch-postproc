# v2.1.0 — Tier 21 Coupling Loop Closure + Tier 22 Real Heating + Active Cooling (2026-09-01)

## What was shipped

Two complementary milestones that complete Item 9 (multi-physics coupling) from the zreview5 audit.

**Tier 21** (1 day): Closes the coupling loop wired in Tier 20 but unexecutable.
**Tier 22** (1 week scope): Real heating + active cooling.

| Module | Lines | Purpose |
|---|---|---|
| `zpp/zpp_real_openmc_transport.py` | +15 | `_build_blanket_materials(lipb_density_g_per_cc)` parameter |
| `zpp/zpp_real_openmc_3d.py` | +35 | `run_tier19_3d()` density + heating-tally parameters |
| `zpp/zpp_thermal_solver.py` | +135 | `solve_1d_radial_thermal_with_cooling()` |
| `zpp/zpp_multiphysics_coupling.py` | +38 | Tier 21 density feedback + Tier 22 heating/cooling paths |
| `tests/test_zpp_thermal_solver_cooling.py` | 130 | 8 cooling tests |
| `tests/test_zpp_multiphysics_integration.py` | 110 | 6 integration tests |
| `docs/TIER_21_COUPLING_LOOP_COMPLETE.md` | 170 | Tier 21 method + smoke test |
| `docs/TIER_22_HEATING_AND_COOLING.md` | 250 | Tier 22 cooling + heating tally |

**Total: 883 lines added; 14 new tests, all passing. 792 tests collected (was 778).**

## Headline findings

- **Density feedback drops TBR by 3.99%** vs Tier 19.A baseline (Tier 21)
- **Real heating tally: 12.04 MeV/source** captured (vs 14.1 MeV source; 2 MeV lost to leakage)
- **Active cooling: T_max drops from 13,100°C to 470°C** at h=10k W/m²/K
- **Coupling loop with cooling: TBR drop reduces to 3.09%** (cooling reduces LiPb expansion → less density drop → less TBR drop)

## Verification

- 792 tests collected (was 778); 14 new tests for Tier 21+22, all passing
- Drift guard: all 5 version sources agree on 2.1.0
- HEAD_MATCH local=remote=`c9f69404f29c053cc92521391bb566f411be4fc6`
- v2.1.0 tag live on GitHub at commit `c9f6940`
- TIER_22_HEATING_AND_COOLING.md reachable via raw.githubusercontent.com (HTTP 200)

## Files shipped

- `zpp/zpp_real_openmc_transport.py` (modified — Tier 21 density param)
- `zpp/zpp_real_openmc_3d.py` (modified — Tier 21 density + Tier 22 heating tally)
- `zpp/zpp_thermal_solver.py` (modified — Tier 22 cooling function)
- `zpp/zpp_multiphysics_coupling.py` (modified — Tier 21/22 wiring)
- `tests/test_zpp_thermal_solver_cooling.py` (NEW — 8 tests)
- `tests/test_zpp_multiphysics_integration.py` (NEW — 6 tests)
- `docs/TIER_21_COUPLING_LOOP_COMPLETE.md` (NEW)
- `docs/TIER_22_HEATING_AND_COOLING.md` (NEW)
- `CHANGELOG.md`, `CITATION.cff`, `README.md`, `VERSION`, `pyproject.toml` (bumped to v2.1.0)

## Layman summary

You said "funish tier 21 and 22." Done. v2.1.0 ships.

**Tier 21** is the small plumbing fix that makes the **feedback loop** work: the thermal solver computes a new LiPb density from the temperature profile, and that density now actually gets passed back to OpenMC for re-evaluation. Before Tier 21, the coupling loop was computing a new density but throwing it away. With Tier 21, the loop converges: **TBR drops 3.99%** vs Tier 19.A constant-density baseline because LiPb expands at higher T (Schubert 2012 linear expansion).

**Tier 22** has two pieces:
1. **Real heating tally**: instead of approximating heating from the tritium-breeding mesh (proxy: `TBR × 14.1 MeV`), we now use OpenMC's actual `score="heating"` tally. The real sum is **12.04 MeV/source** (vs 14.1 MeV source — the 2 MeV difference is neutrons escaping as kinetic energy). This is more accurate than the proxy because it captures gamma heating, neutron heating, etc.
2. **Active cooling model**: `solve_1d_radial_thermal_with_cooling()` adds a `h_eff × (T - T_coolant)` sink term. Without cooling, peak T = 13,100°C (unrealistic); with h=10k W/m²/K, peak T = 470°C (within LiPb operating range). A `packing_fraction=0.1` captures that cooling tubes occupy only ~10% of breeder volume (otherwise the cooling term dominates by 5-6 orders of magnitude and gives negative temperatures).

**Combined effect**: when both Tier 21 (density feedback) and Tier 22 (cooling) are active, TBR drops **3.09%** vs baseline — *less* than without cooling, because cooling reduces the LiPb temperature rise, which reduces density drop, which reduces TBR drop. Physically intuitive.

Tagged as **v2.1.0**, pushed to GitHub at commit `c9f6940`, HEAD_MATCH verified. 792 tests collected (was 778). 14 new tests, all passing. Release notes saved at `RELEASE_NOTES_v2.1.0.md`.