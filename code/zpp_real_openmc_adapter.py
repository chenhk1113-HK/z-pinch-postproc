"""
Real OpenMC adapter for the Z-pinch post-processor.

This module uses openmc-anywhere which provides OpenMC 0.16.0
as an in-place PyPI wheel. No conda required.

HONEST CAVEAT (per AGENTS.md rule 12 - never fabricate results):
openmc-anywhere bundles OpenMC binaries but NOT the cross-section
library. Running a real Monte Carlo TBR simulation requires:
1. Download ENDF cross-sections via openmc.data.download_ace()
   (or copy from conda-forge OpenMC install).
2. Set OPENMC_CROSS_SECTIONS env var to the cross_sections.xml.

If cross-sections are unavailable, this adapter gracefully
falls back to the parametric TBR calculation.
"""

import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass

import numpy as np

from zpp_tbr import TBRInputs, TBRResult, compute_TBR


OPENMC_CROSS_SECTIONS_ENV = "OPENMC_CROSS_SECTIONS"


def check_openmc_install() -> dict:
    """Check openmc-anywhere installation and report state.

    Returns dict with keys:
        installed: True if openmc module imports.
        version: openmc.__version__ or None.
        binary_path: path to openmc.exe CLI or None.
        cross_sections: OPENMC_CROSS_SECTIONS env var or None.
        cross_sections_ready: True if both binary + cross-sections.
    """
    info = {
        "installed": False,
        "version": None,
        "binary_path": None,
        "cross_sections": None,
        "cross_sections_ready": False,
    }
    try:
        import openmc
        info["installed"] = True
        info["version"] = openmc.__version__
    except ImportError:
        return info

    # Find binary
    binary = shutil.which("openmc")
    if binary is None:
        # Project .venv/Scripts/openmc.exe
        candidate = os.path.join(".venv", "Scripts", "openmc.exe")
        if os.path.exists(candidate):
            binary = candidate
    info["binary_path"] = binary

    # Check cross-sections env
    cs = os.environ.get(OPENMC_CROSS_SECTIONS_ENV)
    info["cross_sections"] = cs
    info["cross_sections_ready"] = (
        info["installed"] and binary is not None and cs is not None
        and os.path.exists(cs)
    )
    return info


def get_openmc_anywhere_info() -> dict:
    """Return openmc-anywhere package metadata."""
    try:
        from importlib.metadata import distribution
        dist = distribution("openmc-anywhere")
        return {
            "name": dist.name,
            "version": dist.version,
            "location": dist.locate_file("").as_posix(),
        }
    except Exception:
        return {"name": "openmc-anywhere", "version": None, "location": None}


@dataclass
class OpenMCNeutronicsResult:
    """Result from a real OpenMC neutronics calculation.

    Includes the OpenMC output if available, plus the parametric
    fallback if OpenMC couldn't run.
    """
    openmc_installed: bool
    openmc_version: str
    cross_sections_available: bool
    model_xml_generated: bool
    tally_xml_generated: bool
    run_completed: bool
    parametric_TBR: float  # Always present (fallback).
    openmc_TBR: float | None  # None if not run.
    openmc_TBR_std: float | None
    notes: str


def _build_lipb_material(Li6_enrichment_fraction: float) -> "openmc.Material":
    """Build LiPb breeder material with Li-6 enrichment."""
    import openmc
    Li6_frac = Li6_enrichment_fraction
    Li7_frac = 1.0 - Li6_enrichment_fraction

    mat = openmc.Material(name="LiPb")
    mat.add_element("Li", 1.0, enrichment=Li6_frac, enrichment_target="Li6")
    mat.add_element("Pb", 1.0)
    mat.set_density("g/cm3", 9.4)  # LiPb eutectic density
    return mat


def _build_be_multiplier() -> "openmc.Material":
    """Build Be neutron multiplier."""
    import openmc
    mat = openmc.Material(name="Be_multiplier")
    mat.add_element("Be", 1.0)
    mat.set_density("g/cm3", 1.85)
    return mat


