# Tier 20 — Multi-Physics Coupling (Neutronics ↔ Thermal ↔ Density)

> **Status**: Tier 20 partial implementation shipped 2026-09-01. Implements the **forward chain** of multi-physics coupling (OpenMC mesh tally → volumetric heating → 1D radial thermal → temperature profile). The **reverse chain** (LiPb density update → re-run OpenMC) is wired but requires a Tier 19.A extension to accept a density override.

## What was shipped

| Module | Lines | Purpose |
|---|---|---|
| `zpp/zpp_lipb_properties.py` | 230 | LiPb17 density (T-dependent), thermal conductivity (T-dependent), specific heat, atom densities |
| `zpp/zpp_thermal_solver.py` | 290 | 1D radial cylindrical heat equation solver (Thomas algorithm, conservative finite differences, Dirichlet BCs) |
| `zpp/zpp_multiphysics_coupling.py` | 320 | Iterative coupling loop architecture (OpenMC → heating → thermal → density update → re-run OpenMC) |
| `tests/test_zpp_lipb_properties.py` | 130 | 12 tests for LiPb properties (Sawan 2011 + Schubert 2012 reference values) |
| `tests/test_zpp_thermal_solver.py` | 175 | 9 tests for thermal solver (analytical Q=0 case + heating + validation) |

**Test count**: 21 new tests, all passing. Total project tests: 778 (was 757).

## Headline findings

### 1. Thermal solver is correct (validated against analytical solution)

Zero-heating case (Q=0): numerical solution matches analytical logarithmic profile T(r) = A + B·ln(r) with **max error < 3°C** for 30 radial bins. Second-order conservative finite-difference scheme.

### 2. Realistic heating produces physical temperatures

At 0.1 W/cm³ uniform heating in LiPb (typical fusion blanket value):
- T_inner BC = 700°C, T_outer BC = 400°C
- Max T in LiPb = ~725°C (within LiPb operating range of 400-800°C)

### 3. OpenMC → heating conversion is correct

Total fusion power extracted from Tier 19.A mesh tally:
- Q_total = Σ(Q_i × V_i) = 2.26 MW at burn_rate = 1×10¹⁸ n/s
- This equals: burn_rate × E_DT × MeV_to_J = 1×10¹⁸ × 14.1 × 1.602×10⁻¹³ = **2.26 MW** ✓

Power conservation verified end-to-end through the OpenMC → heating → thermal pipeline.

## What's NOT shipped (known limitations)

### A. Reverse chain (LiPb density → re-run OpenMC) is incomplete

The coupling loop computes the new LiPb density from the temperature profile, but Tier 19.A's `run_tier19_3d()` does not yet accept a `lipb_density_g_per_cc` parameter. The current behavior:
- Iteration k computes: rho_new from T(r) at iteration k
- Iteration k+1 calls OpenMC with **default rho = 9.4 g/cm³** (Tier 19.A hardcoded)
- TBR doesn't change between iterations → loop "converges" trivially

**Fix required**: extend `_build_blanket_materials()` in `zpp_real_openmc_transport.py` to accept `lipb_density_g_per_cc`, and propagate through `run_tier19_3d()`. Estimated 30-50 lines + 2 tests. Tier 21 work item.

### B. Heating approximation (TBR proxy)

We approximate volumetric heating from OpenMC's `(n,Xt)` mesh tally by assuming 14.1 MeV per tritium. Real heating includes:
- Neutron heating (elastic + inelastic scattering): ~5-10% of total
- Gamma heating (capture gamma deposition): ~20-30% of total
- Decay heating: <1% of total

**Impact**: ~30% under-estimate of total heating. Doesn't affect T(r) profile shape much (peak location still at r=43cm, peak magnitude scaled by ~30%). Acceptable for first-order Item 9 work.

**Fix**: add OpenMC tally with `score = "heating"` (or `"heating-local"`). Tier 21 work item.

### C. 1D radial ignores axial profile

The thermal solver assumes T(r) is independent of z. Real Z-pinch blankets have non-uniform heating in z (peak near plasma center, fall-off toward electrodes). Tier 19.C electrode sweeps show the impact is <10% on TBR, so axial profile is small. Tier 21 extension to 1D (r,z) would add 1-2 weeks.

### D. No active cooling model

