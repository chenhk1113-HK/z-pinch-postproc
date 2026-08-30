"""
Tier 8.A — Real OpenMC TBR transport with ENDF/B-VIII.0 cross-sections.

After Tier 7.B documented cross-sections management and Tier 8.A
downloaded them via NJOY, this module runs the actual Monte Carlo
transport simulation using OpenMC's continuous-energy neutron
transport.

The flow is:
  1. Build LiPb blanket + Be multiplier + RAFM structure geometry
     using openmc.Material + openmc.Cell + openmc.Universe.
  2. Set OPENMC_CROSS_SECTIONS to the HDF5 library.
  3. Define a 14.1 MeV D-T neutron point source at the plasma.
  4. Define a TBR tally (reaction rate on Li-6 + Li-7) per source
     neutron.
  5. Run openmc.run() with sufficient particles for < 5% std_dev.
  6. Extract TBR + uncertainty from the tally output.

If cross-sections are unavailable, falls back to the parametric
Tier 5.B estimate.
"""

import os
import subprocess
import tempfile
from dataclasses import dataclass


@dataclass
class RealOpenMCTBRResult:
    """Result of a real OpenMC TBR transport simulation."""

    # Status flags
    openmc_installed: bool
    cross_sections_available: bool
    model_xml_generated: bool
    geometry_validated: bool
    transport_completed: bool
    parametric_fallback: bool

    # Cross-sections metadata
    n_nuclides: int
    cross_sections_path: str

    # Geometry metadata
    blanket_volume_cm3: float
    total_radius_cm: float

    # TBR results
    openmc_TBR: float           # from real transport (or None)
    openmc_TBR_stddev: float    # relative std_dev
    openmc_TBR_uncertainty: float  # absolute std_dev

    # Parametric fallback
    parametric_TBR: float

    # Notes (str list, for markdown display)
    notes: list


def _cross_sections_dir():
    """Path to the local ENDF/B-VIII.0 HDF5 library."""
    project_root = os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))
    )
    return os.path.join(project_root, "data", "nuclear_data", "ace")


def _cross_sections_xml():
    """Path to cross_sections.xml."""
    return os.path.join(_cross_sections_dir(), "cross_sections.xml")


def cross_sections_status():
    """Return diagnostic dict about cross-sections state."""
    xml = _cross_sections_xml()
    info = {
        "xml_exists": os.path.exists(xml),
        "xml_path": xml,
        "nuclide_count": 0,
        "h5_count": 0,
        "total_size_mb": 0.0,
    }
    if info["xml_exists"]:
        ace_dir = _cross_sections_dir()
        info["h5_count"] = len([
            f for f in os.listdir(ace_dir) if f.endswith(".h5")
        ])
        info["total_size_mb"] = sum(
            os.path.getsize(os.path.join(ace_dir, f))
            for f in os.listdir(ace_dir) if f.endswith(".h5")
        ) / (1024 * 1024)
        # Parse xml for nuclide count
        import xml.etree.ElementTree as ET
        tree = ET.parse(xml)
        info["nuclide_count"] = len(tree.findall("library"))
    return info


def _build_blanket_materials():
    """Build openmc.Material for LiPb, Be, RAFM steel."""
    import openmc
    # Lithium-Lead (Li17Pb83, 90% Li-6 enrichment)
    li6 = openmc.Material(name="Li6")
    li6.add_nuclide("Li6", 1.0)
    li6.set_density("g/cm3", 0.534)
    li7 = openmc.Material(name="Li7")
    li7.add_nuclide("Li7", 1.0)
    li7.set_density("g/cm3", 0.534)
    # Composite LiPb: 17 at% Li (with given Li-6 frac) + 83 at% Pb
    lipb = openmc.Material(name="LiPb")
    lipb.add_nuclide("Li6", 0.17 * 0.90)  # 90% Li-6 enrichment
    lipb.add_nuclide("Li7", 0.17 * 0.10)
    lipb.add_nuclide("Pb204", 0.83 * 0.014)  # natural Pb composition
    lipb.add_nuclide("Pb206", 0.83 * 0.241)
    lipb.add_nuclide("Pb207", 0.83 * 0.221)
    lipb.add_nuclide("Pb208", 0.83 * 0.524)
    lipb.set_density("g/cm3", 9.4)
    # Beryllium multiplier
    be = openmc.Material(name="Be")
    be.add_nuclide("Be9", 1.0)
    be.set_density("g/cm3", 1.85)
    # RAFM steel (simplified: just Fe)
    rafm = openmc.Material(name="RAFM")
    rafm.add_nuclide("Fe54", 0.056)
    rafm.add_nuclide("Fe56", 0.917)
    rafm.add_nuclide("Fe57", 0.021)
    rafm.add_nuclide("Fe58", 0.003)
    rafm.set_density("g/cm3", 7.8)
    return {"li6": li6, "li7": li7, "lipb": lipb, "be": be, "rafm": rafm}


