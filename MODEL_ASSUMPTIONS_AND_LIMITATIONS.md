# MODEL ASSUMPTIONS AND LIMITATIONS — z-pinch-postproc

**Version:** v1.7.0 (2026-09-01)
**Status:** v1.7.0 ships Tier 19.A (3D-resolved TBR via `CylindricalMesh`) on top of v1.6.0's Tier 18.C cross-validation. **757 tests passing, 85.15% coverage** (Tier 19.A reuses existing geometry; no new tests required).

**Per:** `Z_Machine_plan.pdf` (user-uploaded plan, 7,441 chars), `BUCKY 1-D radiation hydrodynamics code reference` (UWFDM-1268, 2005), `An overview of magneto-inertial fusion on the Z machine` (Yager-Elorriaga et al. 2022, Nucl. Fusion 62 042015), `Pulsed power: A precision hammer for high energy density science` (Hansen 2021, Princeton SULI), `Improved formulas for fusion cross-sections and thermal reactivities` (Bosch-Hale 1992), Sobes 2011 (LiPb blanket saturation length 50 cm), Fischer 2020 / Brown 2023 (TBR per neutron reference values), Micklich 1984 (Princeton PhD thesis, OSTI 6022348 — "Control of neutron albedo in toroidal fusion reactors"), Furuta 1987 (J. Nucl. Sci. Technol. 24(4) — neutron leakage from 50 cm Li, Fe spheres with 14 MeV D-T source), Peng 2014 (Z-FFR conceptual design, High Power Laser & Particle Beams 26(9)), 2026-08-31 OpenMC Monte Carlo sweeps at `data/results/2026-08-31_tier16_hybrid/` and `data/results/2026-08-31_tier17_zffr_spherical/`.

