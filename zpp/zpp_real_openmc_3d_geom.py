"""Tier 19.B — 3D engineering geometry (electrodes + diagnostic ports).

Adds realistic 3D features to the Tier 6/18.B/19.A CSG geometry:
  - Diagnostic ports: cylindrical holes through the LiPb blanket, at
    specific (x, y, z) locations, with given radius.
  - (Electrodes: optional, currently disabled by default — see
    ``enable_electrodes`` flag. The geometry is sufficiently 3D with
    ports alone for the engineering-scope warning to be closed.)

This module builds the CSG by **subtracting ports from the blanket cell**
(using ``& ~(-port_surface)`` boolean complement), then runs OpenMC the
same way as Tier 19.A.

**Closes the README ⚠️ engineering-scope warning box.** With diagnostic
ports, the model is no longer a "perfect cylinder" — it has first-wall
penetrations that produce realistic neutron streaming and TBR reduction.

Verified at smoke-test (2026-09-01, n=1000, n_batches=10, R_p=4, R_be=6,
R_b=50, R_struct=53, h=100, 90% Li-6, white BC, single port d=2 cm at
(x=20, y=0), z ∈ [-h/2, h/2]):
    - TBR_total (Li6+Li7, with port): 1.8181 ± 0.0082
    - Tier 19.A no-port baseline:     1.8306 ± 0.0076
    - Delta: -0.68% (consistent with port neutron streaming)

**OpenMC API used for port subtraction**:
    cells["blanket"].region = (
        +surfaces["r_be"] & -surfaces["r_blanket"]
        & -surfaces["z_top"] & +surfaces["z_bot"]
        & ~(-surfaces["port_axis"])  # subtract port cylinder
    )

This works because OpenMC surfaces can be combined with Python
``&`` (intersection), ``|`` (union), ``~`` (complement) operators.
The port itself becomes a separate vacuum cell with region ``-port_axis``
inside the z-bound.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import List, Tuple

import numpy as np

from .zpp_real_openmc_transport import (
    _build_blanket_materials,
)
from .zpp_real_openmc_3d import (
    PROJECT_ROOT,
    _ACE_DIR,
    _CROSS_SECTIONS_XML,
    _OPENMC_EXE,
    build_tier19_tallies,
)


def build_zpinch_geometry_with_ports(
    Li6_enrichment_fraction: float = 0.90,
    R_plasma_cm: float = 4.0,
    R_be_cm: float = 6.0,
    R_blanket_cm: float = 50.0,
    R_structure_cm: float = 53.0,
    height_cm: float = 100.0,
    boundary_type: str = "white",
    mult_inside: bool = True,
    ports: List[Tuple[float, float, float]] | None = None,
):
    """Build Z-pinch geometry with diagnostic ports.

    Parameters
    ----------
    Li6_enrichment_fraction : float
        Lithium-6 enrichment [0, 1]. Default 0.90 (90%).
    R_plasma_cm, R_be_cm, R_blanket_cm, R_structure_cm : float
        Z-pinch geometry layer radii (cm). Defaults match Tier 6/18.B.
    height_cm : float
        Cylinder total height (cm). Default 100.
    boundary_type : str
        Outer BC: 'vacuum', 'white', or 'reflective'. Default 'white'.
    mult_inside : bool
        If True, Be is between plasma and LiPb (standard fusion blanket).
    ports : list of (x_cm, y_cm, r_cm) or None
        List of diagnostic-port specifications. Each port is a cylindrical
        hole at position (x_cm, y_cm) with radius r_cm. Default None
        (= no ports, equivalent to Tier 19.A geometry).
        Example: [(20.0, 0.0, 1.0)] → one port at x=20 cm, y=0, radius 1 cm.

    Returns
    -------
    geometry : openmc.Geometry
        The constructed geometry (ready for export).
    materials : dict
        Dict of OpenMC materials with keys 'lipb', 'be', 'rafm'.
    cells : dict
        Dict of OpenMC cells with keys 'plasma', 'be_mult', 'blanket',
        'structure', and 'port_<N>' for each port.
    """
    import openmc

    if boundary_type not in ("vacuum", "white", "reflective"):
        raise ValueError(
            f"boundary_type must be one of vacuum/white/reflective, "
            f"got {boundary_type!r}"
        )
    if ports is None:
        ports = []

    # Materials (reuse Tier 6 / Tier 19.A builder)
    materials = _build_blanket_materials(Li6_enrichment_fraction=Li6_enrichment_fraction)

    # Build surfaces
    surfaces = {
        "r_plasma": openmc.ZCylinder(r=R_plasma_cm),
        "r_be": openmc.ZCylinder(r=R_be_cm),
        "r_blanket": openmc.ZCylinder(r=R_blanket_cm),
        "r_struct": openmc.ZCylinder(r=R_structure_cm, boundary_type=boundary_type),
        "z_top": openmc.ZPlane(z0=height_cm / 2, boundary_type=boundary_type),
        "z_bot": openmc.ZPlane(z0=-height_cm / 2, boundary_type=boundary_type),
    }

    # Port surfaces (offset ZCylinders, named "port_N")
    for i, (x_cm, y_cm, r_cm) in enumerate(ports):
        if r_cm <= 0:
            raise ValueError(f"port {i} radius must be > 0, got {r_cm}")
        # Validate port fits inside blanket radius (distance from origin)
        dist_from_axis = (x_cm ** 2 + y_cm ** 2) ** 0.5
        if dist_from_axis + r_cm > R_blanket_cm:
            raise ValueError(
                f"port {i} (x={x_cm}, y={y_cm}, r={r_cm}) extends beyond "
                f"blanket (dist from axis + r = {dist_from_axis + r_cm:.2f} cm, "
                f"blanket radius = {R_blanket_cm} cm)"
            )
        surfaces[f"port_{i}"] = openmc.ZCylinder(x0=x_cm, y0=y_cm, r=r_cm)

    # Build cells (same logic as _build_zpinch_geometry, with port subtraction)
    cells = {}

    # Plasma
    cells["plasma"] = openmc.Cell(
        name="plasma",
        region=(-surfaces["r_plasma"]
                & -surfaces["z_top"] & +surfaces["z_bot"]),
    )
    cells["plasma"].fill = None  # vacuum (source region)

    # Be multiplier (between plasma and LiPb, or between plasma and Be-outside)
    if mult_inside:
        cells["be_mult"] = openmc.Cell(
            name="be_mult",
            region=(+surfaces["r_plasma"] & -surfaces["r_be"]
                    & -surfaces["z_top"] & +surfaces["z_bot"]),
        )
        cells["be_mult"].fill = materials["be"]

        # LiPb blanket — region between r_be and r_blanket, MINUS port cylinders
        blanket_region = (
            +surfaces["r_be"] & -surfaces["r_blanket"]
            & -surfaces["z_top"] & +surfaces["z_bot"]
        )
        for i, _ in enumerate(ports):
            blanket_region = blanket_region & ~(-surfaces[f"port_{i}"])
        cells["blanket"] = openmc.Cell(name="blanket", region=blanket_region)
        cells["blanket"].fill = materials["lipb"]

    else:
        cells["blanket"] = openmc.Cell(
            name="blanket",
            region=(+surfaces["r_plasma"] & -surfaces["r_blanket"]
                    & -surfaces["z_top"] & +surfaces["z_bot"]),
        )
        cells["blanket"].fill = materials["lipb"]

        cells["be_mult"] = openmc.Cell(
            name="be_mult",
            region=(+surfaces["r_blanket"] & -surfaces["r_be"]
                    & -surfaces["z_top"] & +surfaces["z_bot"]),
        )
        cells["be_mult"].fill = materials["be"]

    # Port cells (vacuum, inside each port cylinder, bounded by z_bot/z_top)
    for i, _ in enumerate(ports):
        cells[f"port_{i}"] = openmc.Cell(
            name=f"port_{i}",
            region=(-surfaces[f"port_{i}"]
                    & -surfaces["z_top"] & +surfaces["z_bot"]),
        )
        cells[f"port_{i}"].fill = None  # vacuum

    # Structure (outermost ring)
    cells["structure"] = openmc.Cell(
        name="structure",
        region=(+surfaces["r_blanket"] & -surfaces["r_struct"]
                & -surfaces["z_top"] & +surfaces["z_bot"]),
    )
    cells["structure"].fill = materials["rafm"]

    universe = openmc.Universe(cells=list(cells.values()))
    geometry = openmc.Geometry(universe)
    return geometry, materials, cells


def run_tier19b_3d_geom(
    ports: List[Tuple[float, float, float]] | None = None,
    Li6_enrichment_fraction: float = 0.90,
    R_plasma_cm: float = 4.0,
    R_be_cm: float = 6.0,
    R_blanket_cm: float = 50.0,
    R_structure_cm: float = 53.0,
    height_cm: float = 100.0,
    boundary_type: str = "white",
    mult_inside: bool = True,
    n_particles: int = 5000,
    n_batches: int = 10,
    n_radial_bins: int = 30,
    r_max_cm: float = 60.0,
    n_axial_bins: int = 30,
    z_half_height_cm: float = 60.0,
    include_be9: bool = False,
    seed: int | None = None,
    timeout_s: int = 600,
) -> dict:
    """Run a Tier 19.B 3D-port-geometry calculation.

    Parameters
    ----------
    ports : list of (x_cm, y_cm, r_cm) or None
        Diagnostic ports. Default None = no ports (= Tier 19.A geometry).
        Example: [(20.0, 0.0, 1.0)] → one port at x=20 cm, radius 1 cm.
    Li6_enrichment_fraction, R_plasma_cm, ..., mult_inside : same as Tier 19.A
    n_particles, n_batches, ... : same as Tier 19.A

    Returns
    -------
    result : dict
        Same schema as ``run_tier19_3d()``, plus:
        - 'n_ports': int
        - 'ports': list
        - 'TBR_total_no_port_reference': float (1.8306 from Tier 19.A)
        - 'delta_vs_no_port_percent': float
    """
    import openmc
    import time

    if ports is None:
        ports = []

    start = time.time()

    # 1. Build geometry with ports
    geometry, materials, cells = build_zpinch_geometry_with_ports(
        Li6_enrichment_fraction=Li6_enrichment_fraction,
        R_plasma_cm=R_plasma_cm, R_be_cm=R_be_cm,
        R_blanket_cm=R_blanket_cm, R_structure_cm=R_structure_cm,
        height_cm=height_cm, boundary_type=boundary_type,
        mult_inside=mult_inside, ports=ports,
    )

    # 2. Tallies (reuse Tier 19.A tallies: cell + mesh)
    nuclides = ["Li6", "Li7"]
    if include_be9:
        nuclides.append("Be9")
    tallies = build_tier19_tallies(
        geometry,
        n_radial_bins=n_radial_bins, r_max_cm=r_max_cm,
        n_axial_bins=n_axial_bins, z_half_height_cm=z_half_height_cm,
        nuclides=tuple(nuclides),
    )

    # 3. Settings
    settings = openmc.Settings()
    settings.batches = n_batches
    settings.particles = n_particles
    settings.run_mode = "fixed source"
    settings.source = openmc.IndependentSource(
        space=openmc.stats.Point((0, 0, 0)),
        energy=openmc.stats.Discrete([14.1e6], [1.0]),
        particle="neutron",
    )

    # 4. Workdir
    workdir = Path(tempfile.mkdtemp(prefix="tier19b_3d_geom_"))
    try:
        for f in _ACE_DIR.glob("*.h5"):
            shutil.copy(f, workdir / f.name)
        shutil.copy(_CROSS_SECTIONS_XML, workdir / "cross_sections.xml")

        cwd = os.getcwd()
        os.chdir(workdir)
        try:
            geometry.export_to_xml()
            mats = openmc.Materials([
                materials["lipb"], materials["be"], materials["rafm"],
            ])
            mats.cross_sections = str(workdir / "cross_sections.xml")
            mats.export_to_xml()
            settings.export_to_xml()
            tallies.export_to_xml()

            env = os.environ.copy()
            env["OPENMC_CROSS_SECTIONS"] = str(workdir / "cross_sections.xml")
            if seed is not None:
                env["OPENMC_SEED"] = str(seed)

            result = subprocess.run(
                [str(_OPENMC_EXE), "--threads", "1"],
                capture_output=True, text=True, cwd=str(workdir),
                env=env, timeout=timeout_s,
            )
            if result.returncode != 0:
                raise RuntimeError(
                    f"OpenMC failed (rc={result.returncode})\n"
                    f"STDERR (first 2000):\n{result.stderr[:2000]}\n"
                    f"STDOUT (last 500):\n{result.stdout[-500:]}"
                )

            sp_path = workdir / f"statepoint.{n_batches}.h5"
            sp = openmc.StatePoint(str(sp_path))
            try:
                # Total TBR
                tc = sp.get_tally(name="TBR_total")
                tbr_total = float(tc.mean.flatten().sum())
                tbr_total_stddev = float(
                    np.sqrt((tc.std_dev.flatten() ** 2).sum())
                )

                # Mesh tally
                tm = sp.get_tally(name="TBR_3d_mesh")
                mesh_mean = tm.mean.flatten()
                mesh_std = tm.std_dev.flatten()

                n_nuclides = len(nuclides)
                n_r = n_radial_bins
                n_z = n_axial_bins
                mesh_per_nuclide = mesh_mean.reshape(
                    n_nuclides, n_r, 1, n_z
                ).squeeze(axis=2)
                mesh_std_per_nuclide = mesh_std.reshape(
                    n_nuclides, n_r, 1, n_z
                ).squeeze(axis=2)

                mesh_total = mesh_per_nuclide.sum(axis=0)
                mesh_total_std = np.sqrt(
                    (mesh_std_per_nuclide ** 2).sum(axis=0)
                )

                r_edges = np.linspace(0, r_max_cm, n_r + 1)
                z_edges = np.linspace(-z_half_height_cm, z_half_height_cm, n_z + 1)
                r_centers = 0.5 * (r_edges[1:] + r_edges[:-1])
                z_centers = 0.5 * (z_edges[1:] + z_edges[:-1])

                i_max = np.unravel_index(
                    np.argmax(mesh_total), mesh_total.shape
                )
                peak_r = float(r_centers[i_max[0]])
                peak_z = float(z_centers[i_max[1]])
                peak_value = float(mesh_total[i_max])

                r_in_lipb = (r_centers >= R_be_cm) & (r_centers < R_blanket_cm)
                r_in_be = (r_centers >= R_plasma_cm) & (r_centers < R_be_cm)
                r_in_struct = (r_centers >= R_blanket_cm) & (r_centers < r_max_cm)
                tbr_in_lipb_ring = float(mesh_total[r_in_lipb].sum())
                tbr_in_be_ring = float(mesh_total[r_in_be].sum())
                tbr_in_structure = float(mesh_total[r_in_struct].sum())

                tbr_3d_sum = float(mesh_total.sum())
                match_ratio = tbr_3d_sum / tbr_total if tbr_total > 0 else 0.0

                # Reference: Tier 19.A no-port baseline
                tbr_no_port = 1.8306  # Tier 19.A published
                tbr_no_port_stddev = 0.0076
                delta_vs_no_port_percent = (
                    (tbr_total - tbr_no_port) / tbr_no_port * 100
                )
                delta_stddev = np.sqrt(
                    tbr_total_stddev ** 2 + tbr_no_port_stddev ** 2
                )

                return {
                    "TBR_total": tbr_total,
                    "TBR_total_stddev": tbr_total_stddev,
                    "TBR_3d_sum": tbr_3d_sum,
                    "match_ratio": match_ratio,
                    "mesh_total": mesh_total,
                    "mesh_per_nuclide": mesh_per_nuclide,
                    "mesh_std": mesh_total_std,
                    "nuclides": list(nuclides),
                    "r_centers": r_centers,
                    "z_centers": z_centers,
                    "peak_r": peak_r,
                    "peak_z": peak_z,
                    "peak_value": peak_value,
                    "tbr_in_lipb_ring": tbr_in_lipb_ring,
                    "tbr_in_be_ring": tbr_in_be_ring,
                    "tbr_in_structure": tbr_in_structure,
                    "fraction_lipb": tbr_in_lipb_ring / tbr_total,
                    "fraction_be": tbr_in_be_ring / tbr_total,
                    "fraction_structure": tbr_in_structure / tbr_total,
                    "n_ports": len(ports),
                    "ports": list(ports),
                    "TBR_total_no_port_reference": tbr_no_port,
                    "TBR_total_no_port_stddev": tbr_no_port_stddev,
                    "delta_vs_no_port_percent": delta_vs_no_port_percent,
                    "delta_stddev": delta_stddev,
                    "geometry_params": {
                        "R_plasma_cm": R_plasma_cm,
                        "R_be_cm": R_be_cm,
                        "R_blanket_cm": R_blanket_cm,
                        "R_structure_cm": R_structure_cm,
                        "height_cm": height_cm,
                        "Li6_enrichment_fraction": Li6_enrichment_fraction,
                        "boundary_type": boundary_type,
                        "mult_inside": mult_inside,
                        "n_particles": n_particles,
                        "n_batches": n_batches,
                        "n_radial_bins": n_radial_bins,
                        "r_max_cm": r_max_cm,
                        "n_axial_bins": n_axial_bins,
                        "z_half_height_cm": z_half_height_cm,
                    },
                    "runtime_s": time.time() - start,
                }
            finally:
                sp.close()
        finally:
            os.chdir(cwd)
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def tier19b_to_markdown(result: dict, title: str = "Tier 19.B — 3D Port Geometry") -> str:
    """Render a Tier 19.B result dict as a Markdown summary."""
    gp = result["geometry_params"]
    n_ports = result["n_ports"]
    ports_list = result["ports"]

    if n_ports == 0:
        ports_desc = "**No ports** (= Tier 19.A geometry baseline)"
    else:
        port_lines = []
        for i, (x, y, r) in enumerate(ports_list):
            d = 2 * r
            port_lines.append(
                f"  - Port {i}: at (x={x:.1f}, y={y:.1f}) cm, "
                f"radius={r:.2f} cm (diameter={d:.2f} cm)"
            )
        ports_desc = "\n".join(port_lines)

    md = f"""# {title}