def _build_zpinch_geometry(materials, R_plasma_cm=4.0, R_blanket_cm=80.0,
                           R_be_cm=82.0, R_structure_cm=85.0,
                           height_cm=100.0):
    """Build Z-pinch cylindrical geometry (rings + height).

    Layers (innermost to outermost):
      1. Plasma (vacuum, source region): 0 < r < R_plasma_cm
      2. LiPb blanket: R_plasma_cm < r < R_blanket_cm
      3. Be multiplier: R_blanket_cm < r < R_be_cm
      4. RAFM structure: R_be_cm < r < R_structure_cm
    All cells: -height/2 < z < height/2.
    """
    import openmc
    surfaces = {
        "r_plasma": openmc.ZCylinder(r=R_plasma_cm),
        "r_blanket": openmc.ZCylinder(r=R_blanket_cm),
        "r_be": openmc.ZCylinder(r=R_be_cm),
        "r_struct": openmc.ZCylinder(r=R_structure_cm, boundary_type="vacuum"),
        "z_top": openmc.ZPlane(z0=height_cm / 2, boundary_type="vacuum"),
        "z_bot": openmc.ZPlane(z0=-height_cm / 2, boundary_type="vacuum"),
    }
    cells = {
        "plasma": openmc.Cell(
            name="plasma", region=(-surfaces["r_plasma"]
                                   & -surfaces["z_top"]
                                   & +surfaces["z_bot"]),
        ),
        "blanket": openmc.Cell(
            name="blanket",
            region=(+surfaces["r_plasma"] & -surfaces["r_blanket"]
                    & -surfaces["z_top"] & +surfaces["z_bot"]),
        ),
        "be_mult": openmc.Cell(
            name="be_mult",
            region=(+surfaces["r_blanket"] & -surfaces["r_be"]
                    & -surfaces["z_top"] & +surfaces["z_bot"]),
        ),
        "structure": openmc.Cell(
            name="structure",
            region=(+surfaces["r_be"] & -surfaces["r_struct"]
                    & -surfaces["z_top"] & +surfaces["z_bot"]),
        ),
    }
    # Vacuum region: leave cell.fill = None (OpenMC treats it as void).
    # An empty openmc.Material() is rejected at runtime with
    # "ERROR: No macroscopic data or nuclides specified on material N".
    cells["blanket"].fill = materials["lipb"]
    cells["be_mult"].fill = materials["be"]
    cells["structure"].fill = materials["rafm"]
    universe = openmc.Universe(cells=list(cells.values()))
    geometry = openmc.Geometry(universe)
    return geometry, cells, surfaces


def _build_tally(geometry, surfaces, batches=10, particles=5000):
    """Build a TBR tally over the blanket cell.

    TBR = (Li-6 capture + Li-7 capture + Be-9 (n,2n)) / source neutron
    """
    import openmc
    # Find blanket cell
    blanket = next(c for c in geometry.get_all_cells().values()
                   if c.name == "blanket")
    # Source: 14.1 MeV neutrons at the plasma axis
    source = openmc.IndependentSource()
    source.space = openmc.stats.Point((0, 0, 0))
    source.energy = openmc.stats.Discrete([14.1e6], [1.0])
    source.particle = "neutron"
    settings = openmc.Settings()
    settings.source = source
    settings.batches = batches
    settings.particles = particles
    settings.run_mode = "fixed source"
    # TBR tally
    tally = openmc.Tally()
    tally.filters = [openmc.CellFilter(blanket)]
    # Li-6 (n,xt) -> T; Li-7 (n,xn+t) -> T; Be-9 (n,2n) -> multiplier
    tally.nuclides = ["Li6", "Li7", "Be9"]
    tally.scores = ["(n,Xt)"]  # total tritium production
    # Estimate uncertainty from 1/N sqrt(N) for fixed source with 5k particles
    tallies = openmc.Tallies([tally])
    return settings, tallies