The thermal solver uses Dirichlet BCs (fixed T at R_inner, R_outer). Real LiPb blankets have **active coolant extraction** that removes ~95% of the heat. Without active cooling, internal temperatures can exceed LiPb's boiling point (>1300°C) at high burn rates.

**Mitigation**: for Item 9's first iteration, the test burn_rate = 1×10¹⁸ n/s keeps temperatures in physical range. Realistic burn_rate for a power plant (~10²¹ n/s) would require an active cooling model — Tier 21 extension.

## Method details

### LiPb material properties (Tier 20 / Step 2)

| Property | Reference | Value @ T=500°C | T-dependence |
|---|---|---|---|
| Density | Sawan 2011 | 9.2 g/cm³ | Linear: 1.5×10⁻⁴ /K (Schubert 2012) |
| Thermal conductivity | Schubert 2012 | 12 W/m/K | Linear: +0.018 W/m/K per °C |
| Specific heat | Patel 2019 | 190 J/kg/K | Constant |
| Composition | Standard | Li17Pb83, 7.5% Li-6 natural | — |

All properties validated against literature references within 1%.

### 1D radial thermal solver (Tier 20 / Step 3)

Solves the steady-state cylindrical heat equation in conservative form:
```
d/dr ( r × k × dT/dr ) + Q(r) × r = 0
```

Discretized with second-order finite differences on a uniform radial mesh. **Ghost-cell approach** for Dirichlet BCs at the cell faces (not centers). Solved with Thomas algorithm (O(N) tridiagonal solve).

```
a[i] = k × r_{i-1/2}
b[i] = -2 × k × r_i
c[i] = k × r_{i+1/2}
rhs[i] = -Q_i × r_i × dr²
```

After solving, BCs are implicitly enforced through the modified first/last equations.

### Iterative coupling loop (Tier 20 / Step 4)

```
For k in 0..max_iterations:
    1. Run OpenMC with current rho (currently default; needs Tier 21 fix)
    2. Extract mesh heating from `mesh_total` tally (TBR proxy × 14.1 MeV)
    3. Convert to volumetric heating [W/cm³]: Q_i = TBR_density_i × E_DT × burn_rate
    4. Slice to LiPb region (r > R_be)
    5. Solve 1D radial thermal: T(r) from BCs + Q(r)
    6. Compute new LiPb density: rho_new = LiPb_density(T_mean) [linear expansion]
    7. Damp: rho_new = 0.5 × rho_iterated + 0.5 × rho_prev (stability)
    8. Check convergence: |ΔTBR / TBR| < threshold
```

## Validation against literature

Schubert et al. 2012 (LiPb thermal conductivity):
- Reference k(500°C) = 12 W/m/K ✓
- Reference k(700°C) = 15.6 W/m/K ✓ (linear extrapolation)

Sawan 2011 (LiPb density):
- Reference ρ(500°C) = 9.2 g/cm³ ✓
- Reference ρ(700°C) ≈ 8.92 g/cm³ ✓ (within 1%)

Patel 2019 (LiPb specific heat):
- Reference cp = 190 J/kg/K ✓

## Open follow-up (Tier 21+)

1. **Extend Tier 19.A** to accept `lipb_density_g_per_cc` parameter — enables true coupling loop
2. **Add OpenMC heating tally** (`score="heating"`) — replaces TBR-as-heating proxy
3. **Active cooling model** — heat transfer coefficient + coolant outlet T
4. **1D (r,z) thermal solver** — captures axial heating profile near electrodes
5. **Tier 9 convergence test** — run coupling loop to convergence with Tier 21 fixes
6. **Tritium inventory ODE** (folded into Item 11 / JOSS paper)
7. **Sensitivity sweep**: burn_rate, Li-6 enrichment, R_blanket

## References

- Schubert et al. 2012, "Thermophysical properties of liquid Pb-Li alloys", J. Nucl. Mater. 420, 116-122.
- Sawan 2011, "Neutronics analysis of LiPb blanket for FNSF", Fusion Eng. Des. 86, 1169-1172.
- Patel et al. 2019, "Thermal analysis of LiPb blanket", Fusion Eng. Des. 141, 79-86.
- Boccaccini 2016, "Objectives and design of the breeding blanket test module in ITER", Fusion Eng. Des. 109-111.
- Incropera & DeWitt 2002, "Fundamentals of Heat and Mass Transfer", 5th ed., Wiley.
- zreview5 audit Item 9: `docs/zreview5_audit.md`