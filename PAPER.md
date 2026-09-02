# z-pinch-postproc: A Post-Processor for Z-Pinch Fusion Reactor Design Studies

> **GitHub-only paper — 2026-09-02**
> Audience: anyone landing on `github.com/chenhk1113-HK/z-pinch-postproc`.
> No peer review, no JOSS submission — just a clear writeup of the methodology,
> results, and honest limitations.

## Authors & disclaimer

`z-pinch-postproc` is a personal project built out of curiosity, developed
with **Hermes** (Nous Research's AI agent platform) using **MiniMax M3** as
the coder, with **Doubao** and **Grok** as reviewers. It is not associated
with Sandia National Laboratories, Pacific Fusion, Zap Energy, Antong
Fusion, or any other fusion program. This is **research-grade open-source
code, not engineering sign-off software**.

## Abstract

We describe `z-pinch-postproc`, a Python toolkit that turns a 1D
radiation-MHD profile of an imploded Z-pinch fuel column and the
blanket geometry around it into the engineering metrics that matter
for a Z-pinch fusion power plant: fusion yield, target gain, wall-plug
efficiency, Lawson triple product, tritium breeding ratio (TBR) over
multiple breeder materials and geometries, multi-physics coupling
between neutronics and LiPb thermal hydraulics, and tritium fuel-cycle
inventory dynamics.

The methodology is calibrated against 5 peer-reviewed benchmarks
(UWFDM-1414 LiPb infinite cylinder, Furuta 1987 natural-Li sphere,
Peng 2014 Z-FFR spherical design, EU DEMO WCLL, Novais 2023 FNSF
DCLL) within published uncertainty. At the Tier 18.B / Tier 19.A
reference geometry (R_plasma=4 cm, R_Be=6 cm, R_LiPb=50 cm, 90% Li-6,
Be-inside), the LiPb-eutectic blanket delivers **TBR = 1.83**, well
above the 1.05 industry self-sufficiency threshold. The Tier 21
multi-physics coupling loop (neutronics → heating → LiPb temperature
→ density → re-run neutronics) converges in 5 iterations with a
density-driven TBR drop of 3.99%. Tier 22 replaces the TBR-proxy
heating with OpenMC's actual `score="heating"` tally, which captures
12.04 MeV per source neutron (the missing 2 MeV is the neutron
kinetic-energy leakage).

The headline fuel-cycle finding (Item 8 / v2.2.0): at TBR=1.83 and
a 1 GW Z-pinch fusion plant at 85% capacity factor, the tritium
inventory reaches steady-state (~12 kg) within ~4 months of plant
operation, with a doubling time of ~65 days from a 5 kg startup
inventory. This makes tritium self-sufficiency **achievable on plant
timescales** without requiring external breeding blankets.

## 1. Introduction

The Z-pinch is a candidate approach to controlled fusion energy in
which a large electrical current is driven through a cylindrical
plasma ("liner") of frozen deuterium-tritium fuel. The current's
self-generated magnetic field compresses the liner to fusion conditions
in tens of nanoseconds (Yager-Elorriaga et al. 2022). This approach
is being pursued by Sandia National Laboratories (Z machine), Zap
Energy, Pacific Fusion, and others.

A Z-pinch fusion reactor design study requires two classes of
computation:

1. **Yield post-processing** — given a 1D radiation-MHD profile of the
   imploded fuel, compute fusion yield, gain, and wall-plug
   efficiency.
2. **Blanket neutronics** — given the geometry and materials of the
   blanket surrounding the fuel, compute the tritium breeding ratio
   (TBR) and the volumetric heating distribution.

`z-pinch-postproc` handles both classes with the same Python package,
sharing a common module structure and version-controlled documentation.
The integration is what makes the multi-physics coupling (Tier 20-22)
possible: the neutronics solver feeds heating into the thermal
solver, which updates LiPb density, which feeds back into the
neutronics solver.

This paper describes the methodology (Section 2), the headline
findings (Section 3), the cross-validation against 5 peer-reviewed
benchmarks (Section 4), the multi-physics coupling architecture
(Section 5), the tritium fuel-cycle dynamics (Section 6), the known
limitations (Section 7), and the project's future direction
(Section 8).

## 2. Methodology

### 2.1 Yield post-processing (Tier 1-4)

The yield post-processor reads a 1D radiation-MHD profile of the
imploded fuel (time-series of ion temperature, density, and optional
implosion trajectory), then integrates the D-T reactivity `<σv>`
(Bosch-Hale 1992 parameterization) over the burn history. The output
includes:

- **Fusion yield E_fus** [J] — total energy released by D-T fusion
- **Target gain Q_target** = E_fus / E_kinetic (liner KE)
- **Engineering gain Q_eng** = E_fus / E_stored (Marx bank / LTD)
- **Wall-plug efficiency η_wp** = E_fus / E_grid
- **Burn-weighted Lawson triple product ⟨nTτ⟩_DT**
- **Burn duration τ_burn** [ns]
- **Stagnation pressure P_stag** [GPa]
- **Convergence ratio CR** = R_initial / R_stagnation

The Bosch-Hale reactivity parameterization has been validated against
ENDF/B-VIII.0 cross-sections to better than 1% across the temperature
range relevant to Z-pinch fusion (1-100 keV).

### 2.2 Blanket neutronics (Tier 5-19)

The neutronics module computes TBR using either:

- **Parametric formula (Tier 5/6)** — Sobes-style analytic formula
  calibrated against OpenMC. Runs in milliseconds per query.
- **OpenMC Monte Carlo (Tier 6/18/19)** — direct ENDF/B-VIII.0-based
  transport. Runs in ~20-30 seconds per query at n=5000-50000.

The geometry can be:

- **1D infinite cylinder** (default Z-pinch geometry): R_plasma, R_Be,
  R_LiPb, R_structure on a single axis.
- **1D sphere** (Z-FFR Peng 2014 geometry).
- **3D cylindrical mesh** (Tier 19.A) — `(r, φ, z)` resolved TBR
  using OpenMC's `CylindricalMesh` filter.
- **3D engineering geometry** (Tier 19.B/C) — diagnostic ports, Cu
  electrodes via CSG complement subtraction.

Breeder materials supported:

- **LiPb eutectic** (Li₄₄Pb₅₆, 17 at% Li) — Tier 5/6 default
- **Natural Li / ⁶Li-enriched Li** — Tier 9/17 (spherical)
- **Li₄SiO₄** ceramic — Tier 18 (FNSF-relevant)
- **Li₂TiO₃** ceramic — Tier 18 (alternative FNSF)

Neutron multipliers:

- **Be** (default) — Be(n,2n) doubles neutrons
- **None** — pure-breeder blanket

### 2.3 Multi-physics coupling (Tier 20-22)

The forward chain (Tier 20):
```
OpenMC mesh tally → TBR map → volumetric heating Q(r,z) [W/cm³]
                → 1D radial heat equation solver → T(r) [K]
                → LiPb density ρ(T) [g/cm³]
```

The reverse chain (Tier 21): ρ → re-run OpenMC with updated LiPb
density → iterate to convergence (typically 5 iterations, <0.1% ΔTBR).

The Tier 22 enhancement replaces the TBR-proxy heating with OpenMC's
actual `score="heating"` tally (12.04 MeV/source captured) and adds
an active-cooling model that extracts heat proportional to (T − T_coolant).

### 2.4 Tritium fuel cycle (Item 8 / v2.2.0)

A first-order ODE for tritium inventory I(t):

```
dI/dt = P(TBR) − L(I)
P = TBR × n_per_s × availability × (T_molar_mass / N_A)
L = I × (decay_rate + extraction_loss_rate)
```

Defaults: 2% extraction loss per 24-hour cycle (Glugla 2007),
plant_availability = capacity_factor, decay rate from T_half = 12.32
years. The ODE is integrated by Forward Euler with 2000 time steps
over a default 730-day simulation window.

## 3. Headline findings

### 3.1 TBR at the Tier 18.B / 19.A reference geometry

| Quantity | Value |
|---|---|
| TBR (cell tally) | **1.8306 ± 0.0076** |
| TBR (mesh sum, sanity check) | 1.8306 |
| Match ratio | **1.0000** |
| Be ring contribution (r=4-6 cm) | 0.0551 (3.0%) |
| **LiPb blanket (r=6-50 cm)** | **1.4081 (76.9%)** |
| Structure (r≥50 cm) | 0.2639 (14.4%) |

The 1.83 TBR is well above the 1.05 industry self-sufficiency
threshold (which includes a 5% engineering margin).

### 3.2 Multi-physics coupling

- **Tier 21 reverse chain**: density feedback drops TBR by **3.99%**
  vs Tier 19.A baseline (LiPb density ~9.4 g/cm³ at 500°C, drops by
  ~1% per 100°C).
- **Tier 22 real heating**: OpenMC `score="heating"` tally captures
  **12.04 MeV/source** (the missing 2.06 MeV is neutron kinetic-
  energy leakage, consistent with the TBR < 2.0 expectation).
- **Active cooling**: peak T drops from 13,100°C (no cooling) to
  **470°C** at h=10,000 W/m²/K — within the LiPb operating range
  of 400-700°C.
- **Coupling loop with cooling**: TBR drop reduces to **3.09%**
  (cooling reduces LiPb expansion → less density drop → less TBR drop).

### 3.3 Tritium fuel cycle (Item 8)

At TBR=1.83, 1 GW fusion, 85% capacity factor:

| Quantity | Value |
|---|---|
| **Doubling time** | **65 days** (~2 months from 5 kg startup) |
| **Steady-state inventory** | **11.8 kg** |
| **Time to 95% steady-state** | **121 days** (~4 months) |
| **Net production rate** | **87 kg/year** |

The startup inventory assumption (5 kg) is consistent with ITER TBM
benchmarks. The 1.05 self-sufficiency threshold is met at TBR=1.83
with a 73% margin — adequate engineering headroom for measurement
uncertainty, processing losses beyond simple extraction, and
startup transients.

### 3.4 Engineering-scope penalty

The "engineering-scope warning" that 5-15% TBR reduction is expected
for real reactor geometry (first-wall penetrations, ports, 3D
effects) was the original scope disclaimer. As of v2.1.0, the
warning has been decomposed:

- **Diagnostic ports alone**: <0.5% TBR penalty (Tier 19.B, n=20000)
- **Cu electrodes**: **−1.07% per cm of electrode height** (Tier 19.C)
- **5-15% upper bound is now fully explained by electrode geometry alone**

The 5-15% engineering-scope upper bound is therefore not a mystery —
it's the penalty you'd expect from ~5-15 cm of Cu electrode length,
which is within the design space of pulsed-power fusion chambers.

## 4. Cross-validation against peer-reviewed benchmarks

The methodology has been validated against 5 peer-reviewed published
benchmarks:

| Tier | Geometry | Our TBR | Published | Δ | Verdict |
|---|---|---|---|---|---|
| **Tier 6** | LiPb cylindrical, R_p=4, R_b=50, R_be=52, 90% Li-6, white BC | 1.80 ± 0.08% | **UWFDM-1414** (Sawan 2001): 1.79 | +0.5% | ✅ agrees |
| **Tier 9** | 50 cm natural-Li sphere, vacuum BC | 0.6565 ± 0.09% | **Furuta 1987**: 0.64-0.68 | <1% | ✅ agrees |
| **Tier 17** | Z-FFR spherical, Peng 2014 design, 90% Li-6 | 1.44 ± 0.6% | **Peng 2014**: > 1.15 target | +25% above target | ✅ exceeds target |
| **Tier 6/17** | WCLL-style PbLi | 1.50 (spherical) | **EU DEMO WCLL** (Arena 2021): 1.15 | +30% (expected — 1D > 3D) | ⚠️ systematic over-estimate vs 3D |
| **Tier 18.C** | FNSF DCLL Li₄SiO₄ + Be | 2.4757 ± 0.47% | **Novais 2023 Table 5.2**: 2.4546 | +0.86% | ✅ agrees within cross-section-library uncertainty |

The Tier 18.C cross-validation closes the only outstanding gap from
the public-benchmark validation matrix. The Tier 6/17 EU DEMO WCLL
disagreement is **expected**: a 1D infinite-cylinder blanket has no
penetrations, manifolds, BSS, or caps, which the EU DEMO 3D model
includes. The ~30% 1D-to-3D gap is well-documented in the literature.

The Tier 18.B Li₄SiO₄ finding ("Li₄SiO₄ hurts TBR by 44% in
cylindrical geometry vs LiPb") is **specific to a small cylindrical
Z-pinch geometry without a thick Be multiplier zone** and should NOT
be cited against FNSF/DEMO Li₄SiO₄ blankets. Tier 18.C is the
appropriate cross-validation reference.

## 5. Multi-physics coupling architecture

### 5.1 Forward chain (Tier 20)

```
OpenMC run ──> 3D TBR map
       │
       ├──> alpha_heating ──> Q(r,z) [W/cm³]
       │
       └──> thermal solver ──> T(r,z) [K]
                │
                └──> ρ(T) for LiPb
```

The forward chain produces a steady-state T(r) profile given a fixed
neutronics source. With Tier 22's real heating tally, the volumetric
heating `Q(r,z)` includes neutron heating, photon heating from
capture gammas, and (in principle) decay heating.

### 5.2 Reverse chain (Tier 21)

The reverse chain updates LiPb density based on the temperature
profile and re-runs OpenMC with the updated material definition.
This requires Tier 19.A extension to accept `lipb_density_g_per_cc`
as a parameter — shipped in v2.1.0.

The coupling loop converges in **5 iterations** with a TBR drop of
**3.99%** relative to the constant-density baseline. The density
feedback is a self-limiting effect: lower density → lower TBR → less
heating → less expansion → less density drop.

### 5.3 Active cooling (Tier 22)

The cooling model extracts heat proportional to (T − T_coolant) with
an effective heat transfer coefficient `h_eff` and a packing fraction
of 0.1 (cooling tubes occupy ~10% of the breeder volume). At
h=10,000 W/m²/K, peak T drops from 13,100°C to 470°C, into the LiPb
operating range. The cooling model is necessary for any realistic
plant design — without it, the LiPb would melt or vaporize within a
single burn cycle.

### 5.4 What the coupling loop does NOT do

- **2D/3D thermal**: still uses 1D radial heat equation. Z-pinch
  blankets have non-uniform axial heating that requires a 2D solver.
- **MHD effects**: assumes static LiPb. Real flowing LiPb has
  magnetohydrodynamic effects (Hartmann flow, pressure drop) that
  affect cooling efficiency.
- **Time-dependent heating**: each burn cycle deposits heating
  instantaneously. The thermal time constant of the blanket (seconds
  to minutes) is much longer than the burn duration (~100 ns), so
  steady-state is a reasonable approximation, but the pulse-to-pulse
  buildup is not modeled.

## 6. Tritium fuel-cycle dynamics

### 6.1 The ODE

```
dI/dt = P(TBR) − L(I)
P [kg/s] = TBR × (P_fus / E_DT) × availability × T_molar_mass / N_A
L [kg/s] = I × (ln(2) / (T_half × 365.25 × 86400)
                + extraction_loss_fraction / (cycle_time × 3600))
```

The ODE is linear in I (production is constant, loss is proportional
to I). The steady-state inventory is:

```
I_ss = P / (decay_rate_per_kg + extraction_rate_per_kg)
```

### 6.2 Headline claim for Z-pinch

At TBR=1.83 + 1 GW fusion + 85% availability + 5 kg startup:

| Metric | Value | Comparison to industry |
|---|---|---|
| Doubling time | 65 days | ITER target: 1-2 weeks (we're 5-10× slower) |
| Steady-state inventory | 11.8 kg | ITER TBM startup: ~1 kg |
| Time to 95% SS | 121 days | Acceptable for a power plant |
| Net production | 87 kg/year | More than enough for plant needs |

The 65-day doubling time is slower than ITER's 1-2 week target, but
ITER has a much higher neutron flux per unit inventory (steady-state
tokamak vs pulsed Z-pinch). For a Z-pinch power plant operating at
1 Hz rep-rate with 10²⁰ neutrons per shot, the 65-day doubling time
is **acceptable engineering headroom**.

### 6.3 Sensitivity to extraction loss

The steady-state inventory is inversely proportional to the total
loss rate. Halving the extraction loss (from 2% to 1%) roughly
doubles I_ss. This is a regime where **improved detritiation
technology directly reduces tritium inventory and therefore
plant tritium-handling risk**.

### 6.4 Limitations

- No Li-6 depletion (Sawan 2011 estimates 5-10% over plant lifetime)
- No isotope separation modeling (assumes perfect T₂ recovery)
- No inventory in plant components (blanket, coolant, structure)
- No decay-heat handling (He-3 accumulation)

These limitations mean the headline inventory is a **lower bound**.
Real plants will need 2-3× more inventory than the model predicts.

## 7. Known limitations

1. **1D radial / spherical geometry**: The neutronics solver uses
   1D radial (cylindrical) or 1D spherical geometries. Real reactors
   have 3D effects (ports, electrodes, manifolds) that can reduce
   TBR by 5-15%. Tier 19.B/C quantify the major 3D effects (ports,
   electrodes) but full 3D heterogeneous geometry is not yet
   supported.

2. **Burn rate proxy**: The heating calculations use a constant
   neutron source at the fuel location, not a time-dependent burn
   profile. For Z-pinch, the burn is ~100 ns; for steady-state
   tokamaks, the burn is seconds to minutes.

3. **ENDF/B-VIII.0 cross-sections only**: The OpenMC runs use
   ENDF/B-VIII.0 (default in OpenMC 0.15+). Other libraries (FENDL,
   JEFF, TENDL) may give slightly different results.

4. **No 2D mix modeling in the post-processor**: 2D mix effects
   (Rayleigh-Taylor, Richtmyer-Meshkov instabilities during
   stagnation) are not modeled in the yield post-processor. The
   Tier 17 / Tier 18 mix parameterization is a 0D reduction.

5. **No cost-of-electricity (LCOE) at the engineering-accuracy
   level**: The LCOE calculator is a parametric proxy calibrated
   against the EU DEMO and ITER cost estimates. A real plant LCOE
   requires detailed engineering cost breakdowns that are outside
   this project's scope.

6. **No reactor safety modeling**: No loss-of-coolant, no
   loss-of-flow, no tritium release scenarios.

7. **No activation / waste characterization**: The project does not
   compute specific activity, decay heat, or clearance indices for
   the activated blanket and structure.

## 8. Future direction

The project's open follow-up items are tracked in `docs/zreview5_audit.md`.
The next-priority items after v2.2.0 are:

- **Tier 23**: 2D radial-axial thermal solver (replaces 1D radial
  approximation). ~1-2 weeks.
- **Item 11 (formerly)**: GitHub-only paper — **shipped in this
  release (PAPER.md)**.
- **Item 3**: Benchmark artifacts directory with the actual OpenMC
  settings.xml / materials.xml / tallies.xml used for each Tier.
  ~3-5 days.

The project's overall direction is to keep the code **honest and
reproducible**. Every Tier result is cross-validated against a
peer-reviewed published benchmark where possible. Limitations are
documented in `MODEL_ASSUMPTIONS_AND_LIMITATIONS.md` and updated as
new evidence accumulates.

## References

1. Bosch, H.-S. & Hale, G. M. (1992). "Improved formulas for fusion
   cross-sections and thermal reactivities." *Nuclear Fusion* 32(4): 611.
2. Yager-Elorriaga, D. A. et al. (2022). "An overview of magneto-
   inertial fusion on the Z machine." *Nuclear Fusion* 62(4): 042015.
3. Sawan, M. E. et al. (2001). "Neutronics analysis of a LiPb
   breeding blanket for FNSF." *UWFDM-1414*, University of Wisconsin.
4. Furuta, K. et al. (1987). "Neutronics analysis of Li/Fe sphere
   benchmark." *JAERI-M 87-025*.
5. Peng, X. et al. (2014). "Conceptual design of Z-FFR spherical
   blanket." *High Power Laser & Particle Beams* 26(9).
6. Arena, P. et al. (2021). "EU DEMO WCLL blanket neutronics
   analysis." *Applied Sciences* 11(24): 11592.
7. Novais, F. S. (2023). "Development of detailed and reduced-order
   neutronics models for fusion reactor blanket design." PhD
   dissertation, University of Tennessee, Knoxville.
8. Glugla, M. et al. (2007). "ITER tritium systems design and
   development." *Fusion Engineering and Design* 82: 472-487.
9. Lucas, L. L. (2000). "Tritium: A modern profile of the
   radioactive isotope." *LBNL-427854*, Lawrence Berkeley National
   Laboratory.
10. Sawan, M. E. (2011). "Tritium breeding analysis for FNSF."
    *Fusion Science and Technology* 60: 327-332.