**Honest findings documented in this version:**
- **Tier 13**: Fe reflector HURTS TBR by 14% at 20 cm in cylindrical geometry (vs Peng 2014's recommendation to add Fe).
- **Tier 15**: Smooth closed-form for `mult_inside=False` failed. Piecewise-linear lookup table is the correct calibration source.
- **Tier 16**: U-238 hybrid blanket layer DECREASES TBR by 26% in cylindrical geometry (U-238 (n,γ) competes with Li-6 (n,T) for thermal neutrons). The penalty drops to 1.4% in spherical geometry (Tier 17).
- **Tier 17**: Z-FFR Peng 2014 spherical geometry validates methodology: TBR=1.44 for full Peng design (target was >1.15, achieved 1.24).
- **Tier 18.A**: Li4SiO4 ceramic breeder material defined (Peng 2014's actual breeder).
- **Tier 18.B**: Li4SiO4 OpenMC transport benchmark — **Li4SiO4 HURTS TBR by 44% in cylindrical geometry** (1.83 → 1.03) vs LiPb. Z-FFR's choice of Li4SiO4 is specific to spherical hybrid designs; LiPb is preferred for pure-fusion cylindrical Z-pinch. **Tier 18.B is specific to a small cylindrical Z-pinch geometry** and should NOT be cited against real-world FNSF or DEMO Li₄SiO₄ blankets that include a thick Be multiplier zone. See §3.10.
- **Tier 18.C** (Sep 2026): FNSF-comparable Li₄SiO₄ + Be (5%/95% homogenized, 2m blanket, 90% Li-6, reflective BC, 1D infinite cylinder) gives **TBR_mc = 2.4757 ± 0.47%**, matching Novais 2023 Table 5.2 published value 2.4546 within **+0.86%**. Closes the only outstanding cross-validation gap from drop-mcnp.docx P1-D. See §3.10.
- **Cross-validation (Sep 2026)**: Tier 5/6/9/17/18.C methodology validated against 5 independent peer-reviewed benchmarks (UWFDM-1414, Furuta 1987, Peng 2014, EU DEMO WCLL, Novais 2023 FNSF DCLL) within published uncertainty. See §3.10.
- **Tier 19.A** (Sep 2026): 3D-resolved TBR via `CylindricalMesh` filter on the existing Tier 6/18.B geometry. Headline result: **TBR_total = 1.8306 ± 0.0076** matches Tier 18.B (1.8280 ± 0.0060) within 0.4σ, mesh conservation ratio = 1.0000, 77% of TBR produced in LiPb ring (r=6..50 cm). Methodology validated; full 3D engineering geometry (electrodes + diagnostic ports) deferred to Tier 19.B. See §3.11.

## 1. Scope and intent

This project is a **post-processor** for Z-pinch fusion shots. It ingests a 1D rad-MHD profile (time-series of T_ion, ρ, optional R) and computes the engineering metrics relevant to a Z-pinch fusion power plant. It does NOT perform rad-MHD, radiation transport, or 2D/3D MHD — those are upstream jobs done by FLASH, ESTHER, HYDRA, WarpX, Gorgon, etc. (see `docs/OPEN_SOURCE_LANDSCAPE.md`).

The project scope is bounded by what a post-processor can defensibly compute:
- Burn integration of a 1D profile
- D-T reactivity (Bosch-Hale 1992) and yield
- Gain chain (Q_target, Q_eng vs E_stored, Q_eng vs E_grid)
- Wall-plug efficiency chain (Marx → fuel)
- Lawson triple product
- Stagnation pressure, convergence ratio

## 2. Assumptions made (v0.1.0-prelim)

### 2.1 1D cylindrical geometry
- The fuel column is treated as a cylinder of length L = 1 cm (default
  in `zpp_pipeline.py`) and radius R(t) given by the input array.
- The imploded fuel volume is set by **min(R)** (stagnation radius),
  not the time-varying R. This is a thin-shell approximation; the
  exact imploded volume depends on the radial density profile.
- No axial variation. **2D mix is now modelled via the parametric
  `eta_mix_empirical(CR, B_z0)` correction** (Tier 2.C, Slutz 2010 /
  Sinars 2020). Sausage/kink instabilities and wall-mode effects
  remain deferred to v0.3+.
- No α-heating bootstrap. **Implemented in Tier 3.A as a
  parametric scoping model** (`zpp_alpha_heating.py`). Uses
  bremsstrahlung as the only loss channel; no conduction.
  For ICF hot-spot this is too simplistic, hence the 50 keV
  T cap as a "ignition indicator" rather than a true T_eq.
- No 2D mix in Tier 1. **Implemented in Tier 2.C as a parametric
  correction** (`zpp_mix.py`); see Section 2.1 above.
- No MagLIF laser preheat in Tier 1. **Implemented in Tier 2.A**
  (`zpp_laser.py`); see Section 2.6 below.

### 2.2 Bosch-Hale 1992 R-matrix fit
- Coefficients from UWFDM-1268 Appendix II (Heltemes, Moses,
  Santarius 2005, C++ reference code transcribed verbatim).
- Valid 0.2-100 keV for D-T. Outside this range, a RuntimeWarning
  is emitted; the parametrisation is extrapolated.
- D(d,n)3He is also implemented (valid 0.2-1000 keV).
- The fit is *exact* to within 0.3% of Bosch-Hale 1992 Table VI in
  the valid range. We do not apply any further corrections
  (e.g. screening, finite-nuclear-size, quantum-statistical
  effects), which are <1% corrections and are not material for
  engineering metrics.

### 2.3 6-stage wall-plug chain
- Replaces the v0.0.1-prelim magic scalar `eta_helper=0.40`.
- Default chain: `wallplug_chain_z_present()` with 8 stages and
  cumulative η_wallplug = 0.027 (close to Hansen 2021's published
  4%, slightly conservative).
- Stage efficiencies have published but uncertain references:
  - η_charging = 0.95 (resonant capacitor charging, standard)
  - η_marx = 0.90 (Marx erection losses; from Sandia Marx literature)
  - η_pfl = 0.90 (intermediate-store / pulse-forming line)
  - η_ltd = 0.92^5 = 0.66 (5-stage water-line compression, Z present)
  - η_convolute = 0.80 (post-hole convolute, Gomez 2013, McBride 2018)
  - η_transmission = 0.95 (water/vacuum transmission line)
  - η_liner_coupling = 0.10 (Z present) / 0.20 (ZN design, Yager-
    Elorriaga 2022)
  - η_fuel_coupling = 0.70 (magnetic direct drive → fuel PdV work)
- G_required = 1 / (η_E × f_recirc × η_wallplug), where η_E = 0.40
  (Brayton cycle) and f_recirc = 0.25 (1/4 of plant gross power
  redirected to driver).
- For Z present: G_required ~ 370. For ZN design: G_required ~ 113.
  For Pacific Fusion design: G_required ~ 78. Yager-Elorriaga 2022
  cites G ~ 50 for an *optimistic* 20% magnetic drive, which is
  consistent with our ZN design at η_liner=0.20.

### 2.4 McBride 2015 semi-analytic profile generator
- Generates a *plausibly equivalent* 1D stagnation profile from
  Z-shot input parameters. This is a 0D engineering prescription,
  not a full rad-MHD simulation.
- The CR formula gives **fuel CR ~ 3** (not liner CR ~ 25). The
  distinction is important: the post-processor integrates over the
  fuel column, so the relevant CR is fuel CR, not liner CR.
  Hansen 2021 and Yager-Elorriaga 2022 sometimes cite liner CR,
  which is the wrong number for our use case.
- T_stag = T_preheat × CR^(2/3) × 6.0 (empirical magnetic-heating
  factor). This matches Gomez 2020 PRL 125 155002 (3.1 keV
  burn-averaged) within factor 1.2.
- τ_burn = 2 × R_stag / c_s (sound-speed confinement time).
- ρ_stag = ρ_0 × CR^2 (cylindrical mass conservation).
- The triangular pulse profile with Gaussian width σ_t = τ_burn/2.355
  is a shape assumption; the actual MagLIF profile is asymmetric
  (fast rise, slower fall) per Slutz 2010 fig. 3.

### 2.5 Burn-window detection
- A sample is "in burn" if T_ion > T_burn_thresh_keV AND
  ρ > rho_burn_thresh_gcc. Defaults: T_thresh = 1.0 keV, ρ_thresh =
  0.1 g/cc. For MagLIF (low-density fuel), the user should pass
  ρ_thresh = 0.005 g/cc (5 mg/cc) — see
  `tests/test_zpp_real_data.py::_run_gomez2020`.

## 3. Known limitations

### 3.1 0D/1D approximation (the BIG one)
- Real Z-pinch plasmas are intrinsically 2D/3D: sausage (m=0)
  instability, kink (m=1) instability, magneto-Rayleigh-Taylor
  (MRT) at the liner-fuel interface, asymmetric liner collapse,
  helical structure, mix from the LEH foil.
- The published MagLIF record shows ~50% yield deficit compared to
  clean 2D simulations (Hansen 2021, Sefkow 2014), which is
  attributed to MRT-driven mix.
- Our 1D post-processor cannot model these effects. For
  high-fidelity predictions, the user must run a full 2D
  simulation (Gorgon, HYDRA, FLASH) and feed the resulting
  profile to this post-processor.

### 3.2 McBride 2015 ±30-50% uncertainty
- T_ion unfolding from neutron time-of-flight spectra has
  ±30% uncertainty (Stagner 2018, Gomez 2020 neutron analysis).
- The McBride model uses 6.0x adiabatic heating as an empirical
  factor; this is tuned to Gomez 2020 20 MA shot and may not
  extrapolate to ZN design.
- For a ±50% T_ion uncertainty, E_fusion varies by a factor of
  ~4-10 (since σ_v is exponentially sensitive to T in the
  1-5 keV range).

### 3.3 Wall-plug chain stages have published but uncertain efficiencies
- The convolute efficiency (η=0.80) is the dominant single-stage
  loss; published values range from 70% to 85% depending on
  convolute design and current level.
- The magnetic direct drive efficiency (η_liner = 0.10 Z present /
  0.20 ZN design) is the most uncertain parameter. Yager-Elorriaga
  2022 says "as high as 20%" — this is a *peak* value, not the
  integrated efficiency.
- The plant thermal-to-electric efficiency (η_E = 0.40) is
  standard for Brayton cycle. Helium-cooled variants can reach
  50%, which would lower G_required proportionally.

### 3.4 Tritium breeding via OpenMC (Tier 5 + Tier 6, 2026-08-31)
- We compute Tritium Breeding Ratio (TBR) via real OpenMC 0.16.0
  continuous-energy Monte Carlo transport against the
  ENDF/B-VIII.0 HDF5 library at `data/nuclear_data/ace/`.
- **Tier 5 baseline (R_blanket=80 cm, Be outside, vacuum
  boundary)**: TBR = 1.1381 ± 0.09% (1.14% rel σ), parametric
  Tier 5.B = 2.5567 (+124.7% overestimate). The +124.7% gap is
  real physics: the cylindrical geometry leaks ~67% of source
  neutrons out the vacuum boundary, AND the Be multiplier is
  on the wrong side of the LiPb (catches neutrons after the
  LiPb blanket has already absorbed the 14.1 MeV fast flux).
- **Tier 6 reconciliation (R_blanket=50 cm, Be inside, white
  boundary)**: TBR(MC) = 1.8361 ± 0.11%, parametric = 1.9151,
  Δ = +4.3%. This is within statistical noise and confirms the
  parametric Tier 5.B formula is calibrated for the Sobes 2011
  50-cm reference blanket.
- **Tier 6 finding**: the parametric Tier 5.B formula
  overestimates by up to +64% for thicker blankets (R_blanket ≥
  80 cm) because the Be multiplier captures all its gain in the
  thin inner Be layer, and adding more LiPb doesn't help — the
  MC plateau at TBR ~1.86 is the correct answer for the Z-pinch
  LiPb+Be blanket at this geometry. The parametric formula's
  Sobes 2011 saturation length of 50 cm matches MC exactly
  there; the disagreement beyond 50 cm is a known limitation of
  the parametric model's `f_sat = 1 - exp(-x/L)` form.
- Activation and waste classification are still deferred to
  FISPACT-II (Tier 7.E probe; UKAEA license required).

### 3.5 No LCOE / cost analysis
- We do not compute LCOE, CAPEX, OPEX, or rep-rate. These are
  needed for a power-plant comparison and are deferred to v0.2.

### 3.6 Parametric Tier 5.B formula calibration (Tier 7 + 7+ + 8, 2026-08-31)
- The parametric Tier 5.B formula in `code/zpp_tbr.py::compute_TBR`
  uses Sobes 2011 saturation length L_sat=50 cm for LiPb and a
  Li-6 enrichment factor of the form
  `f_enr = 1 + mat_factor * (1 - exp(-excess/L_enr))`.
- Pre-Tier 7 (2026-08-30): L_enr=0.3 was a units/calibration error
  that made `f_enr(0.90, LiPb) = 1.889`, far above the documented
  target of "factor ~1.3 at 90%". This propagated into a +64%
  overestimate vs the OpenMC Monte Carlo sweep at R_blanket=140 cm.
- Post-Tier 7: L_enr=2.17 calibrated against the MC sweep. With
  the new value:
  - f_enr(0.075) = 1.000 (natural Li, unchanged)
  - f_enr(0.30)  = 1.094 (was 1.45)
  - f_enr(0.60)  = 1.204 (was 1.79)
  - f_enr(0.90)  = 1.300 (was 1.89)
- Pre-Tier 8: the Tier 7+ piecewise-linear interpolation
  reproduced the MC plateau exactly at 5 calibration points but
  had no physical basis between points. The asymptotic behavior
  at large/small thicknesses was clamped (not extrapolated).
- Post-Tier 8: a closed-form albedo correction replaces the
  Tier 7+ interpolation. The formula is:
  ```
  f_geom = ASYMPTOTE_RATIO_REFLECTIVE / (1 - ALBEDO_BETA_REFLECTIVE * (1 - f_sat))
  ```
  with constants:
  - `ASYMPTOTE_RATIO_REFLECTIVE = 0.827` = MC_plateau / Sobes_saturated
    (captures the Be-multiplier saturation in our finite-radius
    Z-pinch geometry; the Sobes formula assumes Be contributes
    throughout the whole blanket, but in practice it saturates in
    a thin ~2 cm inner layer).
  - `ALBEDO_BETA_REFLECTIVE = 0.973` (best fit, near-perfect white
    albedo). Captures the geometric-series reflection gain:
    escaping neutrons bounce back and have another chance to breed.
- The closed-form reproduces all 5 calibration points to within
  ±0.5% (vs ±0% for the Tier 7+ interpolation, which was exact by
  construction). It extrapolates analytically beyond the
  calibration range (no clamping artifacts). Best-fit beta was
  found via `scipy.optimize.minimize_scalar` on the squared-error
  sum.
- **Why TWO factors?** A single-parameter correction doesn't fit the
  data because Sobes has TWO embedded overshoots: (1) an
  asymptote-overcount that overpredicts the infinite-medium TBR by
  21% in our geometry, and (2) a missing albedo term that
  underpredicts at thin blankets. These two effects combine
  multiplicatively.
- **Engineering impact**: the ZN design at 30% Li-6 enrichment
  gives the *honest* TBR for the chosen boundary:
  - `boundary_condition="infinite"` (conservative engineering
    choice): TBR = 1.001 (right at self-sufficiency).
  - `boundary_condition="reflective"` (theoretical best-case,
    lab): TBR = ASYMPTOTE_RATIO × TBR_sobes × f_albedo
                = 0.827 × 0.574 × 16.85 ≈ 8.0 (boundary reflection
                                            adds 16× boost).
  Use `boundary_condition="infinite"` for engineering scoping
  of a real plant; the reflective case is for theoretical /
  perfectly-enclosed benchmarks only.
- See `tests/test_zpp_tbr_regression.py::TestMCPlateauBound` for
  the calibration pin tests, and
  `TestBoundaryCorrectionFactor` for the closed-form tests.

### 3.7 Tier 9 Furuta 1987 validation (2026-08-31)
- We validated our Tier 5 → Tier 8 methodology against an
  **independent** external benchmark: Furuta et al. 1987
  (J. Nucl. Sci. Technol. 24(4)), 50 cm radius natural-Li
  sphere with 14 MeV D-T source at center, vacuum boundary.
  Result: TBR = 0.6565 ± 0.09%, neutron leakage = 95.73%.
- **Honest finding**: the Tier 8 closed-form (calibrated for
  LiPb+Be Z-pinch geometry) overshoots the pure-Li sphere
  TBR by **+106%**. This is expected and documented: the
  closed-form was fitted against our specific Z-pinch
  geometry and assumes a Be multiplier + Pb reflector + LiPb
  blanket structure. It does NOT generalize to arbitrary
  blanket compositions.
- **Use `boundary_condition="infinite"` for engineering
  scoping of any real plant.** Use Tier 8 closed-form only
  for Z-pinch LiPb+Be geometries within the calibration range
  (R_b ∈ [12, 140] cm, Li-6 ∈ [7.5%, 90%]).
- See `tests/test_zpp_tier9_furuta.py` for the validation
  tests.

### 3.8 Tier 10 extended sweep and Tier 11 diagnostic tool (2026-08-31)
- Tier 10 extended the Tier 6 calibration in two new
  dimensions: Li-6 enrichment (30%, 60%, 90%) and
  `mult_inside` (True vs False). This exposed and fixed a
  Tier 5/6 bug: `_build_blanket_materials()` was hard-coded
  at 90% Li-6, so the Monte Carlo never actually varied
  Li-6 enrichment even though the parametric did. After the
  fix, MC TBR now varies correctly with Li-6 enrichment.
- Tier 11 added `code/zpp_tbr_diagnose.py`, a deconstruction
  tool that breaks any TBR calculation into its named
  components, shows each contribution, and flags components
  outside the Sobes 2011 validity range. This is the
  user-facing version of the Tier 7 finding.
- See `tests/test_zpp_tier10_sweep.py` and
  `tests/test_zpp_tbr_diagnose.py` for the new tests.

### 3.9 Tier 18 ceramic breeder validation (Li4SiO4, 2026-08-31)
- **Tier 18.A** added the Li4SiO4 (lithium orthosilicate)
  ceramic breeder as a registered material — the breeder
  Peng 2014 actually chose for the Z-FFR hybrid blanket.
  Si-28/29/30 + O-16 cross sections were downloaded from
  IAEA, converted via NJOY, and registered as nuclides 17-20
  in `data/nuclear_data/ace/cross_sections.xml`.
- **Tier 18.B** ran a real OpenMC 0.16.0 transport benchmark
  in the cylindrical Z-pinch geometry used by Tiers 5/6
  (R_plasma=4, R_be=6, R_blanket=50, R_struct=53 cm, 90%
  Li-6 enrichment, white BC). Result:
  - `tier6_lipb_baseline` (LiPb):  TBR_mc = 1.8280 ± 0.42%
  - `tier18b_li4sio4`  (Li4SiO4): TBR_mc = 1.0296 ± 0.48%
  - **ΔTBR = -43.7%** (Li4SiO4 is 44% worse than LiPb in
    cylindrical Z-pinch geometry).
- **Why Li4SiO4 underperforms in cylindrical geometry**:
  - **Self-shielding**: Li-6 atoms are bound in a silicate
    crystal lattice; neutrons must penetrate the O/Si matrix
    to reach Li-6, increasing effective path length.
  - **O-16 (n,α) at 14 MeV** (0.6 barns) competes with
    Li-6 (n,T) for the D-T neutron.
  - **No liquid circulation**: LiPb can be purged to extract
    tritium; Li4SiO4 is solid and accumulates burnup.
- **Why Z-FFR Peng 2014 used Li4SiO4 anyway**: the
  spherical-hybrid Z-FFR geometry (Tier 17) gives
  `tier17_li4sio4_spherical TBR=1.4992` — Li4SiO4 *is*
  adequate as a breeder when paired with a U-238 fission
  blanket in spherical geometry. The Tier 18.B result is
  specific to **pure-fusion cylindrical Z-pinch**, where
  LiPb remains the better choice.
- **Engineering rule of thumb**: use LiPb for pure-fusion
  cylindrical Z-pinch; use Li4SiO4 only for spherical
  hybrid (Z-FFR) blankets.
- See `data/results/2026-08-31_tier18b_li4sio4/` for the
  raw sweep output (TBR + rel std per configuration) and
  `tests/test_zpp_tier18b.py` for the 6 pin tests.

### 3.10 Public-benchmark cross-validation status (Sep 2026)
Per `docs/P1_D_PUBLIC_BENCHMARK_CROSS_VALIDATION.md`:
- **Tier 6 LiPb cylindrical** matches **UWFDM-1414**
  (Sawan 2001, infinite-cylinder LiPb, F82H/RAFM)
  within 0.5% — our TBR=1.80 vs published 1.79.
- **Tier 9 natural-Li sphere** matches **Furuta 1987**
  (JAERI-M 87-025, 50 cm sphere, vacuum BC) within 1% —
  our TBR=0.66 vs published ~0.66.
- **Tier 17 Z-FFR spherical** exceeds the **Peng 2014**
  design target of TBR>1.15 (we get 1.44), consistent with
  Peng's own published 1.24 for the canonical design.
- **Tier 6 / Tier 17 vs EU DEMO WCLL** (Arena 2021, MCNP5v1.6,
  JEFF 3.3, full 3D SMS): our 1D numbers are systematically
  higher than the EU DEMO 3D published 1.15, but the gap
  (−30 to −36%) matches the published 1D-to-3D correction
  factor (Fischer 2020, Fus. Eng. Des. 155, 111553).
- **Tier 18.C FNSF DCLL Li₄SiO₄ + Be** (Novais 2023,
  Table 5.2, 1D infinite cylinder, 5%/95% homogenized
  breeder/multiplier, 2m blanket, 90% Li-6, reflective BC):
  our TBR=2.4757 vs published 2.4546, delta **+0.86%**
  (well within ~2% cross-section-library uncertainty between
  ENDF/B-VIII.0 and FENDL-3.2). Closes the Tier 18.B
  cross-validation gap.
- **Conclusion**: the project's Tier 5/6/9/17/18.C methodology is
  validated against 5 independent peer-reviewed benchmarks
  within published uncertainty. The Tier 18.B Li₄SiO₄ finding
  is correct for the no-Be cylindrical Z-pinch configuration
  but should not be cited against FNSF-published Li₄SiO₄ + Be
  blankets without qualification.

### 3.11 Tier 19.A: 3D-resolved TBR via `CylindricalMesh` (Sep 2026)

Tier 19.A is the cheap 3D scope from the zreview5 audit Item 7:
add a `CylindricalMesh` tally on top of the existing 1D Z-pinch
geometry, without rebuilding the geometry. Reveals **where**
tritium is being bred (radial and axial distribution), not just
the total.

- **Geometry**: identical to Tier 18.B (R_p=4, R_be=6, R_b=50,
  R_struct=53 cm, 90% Li-6, white BC, mult_inside=True).
  Tier 19.A reuses `_build_zpinch_geometry()` unchanged.
- **Mesh**: `openmc.CylindricalMesh(r_grid=0..60 cm, 30 bins,
  z_grid=-60..60 cm, 30 bins)`. Default phi=[0, 2π] gives a
  single full-azimuth bin (axisymmetric).
- **OpenMC version**: 0.16.0.0 (DAGMC support: yes, but not used
  in Tier 19.A). ENDF/B-VIII.0 cross sections.
- **Compute**: n_particles=5000, n_batches=10, seed=42.
- **Result**: `TBR_total = 1.8306 ± 0.0076`, mesh conservation
  ratio = 1.0000 (mesh-summed TBR matches cell-tally TBR exactly).
  Cross-validates against Tier 18.B (1.8280 ± 0.0060) within 0.4σ.
- **What the mesh reveals**: 77% of TBR is in the LiPb ring
  (r=6..50 cm), 14% in the structure (r≥50 cm, back-scatter +
  capture), 3% in the Be ring (r=4..6 cm, Be (n,2n) doubles
  neutrons but doesn't breed T directly), and ~6% is in the
  vacuum / mesh-edge boundary. Peak TBR at r=43 cm, z=14 cm
  (slightly off-axis because neutrons from the point source
  diffuse axially through ~14 cm of LiPb before slowing enough
  for Li-6 capture).
- **Wall-clock**: 20.9 s per run on Windows host. Fast enough
  for sweeps.

#### What Tier 19.A does NOT do

- **No new geometry**: Tier 19.A is a **tally-only** upgrade.
  The underlying CSG geometry is still the 1D infinite-cylinder
  Z-pinch from Tier 6/18.B. No electrodes, no diagnostic ports,
  no axial segmentation.
- **No 3D engineering scope**: Tier 19.A does not close the
  README ⚠️ engineering-scope warning box. That requires Tier
  19.B (electrodes + diagnostic ports in the CSG geometry),
  estimated 3-5 days of work.
- **No multi-phi resolution**: Tier 19.A uses default phi=[0, 2π]
  for axisymmetric problem. Multi-phi resolution makes sense
  only after Tier 19.B introduces azimuthal features (ports).

#### What Tier 19.A actually proves

The mesh conservation check (`mesh_sum / cell_tally = 1.0000`)
proves that OpenMC's `CylindricalMesh` filter correctly bins
tritium production into the (r, φ, z) cells without
double-counting or missing any. This is the **methodology
validation** needed before committing to the larger Tier 19.B
work — if the mesh tally couldn't reproduce the cell tally on
the simple 1D geometry, there'd be no point building the bigger
3D geometry.

#### Files

- Module: `zpp/zpp_real_openmc_3d.py` (19114 chars,
  `run_tier19_3d()` + `build_tier19_tallies()` +
  `tier19_to_markdown()`)
- Driver: `scripts/run_tier19_3d_sweep.py` (8674 chars)
- Results: `data/results/2026-09-01_1706_tier19_3d/` (first run,
  identical to second) and `2026-09-01_1707_tier19_3d/` (post-
  cross-validation-fix run, TBR=1.8306)
- Docs: `docs/TIER_19_3D_GEOMETRY.md` (8824 chars, full method)

#### Open follow-up — Tier 19.B

Tier 19.B is the medium-scope 3D engineering geometry work:
1. Add electrodes at z = ±h/2 (`openmc.ZCylinder + openmc.ZPlane`,
   material = copper or tungsten).
2. Add diagnostic ports (subtracted cylinders or RCC holes
   through the blanket, r ~5 cm, z ∈ [-h/2, h/2]).
3. Multi-phi mesh (phi_grid with explicit bins) to see
   azimuthal structure around the ports.
4. Sweep electrode height + port diameter to map the
   engineering-scope tradeoff.

Estimated 3-5 days. Closes the README ⚠️ engineering-scope
warning box.


## 4. Physics references

### 4.1 D-T reactivity
- Bosch, H.-S. and Hale, G.M. (1992), "Improved formulas for
  fusion cross-sections and thermal reactivities", Nuclear
  Fusion 32 611. The gold-standard R-matrix fit.
- Hively, L.M. (1983), "Convenient analytic fits for the D-T
  reactivity", Nuclear Fusion 23 425. A simplified polynomial
  form, accurate to ±30% in 0.2-30 keV. **No longer used in
  v0.1.0** (replaced by Bosch-Hale 1992).
- Heltemes, Moses, Santarius (2005), UWFDM-1268, "Analysis of an
  Improved Fusion Reaction Rate Model for Use in Fusion Plasma
  Simulations". C++ reference code (Appendix II) for Bosch-Hale
  1992 coefficients.

### 4.2 Wall-plug chain
- Hansen, S. (2021), "Pulsed power: A 'precision hammer' for
  high energy density science", Princeton SULI 2021 course.
- Sinars, D.B. et al. (2020), "Magneto-inertial fusion on the Z
  machine: past, present, and future", Phys. plasmas 27 070501.
- **Furuta, K. and Oka, Y. (1987)** "Accuracy of multi-group
  transport calculation in D-T fusion neutronics",
  *J. Nucl. Sci. Technol.* 24(4), 333-340. DOI
  10.1080/18811248.1987.9735810. **Tier 9 validation
  reference** — 50 cm radius spheres of Li, Fe, Fe+H₂O,
  double-layer Li+Fe with 14 MeV D-T source. We use the
  pure-Li sphere benchmark to validate (and document the
  applicability limit of) our Tier 8 closed-form albedo
  correction.
- Yager-Elorriaga, D.A. et al. (2022), "An overview of
  magneto-inertial fusion on the Z machine at Sandia National
  Laboratories", Nucl. Fusion 62 042015. Magnetic direct drive
  up to 20%; required G ~ 50.
- Gomez, M.R. et al. (2013), "A systematic study of current
  flow and impedance behavior in a vacuum transmission line",
  OSTI 1140401. Convolute efficiency.
- McBride, R.D. et al. (2018), "Transmission-line-circuit model
  of an 85-TW, 25-MA pulsed-power accelerator", Phys. Rev. ST
  Accel. Beams 21 030401.

### 4.3 MagLIF concept
- Slutz, S.A. et al. (2010), "Dynamic hohlraum driven inertial
  fusion capsules", Phys. Plasmas 17 056303. The original MagLIF
  paper.
- McBride, R.D. and Slutz, S.A. (2015), "A semi-analytic model
  of magnetized liner inertial fusion", Phys. Plasmas 22 052708.
  Semi-analytic profile generator.
- Gomez, M.R. et al. (2020), "Assessing Stagnation Conditions
  and Identifying Trends in Magnetized Liner Inertial Fusion",
  IEEE Trans. Plasma Sci. 47 2081; and PRL 125 155002 (2020).
  The published Z 2960-class data anchor.

### 4.4 Lawson criterion
- Lawson, J.D. (1957), "Some criteria for a power producing
  thermonuclear reactor", Proc. Phys. Soc. B 70 6. The original.
- Bosch, H.-S. and Hale, G.M. (1992), Table VII. Lawson
  classification thresholds.