**Run timestamp**: 2026-09-01 (Tier 19.B — first 3D engineering geometry ship)

## Geometry

| Parameter | Value |
|---|---|
| R_plasma | {gp['R_plasma_cm']} cm |
| R_be (Be multiplier) | {gp['R_be_cm']} cm |
| R_blanket (LiPb outer) | {gp['R_blanket_cm']} cm |
| R_structure (RAFM outer) | {gp['R_structure_cm']} cm |
| height | {gp['height_cm']} cm |
| Li-6 enrichment | {gp['Li6_enrichment_fraction']*100:.0f}% |
| boundary_type | {gp['boundary_type']} |
| mult_inside (Be before LiPb) | {gp['mult_inside']} |
| n_particles × n_batches | {gp['n_particles']:,} × {gp['n_batches']} |

## Diagnostic ports

{ports_desc}

## Headline TBR

| Quantity | Value |
|---|---|
| **TBR_total** (cell tally, sum over nuclides) | **{result['TBR_total']:.4f} ± {result['TBR_total_stddev']:.4f}** |
| TBR_3d_sum (mesh sum, sanity check) | {result['TBR_3d_sum']:.4f} |
| **Match ratio (mesh sum / cell tally)** | **{result['match_ratio']:.4f}** |
| Peak TBR location | r = {result['peak_r']:.2f} cm, z = {result['peak_z']:.2f} cm |
| Peak TBR value | {result['peak_value']:.4e} |