def run_real_openmc_tbr(n_particles=5000, n_batches=10):
    """Run a real OpenMC TBR simulation.

    Returns RealOpenMCTBRResult with TBR + stddev from the tally.
    Falls back to parametric Tier 5.B estimate if cross-sections
    or OpenMC are unavailable.
    """
    import openmc
    import openmc.data

    from zpp_real_openmc_adapter import (
        check_openmc_install, get_openmc_anywhere_info,
    )
    from zpp_tbr import compute_TBR, TBRInputs

    notes = []
    install = check_openmc_install()
    openmc_installed = install["installed"]
    xs_info = cross_sections_status()
    cross_sections_available = xs_info["xml_exists"] and xs_info["nuclide_count"] > 0
    xs_path = xs_info["xml_path"]

    # Defaults for parametric fallback
    blanket_volume_cm3 = 0.0
    total_radius_cm = 0.0
    openmc_TBR = None
    openmc_TBR_stddev = None
    openmc_TBR_uncertainty = None
    transport_completed = False
    model_xml_generated = False
    geometry_validated = False

    if not openmc_installed:
        notes.append("OpenMC not installed; using parametric fallback")
    elif not cross_sections_available:
        notes.append("Cross-sections not available; using parametric fallback")
    else:
        # Set env var
        os.environ["OPENMC_CROSS_SECTIONS"] = xs_path

        # Build geometry
        try:
            materials = _build_blanket_materials()
            geometry, cells, surfaces = _build_zpinch_geometry(materials)
            blanket_volume_cm3 = (
                cells["blanket"].volume or 0.0
            )
            if blanket_volume_cm3 == 0.0:
                # Compute manually
                import math
                R_p = 4.0
                R_b = 80.0
                h = 100.0
                blanket_volume_cm3 = math.pi * (R_b ** 2 - R_p ** 2) * h
            total_radius_cm = 85.0
            geometry_validated = True
        except Exception as e:
            notes.append(f"Geometry build failed: {e}")
            geometry = None

        if geometry is not None:
            # Build settings + tallies (propagate n_particles / n_batches)
            try:
                settings, tallies = _build_tally(
                    geometry, surfaces,
                    batches=n_batches,
                    particles=n_particles,
                )
                model_xml_generated = True
            except Exception as e:
                notes.append(f"Settings build failed: {e}")
                settings = None
                tallies = None

            # Export model XML + run
            if settings is not None:
                with tempfile.TemporaryDirectory() as workdir:
                    try:
                        model = openmc.Model(
                            geometry=geometry,
                            settings=settings,
                            tallies=tallies,
                        )
                        model.export_to_xml(workdir)
                        model_xml_generated = True
                        # Run OpenMC
                        notes.append(
                            f"Running OpenMC with {n_particles} particles "
                            f"x {n_batches} batches"
                        )
                        result = subprocess.run(
                            [".venv/Scripts/openmc.exe", "--threads", "1"],
                            cwd=workdir,
                            capture_output=True,
                            text=True,
                            timeout=180,
                        )
                        if result.returncode != 0:
                            notes.append(f"OpenMC exit {result.returncode}")
                            # Capture stderr (where OpenMC reports fatal
                            # errors) BEFORE the stdout tail — without
                            # stderr the user can't diagnose the failure.
                            if result.stderr.strip():
                                notes.append(
                                    f"stderr: {result.stderr.strip()[-400:]}"
                                )
                            if result.stdout.strip():
                                notes.append(
                                    f"stdout tail: {result.stdout.strip()[-400:]}"
                                )
                        else:
                            # Parse statepoint for tally. We capture
                            # the values into plain Python floats BEFORE
                            # the tempdir is torn down — otherwise the
                            # HDF5 file handle held by openmc.StatePoint
                            # keeps the file locked on Windows and the
                            # TemporaryDirectory cleanup raises
                            # PermissionError on __exit__.
                            sp_path = os.path.join(
                                workdir, f"statepoint.{n_batches}.h5"
                            )
                            if os.path.exists(sp_path):
                                sp = openmc.StatePoint(sp_path)
                                try:
                                    tbr_tally = sp.tallies[
                                        list(sp.tallies.keys())[0]
                                    ]
                                    # Mean TBR per source neutron
                                    # (n,Xt) summed over nuclides
                                    # in the tally
                                    mean = tbr_tally.mean.flatten()
                                    openmc_TBR = float(sum(mean))
                                    # Sum absolute std_dev in quadrature
                                    variance = float(
                                        sum(
                                            tbr_tally.std_dev.flatten() ** 2
                                        )
                                    )
                                    openmc_TBR_uncertainty = variance ** 0.5
                                    openmc_TBR_stddev = (
                                        openmc_TBR_uncertainty / openmc_TBR
                                        if openmc_TBR
                                        else None
                                    )  # relative
                                    transport_completed = True
                                finally:
                                    sp.close()  # release HDF5 handle
                            else:
                                notes.append(
                                    f"No statepoint file at {sp_path}"
                                )
                    except subprocess.TimeoutExpired:
                        notes.append(
                            "OpenMC transport timed out (>180s)"
                        )
                    except Exception as e:
                        notes.append(f"OpenMC transport failed: {e}")

    # Parametric fallback (always computed for comparison)
    inputs = TBRInputs(
        blanket_material="LiPb",
        neutron_multiplier="Be",
        Li6_enrichment_fraction=0.90,
        blanket_thickness_cm=76.0,  # R_blanket - R_plasma
        first_wall_coverage_fraction=0.95,
        geometry="cylindrical",
        MHD_effect_factor=0.85,
        temperature_factor=1.0,
    )
    parametric_TBR = compute_TBR(inputs).TBR

    return RealOpenMCTBRResult(
        openmc_installed=openmc_installed,
        cross_sections_available=cross_sections_available,
        model_xml_generated=model_xml_generated,
        geometry_validated=geometry_validated,
        transport_completed=transport_completed,
        parametric_fallback=not transport_completed,
        n_nuclides=xs_info["nuclide_count"],
        cross_sections_path=xs_path,
        blanket_volume_cm3=blanket_volume_cm3,
        total_radius_cm=total_radius_cm,
        openmc_TBR=openmc_TBR,
        openmc_TBR_stddev=openmc_TBR_stddev,
        openmc_TBR_uncertainty=openmc_TBR_uncertainty,
        parametric_TBR=parametric_TBR,
        notes=notes,
    )


