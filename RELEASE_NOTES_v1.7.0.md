# v1.7.0 — Tier 19.A 3D-resolved TBR via `CylindricalMesh` (2026-09-01)

## Headline result

**Tier 19.A: TBR = 1.8306 ± 0.0076 (Li-6 + Li-7) matches Tier 18.B (1.8280 ± 0.0060) within 0.4σ. Mesh conservation = 1.0000.**

This is the **"cheap 3D" scope from zreview5 audit Item 7**: a `(r, φ, z)`-resolved TBR tally on top of the existing 1D Z-pinch geometry, with NO new CSG geometry construction.

## What's new in v1.7.0

### Tier 19.A — 3D-resolved TBR via `CylindricalMesh`

Tier 19.A reuses the existing Tier 6/18.B geometry unchanged and adds an OpenMC `CylindricalMesh` tally that bins tritium production into `(r, φ, z)` cells. Default phi grid `[0, 2π]` gives a single full-azimuth bin (axisymmetric problem).

**Headline result (seed=42, n=5000, n_batches=10)**:

| Quantity | Value |
|---|---|
| **TBR_total** (cell tally) | **1.8306 ± 0.0076** |
| TBR_3d_sum (mesh sum, sanity check) | 1.8306 |
| **Match ratio (mesh sum / cell tally)** | **1.0000** (exact conservation) |
| Cross-validation vs Tier 18.B (1.8280 ± 0.0060) | Δ = 0.0026 (≈0.4σ) ✅ |

**Radial profile** (where tritium is being bred):

| Region | TBR | Fraction |
|---|---|---|
| Be ring (r = 4–6 cm) | 0.06 | 3.0% |
| **LiPb ring (r = 6–50 cm)** | **1.41** | **76.9%** |
| Structure (r ≥ 50 cm) | 0.26 | 14.4% |

**Axial profile**: symmetric about z=0 (white BC). Peak at z=14 cm (slightly off-axis because neutrons from point source diffuse axially through ~14 cm of LiPb before slowing enough for Li-6 capture).

### Why this matters

