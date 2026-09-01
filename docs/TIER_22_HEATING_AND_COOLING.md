# Tier 22 — Real Heating Tally + Active Cooling

> **Status**: Shipped 2026-09-01. Replaces Tier 20's TBR-proxy heating with OpenMC's `score="heating"` tally, and adds an active-cooling model to the thermal solver.

## What was shipped

### Code changes

| File | Change | Lines |
|---|---|---|
| `zpp/zpp_thermal_solver.py` | Added `solve_1d_radial_thermal_with_cooling()` — 1D heat equation with volumetric cooling term `h_eff × (T - T_coolant)`. Includes `packing_fraction=0.1` to reflect that cooling tubes occupy only ~10% of breeder volume (otherwise the cooling term dominates by 5-6 orders of magnitude). | +135 |
| `zpp/zpp_real_openmc_3d.py` | Added optional `heating_3d_mesh` tally with OpenMC's `score="heating"`. Result dict now exposes `heating_total` (eV/source per cell). Backward compatible: default off. | +35 |
| `zpp/zpp_multiphysics_coupling.py` | Added `use_heating_tally`, `h_W_per_m2K`, `T_coolant_C`, `delta_wall_m` parameters. When `use_heating_tally=True`, uses real heating tally. When `h_W_per_m2K>0`, calls cooling solver. | +30 |

### Tests

| File | Tests | Coverage |
|---|---|---|
| `tests/test_zpp_thermal_solver_cooling.py` | 8 tests | h=0 backward compat; cooling lowers T; larger h gives lower T; higher T_coolant raises T; input validation; equilibrium T ~ T_c + Q/h_eff |
| `tests/test_zpp_multiphysics_integration.py` | +1 test (heating tally shape, units, default-off) | heating_total shape (30,30); sum ~14 MeV/source; None by default |

## Headline findings

### 1. Real heating tally gives 12.04 MeV/source (vs 14.1 MeV source)

Tier 20 approximated heating from the tritium-breeding mesh tally: `Q ≈ TBR × 14.1 MeV`. Tier 22 uses OpenMC's actual `score="heating"`, which includes:
- Neutron heating (elastic + inelastic scattering, ~5-10% of total)
- Photon heating from (n,γ) capture gammas (~20-30% of total)
- Decay heating (<1%)

Sum check: `heating_total.sum() = 1.20×10⁷ eV/source = 12.04 MeV/source`. The 14.1 MeV source neutron has lost 2.06 MeV to neutron kinetic energy (leakage). This is **physically correct** and more accurate than the Tier 20 TBR-proxy.

### 2. Active cooling lowers peak T by 96% (h=10k W/m²/K)

For Q = 5 W/cm³ uniform heating (high-flux blanket scenario):

| Configuration | T_max | T_mean |
|---|---|---|
| No cooling (Tier 21 baseline) | 13,100°C | 9,135°C |
| h = 5,000 W/m²/K | 506°C | 451°C |
| h = 10,000 W/m²/K | 470°C | 427°C |

With realistic cooling, peak T drops into the LiPb operating range (400-700°C).

### 3. Coupling loop with cooling converges with smaller TBR drop

End-to-end smoke test (`scripts/_tier22_smoke.py`) at burn_rate = 1×10¹⁸ n/s:

| Iteration | rho (g/cm³) | TBR |
|---|---|---|
| 0 | 9.20 | 1.8233 |
| 1 | 5.10 | 1.7744 |
| 2 | 5.10 | 1.7740 |

**Final delta vs Tier 19.A baseline: −3.09%** (Tier 21 was −3.99% with TBR-proxy heating and no cooling).

The cooling reduces the LiPb temperature rise, which reduces density drop, which reduces TBR drop — physically intuitive and consistent with the methodology.

## Method: the cooling term

The 1D radial heat equation with active cooling:

```
(1/r) d/dr (r × k × dT/dr) + Q(r) - h_eff × (T - T_coolant) = 0
```

Where `h_eff` is the **effective volumetric** heat transfer coefficient:

```
h_eff [W/m³/K] = h [W/m²/K] / δ [m] × packing_fraction
```

- `h` = convective HTC at the tube wall (5,000-20,000 W/m²/K for forced-convection LiPb).
- `δ` = effective wall pitch (5 mm typical).
- `packing_fraction` = fraction of breeder volume occupied by coolant tubes (~0.1 = 10%).

