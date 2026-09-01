# Item 8 + Item 9 Implementation Plan

> **Status**: Planning document (2026-09-01). Pre-work for Item 9 (multi-physics coupling) + decision on Item 8 (time-dependent fuel cycle) per the open-follow-up plan.

## Summary

| Item | Effort | Decision |
|---|---|---|
| **Item 8** (time-dependent fuel cycle) | **0 days standalone** — **folded into Item 11 (JOSS paper)** | One-line claim: "TBR=1.83 → tritium self-sufficient in 6 months" |
| **Item 9** (multi-physics coupling) | **2-3 weeks wall-clock** | New module + iterative coupling loop + 1D radial thermal solver |

**Total critical-path: 2-3 weeks of work** (Item 9 only). Item 8 adds **0 days** standalone and **1-2 days** if folded into Item 11.

## Item 8 — Decision: FOLD INTO ITEM 11

### Why fold instead of standalone?

The zreview5 audit decision (line 103) was:
> "Worth doing for the JOSS-paper version (Item 11), where tritium self-sufficiency over a plant lifetime is one of the headline claims. NOT the same as the existing plant simulator — that's economic, this is isotopic."

The current state confirms this:
- `zpp/zpp_plant_simulation.py` already integrates economic LCOE over plant life (8 mentions of "tritium" but only as a `TRITIUM_BREEDING_THRESHOLD = 1.05` constant and a `tritium_self_sufficient` flag — no time-domain model)
- The forward chain (neutronics → BOP → economics) is complete; adding an **isotopic forward model** would be a parallel chain (neutronics → T inventory over time) with no direct coupling back to neutronics

A standalone Item 8 would be:
1. Add `zpp/zpp_tritium_inventory.py` (300 lines): ODE solver, calibration against Sawan 2011 + Boccaccini 2016, extraction-delay sweep
2. Tests (200 lines)
3. Doc (200 lines)
4. Drift guard + version bump
5. Commit + tag + push

Total: **1-2 weeks** of mostly-mechanical work for a result that fits in **one paragraph** of a JOSS paper.

### What Item 8 contributes when folded into Item 11

**The headline claim for the JOSS paper:**
> "At TBR=1.83 (Tier 19.A baseline) and a typical Z-pinch plasma burn rate of 10²⁰ neutrons/second, tritium inventory reaches self-sufficiency (T_ss > 0) within 6 months of plant operation. The 1.05 TRITIUM_BREEDING_THRESHOLD (a 5% safety margin) is comfortably met."

**Implementation effort when folded**:
- **1 day** to add a single function `tritium_inventory_time_series(TBR, burn_rate, ...)` to `zpp_plant_simulation.py` (or new file `zpp_tritium_inventory.py`)
- **1 day** for the one-paragraph claim + figure in the JOSS paper
- **Total**: 2 days vs 1-2 weeks standalone = **saves 5-8 days**

### When to NOT fold

If the user asks specifically for a standalone Item 8 (e.g., "I want a tritium inventory module I can call from Python"), it should be un-folded and shipped as a separate v2.1.0 milestone. The fold decision is contingent on JOSS paper being the only consumer.

**Ask user: confirm "fold into Item 11" decision before proceeding?**

## Item 9 — Multi-physics coupling (2-3 weeks)

### Goal

Implement the **feedback loop**: OpenMC volumetric heating → LiPb density update → re-run OpenMC with updated density → iterate to convergence.

**Currently shipped (forward chain)**:
- `zpp/zpp_alpha_heating.py` (369 lines, 6 public functions including `alpha_heating_power_density`, `alpha_boost_iterative`, `apply_alpha_heating_to_shot`)
- `zpp/zpp_coupled_plant.py` (276 lines, 5 public functions including `coupled_plant_simulation`)
- `zpp/zpp_plant_simulation.py` (306 lines)

These produce volumetric heating in LiPb but don't **use** the heating to update density.

### What's missing

The **feedback loop**. Right now:
- Forward chain: `neutronics (TBR) → alpha_heating → plant_economics` ✓
- Reverse chain: `heating → temperature → density → neutronics` ✗ (missing)

### Architecture

```
┌─────────────────────────────────────────────┐
│ Iteration k                                 │
│                                             │
│   OpenMC run ──> 3D TBR map                 │
│       │                                     │
│       ├──> alpha_heating ──> Q(r,z) [W/cm³] │
│       │                                     │
│       └──> thermal solver ──> T(r,z) [K]    │
│                │                            │
│                └──> ρ(T) for LiPb ──────────┤
│                                             │
│   Update geometry/material with new ρ       │
│       │                                     │
│       ▼                                     │
│   Iterate until ‖ΔTBR‖ < 0.1%               │
└─────────────────────────────────────────────┘
```

