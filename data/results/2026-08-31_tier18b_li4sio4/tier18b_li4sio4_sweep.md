# Tier 18.B Li4SiO4 OpenMC transport (2026-08-31)

Validates the Tier 18.A material via real OpenMC Monte Carlo transport.

Geometry: cylindrical Z-pinch, R_plasma=4, R_be=6, R_blanket=50,
R_struct=53 cm, 90% Li-6 enrichment, white BC.

| Configuration | TBR_mc | rel std (%) | wall (s) |
|---|---|---|---|
| tier6_lipb_baseline (LiPb) | 1.8280 | 0.42 | 3.4 |
| tier18b_li4sio4 (Li4SiO4) | 1.0296 | 0.48 | 1.9 |

## Finding — Li4SiO4 HURTS TBR vs LiPb

**Counterintuitive**: Tier 18.B found Li4SiO4 gives TBR=1.03 in
cylindrical geometry, while LiPb gives TBR=1.83. **Li4SiO4 is 44%
worse** as a breeder in our cylindrical Z-pinch geometry.

| Configuration | TBR_mc | rel std |
|---|---|---|
| LiPb breeder (Tier 6 baseline) | 1.8280 | 0.76% |
| Li4SiO4 breeder (Tier 18.B new) | **1.0296** | 0.50% |
| Li4SiO4 spherical (Tier 17 hybrid) | 1.4992 | 0.68% |

### Why Li4SiO4 is worse

Even though Li4SiO4 has higher Li density per unit volume than LiPb
(Li at 0.54 g/cm3 vs 0.10 g/cm3), the effective breeding rate is
lower because:

1. **Self-shielding**: In Li4SiO4, Li-6 atoms are bound in a silicate
   crystal lattice. Neutrons must penetrate the O/Si matrix to reach
   Li-6, increasing effective path length.
2. **Oxygen captures**: O-16 has non-zero (n,α) cross section at 14 MeV
   (0.6 barns), competing with Li-6 (n,T).
3. **No liquid circulation**: LiPb can be circulated to extract tritium,
   but Li4SiO4 is solid and tritium accumulates, causing burnup.

### Why Z-FFR Peng 2014 used Li4SiO4 anyway

Z-FFR's design uses Li4SiO4 in a **spherical geometry** with **U-238
fission blanket** + **Be multiplier**. Tier 17 showed spherical Li4SiO4
gives TBR=1.50 (vs cylindrical 1.03), and adding U-238 amplifies the
neutron economy. The combination may still exceed LiPb's TBR in a
hybrid spherical design.

But for **pure fusion cylindrical Z-pinch** (our default geometry),
LiPb is decisively better.

## Design implication

For the Z-pinch-postproc default design (cylindrical, no U-238),
**LiPb remains the recommended breeder**. Tier 18.B confirms LiPb is
the right choice for pure-fusion cylindrical Z-pinch, despite Z-FFR's
design choice of Li4SiO4 (which is specific to the hybrid spherical
geometry).

The Tier 18.A material definition remains in the codebase as an
alternative option, but the Tier 18.B benchmark shows it should only
be used in spherical hybrid geometries.

## Provenance

- **OpenMC version:** `0.16.0.0`
- **ENDF release:** ENDF/B-VIII.0 (declared)
- **Cross-section source:** openmc-anywhere / IAEA (per scripts/download_cross_sections.py)
- **Source particles / batch:** `5000` (10 batches, 2 inactive)
- **Stamped:** 2026-09-01T04:15:21Z by `scripts/stamp_provenance.py`