def _build_structure_material(structure: str) -> "openmc.Material":
    """Build structure material (RAFM, SS316, etc.)."""
    import openmc
    mat = openmc.Material(name=f"structure_{structure}")
    # Simplified RAFM composition (Eurofer97 approx).
    if structure.lower() in ("rafm", "eurofer"):
        mat.add_element("Fe", 0.89)
        mat.add_element("Cr", 0.09)
        mat.add_element("W", 0.01)
        mat.add_element("V", 0.005)
        mat.add_element("Ta", 0.005)
    else:
        # Default to Fe for unknown structures
        mat.add_element("Fe", 1.0)
    mat.set_density("g/cm3", 7.8)
    return mat


def build_openmc_tbr_model(
    inp: TBRInputs,
    work_dir: str,
) -> tuple:
    """Build an OpenMC model for TBR calculation.

    Returns (model, geometry_xml_path, materials_xml_path).

    Does NOT run the simulation - that requires cross-sections.
    The XML files are written to work_dir for inspection.
    """
    import openmc

    os.makedirs(work_dir, exist_ok=True)

    # Outer cylinder (vacuum boundary)
    outer_r = inp.blanket_thickness_cm + 10.0  # 10 cm FW + structure
    outer_surface = openmc.ZCylinder(r=outer_r)
    outer_cell_region = -outer_surface
    outer_cell = openmc.Cell(name="outer")

    # Blanket region (with multiplier if any)
    blanket_outer = openmc.ZCylinder(r=inp.blanket_thickness_cm)
    blanket_region = -blanket_outer
    if inp.neutron_multiplier == "Be":
        blanket_mat = _build_be_multiplier()
        blanket_cell = openmc.Cell(name="multiplier", fill=blanket_mat, region=blanket_region)
    else:
        blanket_mat = _build_lipb_material(inp.Li6_enrichment_fraction)
        blanket_cell = openmc.Cell(name="breeder", fill=blanket_mat, region=blanket_region)

    # Source: 14.1 MeV neutron at z=0 (plasma center)
    source = openmc.IndependentSource(
        space=openmc.stats.Point(),
        energy=openmc.stats.Discrete([14.1e6], [1.0]),
    )

    # Geometry with two cells: inner breeder, outer vacuum
    blanket_cell_outer_region = +blanket_outer & -outer_surface
    outer = openmc.Cell(name="outer", region=blanket_cell_outer_region)

    geometry = openmc.Geometry([blanket_cell, outer])

    # Materials
    materials = openmc.Materials([blanket_mat])

    # Settings
    settings = openmc.Settings()
    settings.run_mode = "fixed source"
    settings.batches = 10
    settings.particles = 1000
    settings.source = source

    # Tally: tritium production
    tally = openmc.Tally(name="tbr")
    tally.filters = [openmc.CellFilter(blanket_cell)]
    tally.scores = ["H3-production"]

    tallies = openmc.Tallies([tally])

    # Build model
    model = openmc.Model(geometry, materials, settings, tallies)

    # Export XML
    model.export_to_xml(directory=work_dir)

    geom_xml = os.path.join(work_dir, "geometry.xml")
    mat_xml = os.path.join(work_dir, "materials.xml")
    return model, geom_xml, mat_xml