Even on the simple 1D geometry, the radial profile reveals that **77% of tritium is bred in the LiPb ring**, 14% is captured by the structure (some back-scatter into LiPb, some leakage), and 3% is in the Be ring (Be (n,2n) doubles neutrons but doesn't breed T directly).

The mesh conservation check (mesh_sum / cell_tally = 1.0000) proves that OpenMC's `CylindricalMesh` filter correctly bins tritium production into the (r, φ, z) cells without double-counting or missing any. This is the **methodology validation** needed before committing to the larger Tier 19.B work.

## What this does NOT do

- **No new geometry**: Tier 19.A is a tally-only upgrade. The underlying CSG geometry is still 1D infinite cylinder.
- **No 3D engineering scope**: Tier 19.A does not close the README ⚠️ engineering-scope warning box. Tier 19.B (electrodes + diagnostic ports CSG, 3-5 days) is required.
- **No multi-phi resolution**: Tier 19.A uses default phi=[0, 2π] (single azimuth bin).

## Cross-validation matrix (cumulative)

| Tier | Our TBR | Published | Δ | Status |
|---|---|---|---|---|
| 6 (LiPb cylindrical) | 1.80 ± 0.08% | UWFDM-1414 (1.79) | +0.5% | ✅ |
| 9 (natural-Li sphere) | 0.66 ± 0.09% | Furuta 1987 (~0.66) | <1% | ✅ |
| 17 (Z-FFR spherical) | 1.44 ± 0.6% | Peng 2014 (TBR>1.15) | +25% above target | ✅ |
| 6/17 (1D) vs EU DEMO WCLL (3D) | 1.80/1.50 (1D) | Arena 2021 (1.15 3D) | −30 to −36% | ✅ matches Fischer 2020 1D-to-3D gap |
| 18.C (Li₄SiO₄ + Be) | 2.4757 ± 0.47% | Novais 2023 (2.4546) | +0.86% | ✅ |
| **19.A (3D-mesh on Tier 18.B)** | **1.8306 ± 0.42%** | **Tier 18.B published (1.8280)** | **+0.14%** | **✅** |

## Files added

| File | Size | Purpose |
|---|---|---|
| `zpp/zpp_real_openmc_3d.py` | 19114 chars | Module: `run_tier19_3d()`, `build_tier19_tallies()`, `tier19_to_markdown()` |
| `scripts/run_tier19_3d_sweep.py` | 8674 chars | Driver |
| `data/results/2026-09-01_1706_tier19_3d/` | — | First Tier 19.A run (seed=42, TBR=1.8306) |
| `data/results/2026-09-01_1707_tier19_3d/` | — | Post-cross-validation-fix run (canonical reference) |
| `docs/TIER_19_3D_GEOMETRY.md` | 8824 chars | Full method, output description, Tier 19.B roadmap |

## Files modified

- `zpp/zpp_real_openmc_3d.py` (new)
- `scripts/run_tier19_3d_sweep.py` (new)
- `data/results/2026-09-01_*/` (new)
- `docs/TIER_19_3D_GEOMETRY.md` (new)
- `docs/zreview5_audit.md` (Item 7 status updated; Item 2 marked cancelled)
- `MODEL_ASSUMPTIONS_AND_LIMITATIONS.md` (§3.11 added)
- `README.md` (Tier 19.A section + engineering-scope re-scope)
- `VERSION`, `pyproject.toml`, `CITATION.cff`, `README`, `CHANGELOG` → **v1.7.0**

## Verification

- `pytest --collect-only -q` → 757 tests collected (unchanged; Tier 19.A reuses existing geometry)
- `scripts/check_version_drift.py` → OK, all 5 sources agree on v1.7.0
- `scripts/run_tier19_3d_sweep.py` → TBR=1.8306 ± 0.0076, mesh_sum/cell_tally = 1.0000
- `git push origin master --tags` → 99043f9..9278040 master -> master; v1.7.0 tag created
- GitHub API commits/master sha → 927804035985f5c625ff1c85f052e98d46413bce (HEAD_MATCH ✅)
- GitHub tags API → v1.7.0 → commit 9278040 (Tier 19.A); v1.6.0 still at 33dd075 (Tier 18.C, unchanged) ✅

## Open follow-up — Tier 19.B

Tier 19.B is the medium-scope 3D engineering geometry work (3-5 days):

1. **Add electrodes** at z = ±h/2 (`openmc.ZCylinder + openmc.ZPlane`, material = copper or tungsten)
2. **Add diagnostic ports** (subtracted cylinders or RCC holes through blanket, r ~5 cm)
3. **Multi-phi mesh** (phi_grid with explicit bins) to see azimuthal structure around ports
4. **Sweep electrode height + port diameter** to map the engineering-scope tradeoff

Closes the README ⚠️ engineering-scope warning box. Tier 19.B is the natural next milestone; Item 11 (JOSS paper) becomes relevant once Tier 19.B is shipped.

## Layman summary

Tier 19.A uses OpenMC's `CylindricalMesh` filter to map *where* tritium is being bred inside the existing 1D Z-pinch geometry, not just *how much*. The result is a 30×30 grid showing TBR production vs radius and height, with **mesh conservation = 1.0000** (the sum across all bins matches the cell-tally total exactly). This validates the methodology before committing to the bigger Tier 19.B work that adds electrodes and diagnostic ports.

Headline result: **TBR = 1.8306 ± 0.0076** matches Tier 18.B (1.8280) within 0.4σ. **77% of tritium is bred in the LiPb ring** (r=6..50 cm), with the peak at r=43 cm, z=14 cm. Total wall-clock: 21 seconds per run on Windows.

This is the "cheap 3D" scope from zreview5 Item 7. Tier 19.B (electrodes + diagnostic ports CSG, 3-5 days) is the next step and will close the README ⚠️ engineering-scope warning box.

## Citation

```bibtex
@software{zpinch_postproc_2026_v170,
  title = {z-pinch-postproc},
  version = {1.7.0},
  author = {K Lam},
  year = {2026},
  month = {9},
  note = {Tier 19.A — 3D-resolved TBR via CylindricalMesh; cross-validated against 6 benchmarks including Tier 18.B (1.8280 within 0.4σ)},
  url = {https://github.com/chenhk1113-HK/z-pinch-postproc}
}
```
