#!/usr/bin/env python3
"""Tier 19.A — 3D-resolved TBR sweep on the existing Tier 6 1D geometry.

This is the "cheap" 3D scope from the zreview5 audit Item 7: add a
CylindricalMesh tally on top of the existing 1D Z-pinch geometry. Maps
tritium-breeding vs (r, z). No new geometry construction.

Baseline geometry (matches Tier 6):
    - R_plasma   = 4.0 cm
    - R_be       = 6.0 cm  (Be INSIDE blanket, standard fusion design)
    - R_blanket  = 50.0 cm (LiPb)
    - R_struct   = 53.0 cm (RAFM)
    - height     = 100.0 cm
    - Li-6 enr   = 0.90
    - boundary   = white (reflective)
    - source     = 14.1 MeV D-T neutron at origin

Mesh resolution:
    - 30 radial bins × 30 axial bins (2 cm × 4 cm cells)
    - r_max = 60 cm, z_half = 60 cm

Default n_particles × n_batches = 5000 × 10 (≈ 1-2 min wall-clock per run
on Windows; Tier 6 convergence showed this is fully converged at <1% stddev).

Output:
    data/results/<YYYY-MM-DD>_tier19_3d/
        tier19_3d_baseline.json   (full result dict)
        tier19_3d_baseline.md     (human-readable summary)
        mesh_total.npy            (n_r, n_z) array
        mesh_per_nuclide.npy      (n_nuclides, n_r, n_z) array

Usage:
    .venv/Scripts/python.exe scripts/run_tier19_3d_sweep.py
    .venv/Scripts/python.exe scripts/run_tier19_3d_sweep.py --Li6 0.6
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import numpy as np

# Add project root to path so we can import zpp.*
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from zpp.zpp_real_openmc_3d import run_tier19_3d, tier19_to_markdown

# Same nuclear-data provenance stamp used by other Tier sweeps in this project
TZ_BEIJING = timezone(timedelta(hours=8))
TIMESTAMP = datetime.now(TZ_BEIJING).strftime("%Y-%m-%d_%H%M")
DATE_DIR = datetime.now(TZ_BEIJING).strftime("%Y-%m-%d_%H%M")
RESULT_DIR = (
    PROJECT_ROOT / "data" / "results" / f"{TIMESTAMP}_tier19_3d"
)


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Tier 19.A: 3D-resolved TBR sweep via CylindricalMesh."
    )
    p.add_argument(
        "--Li6", type=float, default=0.90,
        help="Li-6 enrichment fraction [0, 1]. Default 0.90.",
    )
    p.add_argument(
        "--height", type=float, default=100.0,
        help="Z-pinch cylinder height (cm). Default 100.",
    )
    p.add_argument(
        "--R_blanket", type=float, default=50.0,
        help="LiPb blanket outer radius (cm). Default 50.",
    )
    p.add_argument(
        "--n_particles", type=int, default=5000,
        help="Particles per batch. Default 5000 (matches Tier 6).",
    )
    p.add_argument(
        "--n_batches", type=int, default=10,
        help="Number of batches. Default 10 (matches Tier 6).",
    )
    p.add_argument(
        "--n_radial_bins", type=int, default=30,
        help="Radial mesh bins. Default 30 (2 cm resolution at r_max=60).",
    )
    p.add_argument(
        "--r_max", type=float, default=60.0,
        help="Outer r of mesh (cm). Default 60.",
    )
    p.add_argument(
        "--n_axial_bins", type=int, default=30,
        help="Axial mesh bins. Default 30 (4 cm resolution at z_half=60).",
    )
    p.add_argument(
        "--z_half", type=float, default=60.0,
        help="Half-height of mesh (cm). Default 60.",
    )
    p.add_argument(
        "--include_be9", action="store_true",
        help="Include Be-9 (n,2n) in the mesh tally.",
    )
    p.add_argument(
        "--seed", type=int, default=42,
        help="OpenMC seed for reproducibility. Default 42.",
    )
    return p.parse_args()


def _save_result(result: dict, out_dir: Path, tag: str = "baseline") -> None:
    """Save JSON + Markdown + npy arrays. Strip ndarray → list for JSON."""
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"tier19_3d_{tag}.json"
    md_path = out_dir / f"tier19_3d_{tag}.md"
    mesh_total_path = out_dir / "mesh_total.npy"
    mesh_per_nuclide_path = out_dir / "mesh_per_nuclide.npy"
    r_centers_path = out_dir / "r_centers.npy"
    z_centers_path = out_dir / "z_centers.npy"

    # Save npy arrays first (binary, lossless)
    np.save(mesh_total_path, result["mesh_total"])
    np.save(mesh_per_nuclide_path, result["mesh_per_nuclide"])
    np.save(r_centers_path, result["r_centers"])
    np.save(z_centers_path, result["z_centers"])

    # JSON-able view (no ndarray)
    json_view = {
        "TBR_total": result["TBR_total"],
        "TBR_total_stddev": result["TBR_total_stddev"],
        "TBR_3d_sum": result["TBR_3d_sum"],
        "match_ratio": result["match_ratio"],
        "peak_r": result["peak_r"],
        "peak_z": result["peak_z"],
        "peak_value": result["peak_value"],
        "tbr_in_lipb_ring": result["tbr_in_lipb_ring"],
        "tbr_in_be_ring": result["tbr_in_be_ring"],
        "tbr_in_structure": result["tbr_in_structure"],
        "fraction_lipb": result["fraction_lipb"],
        "fraction_be": result["fraction_be"],
        "fraction_structure": result["fraction_structure"],
        "nuclides": result["nuclides"],
        "geometry_params": result["geometry_params"],
        "runtime_s": result["runtime_s"],
        "npy_files": {
            "mesh_total": str(mesh_total_path.relative_to(PROJECT_ROOT)),
            "mesh_per_nuclide": str(
                mesh_per_nuclide_path.relative_to(PROJECT_ROOT)
            ),
            "r_centers": str(r_centers_path.relative_to(PROJECT_ROOT)),
            "z_centers": str(z_centers_path.relative_to(PROJECT_ROOT)),
        },
    }
    json_path.write_text(json.dumps(json_view, indent=2, sort_keys=True))

    md_path.write_text(tier19_to_markdown(result))

    print(f"\nWrote:")
    print(f"  {json_path.relative_to(PROJECT_ROOT)}")
    print(f"  {md_path.relative_to(PROJECT_ROOT)}")
    print(f"  {mesh_total_path.relative_to(PROJECT_ROOT)}")
    print(f"  {mesh_per_nuclide_path.relative_to(PROJECT_ROOT)}")


def main() -> int:
    args = _parse_args()
    print("=" * 72)
    print("Tier 19.A — 3D-resolved TBR (CylindricalMesh on Tier 6 1D geometry)")
    print("=" * 72)
    print(f"  Li-6 enrichment: {args.Li6*100:.0f}%")
    print(f"  Geometry: R_blanket={args.R_blanket}, height={args.height}")
    print(f"  Compute: {args.n_particles:,} particles × {args.n_batches} batches")
    print(f"  Mesh:    {args.n_radial_bins} × {args.n_axial_bins} bins (r × z)")
    print(f"  Seed:    {args.seed}")
    print(f"  Output:  {RESULT_DIR.relative_to(PROJECT_ROOT)}")
    print()
    print("Running OpenMC — please wait ...")
    sys.stdout.flush()

    result = run_tier19_3d(
        R_blanket_cm=args.R_blanket,
        height_cm=args.height,
        Li6_enrichment_fraction=args.Li6,
        n_particles=args.n_particles,
        n_batches=args.n_batches,
        n_radial_bins=args.n_radial_bins,
        r_max_cm=args.r_max,
        n_axial_bins=args.n_axial_bins,
        z_half_height_cm=args.z_half,
        include_be9=args.include_be9,
        seed=args.seed,
    )

    # Headline summary on stdout
    print()
    print("=" * 72)
    print(f"  TBR_total (cell tally):       {result['TBR_total']:.4f} ± {result['TBR_total_stddev']:.4f}")
    print(f"  TBR_3d_sum (mesh):            {result['TBR_3d_sum']:.4f}")
    print(f"  Match ratio (mesh/total):     {result['match_ratio']:.4f}")
    print(f"  Peak TBR at r={result['peak_r']:.1f} cm, z={result['peak_z']:.1f} cm ({result['peak_value']:.4e})")
    print(f"  TBR in LiPb ring (r=6..50):   {result['tbr_in_lipb_ring']:.4f} ({result['fraction_lipb']*100:.1f}%)")
    print(f"  TBR in Be ring (r=4..6):      {result['tbr_in_be_ring']:.4f} ({result['fraction_be']*100:.1f}%)")
    print(f"  TBR in structure (r>=50):     {result['tbr_in_structure']:.4f} ({result['fraction_structure']*100:.1f}%)")
    print(f"  Runtime:                      {result['runtime_s']:.1f} s")
    print("=" * 72)

    _save_result(result, RESULT_DIR, tag="baseline")

    # Cross-validation check.
    # Tier 19.A default geometry matches Tier 18.B (mult_inside=True, R_be=6):
    #     Tier 18.B published: TBR = 1.8280 ± 0.33% (rel std 0.006)
    # If mult_inside=False, compare against Tier 6 baseline (1.7996 ± 0.23%).
    # Determine which comparator to use based on geometry.
    gp = result["geometry_params"]
    if gp["mult_inside"]:
        # Tier 18.B comparator
        ref_tbr = 1.8280
        ref_label = "Tier 18.B (mult_inside=True)"
        ref_std = 0.0060
    else:
        # Tier 6 baseline comparator
        ref_tbr = 1.7996
        ref_label = "Tier 6 (mult_inside=False)"
        ref_std = 0.0042
    diff = abs(result["TBR_total"] - ref_tbr)
    if diff < 2 * ref_std:
        print(f"\n✅ Cross-validation PASSED: Tier 19 TBR within 2σ of {ref_label} ({ref_tbr:.4f}).")
    elif diff < 3 * ref_std:
        print(f"\n⚠️  Cross-validation MARGINAL: Tier 19 TBR within 3σ of {ref_label} ({ref_tbr:.4f}).")
    else:
        print(f"\n❌ Cross-validation FAILED: Tier 19 TBR differs from {ref_label} ({ref_tbr:.4f}) by {diff:.4f} (>3σ).")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
