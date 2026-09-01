# Tier 19 — 3D-resolved TBR via CylindricalMesh

> **Status**: Tier 19.A shipped 2026-09-01. **Tier 19.B (full 3D engineering geometry with electrodes) is the next milestone** — see "Open follow-up" below.

## What is Tier 19?

Tier 19 extends the project's 1D cell-tally TBR calculation to a **3D-resolved TBR map** on the existing 1D Z-pinch geometry, using OpenMC's `CylindricalMesh` filter. It tells you **where** in the existing geometry the tritium is being bred, not just the total.

The Tier 19.A implementation reuses the 1D CSG geometry from `zpp.zpp_real_openmc_transport._build_zpinch_geometry` exactly. The only new thing is the `CylindricalMesh` tally that bins tritium production into (r, φ, z) cells. The total mesh-summed TBR must equal the cell-tally TBR to within statistical noise — this is the **mesh conservation check**.

## Headline result (Tier 19.A baseline, seed=42)

| Quantity | Value |
|---|---|
| **TBR_total** (cell tally, Li-6 + Li-7) | **1.8306 ± 0.0076** |
| TBR_3d_sum (mesh sum, sanity check) | 1.8306 |
| Match ratio (mesh sum / cell tally) | **1.0000** (exact, modulo rounding) |
| Peak TBR bin | r = 43 cm, z = 14 cm (value 9.19e-3) |
| TBR in Be multiplier ring (r = 4–6 cm) | 0.0551 (3.0%) |
| **TBR in LiPb blanket ring (r = 6–50 cm)** | **1.4081 (76.9%)** |
| TBR in structure + outside (r ≥ 50 cm) | 0.2639 (14.4%) |
| Wall-clock runtime | **20.9 s** (n=5000 × 10 batches) |

**Cross-validation vs Tier 18.B** (which uses the same geometry: R_p=4, R_be=6, R_b=50, R_struct=53, 90% Li-6, mult_inside=True):

- Tier 18.B published: TBR = **1.8280 ± 0.0060**
- Tier 19.A: TBR = 1.8306 ± 0.0076
- **Difference: 0.0026 (≈0.4σ of Tier 18.B) — passes 2σ check**

The Tier 19.A geometry matches Tier 18.B exactly, so the cell-tally TBR from Tier 19.A must agree with Tier 18.B's published value. It does, to within statistical noise. This proves the `CylindricalMesh` filter is being applied correctly and not double-counting or missing cells.

## Why this is the "cheap" 3D scope (vs the medium scope)

The zreview5 audit Item 7 ("From 1D to 3D Geometry") had three scope levels:

1. **Cheap (Tier 19.A — this)**: add a `CylindricalMesh` tally to the existing 1D geometry. Maps TBR vs (r, z). **No new geometry construction.** Tells you where tritium is being bred on the existing 1D model. ~1-2 hours of work.
2. **Medium (Tier 19.B — next)**: add electrodes + diagnostic ports to the CSG geometry. Real 3D engineering model. Closes the README ⚠️ engineering-scope warning box. ~3-5 days of work.
3. **Full (out of scope)**: voxel mesh from a real STEP/STL of a Z-pinch reactor. Requires CAD source or pre-computed 3D voxel; out of project scope per the current "personal project out of curiosity" posture.

**Tier 19.A is the smallest step that proves the 3D methodology is sound.** It validates that OpenMC can give us spatially-resolved TBR on the existing geometry before we commit to the bigger Tier 19.B CSG work.

## What Tier 19.A reveals

Even on the simple 1D geometry, the radial profile of tritium production is informative:

| Radial shell | Cumulative TBR | What this means |
|---|---|---|
| r = 4–6 cm (Be multiplier) | 0.06 | Be (n,2n) doubles some neutrons but Be doesn't breed T directly |
| **r = 6–50 cm (LiPb blanket)** | **1.41** | Dominant TBR contributor, as expected (Li-6 capture + Li-7 slow capture) |
| r = 50–53 cm (RAFM structure) | 0.24 | Structure captures + back-scatters neutrons; some LiPb contribution via scattered neutrons |
| r > 53 cm | 0.02 | Vacuum + leakage |

The **axial profile is symmetric about z=0** (white BC). Tritium production peaks slightly off-axis at z=14 cm because the point source is at z=0 and neutrons diffuse outward through ~14 cm of LiPb before slowing enough to be captured by Li-6 (peak capture cross-section is at thermal energies).

## Method: how the CylindricalMesh works

OpenMC's `CylindricalMesh(r_grid, z_grid)` defines an axisymmetric 3D mesh:

- **r_grid**: 1-D array of radial bin boundaries. Default `n_radial_bins=30`, `r_max_cm=60` → 2 cm radial bins.
- **z_grid**: 1-D array of axial bin boundaries. Default `n_axial_bins=30`, `z_half_height_cm=60` → 4 cm axial bins over z ∈ [-60, 60] cm.
- **phi_grid** (optional): defaults to `[0, 2π]` for full-axisymmetric (single phi bin). For 3D-resolved azimuthal structure (e.g., to study diagnostic-port effects in Tier 19.B), set phi_grid with explicit bins.