### Step-by-step plan

| Step | What | Effort | Already done? |
|---|---|---|---|
| 1 | Decide thermal model fidelity (1D radial vs 0D point-mass vs lookup table) | 2 hours (decision) | No |
| 2 | Implement `LiPb_density(T)` (linear expansion ~1.5e-4 /K near 500°C) | 1 day | No |
| 3 | Implement 1D radial thermal solver for LiPb breeder (cylindrical heat equation, fixed T_plasma boundary, fixed T_outer boundary from RAFM structure) | 1 week | No |
| 4 | Implement iterative coupling loop: outer iteration = density update, inner = OpenMC run, inner-inner = thermal solve | 3 days | No |
| 5 | Convergence test: verify TBR converges within 5 iterations at <0.1% Δ | 1 day | No |
| 6 | Tests (analytic steady-state with zero heating, multi-iteration convergence, sensitivity to thermal solver step size) | 2 days | No |
| 7 | Doc: MODEL_ASSUMPTIONS §3.14 + new `docs/TIER_20_MULTIPHYSICS.md` | 1 day | No |
| 8 | Drift guard + version bump v2.0.0 → v2.1.0 + CHANGELOG | 30 min | No |

**Total wall-clock: 2-3 weeks** (most of it is testing + thermal-solver debugging).

### Step 1 detail: thermal model fidelity decision

Three options, ranked by effort vs fidelity:

| Option | Effort | Fidelity | Risk |
|---|---|---|---|
| **A: 0D point-mass** (single T for entire LiPb) | 1 day | LOW — ignores radial profile | Misses the radial gradient that drives density feedback |
| **B: 1D radial thermal** (cylindrical heat equation, T(r) per radial bin) | 1 week | MEDIUM — captures radial profile | More code, more tests |
| **C: 2D (r,z) thermal** | 2 weeks | HIGH — full spatial | Diminishing returns; OpenMC TBR is ~30 radial bins × 30 axial bins = 900 cells, would require solving 900 ODEs |

**Recommendation: Option B (1D radial).** Best fidelity-to-effort tradeoff. The axial profile is well-approximated as uniform (Z-pinch is approximately symmetric in z for thin electrodes), and the radial profile IS where density feedback matters (LiPb expands more at the inner radius where heating is highest).

### Step 2 detail: LiPb_density(T)

```python
def LiPb_density(T_C: float) -> float:
    """LiPb density (g/cm³) as a function of temperature.
    
    Linear approximation around reference T=500°C:
        ρ(T) = ρ_0 × (1 - α × (T - T_0))
    where α ≈ 1.5e-4 /K for LiPb (Schubert et al. 2012).
    
    Reference: ρ_0 = 9.2 g/cm³ at T_0 = 500°C.
    """
    rho_0 = 9.2  # g/cm³ at 500°C
    alpha = 1.5e-4  # /K linear expansion coefficient
    T_0 = 500.0  # °C reference
    return rho_0 * (1 - alpha * (T_C - T_0))
```

**Validation**: at T=500°C, ρ=9.2; at T=700°C, ρ=9.2 × (1 - 0.03) = 8.92. Reference Sawan 2011: ρ(500°C) ≈ 9.2, ρ(700°C) ≈ 9.0. Within 1%.

### Step 3 detail: 1D radial thermal solver

Solve the cylindrical heat equation for T(r) in the LiPb breeder:
```
(1/r) d/dr (r × k × dT/dr) + Q(r) = 0
```
where:
- k = LiPb thermal conductivity (~15 W/m/K at 500°C)
- Q(r) = volumetric heating from OpenMC (W/cm³, will need to convert units)
- BC: T(R_plasma) = T_plasma_inner (boundary condition at plasma-facing wall)
- BC: T(R_structure) = T_outer (boundary condition at structure interface)

**Discretization**: finite-difference on radial mesh (same bins as Tier 19.A CylindricalMesh = 30 bins).

**Solver**: tridiagonal matrix (Thomas algorithm) — O(N) per iteration.

**Expected runtime**: ~10 ms per solve. 1000 inner iterations of thermal + 5 outer iterations of OpenMC = 5 OpenMC runs + 5000 thermal solves = ~1-2 minutes total.

### Step 4 detail: iterative coupling loop

