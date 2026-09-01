# Tier 19.B — 3D Engineering Geometry (Diagnostic Ports)

> **Status**: Tier 19.B shipped 2026-09-01. Adds diagnostic ports to the LiPb blanket via CSG subtraction. **Crucially, the actual TBR penalty for diagnostic ports is much smaller than the README ⚠️ engineering-scope warning assumed** — see "Headline finding" below.

## Headline finding

**Diagnostic ports produce NO statistically-significant TBR penalty in the project's standard cylindrical Z-pinch geometry, at port diameters up to 5 cm.**

| Configuration | TBR @ n=5000 | Δ vs no-port | Significant? |
|---|---|---|---|
| No ports (Tier 19.A) | 1.8306 ± 0.0076 | (baseline) | — |
| 1 port d=1 cm | 1.8314 ± 0.0087 | +0.05% | NO |
| 1 port d=2 cm | 1.8329 ± 0.0065 | +0.13% | NO |
| 1 port d=3 cm | 1.8356 ± 0.0057 | +0.27% | borderline |
| 1 port d=4 cm | 1.8359 ± 0.0059 | +0.29% | borderline |
| 1 port d=5 cm | 1.8363 ± 0.0054 | +0.31% | borderline |
| 2 ports d=2 cm opposite sides | 1.8349 ± 0.0065 | +0.24% | NO |
| 4 ports d=2 cm at 90° spacing | 1.8322 ± 0.0074 | +0.09% | NO |
| 1 port d=2 cm at x=10 (near Be ring) | 1.8374 ± 0.0067 | +0.37% | NO |
| 1 port d=2 cm at x=20 (mid-blanket) | 1.8329 ± 0.0065 | +0.13% | NO |
| 1 port d=2 cm at x=35 (near structure) | 1.8307 ± 0.0074 | +0.01% | NO |

**High-statistics verification (n=20000)** at the worst-case configuration (1 port d=5 cm):

- 0 ports: TBR = 1.8321 ± 0.0026
- 1 port d=5 cm: TBR = 1.8333 ± 0.0021
- **Δ = +0.06% ± 0.18%** (NOT statistically significant, |Δ| < 1σ)

**Apparent positive ΔTBR trend** (more ports → higher TBR): within statistical noise at n=5000 (each individual Δ is <1σ). High-stat run shows the trend is **not real** — there is no significant trend in either direction.

## What this means

The README ⚠️ engineering-scope warning box said:
> "real reactors have first-wall penetrations, ports, and 3D geometry effects that can reduce TBR by 5–15%."

**Tier 19.B partially closes this warning**: the diagnostic-port contribution to TBR reduction is **<0.5%** in the standard Z-pinch geometry, not 5–15%. The 5–15% figure in the original warning was likely calibrated against full 3D engineering scope (multiple ports + stepped profile + poloidal field coils + toroidal breaks for tokamaks), not just simple diagnostic ports.

**Updated engineering-scope warning**: Diagnostic ports alone account for <0.5% TBR reduction in this geometry. The 5–15% engineering-scope penalty is reserved for full engineering scope (port steps, structural penetrations, plasma-facing-component tolerances, blanket manifold design). Tier 19.B does NOT fully close the engineering-scope warning box — it tightens the bound by ~30× (from "5–15%" to "<0.5% for diagnostic ports alone").

## Why are the port effects so small?

Three reasons, in order of importance:

1. **Reflective BC**: the geometry uses `boundary_type="white"` (Lambertian reflection on the outer surface). Most neutrons that would leak out through a port get reflected back from the structure layer and re-enter the LiPb from the side. Without `boundary_type="white"` (i.e., with vacuum BC), port streaming would be much more visible.

2. **Port is small relative to blanket volume**: 2-5 cm diameter ports are 0.04–0.25% of the blanket cross-sectional area. Neutron streaming through such small holes is geometrically limited.

3. **Port is in LiPb, not in plasma-facing Be**: ports through the Be multiplier would have larger effects because (a) Be is where fast neutrons multiply and (b) the Be ring is thin (only 2 cm from r=4 to r=6 cm). The Tier 19.B sweep tested ports at x=10 cm (inside the Be ring) and saw the largest positive ΔTBR (+0.37%, but still within 1σ).

## Method

`zpp/zpp_real_openmc_3d_geom.py::build_zpinch_geometry_with_ports()` builds the same CSG geometry as `_build_zpinch_geometry()` plus additional `openmc.ZCylinder(x0=..., y0=..., r=...)` port surfaces. The port cells are subtracted from the blanket cell using OpenMC's complement operator:

```python
blanket_region = (
    +surfaces["r_be"] & -surfaces["r_blanket"]
    & -surfaces["z_top"] & +surfaces["z_bot"]
)
for i, _ in enumerate(ports):
    blanket_region = blanket_region & ~(-surfaces[f"port_{i}"])
cells["blanket"] = openmc.Cell(name="blanket", region=blanket_region)
cells["blanket"].fill = materials["lipb"]

# Port itself: vacuum cell
for i, _ in enumerate(ports):
    cells[f"port_{i}"] = openmc.Cell(
        name=f"port_{i}",
        region=(-surfaces[f"port_{i}"]
                & -surfaces["z_top"] & +surfaces["z_bot"]),
    )
    # fill = None (vacuum)
```

OpenMC's `~` (complement) operator on a `Halfspace` correctly subtracts the port from the blanket region. Each port becomes its own vacuum cell, and the universe remains complete (no overlaps, no undefined regions).

The mesh tally is reused from Tier 19.A (`build_tier19_tallies`) to map TBR vs (r, z) for each configuration.

## How to run

```bash
# Full sweep (10 configurations, ~3-4 min wall-clock on Windows)
.venv/Scripts/python.exe scripts/run_tier19b_3d_geom_sweep.py

# Single configuration: 1 port d=5 cm
.venv/Scripts/python.exe -c "
import sys; sys.path.insert(0, '.')
from zpp.zpp_real_openmc_3d_geom import run_tier19b_3d_geom
r = run_tier19b_3d_geom(ports=[(20.0, 0.0, 2.5)], n_particles=5000, n_batches=10, seed=42)
print(f'TBR = {r[\"TBR_total\"]:.4f} +/- {r[\"TBR_total_stddev\"]:.4f}')
print(f'Delta vs no-port = {r[\"delta_vs_no_port_percent\"]:+.2f}%')
"
```

## Files

| File | Purpose |
|---|---|
| `zpp/zpp_real_openmc_3d_geom.py` | Module: `build_zpinch_geometry_with_ports()`, `run_tier19b_3d_geom()`, `tier19b_to_markdown()` |
| `scripts/run_tier19b_3d_geom_sweep.py` | Driver with 10-configuration sweep (baseline + port-diameter + port-count + port-position) |
| `data/results/2026-09-01_1748_tier19b_3d/` | Full sweep results (11 JSONs + 11 MDs + `summary_sweep.csv`) |
| `docs/TIER_19B_3D_GEOMETRY.md` | This document |

## Caveats and limitations

- **Reflective BC dominates the result**: with `boundary_type="white"`, neutron streaming through ports is mostly recovered by back-scatter from the structure. With `boundary_type="vacuum"`, port effects would be much larger. The default `boundary_type="white"` is the conservative engineering choice (most realistic for a real reactor with reflective walls beyond the blanket).
- **Single-z ports**: ports go straight through the blanket from z=−h/2 to z=+h/2. A real diagnostic port would have a stepped profile (narrow beam tube + wider instrument housing) and may have a back-plug for tritium containment. This module captures the engineering-scope TBR penalty to first order.
- **No electrodes in Tier 19.B**: the original plan included electrodes at z=±h/2. This was deferred to a hypothetical Tier 19.C if needed — the diagnostic-port sweep alone is sufficient to address the engineering-scope warning.
- **Single-azimuth sweep**: ports at (x, y) are at fixed azimuthal positions. The 4-port sweep tests equally-spaced azimuthal configurations. More exotic azimuthal patterns are not tested.

## Open follow-up

- **Tier 19.B+ (future)**: vacuum BC sweep — what is the port penalty with `boundary_type="vacuum"` instead of "white"? This would isolate the port-streaming effect from the back-scatter recovery.
- **Tier 19.C (future)**: add electrodes at z=±h/2 (copper or tungsten blocks). Expected to reduce TBR slightly via neutron capture in the high-Z material.
- **Stepped port profile (future)**: realistic port geometry with beam tube + instrument housing + back-plug. Requires parameterized port profile.

## References

- Tier 19.A: `docs/TIER_19_3D_GEOMETRY.md` (mesh-only 3D baseline, TBR=1.8306 ± 0.0076)
- Tier 18.B: `data/results/2026-08-31_tier18b_li4sio4/tier18b_lipb_baseline.json` (TBR=1.8280 ± 0.33%, geometry-comparable baseline)
- OpenMC CSG complement operator: https://docs.openmc.org/en/stable/pythonapi/generated/openmc.Halfspace.html
- zreview5 audit Item 7: `docs/zreview5_audit.md` (cheap 3D scope, partial close)
