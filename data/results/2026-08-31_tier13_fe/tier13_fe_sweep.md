# Tier 13 Fe reflector sweep (2026-08-31)

R_blanket = 50 cm, mult_inside = True, 90% Li-6, white BC,
5,000 particles × 10 batches, OpenMC 0.16.0, ENDF/B-VIII.0.

| Fe thickness (cm) | TBR_mc | rel std (%) | wall (s) | ΔTBR vs no-Fe |
|---|---|---|---|---|
| 0 (no Fe) | 1.8306 | 0.42 | 16.1 | baseline |
| 5 | 1.7871 | 0.37 | 15.3 | −2.4% |
| 10 | 1.7050 | 0.33 | 16.4 | −6.9% |
| 20 | 1.5735 | 0.46 | 17.6 | −14.0% |

## Finding — counterintuitive result

**Adding an Fe reflector DECREASES TBR** in our LiPb+Be geometry,
in contrast to the expectation from Peng 2014 Z-FFR paper which
recommends Fe reflectors.

Physics explanation:

1. **Fe-56 has small (n,2n) cross-section at 14 MeV**.
   The dominant reactions in Fe-56 at 14 MeV are:
     - (n,n')p threshold at ~14 MeV but cross-section is small
     - (n,2n) threshold at ~14 MeV but cross-section is much
       smaller than Be-9 (which has σ(n,2n) ≈ 0.5 barns at 14 MeV
       vs Fe-56 ≈ 0.05 barns)
     - (n,p), (n,α) — these ABSORB neutrons without multiplying.

2. **Fe acts as a parasitic absorber, not a reflector.** In our
   LiPb+Be blanket, the Fe reflector (between Be and structure)
   catches neutrons that escape the LiPb but does NOT multiply
   them. The absorbed neutrons are lost.

3. **Z-FFR may use a different geometry or material system.**
   Peng 2014 Z-FFR uses a hybrid blanket (with fissionable fuel
   U-238 / Th-232). The Fe reflector helps in a FISSION blanket
   (because Fe back-scatters fast neutrons that then fission
   U-238), but in a FUSION-ONLY blanket it just absorbs them.
   Z-FFR is also spherical geometry, not Z-pinch cylindrical.

## What this changes for the design

For our **fusion-only LiPb+Be Z-pinch blanket**, the design
recommendation is:
  - **NO Fe reflector** between Be and structure
  - The Be layer (which has σ(n,2n) ≈ 0.5 barns at 14 MeV)
    IS the neutron multiplier, and putting Fe in series with it
    reduces the effective multiplier gain.

For a **hybrid fusion-fission blanket** (Z-FFR style), the Fe
reflector may still be useful — but Tier 13 does NOT test that
geometry. A v1.4 candidate Tier 15 would be: build a hybrid
blanket geometry with U-238 layer and re-run the Fe reflector
sweep to see if the sign flips.

For comparison, Tier 6.A baseline at R_b=50, mult_inside=True,
no Fe reflector gave TBR = 1.8306 ± 0.42% (this Tier 13 result
matches it within statistical error).

## Provenance

- **OpenMC version:** `0.16.0.0`
- **ENDF release:** ENDF/B-VIII.0 (declared)
- **Cross-section source:** openmc-anywhere / IAEA (per scripts/download_cross_sections.py)
- **Source particles / batch:** `5000` (10 batches, 2 inactive)
- **Stamped:** 2026-09-01T04:15:21Z by `scripts/stamp_provenance.py`