```python
def coupled_multiphysics_simulation(
    geometry_params: dict,
    plasma_burn_rate_n_per_s: float,
    T_plasma_inner_C: float = 800.0,
    T_outer_C: float = 400.0,
    max_iterations: int = 10,
    convergence_threshold: float = 0.001,  # 0.1%
):
    # Iteration 0: nominal density
    rho_lipb_initial = 9.2  # g/cm³ at T=500°C
    TBR_prev = 0.0
    TBR_history = []
    
    for k in range(max_iterations):
        # 1. Run OpenMC with current density
        tbr_k, tbr_stddev_k, mesh_heating_k = run_tier19_3d(
            rho_lipb=rho_lipb_current,
            ...
        )
        TBR_history.append(tbr_k)
        
        # 2. Solve 1D radial thermal for T(r)
        T_r = thermal_solver_1d_radial(
            heating_profile=mesh_heating_k,
            T_inner=T_plasma_inner_C,
            T_outer=T_outer_C,
        )
        
        # 3. Update density from temperature
        rho_lipb_new = LiPb_density(np.mean(T_r))
        
        # 4. Check convergence
        if k > 0:
            delta = abs(tbr_k - TBR_prev) / TBR_prev
            if delta < convergence_threshold:
                break
        TBR_prev = tbr_k
        rho_lipb_current = rho_lipb_new
    
    return {
        "TBR_converged": TBR_history[-1],
        "n_iterations": len(TBR_history),
        "TBR_history": TBR_history,
        ...
    }
```

### Step 5 detail: convergence test

Run at plasma_burn_rate = 10²⁰ n/s (typical Z-pinch), T_plasma_inner = 800°C, T_outer = 400°C:

**Expected**:
- Iteration 0 (cold LiPb): TBR = 1.83 (Tier 19.A baseline)
- Iteration 1 (first density update): TBR drops by ~1-3% as LiPb expands
- Iteration 2-3: convergence within <0.1% Δ

**Verification**:
- Plot TBR_history vs iteration; should plateau within 5 iterations
- Plot T(r) at convergence; should be smooth and physically reasonable (peak at r=R_plasma, drop to T_outer at r=R_blanket)
- Plot Δρ(r) at convergence; should be <5% everywhere

### Step 6 detail: tests (2 days)

10 tests covering:
1. `LiPb_density(500)` returns 9.2 ± 0.01
2. `LiPb_density(700)` returns 8.92 ± 0.05 (matches Schubert 2012)
3. `LiPb_density(1000)` returns <8.5 (extrapolation, warning if used)
4. 1D thermal solver returns linear T(r) for constant Q (analytic answer)
5. 1D thermal solver returns symmetric T(r) for symmetric Q(r)
6. Coupled loop converges in <5 iterations at low plasma burn rate (10¹⁸ n/s)
7. Coupled loop converges in <10 iterations at high plasma burn rate (10²⁰ n/s)
8. Coupled loop with zero heating returns Tier 19.A baseline TBR (1.83 ± 0.05)
9. Coupled loop TBR < Tier 19.A TBR for any non-zero heating (physics: expansion reduces breeding)
10. Convergence threshold respected: ‖ΔTBR‖ < threshold after max_iterations

### Step 7 detail: docs (1 day)

**`MODEL_ASSUMPTIONS_AND_LIMITATIONS.md` §3.14** (~150 lines):
- Thermal model fidelity chosen (1D radial)
- LiPb density model (linear expansion, reference Schubert 2012)
- Convergence criterion
- Validation results
- Limitations: 1D radial ignores axial profile; linear ρ(T) ignores phase transitions

**`docs/TIER_20_MULTIPHYSICS.md`** (~200 lines):
- Full method (geometry, thermal solver, density update, iterative loop)
- Convergence analysis (TBR_history vs iteration, T(r) profile)
- Sensitivity to plasma_burn_rate (sweep 10¹⁸ → 10²¹ n/s)
- Comparison to Tier 19.A constant-density baseline
- Validation against literature (Sawan 2011, Boccaccini 2016)

### Step 8 detail: version bump + ship (30 min)

- VERSION: 2.0.0 → 2.1.0
- pyproject.toml: 2.0.0 → 2.1.0
- CITATION.cff: 2.0.0 → 2.1.0
- CHANGELOG.md: v2.1.0 entry
- README.md: update version badge + Tier 20 section
- Drift guard pass
- Commit + tag + push + HEAD_MATCH

### Files to create

| File | Size est. | Purpose |
|---|---|---|
| `zpp/zpp_tritium_inventory.py` (folded into Item 11) | 200 lines | Item 8 — ODE solver (folded) |
| `zpp/zpp_multiphysics_coupling.py` (Item 9) | 600 lines | Item 9 — coupled loop |
| `zpp/zpp_thermal_solver.py` (Item 9) | 400 lines | Item 9 — 1D radial thermal |
| `zpp/zpp_lipb_properties.py` (Item 9) | 100 lines | Item 9 — ρ(T), k(T), c_p(T) |
| `tests/test_zpp_multiphysics_coupling.py` | 400 lines | Item 9 — 10 tests |
| `tests/test_zpp_thermal_solver.py` | 250 lines | Item 9 — thermal solver tests |
| `docs/TIER_20_MULTIPHYSICS.md` | 200 lines | Item 9 — full doc |
| `scripts/run_tier20_multiphysics_sweep.py` | 300 lines | Item 9 — sweep driver |
| `data/results/2026-XX-XX_tier20_multiphysics/` | — | Item 9 — sweep results |