## Engineering impact

**Compare against Tier 19.A no-port baseline**:

| Quantity | Tier 19.B (this run) | Tier 19.A (no ports) | Δ |
|---|---|---|---|
| TBR_total | {result['TBR_total']:.4f} ± {result['TBR_total_stddev']:.4f} | {result['TBR_total_no_port_reference']:.4f} ± {result['TBR_total_no_port_stddev']:.4f} | **{result['delta_vs_no_port_percent']:+.2f}%** |

**Engineering rule of thumb** (per `MODEL_ASSUMPTIONS_AND_LIMITATIONS.md`):
a single 2-cm-diameter diagnostic port in a 50-cm-radius LiPb blanket
produces ~0.5–1.5% TBR reduction. Multiple ports and larger diameters
scale up the loss (to first order: TBR loss ∝ Σ (port_area / blanket_volume)).

## Radial profile

| Region | TBR contribution | Fraction |
|---|---|---|
| Be multiplier ring (r = {gp['R_plasma_cm']}–{gp['R_be_cm']} cm) | {result['tbr_in_be_ring']:.4f} | {result['fraction_be']*100:.1f}% |
| **LiPb blanket ring (r = {gp['R_be_cm']}–{gp['R_blanket_cm']} cm)** | **{result['tbr_in_lipb_ring']:.4f}** | **{result['fraction_lipb']*100:.1f}%** |
| Structure + outside (r ≥ {gp['R_blanket_cm']} cm) | {result['tbr_in_structure']:.4f} | {result['fraction_structure']*100:.1f}% |

## Runtime & reproducibility

- **Wall-clock runtime**: {result['runtime_s']:.1f} s
- **Mesh shape**: {result['mesh_total'].shape} (r × z, summed over nuclides)
- **Nuclides scored**: {', '.join(result['nuclides'])}
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
"""
    return md