def real_openmc_tbr_calculation(inp: TBRInputs) -> OpenMCNeutronicsResult:
    """Run a real OpenMC TBR calculation if cross-sections available.

    Falls back to parametric TBR (compute_TBR) if:
    - openmc-anywhere not installed
    - cross-sections not available
    - simulation fails

    Returns OpenMCNeutronicsResult with both values (when available).
    """
    info = check_openmc_install()
    param_result = compute_TBR(inp)
    param_TBR = param_result.TBR

    notes = []
    notes.append(f"openmc-anywhere: {'installed' if info['installed'] else 'NOT installed'}")
    if info["version"]:
        notes.append(f"openmc version: {info['version']}")
    notes.append(f"cross-sections: {'available' if info['cross_sections_ready'] else 'NOT available'}")

    if not info["installed"]:
        notes.append("Falling back to parametric TBR (openmc module not importable)")
        return OpenMCNeutronicsResult(
            openmc_installed=False,
            openmc_version="N/A",
            cross_sections_available=False,
            model_xml_generated=False,
            tally_xml_generated=False,
            run_completed=False,
            parametric_TBR=param_TBR,
            openmc_TBR=None,
            openmc_TBR_std=None,
            notes="; ".join(notes),
        )

    # Try to build the model (works without cross-sections)
    model_xml_gen = False
    tally_xml_gen = False
    try:
        with tempfile.TemporaryDirectory() as work_dir:
            model, geom_xml, mat_xml = build_openmc_tbr_model(inp, work_dir)
            model_xml_gen = os.path.exists(geom_xml)
            tally_xml_gen = os.path.exists(os.path.join(work_dir, "tallies.xml"))
    except Exception as e:
        notes.append(f"Model build failed: {e}")

    run_completed = False
    openmc_TBR_val = None
    openmc_TBR_std = None

    if info["cross_sections_ready"] and info["binary_path"]:
        # Try a real run
        try:
            with tempfile.TemporaryDirectory() as work_dir:
                model, _, _ = build_openmc_tbr_model(inp, work_dir)
                # Reduce batches/particles for fast smoke test
                model.settings.batches = 5
                model.settings.particles = 100
                # Run
                result_path = model.run(cwd=work_dir, output=False)
                with openmc.StatePoint(result_path) as sp:
                    t = sp.get_tally(name="tbr")
                    openmc_TBR_val = float(t.mean.item())
                    openmc_TBR_std = float(t.std_dev.item())
                run_completed = True
                notes.append(f"OpenMC TBR = {openmc_TBR_val:.4f} +/- {openmc_TBR_std:.4f}")
        except Exception as e:
            notes.append(f"OpenMC run failed: {e}")
    else:
        notes.append("Cross-sections missing; skipping OpenMC run, using parametric TBR")

    return OpenMCNeutronicsResult(
        openmc_installed=info["installed"],
        openmc_version=info["version"] or "unknown",
        cross_sections_available=info["cross_sections_ready"],
        model_xml_generated=model_xml_gen,
        tally_xml_generated=tally_xml_gen,
        run_completed=run_completed,
        parametric_TBR=param_TBR,
        openmc_TBR=openmc_TBR_val,
        openmc_TBR_std=openmc_TBR_std,
        notes="; ".join(notes),
    )


def real_openmc_markdown(result: OpenMCNeutronicsResult) -> str:
    """Format an OpenMCNeutronicsResult as Markdown."""
    lines = ["# Real OpenMC neutronics result", ""]
    lines.append(f"- **openmc-anywhere installed**: {result.openmc_installed}")
    lines.append(f"- **openmc version**: {result.openmc_version}")
    lines.append(f"- **cross-sections available**: {result.cross_sections_available}")
    lines.append(f"- **model XML generated**: {result.model_xml_generated}")
    lines.append(f"- **tally XML generated**: {result.tally_xml_generated}")
    lines.append(f"- **simulation completed**: {result.run_completed}")
    lines.append("")
    lines.append("## TBR results")
    lines.append("")
    lines.append(f"- **Parametric TBR** (always computed): {result.parametric_TBR:.4f}")
    if result.openmc_TBR is not None:
        lines.append(
            f"- **OpenMC TBR**: {result.openmc_TBR:.4f} +/- {result.openmc_TBR_std:.4f}"
        )
    else:
        lines.append("- **OpenMC TBR**: not run (cross-sections unavailable or run failed)")
    lines.append("")
    lines.append("## Notes")
    lines.append("")
    lines.append(result.notes)
    return "\n".join(lines)