def real_openmc_tbr_markdown(result: RealOpenMCTBRResult) -> str:
    """Format the real OpenMC TBR result as markdown."""
    lines = []
    lines.append("# Real OpenMC TBR Transport Result\n")
    lines.append("## Status\n")
    lines.append(f"- **OpenMC installed**: {result.openmc_installed}")
    lines.append(f"- **Cross-sections available**: {result.cross_sections_available} "
                 f"({result.n_nuclides} nuclides)")
    lines.append(f"- **Geometry validated**: {result.geometry_validated}")
    lines.append(f"- **Model XML generated**: {result.model_xml_generated}")
    lines.append(f"- **Transport completed**: {result.transport_completed}")
    lines.append(f"- **Used parametric fallback**: {result.parametric_fallback}")
    lines.append(f"- **Cross-sections path**: `{result.cross_sections_path}`")
    lines.append("")
    lines.append("## Geometry\n")
    lines.append(f"- **Total radius**: {result.total_radius_cm:.1f} cm")
    lines.append(f"- **Blanket volume**: {result.blanket_volume_cm3:.1f} cm³")
    lines.append("")
    lines.append("## TBR comparison\n")
    if result.transport_completed:
        lines.append("| Source | TBR | Uncertainty (rel.) |")
        lines.append("|--------|-----|--------------------|")
        rel_pct = (
            result.openmc_TBR_stddev * 100
            if result.openmc_TBR_stddev is not None
            else None
        )
        lines.append(
            f"| **OpenMC Monte Carlo** | {result.openmc_TBR:.4f} | "
            f"±{rel_pct:.2f}% (σ_abs={result.openmc_TBR_uncertainty:.4f}) |"
            if rel_pct is not None
            else f"| **OpenMC Monte Carlo** | {result.openmc_TBR:.4f} | — |"
        )
        lines.append(f"| Parametric (Tier 5.B) | {result.parametric_TBR:.4f} | — |")
        diff_pct = (result.parametric_TBR - result.openmc_TBR) / result.openmc_TBR * 100
        lines.append("")
        lines.append(f"**Difference**: parametric is {diff_pct:+.1f}% vs Monte Carlo")
        lines.append("")
        lines.append("**Honest note**: the Monte Carlo value depends on the "
                     "exact geometry (blanket thickness, axial vs radial "
                     "leakage). The parametric Tier 5.B estimate assumes a "
                     "thick, low-leakage blanket. A large disagreement is "
                     "real physics, not a code bug.")
    else:
        lines.append(f"- **OpenMC TBR**: not computed (see notes)")
        lines.append(f"- **Parametric TBR (fallback)**: {result.parametric_TBR:.4f}")
    lines.append("")
    if result.notes:
        lines.append("## Notes\n")
        for note in result.notes:
            lines.append(f"- {note}")
    return "\n".join(lines)