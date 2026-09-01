"""Tier 19.C — Electrode CSG in Z-pinch 3D geometry.

Adds cylindrical **electrode blocks** at z = ±h/2 (where plasma current
dumps in a real Z-pinch) to the Tier 19.A/B geometry. The electrodes
are modelled as solid Cu cylinders with radius = R_blanket (so they
fill the entire end-cap region) and height = h_elec_cm.

Why this matters
----------------
A real Z-pinch has electrodes where the plasma current dumps. These
electrodes are typically made of high-Z, high-conductivity metals
(Cu, W, stainless). They capture neutrons and reduce TBR. Quantifying
this effect completes the engineering-scope picture:
- Tier 19.B quantified diagnostic ports (<0.5% TBR penalty)
- Tier 19.C quantifies electrode TBR penalty

The result closes the README ⚠️ engineering-scope warning box for
realistic Z-pinch geometries.

Public API
----------
- ``build_zpinch_geometry_with_electrodes`` — geometry builder
- ``run_tier19c_3d_electrodes`` — run a single configuration
- ``tier19c_to_markdown`` — render a result as Markdown
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import List, Tuple

import numpy as np

from .zpp_real_openmc_3d_geom import (
    build_zpinch_geometry_with_ports,
)
from .zpp_real_openmc_3d import (
    PROJECT_ROOT,
    _ACE_DIR,
    _CROSS_SECTIONS_XML,
    _OPENMC_EXE,
    build_tier19_tallies,
)


def _make_cu_material(openmc, density_g_cc: float = 8.96):
    """Build a natural Cu material (Cu-63 + Cu-65 natural abundance).

    Density: 8.96 g/cm³ (pure copper at room temperature).
    Composition: Cu-63 69.17%, Cu-65 30.83% (natural abundance).
    """
    cu = openmc.Material(name="Cu_electrode")
    cu.set_density("g/cm3", density_g_cc)
    cu.add_nuclide("Cu63", 0.6917)
    cu.add_nuclide("Cu65", 0.3083)
    return cu


def build_zpinch_geometry_with_electrodes(
    Li6_enrichment_fraction: float = 0.90,
    R_plasma_cm: float = 4.0,
    R_be_cm: float = 6.0,
    R_blanket_cm: float = 50.0,
    R_structure_cm: float = 53.0,
    height_cm: float = 100.0,
    boundary_type: str = "white",
    mult_inside: bool = True,
    ports: List[Tuple[float, float, float]] | None = None,
    h_elec_cm: float = 5.0,
    electrode_material: str = "Cu",
    R_electrode_cm: float | None = None,
):
    """Build Z-pinch geometry with electrodes at z=±h/2.

    The electrodes are cylindrical blocks that fill the end-cap regions.
    They occupy z ∈ [-h/2, -h/2 + h_elec_cm] (bottom) and
    z ∈ [h/2 - h_elec_cm, h/2] (top), with radius R_electrode_cm
    (default = R_blanket_cm to fill the entire cross-section).
    """
    import openmc

    if boundary_type not in ("vacuum", "white", "reflective"):
        raise ValueError(
            f"boundary_type must be one of vacuum/white/reflective, "
            f"got {boundary_type!r}"
        )
    if electrode_material != "Cu":
        raise NotImplementedError(
            f"Only Cu electrodes supported in Tier 19.C (got {electrode_material!r})"
        )
    if h_elec_cm <= 0:
        raise ValueError(f"h_elec_cm must be > 0, got {h_elec_cm}")
    if h_elec_cm >= height_cm / 2:
        raise ValueError(
            f"h_elec_cm={h_elec_cm} too large (must be < height_cm/2={height_cm/2})"
        )

    if R_electrode_cm is None:
        R_electrode_cm = R_blanket_cm
    if R_electrode_cm > R_blanket_cm:
        raise ValueError(
            f"R_electrode_cm={R_electrode_cm} > R_blanket_cm={R_blanket_cm}"
        )

    if ports is None:
        ports = []

    # Build the base geometry (Tier 19.B: ports + blanket + structure)
    geometry, materials, cells = build_zpinch_geometry_with_ports(
        Li6_enrichment_fraction=Li6_enrichment_fraction,
        R_plasma_cm=R_plasma_cm,
        R_be_cm=R_be_cm,
        R_blanket_cm=R_blanket_cm,
        R_structure_cm=R_structure_cm,
        height_cm=height_cm,
        boundary_type=boundary_type,
        mult_inside=mult_inside,
        ports=ports,
    )

    # Add Cu material
    cu_mat = _make_cu_material(openmc)
    materials["cu_electrode"] = cu_mat

    # Add inner z-planes that bound the electrodes
    z_mid = height_cm / 2
    surfaces = {
        "z_bot_outer": openmc.ZPlane(z0=-z_mid, boundary_type=boundary_type),
        "z_bot_inner": openmc.ZPlane(z0=-z_mid + h_elec_cm),
        "z_top_inner": openmc.ZPlane(z0=z_mid - h_elec_cm),
        "z_top_outer": openmc.ZPlane(z0=z_mid, boundary_type=boundary_type),
        "r_electrode": openmc.ZCylinder(r=R_electrode_cm),
    }

    # Electrode regions
    top_elec_region = (
        -surfaces["r_electrode"]
        & +surfaces["z_top_inner"] & -surfaces["z_top_outer"]
    )
    bot_elec_region = (
        -surfaces["r_electrode"]
        & +surfaces["z_bot_outer"] & -surfaces["z_bot_inner"]
    )

    # CARVE electrode regions out of blanket cell (and be_mult if it's there)
    if "blanket" in cells:
        cells["blanket"].region = (
            cells["blanket"].region & ~top_elec_region & ~bot_elec_region
        )
    if "be_mult" in cells:
        cells["be_mult"].region = (
            cells["be_mult"].region & ~top_elec_region & ~bot_elec_region
        )

    # Create electrode cells
    cells["electrode_top"] = openmc.Cell(name="electrode_top", region=top_elec_region)
    cells["electrode_top"].fill = cu_mat

    cells["electrode_bot"] = openmc.Cell(name="electrode_bot", region=bot_elec_region)
    cells["electrode_bot"].fill = cu_mat

    # Rebuild universe with new cells
    universe = openmc.Universe(cells=list(cells.values()))
    geometry = openmc.Geometry(universe)

    return geometry, materials, cells


def run_tier19c_3d_electrodes(
    h_elec_cm: float = 5.0,
    electrode_material: str = "Cu",
    R_electrode_cm: float | None = None,
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
    seed: int | None = 42,
    timeout_s: int = 600,
) -> dict:
    """Run a Tier 19.C electrode-geometry calculation."""
    import time

    if ports is None:
        ports = []

    start = time.time()

    # 1. Build geometry with electrodes
    geometry, materials, cells = build_zpinch_geometry_with_electrodes(
        Li6_enrichment_fraction=Li6_enrichment_fraction,
        R_plasma_cm=R_plasma_cm, R_be_cm=R_be_cm,
        R_blanket_cm=R_blanket_cm, R_structure_cm=R_structure_cm,
        height_cm=height_cm, boundary_type=boundary_type,
        mult_inside=mult_inside, ports=ports,
        h_elec_cm=h_elec_cm,
        electrode_material=electrode_material,
        R_electrode_cm=R_electrode_cm,
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

    # 3. Settings (mirror Tier 19.B pattern)
    import openmc
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
    workdir = Path(tempfile.mkdtemp(prefix="tier19c_3d_elec_"))
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
                materials["cu_electrode"],
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

                # Reference: Tier 19.A no-electrode baseline
                tbr_no_elec = 1.8306  # Tier 19.A published
                tbr_no_elec_stddev = 0.0076
                delta_vs_no_elec_percent = (
                    (tbr_total - tbr_no_elec) / tbr_no_elec * 100
                )

                runtime = time.time() - start

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
                    "fraction_lipb": tbr_in_lipb_ring / tbr_total if tbr_total > 0 else 0.0,
                    "fraction_be": tbr_in_be_ring / tbr_total if tbr_total > 0 else 0.0,
                    "fraction_structure": tbr_in_structure / tbr_total if tbr_total > 0 else 0.0,
                    "h_elec_cm": h_elec_cm,
                    "electrode_material": electrode_material,
                    "R_electrode_cm": R_electrode_cm if R_electrode_cm is not None else R_blanket_cm,
                    "ports": list(ports),
                    "n_ports": len(ports),
                    "boundary_type": boundary_type,
                    "Li6_enrichment_fraction": Li6_enrichment_fraction,
                    "R_plasma_cm": R_plasma_cm, "R_be_cm": R_be_cm,
                    "R_blanket_cm": R_blanket_cm, "R_structure_cm": R_structure_cm,
                    "height_cm": height_cm,
                    "TBR_total_no_electrode_reference": tbr_no_elec,
                    "TBR_total_no_electrode_reference_stddev": tbr_no_elec_stddev,
                    "delta_vs_no_electrode_percent": delta_vs_no_elec_percent,
                    "n_particles": n_particles,
                    "n_batches": n_batches,
                    "seed": seed,
                    "runtime_s": runtime,
                    "tier": "19.C",
                }
            finally:
                sp.close()
        finally:
            os.chdir(cwd)
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def tier19c_to_markdown(result: dict) -> str:
    """Render a Tier 19.C result as Markdown."""
    lines = []
    lines.append(f"# Tier 19.C Result: h_elec={result['h_elec_cm']} cm")
    lines.append("")
    lines.append("## Geometry")
    lines.append(f"- **Electrode material**: {result['electrode_material']}")
    lines.append(f"- **Electrode height (h_elec)**: {result['h_elec_cm']} cm (each end)")
    lines.append(f"- **Electrode radius**: {result['R_electrode_cm']} cm")
    lines.append(f"- **Boundary type**: {result['boundary_type']}")
    lines.append(f"- **Li-6 enrichment**: {result['Li6_enrichment_fraction']*100:.0f}%")
    if result['n_ports'] > 0:
        lines.append(f"- **Diagnostic ports**: {result['n_ports']} port(s)")
    lines.append(f"- **Plasma radius / Be / Blanket / Structure**: "
                 f"{result['R_plasma_cm']} / {result['R_be_cm']} / "
                 f"{result['R_blanket_cm']} / {result['R_structure_cm']} cm")
    lines.append(f"- **Height**: {result['height_cm']} cm")
    lines.append(f"- **n_particles × n_batches**: {result['n_particles']:,} × "
                 f"{result['n_batches']}")
    lines.append(f"- **seed**: {result['seed']}")
    lines.append("")
    lines.append("## TBR Result")
    lines.append(f"- **TBR_total = {result['TBR_total']:.4f} ± "
                 f"{result['TBR_total_stddev']:.4f}**")
    lines.append(f"- **Δ vs no-electrode (Tier 19.A baseline = "
                 f"{result['TBR_total_no_electrode_reference']:.4f})**: "
                 f"{result['delta_vs_no_electrode_percent']:+.2f}%")
    lines.append(f"- **Mesh-vs-cell match ratio**: {result['match_ratio']:.4f}")
    lines.append(f"- **Runtime**: {result['runtime_s']:.1f} s")
    lines.append("")
    lines.append("## TBR Spatial Distribution")
    lines.append(f"- **TBR in LiPb ring (r=[{result['R_be_cm']}, {result['R_blanket_cm']}) cm)**: "
                 f"{result['tbr_in_lipb_ring']:.4f} ({result['fraction_lipb']*100:.1f}%)")
    lines.append(f"- **TBR in Be ring (r=[{result['R_plasma_cm']}, {result['R_be_cm']}) cm)**: "
                 f"{result['tbr_in_be_ring']:.4f} ({result['fraction_be']*100:.1f}%)")
    lines.append(f"- **TBR in structure (r>=R_blanket)**: "
                 f"{result['tbr_in_structure']:.4f} ({result['fraction_structure']*100:.1f}%)")
    lines.append(f"- **Peak TBR location**: r={result['peak_r']:.1f} cm, "
                 f"z={result['peak_z']:.1f} cm (value={result['peak_value']:.4f})")
    return "\n".join(lines) + "\n"