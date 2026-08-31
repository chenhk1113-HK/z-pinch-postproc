"""
Geometry-aware TBR: sweep blanket thickness for each radial build.

Tier 5.A used coverage_fraction() from the radial build to compute
TBR at a single blanket thickness. Tier 5.B generalizes: for each
of the four pre-defined radial builds, sweep blanket thickness
[10, 20, 30, 40, 50, 60, 80, 100] cm and compute TBR as a
function of geometry-informed coverage.

Outputs:
- TBR_saturation_curves: dict of build_name -> list of
  (thickness_cm, TBR) tuples showing the saturation curve.
- best_blanket_thickness: for each build, the thickness at which
  TBR reaches 95% of saturation.
- build_compare_table: comparison across builds at a target
  thickness (default 50 cm).

Use cases:
- Identify the minimum blanket thickness for tritium self-
  sufficiency in each geometry.
- Compare geometries on a level playing field.
- Inform the blanket design choice for a given geometry.
"""
from __future__ import annotations
from dataclasses import dataclass, field
import numpy as np

from zpp.zpp_tbr import (
    TBRInputs, compute_TBR, TBRResult,
)
from zpp.zpp_geometry import (
    ZIFERadialBuild, get_build, ALL_BUILDS,
)


# Default tritium self-sufficiency threshold for geometry-aware TBR.
DEFAULT_TRITIUM_THRESHOLD = 1.05


# Blanket thickness sweep values [cm].
THICKNESS_SWEEP_CM = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 80.0, 100.0, 150.0, 200.0]


@dataclass
class SaturationCurve:
    """TBR vs blanket thickness for one radial build + one blanket."""
    build_name: str
    blanket_material: str
    neutron_multiplier: str
    Li6_enrichment_fraction: float
    MHD_effect_factor: float
    thickness_cm_list: list
    TBR_list: list
    coverage_fraction: float
    notes: str = ""

    def TBR_saturation(self) -> float:
        """Asymptotic TBR at thick blanket."""
        return self.TBR_list[-1] if self.TBR_list else 0.0

    def TBR_95pct_thickness_cm(self) -> float:
        """Thickness at which TBR reaches 95% of saturation."""
        sat = self.TBR_saturation()
        for thk, tbr in zip(self.thickness_cm_list, self.TBR_list):
            if tbr >= 0.95 * sat:
                return thk
        return self.thickness_cm_list[-1] if self.thickness_cm_list else 0.0

    def TBR_at_thickness(self, thickness_cm: float) -> float:
        """Get TBR at a specific thickness (interpolated)."""
        if not self.thickness_cm_list:
            return 0.0
        if thickness_cm <= self.thickness_cm_list[0]:
            return self.TBR_list[0]
        if thickness_cm >= self.thickness_cm_list[-1]:
            return self.TBR_list[-1]
        for i in range(len(self.thickness_cm_list) - 1):
            t0, t1 = self.thickness_cm_list[i], self.thickness_cm_list[i + 1]
            if t0 <= thickness_cm <= t1:
                b0, b1 = self.TBR_list[i], self.TBR_list[i + 1]
                return b0 + (b1 - b0) * (thickness_cm - t0) / (t1 - t0)
        return self.TBR_list[-1]


@dataclass
class BlanketThicknessSweep:
    """TBR vs thickness sweep for one radial build."""
    build_name: str
    geometry: ZIFERadialBuild
    coverage_fraction: float
    curves: dict  # (material, multiplier) -> SaturationCurve


def tbr_vs_thickness(
    build_name: str,
    blanket_material: str = "LiPb",
    neutron_multiplier: str = "Be",
    Li6_enrichment_fraction: float = 0.30,
    MHD_effect_factor: float = 0.90,
    thickness_list: list = None,
) -> SaturationCurve:
    """Compute TBR vs blanket thickness for one build + blanket."""
    if thickness_list is None:
        thickness_list = THICKNESS_SWEEP_CM
    geometry = get_build(build_name)
    if "Z" in build_name or build_name in ("GF-MTF", "Zap-SFZ"):
        coverage = geometry.coverage_fraction("Z-pinch")
    else:
        coverage = geometry.coverage_fraction("tokamak")
    TBR_list = []
    for thk in thickness_list:
        inp = TBRInputs(
            blanket_material=blanket_material,
            neutron_multiplier=neutron_multiplier,
            blanket_thickness_cm=thk,
            Li6_enrichment_fraction=Li6_enrichment_fraction,
            MHD_effect_factor=MHD_effect_factor,
            first_wall_coverage_fraction=coverage,
        )
        r = compute_TBR(inp)
        TBR_list.append(r.TBR)
    return SaturationCurve(
        build_name=build_name,
        blanket_material=blanket_material,
        neutron_multiplier=neutron_multiplier,
        Li6_enrichment_fraction=Li6_enrichment_fraction,
        MHD_effect_factor=MHD_effect_factor,
        thickness_cm_list=list(thickness_list),
        TBR_list=TBR_list,
        coverage_fraction=coverage,
        notes=f"build={build_name}, blanket={blanket_material}+{neutron_multiplier}, "
              f"Li6={Li6_enrichment_fraction:.0%}, coverage={coverage:.3f}",
    )


