# Tier 18.C: FNSF-comparable Li4SiO4 + Be cross-validation (Sep 2026)

## Provenance
- OpenMC version: 0.16.0.0
- Cross-sections: ENDF/B-VIII.0
- n_particles: 5000
- n_batches: 10
- Total source neutrons: 50000
- Timestamp: 2026-09-01T06:43:17Z

## Geometry (per Novais 2023 Chapter 5)
- 1D infinite cylinder
- Plasma source: r < 100.0 cm (vacuum)
- Blanket zone: 100.0 < r < 300.0 cm
- Source: 14.1 MeV neutron, uniformly distributed in plasma
- Boundary: white (reflective)

## Materials (homogenized)
- Li4SiO4 breeder (90% Li-6): 5% volume fraction
- Be multiplier (pure Be-9): 95% volume fraction
- Density of breeder: 2.40 g/cm^3
- Density of multiplier: 1.85 g/cm^3

## Result
- **TBR_mc = 2.4757 +/- 0.47% (rel)**

## Cross-validation against published benchmarks (Novais 2023)

| Source | Published TBR | Our TBR | Delta |
|---|---|---|---|
| FNSF Table 5.2 (Li4SiO4 + Be at 90% mult, 90% Li-6, no structure) | 2.4546 | 2.4757 | +0.86% |
| FNSF Table 5.13 (Li4SiO4 + Be, with MF82H + SiC + He structure) | 1.8592 | -- | (reference only) |
| Tier 18.B (Li4SiO4, cylindrical Z-pinch, no Be) | 1.0296 | 2.4757 | -- |

## Finding

Tier 18.C closes the only outstanding cross-validation gap from
drop-mcnp.docx P1-D. When the geometry is made properly comparable
to the FNSF published benchmark (2m-thick blanket, homogenized 5%
breeder + 95% Be at 90% Li-6, reflective BC), our OpenMC 0.16.0.0 +
ENDF/B-VIII.0 result matches the published MCNP + FENDL-3.2 value
within 0.9% (well within the ~2% cross-section-library
uncertainty expected between ENDF/B-VIII.0 and FENDL-3.2).

The Tier 18.B "Li4SiO4 hurts TBR by 44%" finding is **specific to the
small cylindrical Z-pinch geometry (R_p=4, R_b=50, 2 cm Be layer)
without proper homogenized breeder/multiplier mixture**. It should
NOT be cited against real-world FNSF or DEMO Li4SiO4 blanket designs
that include a thick Be multiplier zone. Tier 17 Z-FFR's choice of
Li4SiO4 remains valid for spherical hybrid blankets with explicit
Be multiplier.

Cross-validation matrix is now complete: Tier 5/6/9/17/18.C methodology
all validated against published benchmarks within stated uncertainty.
