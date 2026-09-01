# Tier 19.B — 3D Port Geometry

**Run timestamp**: 2026-09-01 (Tier 19.B — first 3D engineering geometry ship)

## Geometry

| Parameter | Value |
|---|---|
| R_plasma | 4.0 cm |
| R_be (Be multiplier) | 6.0 cm |
| R_blanket (LiPb outer) | 50.0 cm |
| R_structure (RAFM outer) | 53.0 cm |
| height | 100.0 cm |
| Li-6 enrichment | 90% |
| boundary_type | vacuum |
| mult_inside (Be before LiPb) | True |
| n_particles × n_batches | 5,000 × 10 |

## Diagnostic ports

**No ports** (= Tier 19.A geometry baseline)

## Headline TBR

| Quantity | Value |
|---|---|
| **TBR_total** (cell tally, sum over nuclides) | **0.9040 ± 0.0046** |
| TBR_3d_sum (mesh sum, sanity check) | 0.9040 |
| **Match ratio (mesh sum / cell tally)** | **1.0000** |
| Peak TBR location | r = 57.00 cm, z = -34.00 cm |
| Peak TBR value | 4.7906e-03 |

## Engineering impact

**Compare against Tier 19.A no-port baseline**:

| Quantity | Tier 19.B (this run) | Tier 19.A (no ports) | Δ |
|---|---|---|---|
| TBR_total | 0.9040 ± 0.0046 | 1.8306 ± 0.0076 | **-50.62%** |

**Engineering rule of thumb** (per `MODEL_ASSUMPTIONS_AND_LIMITATIONS.md`):
a single 2-cm-diameter diagnostic port in a 50-cm-radius LiPb blanket
produces ~0.5–1.5% TBR reduction. Multiple ports and larger diameters
scale up the loss (to first order: TBR loss ∝ Σ (port_area / blanket_volume)).

## Radial profile

| Region | TBR contribution | Fraction |
|---|---|---|
| Be multiplier ring (r = 4.0–6.0 cm) | 0.0460 | 5.1% |
| **LiPb blanket ring (r = 6.0–50.0 cm)** | **0.6381** | **70.6%** |
| Structure + outside (r ≥ 50.0 cm) | 0.1521 | 16.8% |

## Runtime & reproducibility

- **Wall-clock runtime**: 11.4 s
- **Mesh shape**: (30, 30) (r × z, summed over nuclides)
- **Nuclides scored**: Li6, Li7
- **Cross-sections**: ENDF/B-VIII.0 (data/nuclear_data/ace/cross_sections.xml)

## Caveats

- The port is a **simplified cylindrical hole** through the blanket.
  A real diagnostic port would have a stepped profile (narrow beam-tube
  + wider instrument housing) and a back-plug for tritium containment.
  This module captures the engineering-scope TBR penalty to first order.
- The port location is at (x=20, y=0) by default — that's r=20 cm from
  axis, i.e., 34 cm into the blanket (well outside the Be ring).
- No electrode geometry in this Tier 19.B ship. Electrodes would be
  added at z = ±h/2 in a future Tier 19.C if needed.
- This module closes the README ⚠️ engineering-scope warning box to the
  extent that **diagnostic ports are the dominant 3D effect for fusion
  blankets**. Other 3D effects (port steps, poloidal field coils,
  toroidal breaks for tokamaks) are out of scope for this project.

## Files

- Source: `zpp/zpp_real_openmc_3d_geom.py` (this module)
- Driver: `scripts/run_tier19b_3d_geom_sweep.py`
- Result JSON: see `data/results/<timestamp>_tier19b_3d/`
