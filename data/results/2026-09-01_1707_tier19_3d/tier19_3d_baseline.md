# Tier 19 — 3D Mesh TBR

**Run timestamp**: 2026-09-01 (Tier 19.A — first 3D-mesh TBR ship)

## Geometry

| Parameter | Value |
|---|---|
| R_plasma | 4.0 cm |
| R_be (Be multiplier) | 6.0 cm |
| R_blanket (LiPb outer) | 50.0 cm |
| R_structure (RAFM outer) | 53.0 cm |
| height | 100.0 cm |
| Li-6 enrichment | 90% |
| boundary_type | white |
| mult_inside (Be before LiPb) | True |
| n_particles × n_batches | 5,000 × 10 |

## Headline TBR

| Quantity | Value |
|---|---|
| **TBR_total** (cell tally, sum over nuclides) | **1.8306 ± 0.0076** |
| TBR_3d_sum (mesh sum, sanity check) | 1.8306 |
| **Match ratio (mesh sum / cell tally)** | **1.0000** |
| Peak TBR location | r = 43.00 cm, z = 14.00 cm |
| Peak TBR value | 9.1931e-03 |

**Cross-check vs Tier 6 baseline (1.80 ± 0.23%)**: this Tier 19.A result of
1.8306 should agree within statistical noise.

## Where the tritium is being bred

The 3D-mesh tally reveals the radial / axial distribution of tritium
production. Summed over all z-slices (i.e., total TBR per radial shell):

| Region | TBR contribution | Fraction |
|---|---|---|
| Be multiplier ring (r = 4.0–6.0 cm) | 0.0551 | 3.0% |
| **LiPb blanket ring (r = 6.0–50.0 cm)** | **1.4081** | **76.9%** |
| Structure + outside (r ≥ 50.0 cm) | 0.2639 | 14.4% |

## Runtime & reproducibility

- **Wall-clock runtime**: 20.9 s
- **Mesh shape**: (30, 30) (r × z, summed over nuclides)
- **Nuclides scored**: Li6, Li7
- **Cross-sections**: ENDF/B-VIII.0 (data/nuclear_data/ace/cross_sections.xml)

## Caveats

- The mesh resolves TBR on the existing **1D infinite-cylinder geometry**,
  NOT a 3D engineering geometry with electrodes. Tier 19.B (next) will add
  electrodes and diagnostic ports.
- The mesh bins outside the geometry (r > 53.0 cm,
  |z| > 50.0 cm) show near-zero TBR as expected (vacuum).
- Match ratio of 1.0000 should be ≈ 1.000 ± statistical
  noise. Any deviation >1% indicates mesh-resolution-induced bias.

## Files

- Source: `zpp/zpp_real_openmc_3d.py` (this module)
- Driver: `scripts/run_tier19_3d_sweep.py`
- Result JSON: see `data/results/<timestamp>_tier19_3d/`
