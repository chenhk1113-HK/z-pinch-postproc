#!/usr/bin/env python3
"""Reproduce the Tier 6 LiPb baseline OpenMC run (per drop-mcnp.docx §P1-C).

Tier 6 cylindrical Z-pinch LiPb baseline geometry:
  - Plasma inner radius:    R_plasma   = 4.0 cm
  - Be multiplier outer:    R_be       = 52.0 cm   (Be OUTSIDE the blanket)
  - Blanket outer:          R_blanket  = 50.0 cm   (LiPb)
  - Structure outer:        R_struct   = 53.0 cm   (RAFM steel)
  - Height:                 height     = 100.0 cm
  - Li-6 enrichment:        Li6_enr    = 0.90      (90% enriched)
  - Boundary:               reflective (white) on all outer surfaces
  - Source:                 14.1 MeV D-T neutron, isotropic point source at origin

Published baseline: TBR_mc = 1.7996 +/- 0.23% at n_particles=5000
(see data/results/2026-09-01_tier6_convergence/ for the convergence curve).

This is the same geometry as the Tier 6 baseline, but with Be OUTSIDE
the blanket (R_be=52 > R_blanket=50). The Tier 18.B sweep uses Be INSIDE
(R_be=6 < R_blanket=50), giving TBR=1.8280. The ~2% difference is
real layer-order physics, not a bug.

Run with:
    export OPENMC_CROSS_SECTIONS=data/nuclear_data/ace/cross_sections.xml
    python scripts/run_tier6_sweep.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "data" / "results" / "2026-08-31_tier6_baseline"
OUT_PATH = OUT_DIR / "tier6_lipb_baseline.json"


def main() -> int:
    print("Tier 6 LiPb baseline reproduction (per drop-mcnp.docx P1-C)")
    print(f"Output: {OUT_PATH.relative_to(REPO_ROOT)}\n")
    code = (
        "import os\n"
        "os.environ['OPENMC_CROSS_SECTIONS'] = 'data/nuclear_data/ace/cross_sections.xml'\n"
        "from zpp.zpp_real_openmc_transport import run_real_openmc_tbr\n"
        "r = run_real_openmc_tbr(\n"
        "    n_particles=5000, n_batches=10,\n"
        "    R_plasma_cm=4.0, R_be_cm=52.0, R_blanket_cm=50.0,\n"
        "    R_structure_cm=53.0, mult_inside=False,\n"
        "    Li6_enrichment_fraction=0.90, boundary_type='reflective',\n"
        ")\n"
        "print(f'{r.openmc_TBR:.7f} {r.openmc_TBR_stddev*100:.4f}')\n"
    )
    env = os.environ.copy()
    env["OPENMC_CROSS_SECTIONS"] = str(REPO_ROOT / "data" / "nuclear_data" / "ace" / "cross_sections.xml")
    out = subprocess.run(
        [str(REPO_ROOT / ".venv" / "Scripts" / "python.exe"), "-c", code],
        capture_output=True, text=True, timeout=120, env=env,
    )
    if out.returncode != 0:
        print(f"OpenMC run failed:\n  stdout: {out.stdout}\n  stderr: {out.stderr[:500]}", file=sys.stderr)
        return 1
    tbr, rel_std = out.stdout.strip().split()
    result = {
        "label": "tier6_lipb_baseline",
        "breeder": "LiPb",
        "TBR_mc": float(tbr),
        "TBR_rel_stddev": float(rel_std) / 100,
        "geometry": "R_plasma=4, R_be=52 (Be outside), R_blanket=50, R_struct=53 cm, Li-6=90%, mult_inside=False, reflective BC",
        "n_particles": 5000,
        "n_batches": 10,
    }
    print(f"  TBR_mc = {result['TBR_mc']:.4f} +/- {result['TBR_rel_stddev']*100:.3f}%")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"\nWrote {OUT_PATH.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