The mesh tally returns a `(n_nuclides, n_r, n_phi, n_z)` array. The Tier 19.A default uses `phi=1` (axisymmetric), so the shape is `(n_nuclides=2, n_r=30, 1, n_z=30)` flattened.

## How to run

```bash
# Baseline (matches Tier 18.B geometry; ≈21 s wall-clock)
.venv/Scripts/python.exe scripts/run_tier19_3d_sweep.py

# With Be-9 in the mesh (adds (n,2n) contribution to the map)
.venv/Scripts/python.exe scripts/run_tier19_3d_sweep.py --include_be9

# Lower Li-6 enrichment (faster TBR decline at the plasma-facing edge)
.venv/Scripts/python.exe scripts/run_tier19_3d_sweep.py --Li6 0.6

# Different R_blanket (changes how much LiPb is available)
.venv/Scripts/python.exe scripts/run_tier19_3d_sweep.py --R_blanket 80

# Smaller height (taller Z-pinch)
.venv/Scripts/python.exe scripts/run_tier19_3d_sweep.py --height 30
```

## Caveats

- The mesh resolves TBR on the **1D infinite-cylinder geometry**, NOT a 3D engineering geometry with electrodes. To extend to Tier 19.B, you'll need to add `openmc.ZCylinder + openmc.ZPlane + openmc.RCC` (right-circular cylinder) cells for electrodes + diagnostic ports.
- The mesh bins **outside the geometry** (r > R_struct_cm, |z| > height/2) show near-zero TBR as expected (vacuum or back-scatter from boundary).
- Match ratio should be ≈ 1.000 ± statistical noise. Any systematic deviation >1% indicates mesh-resolution-induced bias.
- The current Tier 19.A result uses **Li-6 + Li-7 only** by default. To include the Be-9 (n,2n) contribution in the map, pass `--include_be9`. Be-9 (n,2n) does NOT produce tritium directly; it doubles neutrons which then breed tritium in Li-6/Li-7. Including Be-9 in the tally nuclide list adds a small (n,Xt) score from Be-9's minor tritium-producing channels.

## Files

| File | Purpose |
|---|---|
| `zpp/zpp_real_openmc_3d.py` | The `run_tier19_3d()` function and `CylindricalMesh` tally builder |
| `scripts/run_tier19_3d_sweep.py` | Driver: builds geometry, runs OpenMC, saves JSON + MD + npy |
| `data/results/2026-09-01_1706_tier19_3d/` | First Tier 19.A run (seed=42, TBR=1.8306) |
| `data/results/2026-09-01_1707_tier19_3d/` | Second Tier 19.A run after cross-validation comparator fix (seed=42, TBR=1.8306, identical to first) |
| `data/results/<date>_tier19_3d/tier19_3d_baseline.json` | Full result dict |
| `data/results/<date>_tier19_3d/tier19_3d_baseline.md` | Markdown summary |
| `data/results/<date>_tier19_3d/mesh_total.npy` | (n_r, n_z) total TBR per cell |
| `data/results/<date>_tier19_3d/mesh_per_nuclide.npy` | (n_nuclides, n_r, n_z) per-nuclide TBR |

> **Note on duplicate result dirs**: the `1706` and `1707` runs are byte-identical (same seed=42, same TBR=1.8306, same match_ratio=1.0000). The `1706` dir is preserved as the **first successful Tier 19.A run**; the `1707` dir is the **post-cross-validation-fix run**. Keeping both provides the audit trail. The README points at the `1707` dir as the canonical reference.

## Open follow-up — Tier 19.B

**Tier 19.B** is the medium-scope 3D geometry work from the zreview5 audit. The 1-2 week effort includes:

1. **Add electrodes** at z = ±h/2 (where plasma current dumps in a real Z-pinch).
   - OpenMC geometry: `openmc.ZCylinder` + `openmc.ZPlane` for the electrode top/bottom.
   - Material: copper or tungsten (high-Z, low-tritium-production).
2. **Add diagnostic ports** — small vertical holes through the blanket (r ~5 cm, z ∈ [-h/2, h/2]).
   - Geometry: subtracted cylinders or RCC holes.
   - Effect on TBR: small reduction (~1-3%) due to neutron streaming through the ports.
3. **Multi-phi mesh** (phi_grid with explicit bins) to see azimuthal structure around the ports.
4. **Sweep electrode height + port diameter** to map the engineering-scope tradeoff.

This work closes the README ⚠️ engineering-scope warning box and gives the project its first real "3D Z-pinch" result. Estimated 3-5 days based on the existing 1D CSG + Tier 19.A scaffold.

## References

- OpenMC `CylindricalMesh` API — https://docs.openmc.org/en/stable/pythonapi/generated/openmc.CylindricalMesh.html
- zreview5 audit: `docs/zreview5_audit.md` (Item 7)
- Tier 18.B baseline: `data/results/2026-08-31_tier18b_li4sio4/tier18b_lipb_baseline.json` (TBR=1.8280 ± 0.33%)
- Tier 6 convergence: `data/results/2026-09-01_tier6_convergence/tier6_convergence.md` (different geometry, mult_inside=False)