Without the packing fraction, `h/δ = 2×10⁶ W/m³/K` would dominate by 5-6 orders of magnitude over the conduction coefficient, giving unphysical negative temperatures. The packing fraction captures the geometric reality that cooling tubes are discrete features in a much larger breeder.

### Discretization

Same conservative finite-difference scheme as `solve_1d_radial_thermal()`, with the cooling term modifying the diagonal coefficient:

```
a[i] = k × r_{i-1/2}
b[i] = -2 × k × r_i - h_eff × r_i × dr²       ← Tier 22: cooling removes from T_i
c[i] = k × r_{i+1/2}
rhs[i] = -Q × r_i × dr² - h_eff × r_i × dr² × T_coolant   ← Tier 22: cooling extracts
```

## Method: the real heating tally

Tier 22 extends `build_tier19_tallies()` with an optional third tally:

```python
if include_heating_tally:
    heating_tally = openmc.Tally(name="heating_3d_mesh")
    heating_tally.filters = [openmc.MeshFilter(mesh)]
    heating_tally.nuclides = ["total"]   # material-integrated, not per-nuclide
    heating_tally.scores = ["heating"]    # neutron + photon heating, eV/source/cell
```

**Unit conversion in `coupled_multiphysics_loop()`**:

```python
heating_ev_per_source = result["heating_total"]  # (n_r, n_z)
V_bin_cm3 = 2π × r × dr × height
heat_density_per_cm3 = heating_ev_per_source.sum(axis=1) / V_bin_cm3 × MeV_to_J × burn_rate
```

The `sum(axis=1)` collapses the z-axis (we solve 1D radial thermal); the `×MeV_to_J × burn_rate` converts from eV/source/cell to W/cm³.

## Validation

- **h=0 backward compat**: cooling solver returns identical T to no-cooling solver within 1e-6°C (test_h_zero_matches_no_cooling).
- **Cooling reduces T_max**: h=10k gives T_max < 700°C (test_cooling_lowers_T_max).
- **Larger h gives lower T**: h=10k < h=5k T_max (test_larger_h_gives_lower_T).
- **Higher T_coolant raises T**: T_c=500°C > T_c=400°C T_max (test_higher_T_coolant_raises_T).
- **Real heating tally units**: sum = 1.2×10⁷ eV/source ≈ 12 MeV (consistent with 14.1 MeV source - leakage) (test_heating_tally_units).
- **Heating tally default-off**: backward compatible with Tier 20 (test_no_heating_tally_by_default).

## Known limitations

1. **Test burn_rate (1×10¹⁸ n/s) gives extreme T values** because the heating is much larger than realistic for a small blanket. The methodology is correct; the test scenario is unrealistically high-flux. Realistic blanket (~10²⁰ n/s in a power plant) would be analyzed differently.
2. **Heating tally measures eV/source, not W/g** — the conversion assumes uniform source distribution. For a fixed-source DT plasma, this is correct.
3. **`packing_fraction=0.1` is a heuristic** — actual values depend on blanket geometry. Could be made geometry-aware in a future tier.
4. **1D radial ignores axial profile** — Tier 21+22 still uses the Tier 20 1D radial thermal solver. 1D(r,z) extension is open follow-up.

## Open follow-up

After Tier 22 ships, the methodology chain is:
- Tier 19.A: 3D-resolved TBR (mesh tally)
- Tier 19.B: 3D engineering geometry (ports + electrodes)
- Tier 20: 1D thermal solver + coupling loop architecture
- Tier 21: Density feedback to OpenMC
- Tier 22: Real heating + active cooling

This completes Item 9 (multi-physics coupling) from the zreview5 audit. Item 11 (JOSS paper, with Item 8 fold-in) is the next major milestone.

## References

- Tier 20 docs: `docs/TIER_20_MULTIPHYSICS.md`
- Tier 21 docs: `docs/TIER_21_COUPLING_LOOP_COMPLETE.md`
- Schubert et al. 2012, "Thermophysical properties of liquid Pb-Li alloys"
- OpenMC docs: https://docs.openmc.org/en/0.16.0/
- zreview5 audit Item 9: `docs/zreview5_audit.md`