def sweep_blanket_thickness(
    build_names: list = None,
    blankets: list = None,
    Li6_enrichment_fraction: float = 0.30,
    MHD_effect_factor: float = 0.90,
) -> dict:
    """Sweep TBR across (build, blanket_material, multiplier) combinations.

    Args:
        build_names: List of pre-defined build names (default: all 4).
        blankets: List of (material, multiplier) tuples.
        Li6_enrichment_fraction: Li-6 enrichment (default 30%).
        MHD_effect_factor: MHD losses (default 0.90).

    Returns:
        dict of build_name -> BlanketThicknessSweep.
    """
    if build_names is None:
        build_names = list(ALL_BUILDS.keys())
    if blankets is None:
        blankets = [("LiPb", "Be"), ("LiPb", "Pb"), ("FLiBe", "Be")]
    results = {}
    for build_name in build_names:
        geometry = get_build(build_name)
        if "Z" in build_name or build_name in ("GF-MTF", "Zap-SFZ"):
            coverage = geometry.coverage_fraction("Z-pinch")
        else:
            coverage = geometry.coverage_fraction("tokamak")
        curves = {}
        for mat, mult in blankets:
            curve = tbr_vs_thickness(
                build_name, mat, mult,
                Li6_enrichment_fraction=Li6_enrichment_fraction,
                MHD_effect_factor=MHD_effect_factor,
            )
            curves[(mat, mult)] = curve
        results[build_name] = BlanketThicknessSweep(
            build_name=build_name,
            geometry=geometry,
            coverage_fraction=coverage,
            curves=curves,
        )
    return results


def build_compare_at_thickness(
    sweeps: dict,
    target_thickness_cm: float = 50.0,
    blanket_material: str = "LiPb",
    neutron_multiplier: str = "Be",
    tritium_threshold: float = DEFAULT_TRITIUM_THRESHOLD,
) -> list:
    """Compare all builds at a target blanket thickness.

    Returns:
        list of dicts, one per build, with TBR, coverage, etc.
    """
    rows = []
    for build_name, sweep in sweeps.items():
        curve = sweep.curves.get((blanket_material, neutron_multiplier))
        if curve is None:
            continue
        TBR_at_target = curve.TBR_at_thickness(target_thickness_cm)
        sat = curve.TBR_saturation()
        rows.append({
            "build_name": build_name,
            "blanket_material": blanket_material,
            "neutron_multiplier": neutron_multiplier,
            "target_thickness_cm": target_thickness_cm,
            "coverage_fraction": sweep.coverage_fraction,
            "TBR_at_target": TBR_at_target,
            "TBR_saturation": sat,
            "TBR_saturation_ratio": TBR_at_target / sat if sat > 0 else 0,
            "TBR_95pct_thickness_cm": curve.TBR_95pct_thickness_cm(),
            "sufficient_at_target": TBR_at_target >= tritium_threshold,
            "notes": curve.notes,
        })
    return rows


def compare_table_markdown(rows: list) -> str:
    """Format the build comparison as Markdown."""
    headers = ["Build", "Blanket", "Mult", "Thk (cm)", "Coverage",
               "TBR @ thk", "TBR sat", "% sat", "Thk@95%", "Sufficient"]
    lines = [
        "| " + " | ".join(headers) + " |",
        "|" + "|".join(["---"] * len(headers)) + "|",
    ]
    for r in rows:
        lines.append("| " + " | ".join([
            r["build_name"], r["blanket_material"], r["neutron_multiplier"],
            f"{r['target_thickness_cm']:.0f}", f"{r['coverage_fraction']:.3f}",
            f"{r['TBR_at_target']:.3f}", f"{r['TBR_saturation']:.3f}",
            f"{r['TBR_saturation_ratio']:.0%}",
            f"{r['TBR_95pct_thickness_cm']:.0f}",
            "✓" if r["sufficient_at_target"] else "✗",
        ]) + " |")
    return "\n".join(lines)


def saturation_curve_csv(curve: SaturationCurve) -> str:
    """Format a single saturation curve as CSV."""
    lines = ["thickness_cm,TBR"]
    for thk, tbr in zip(curve.thickness_cm_list, curve.TBR_list):
        lines.append(f"{thk},{tbr:.4f}")
    return "\n".join(lines)
