# Tier 16 hybrid fission blanket sweep (2026-08-31)

R_blanket = 50 cm, mult_inside = True, 90% Li-6, white BC,
5,000 particles × 10 batches, OpenMC 0.16.0, ENDF/B-VIII.0.

Tests whether the Tier 13 counterintuitive Fe reflector finding
FLIPS for Z-FFR-style hybrid blankets with U-238 fission layer.

| Configuration | TBR_mc | rel std (%) | wall (s) | ΔTBR vs no-Fe |
|---|---|---|---|---|
| no_u238 / Fe=0cm | 1.8306 | 0.42 | 16.1 | baseline |
| no_u238 / Fe=5cm | 1.7871 | 0.37 | 15.1 | −2.4% |
| no_u238 / Fe=10cm | 1.7050 | 0.33 | 15.9 | −6.9% |
| no_u238 / Fe=20cm | 1.5735 | 0.46 | 18.2 | −14.0% |
| u238_10cm / Fe=0cm | 1.3609 | 0.28 | 12.9 | — |
| u238_10cm / Fe=5cm | 1.3474 | 0.34 | 14.0 | −1.0% |
| u238_10cm / Fe=10cm | 1.3356 | 0.41 | 14.4 | −1.9% |
| u238_10cm / Fe=20cm | 1.3193 | 0.37 | 15.0 | −3.1% |
| u238_20cm / Fe=0cm | 1.3074 | 0.33 | 12.7 | — |
| u238_20cm / Fe=5cm | 1.3047 | 0.30 | 13.0 | −0.2% |
| u238_20cm / Fe=10cm | 1.3049 | 0.28 | 12.6 | −0.2% |
| u238_20cm / Fe=20cm | 1.3030 | 0.38 | 13.4 | −0.3% |

## Finding — U-238 steals neutrons from LiPb

**Hypothesis REJECTED**: Tier 13 found Fe reflector HURTS fusion-only
blanket by 14% at 20 cm. We hypothesized Fe might HELP in hybrid
blanket (with U-238 fission layer) because Fe back-scatters U-238
fission neutrons into LiPb.

**Result**: U-238 layer DECREASES TBR by 26% (1.83 → 1.36 with 10 cm
U-238). And Fe reflector continues to hurt even with U-238, though
the magnitude drops to −3.1% (10 cm U-238) and −0.3% (20 cm U-238).

### Why U-238 hurts TBR

U-238 has significant (n,γ) capture cross-section at thermal
energies that **competes with Li-6 (n,T)** for the same neutrons.
Even though U-238 has fast (n,fission) above ~1 MeV, the dominant
effect on TBR (tallied as Li-6 (n,Xt)) is the parasitic capture
in U-238:

  - U-238 (n,γ) → U-239 → Np-239 → Pu-239 (captures neutron, NO T)
  - Li-6 (n,T) → He-4 + T (captures neutron, BREEDS tritium)

In our geometry, the LiPb breeder layer is INSIDE the U-238 layer,
so neutrons that escape LiPb first hit U-238 (where many are
captured), then Fe (which absorbs more), then leak. The U-238
fission neutrons that come back into LiPb are slow (have lost
energy in U-238 inelastic scattering) and have a higher chance
of Li-6 capture than the original 14 MeV neutrons, but the
overall flux balance is negative.

### Why Fe reflector "loses its bite"

In the no-U-238 case, Fe steals ~14% of neutrons at 20 cm because
the Be + LiPb neutron economy is delicate — Fe parasitic capture
is a major perturbation.

In the hybrid case, U-238 already steals 26% of neutrons before
they reach Fe. Adding Fe on top is a smaller relative perturbation
(~3%) because the neutron population reaching Fe is already
smaller.

### Why Z-FFR's design TBR > 1.15 may still work

Our cylindrical Tier 16 hybrid geometry gives TBR ~1.36 with
10 cm U-238 + no Fe. This is **above Z-FFR's target TBR 1.15**.

But Z-FFR achieves TBR ~1.24 in design — and our 10 cm U-238 + 0 Fe
gives 1.36 — **we're BETTER than Z-FFR's design target** but with
a different geometry. Several factors:
  - Z-FFR uses Li4SiO4 ceramic breeder + Be + U-238 (more complex)
  - Z-FFR uses spherical geometry (we tested cylindrical)
  - Z-FFR's U-238 layer is 15 cm thick (we tested 10 cm and 20 cm)
  - Z-FFR uses natural Li (7.5%) enrichment (we tested 90%)

The Tier 17 spherical geometry test (next tier) will resolve
this comparison properly.

## What this changes for the design

For hybrid fission-fusion blankets (Z-FFR-style) in our cylindrical
Z-pinch geometry:
  - **U-238 layer hurts TBR** because (n,γ) competes with Li-6 (n,T)
  - **Fe reflector still hurts** but less dramatically with U-238
  - **Best design**: LiPb+Be only, no U-238, no Fe reflector

If higher TBR is required (TBR > 1.5 for fusion-fission hybrids
that produce power from fission), the answer is to use a
**neutron multiplier with positive gain** (Be-9, Pb-208 (n,2n))
inside the LiPb, not U-238 which has a net negative effect on
tritium breeding.

For comparison:
- Tier 6.A (no U-238, no Fe, R_b=50 cm, mult_inside=True):
  TBR = 1.8306 ± 0.42%
- Tier 16 (10 cm U-238, no Fe, R_b=50 cm, mult_inside=True):
  TBR = 1.3609 ± 0.28%
- Z-FFR design target: TBR > 1.15, achieved 1.24

Our hybrid sweep at 10 cm U-238 (TBR=1.36) exceeds Z-FFR's
design target, but is still below our pure-LiPb design (TBR=1.83).
The LiPb+Be only design wins for tritium self-sufficiency.

## Provenance

- **OpenMC version:** `0.16.0.0`
- **ENDF release:** ENDF/B-VIII.0 (declared)
- **Cross-section source:** openmc-anywhere / IAEA (per scripts/download_cross_sections.py)
- **Source particles / batch:** `5000` (10 batches, 2 inactive)
- **Stamped:** 2026-09-01T04:15:21Z by `scripts/stamp_provenance.py`