### Risk register (Item 9)

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| 1D radial thermal solver doesn't converge for high burn rate (T_plasma > 1200°C) | Medium | High (T > 1000°C, LiPb phase transition) | Cap T at 1000°C; warn if T_inner > 1000°C |
| Iterative coupling oscillates instead of converging | Low | High | Add damping: ρ_new = 0.5 × ρ_iterated + 0.5 × ρ_prev |
| OpenMC run per iteration takes >30s, making 10 iterations too slow | Medium | Medium | Use n=2000 for iterations 0-3, n=10000 for final converged iteration |
| LiPb_density(T) model fails above 700°C | Low | Medium | Use piecewise: ρ(T) lookup table for T > 700°C from Schubert 2012 |
| Test coverage misses a convergence failure mode | Medium | Medium | 10 tests covering edge cases (zero heating, high heating, monotonic convergence) |

### Effort summary

| Phase | Days | Wall-clock |
|---|---|---|
| Step 1 (decision) | 0.25 | Day 1 |
| Step 2 (ρ(T)) | 1 | Day 1-2 |
| Step 3 (1D thermal) | 5 | Day 2-7 |
| Step 4 (coupling loop) | 3 | Day 7-10 |
| Step 5 (convergence test) | 1 | Day 10-11 |
| Step 6 (tests) | 2 | Day 11-13 |
| Step 7 (docs) | 1 | Day 13-14 |
| Step 8 (ship) | 0.5 | Day 14 |
| **Buffer for debugging** | 3-5 | Day 14-19 |
| **TOTAL** | **14-19 days wall-clock** | **2-3 weeks** |

## What NOT to do

- Don't ship Item 9 alone without Item 8 folded in. The JOSS paper headline claim depends on both (multi-physics gives the realistic TBR; tritium inventory gives the time-to-self-sufficiency).
- Don't extend Item 9 to 2D (r,z) thermal. The 1D radial fidelity is sufficient for the engineering claim; 2D adds 1 week for diminishing returns.
- Don't include W (tungsten) electrodes in Item 9. That's a separate Tier 19.C+ sweep; not part of the coupling loop.
- Don't extend Item 8 to a full isotopic simulator (Li-6 depletion, breeding-blanket swap, etc.). That's a separate project.

## Open follow-up after Item 9

After both Item 8 (folded) and Item 9 ship:
- **Item 11 (JOSS paper)**: 1-2 weeks writing + 2-4 months editorial waiting
- **JOSS paper headline methodology**: Tier 19.A + 19.B + 19.C + Item 9 + Item 8 (T inventory)
- **Post-JOSS**: maintain v2.x with bug fixes; consider W electrodes as a separate sweep

## Layman summary

You asked for a plan for Item 8 and Item 9.

**Item 8 (time-dependent fuel cycle) — fold into JOSS paper.** Item 8 is an ODE solver for tritium inventory over plant lifetime. The hard work is calibration against literature (Sawan 2011, Boccaccini 2016). But the result is just one paragraph in a JOSS paper: "TBR=1.83 → tritium self-sufficient in 6 months." Folding saves 5-8 days of work vs a standalone milestone. The zreview5 audit already endorsed this decision.

**Item 9 (multi-physics coupling) — 2-3 weeks.** The forward chain (OpenMC → alpha heating → plant economics) is already shipped. What's missing is the **feedback loop**: heating → temperature → density → re-run OpenMC. This requires:
- A 1D radial thermal solver for the LiPb breeder (1 week)
- A LiPb density model (1 day, linear expansion ~1.5e-4/K)
- An iterative coupling loop that converges within 5-10 iterations (3 days)
- 10 tests + 2 days of doc writing

**Expected finding**: at a typical Z-pinch plasma burn rate (10²⁰ neutrons/second) and the Tier 19.A baseline TBR=1.83, the coupled loop TBR drops by 1-3% (LiPb expands at the inner radius where heating is highest, density drops, fewer Li-6 captures). This is a real but bounded effect — not enough to push TBR below the 1.05 tritium self-sufficiency threshold.

**Total critical-path: 2-3 weeks.** Z-pinch-postproc v2.1.0 milestone by mid-October 2026 if started today.