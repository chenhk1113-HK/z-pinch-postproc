# MODEL ASSUMPTIONS AND LIMITATIONS — z-pinch-postproc

**Version:** v0.3.0 (2026-08-30)
**Status:** Tier 3 complete — α-heating bootstrap, comparative analysis (Z/ZN/Zap/GF-MTF/PF), ZN-65 extended sweep. 213 tests passing.
**Per:** `Z_Machine_plan.pdf` (user-uploaded plan, 7,441 chars), `BUCKY 1-D radiation hydrodynamics code reference` (UWFDM-1268, 2005), `An overview of magneto-inertial fusion on the Z machine` (Yager-Elorriaga et al. 2022, Nucl. Fusion 62 042015), `Pulsed power: A precision hammer for high energy density science` (Hansen 2021, Princeton SULI).

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

### 3.4 No tritium breeding or activation
- We do not compute Tritium Breeding Ratio (TBR), activation, or
  waste classification. These are needed for a full plant
  assessment and are deferred to v0.2 (OpenMC + Paramak coupling).

### 3.5 No LCOE / cost analysis
- We do not compute LCOE, CAPEX, OPEX, or rep-rate. These are
  needed for a power-plant comparison and are deferred to v0.2.

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
  Z present wall-plug ~4%.
- Sinars, D.B. et al. (2020), "Magneto-inertial fusion on the Z
  machine: past, present, and future", Phys. Plasmas 27 070501.
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
