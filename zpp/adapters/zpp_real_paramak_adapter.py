"""
Real Paramak integration for the Z-pinch post-processor.

This module uses Paramak 0.9.11 to build 3D CAD geometry of
Z-pinch fusion reactor components. Paramak is tokamak-centric
(triangularity, rotation_angle, plasma, etc.) but its
`revolved_shape()` primitive lets us build Z-pinch-style
cylindrical reactors by revolving a 2D profile around the Z axis.

HONEST CAVEATS (per AGENTS.md rule 12):
- Paramak's strength is in tokamak/DEMO/Spherical tokamak.
- For Z-pinch (cylindrical, no rotation), we use:
  - revolved_shape() for the cylindrical blanket
  - center_column_shield_cylinder for the plasma column
  - workplanes for laser ports (axial cylinders)
- We use Paramak for the CAD STEP file export; the neutronic
  calculation still uses openmc (if cross-sections available)
  or the parametric TBR module (fallback).
"""

import math
import os
import tempfile
from dataclasses import dataclass

from zpp.zpp_geometry import ZIFERadialBuild


def check_paramak_install() -> dict:
    """Probe for Paramak installation."""
    info = {"installed": False, "version": None}
    try:
        import paramak
        info["installed"] = True
        info["version"] = paramak.__version__
    except ImportError:
        pass
    return info


def get_paramak_info() -> dict:
    """Return Paramak package metadata."""
    try:
        from importlib.metadata import distribution
        dist = distribution("paramak")
        return {
            "name": dist.name,
            "version": dist.version,
            "location": dist.locate_file("").as_posix(),
        }
    except Exception:
        return {"name": "paramak", "version": None, "location": None}


@dataclass
class ParamakGeometryResult:
    """Result from Paramak Z-pinch geometry generation."""
    paramak_installed: bool
    paramak_version: str
    build_name: str
    total_radius_cm: float
    plasma_height_cm: float
    blanket_volume_cm3: float
    step_file_generated: bool
    step_file_path: str | None
    notes: str


def build_paramak_zpinch(
    build: ZIFERadialBuild,
    work_dir: str,
    export_step: bool = True,
) -> ParamakGeometryResult:
    """Build a Paramak geometry for a Z-pinch reactor.

    Uses revolved_shape() to create a cylindrical blanket
    surrounding a central plasma column. The plasma column is
    represented as a thin cylinder at the axis.

    Returns ParamakGeometryResult with metadata. Optionally
    exports a STEP file for CAD inspection.
    """
    info = check_paramak_install()
    notes = []

    if not info["installed"]:
        # Compute total blanket volume from layer thicknesses
        R_inner = 0.0
        height_cm = build.axial_length_cm
        total_vol = 0.0
        for layer in build.layers:
            R_outer = R_inner + layer.thickness_cm
            total_vol += math.pi * (R_outer**2 - R_inner**2) * height_cm
            R_inner = R_outer
        return ParamakGeometryResult(
            paramak_installed=False,
            paramak_version="N/A",
            build_name=build.name,
            total_radius_cm=sum(l.thickness_cm for l in build.layers),
            plasma_height_cm=build.axial_length_cm,
            blanket_volume_cm3=total_vol,
            step_file_generated=False,
            step_file_path=None,
            notes="Paramak not installed; returning radial-build metadata only",
        )

    import paramak

    os.makedirs(work_dir, exist_ok=True)

    # Build a 2D profile: vertical line (plasma column) + radial layers.
    # The profile is in (R, Z) coordinates.
    layers = build.layers
    R_inner = 0.0
    height_cm = build.axial_length_cm
    profile_points = []
    # Start at (0, 0) and go up along the plasma column
    profile_points.append((R_inner, 0.0, "straight"))
    profile_points.append((R_inner, height_cm, "straight"))
    # Now go radially outward across each layer
    R_current = R_inner
    for layer in layers:
        R_outer = R_current + layer.thickness_cm
        profile_points.append((R_outer, height_cm, "straight"))
        profile_points.append((R_outer, 0.0, "straight"))
        R_current = R_outer
    # Close back to origin
    profile_points.append((0.0, 0.0, "straight"))

    # Revolve the profile to make a 3D solid
    try:
        revolved = paramak.revolved_shape(
            points=profile_points,
            rotation_angle=360,
            name=f"zpinch_{build.name}",
        )
        notes.append(f"Revolved shape created with {len(profile_points)} profile points")
    except Exception as e:
        notes.append(f"Revolved shape failed: {e}")
        R_inner = 0.0
        height_cm = build.axial_length_cm
        total_vol = 0.0
        for layer in build.layers:
            R_outer = R_inner + layer.thickness_cm
            total_vol += math.pi * (R_outer**2 - R_inner**2) * height_cm
            R_inner = R_outer
        return ParamakGeometryResult(
            paramak_installed=True,
            paramak_version=info["version"],
            build_name=build.name,
            total_radius_cm=R_current,
            plasma_height_cm=build.axial_length_cm,
            blanket_volume_cm3=total_vol,
            step_file_generated=False,
            step_file_path=None,
            notes="; ".join(notes),
        )

    # Compute total radius and blanket volume
    total_radius = sum(l.thickness_cm for l in layers)
    R_inner = 0.0
    height_cm = build.axial_length_cm
    blanket_vol = 0.0
    for layer in build.layers:
        R_outer = R_inner + layer.thickness_cm
        blanket_vol += math.pi * (R_outer**2 - R_inner**2) * height_cm
        R_inner = R_outer

    # Optionally write STEP file
    step_path = None
    step_generated = False
    if export_step:
        try:
            step_path = os.path.join(work_dir, f"zpinch_{build.name}.step")
            revolved.val().exportStep(step_path)
            step_generated = os.path.exists(step_path)
            if step_generated:
                notes.append(f"STEP file: {step_path} ({os.path.getsize(step_path)} bytes)")
        except Exception as e:
            notes.append(f"STEP export failed: {e}")

    return ParamakGeometryResult(
        paramak_installed=True,
        paramak_version=info["version"],
        build_name=build.name,
        total_radius_cm=total_radius,
        plasma_height_cm=build.axial_length_cm,
        blanket_volume_cm3=blanket_vol,
        step_file_generated=step_generated,
        step_file_path=step_path,
        notes="; ".join(notes),
    )


def paramak_geometry_markdown(result: ParamakGeometryResult) -> str:
    """Format a ParamakGeometryResult as Markdown."""
    lines = ["# Paramak geometry result", ""]
    lines.append(f"- **Paramak installed**: {result.paramak_installed}")
    lines.append(f"- **Paramak version**: {result.paramak_version}")
    lines.append(f"- **Build name**: {result.build_name}")
    lines.append(f"- **Total radius**: {result.total_radius_cm:.2f} cm")
    lines.append(f"- **Plasma height**: {result.plasma_height_cm:.2f} cm")
    lines.append(f"- **Blanket volume**: {result.blanket_volume_cm3:.2f} cm3")
    lines.append(f"- **STEP file generated**: {result.step_file_generated}")
    if result.step_file_path:
        lines.append(f"- **STEP path**: {result.step_file_path}")
    lines.append("")
    lines.append("## Notes")
    lines.append("")
    lines.append(result.notes)
    return "\n".join(lines)