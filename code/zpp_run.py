#!/usr/bin/env python3
"""
zpp_run.py — CLI entry point for the Z-pinch post-processor.

Usage:
    python zpp_run.py --input PROFILE.csv \
                      --driver-E-stored-MJ 11.5 \
                      --driver-efficiency 0.15 \
                      --liner-KE-MJ 0.45 \
                      --eta-helper 0.40 \
                      --output OUTPUT.json \
                      [--shot-id z2960] \
                      [--R-initial-cm 0.5]

The CLI ingests a 1D rad-MHD profile (CSV or JSON), runs the pipeline,
and writes a single report JSON conforming to PLAN_v0.1.md §5.3.
"""
from __future__ import annotations
import argparse
import datetime
import sys
from pathlib import Path

# Allow `python zpp_run.py` from anywhere by adding the script's dir to sys.path
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import numpy as np
from zpp_pipeline import run_pipeline
from zpp_io import read_profile, write_report


def _build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="zpp_run",
        description="Z-pinch fusion post-processor (v0.0.1-prelim)",
    )
    p.add_argument("--input", required=True, help="Path to 1D profile CSV/JSON")
    p.add_argument(
        "--driver-E-stored-MJ",
        type=float,
        required=True,
        help="Driver stored electrical energy [MJ] (Marx bank / LTD)",
    )
    p.add_argument(
        "--driver-efficiency",
        type=float,
        default=0.15,
        help="Driver efficiency (energy delivered to liner / stored). Default 0.15.",
    )
    p.add_argument(
        "--liner-KE-MJ",
        type=float,
        required=True,
        help="Liner kinetic energy at peak velocity [MJ]",
    )
    p.add_argument(
        "--eta-helper",
        type=float,
        default=0.40,
        help="Thermal-to-electric efficiency (Brayton cycle). Default 0.40.",
    )
    p.add_argument(
        "--R-initial-cm",
        type=float,
        default=None,
        help="Initial liner outer radius [cm] (for convergence ratio)",
    )
    p.add_argument(
        "--output",
        required=True,
        help="Path to output report JSON",
    )
    p.add_argument(
        "--shot-id",
        default="synthetic",
        help="Shot ID for the report's input_provenance",
    )
    p.add_argument(
        "--simulator",
        default="synthetic",
        help="Name of the simulator that produced the input profile",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    p = _build_argparser()
    args = p.parse_args(argv)

    prof = read_profile(args.input)
    n_samples = len(prof["time_ns"])

    # Driver parameters
    E_stored_J = args.driver_E_stored_MJ * 1e6  # MJ -> J
    E_kinetic_J = args.liner_KE_MJ * 1e6
    # E_kinetic is the result of driver_efficiency × E_stored for consistency.
    # If the user gave both, trust the explicit --liner-KE-MJ.
    E_kin_from_driver = E_stored_J * args.driver_efficiency
    if abs(E_kinetic_J - E_kin_from_driver) / max(E_kin_from_driver, 1e-30) > 0.30:
        # Sanity warning: explicit KE differs from driver × efficiency by >30%
        import warnings
        warnings.warn(
            f"zpp_run: --liner-KE-MJ ({args.liner_KE_MJ} MJ) differs from "
            f"--driver-E-stored-MJ * --driver-efficiency "
            f"({E_kin_from_driver/1e6:.2f} MJ) by >30%. Using the explicit value.",
            RuntimeWarning,
            stacklevel=1,
        )

    radius_cm = prof.get("radius_cm", None)

    provenance = {
        "source_file": str(args.input),
        "simulator": args.simulator,
        "shot_id": args.shot_id,
        "n_samples": int(n_samples),
        "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
        "zpp_version": "0.0.1-prelim",
        "driver_E_stored_MJ": args.driver_E_stored_MJ,
        "driver_efficiency": args.driver_efficiency,
        "liner_KE_MJ": args.liner_KE_MJ,
        "eta_helper": args.eta_helper,
        "R_initial_cm": args.R_initial_cm,
    }

    report = run_pipeline(
        time_ns=prof["time_ns"],
        T_keV=prof["T_keV"],
        rho_gcc=prof["rho_gcc"],
        E_stored_J=E_stored_J,
        E_kinetic_J=E_kinetic_J,
        radius_cm=radius_cm,
        R_initial_cm=args.R_initial_cm,
        eta_helper=args.eta_helper,
        input_provenance=provenance,
    )

    write_report(report, args.output)
    # One-line stdout summary so the user can sanity-check at a glance
    r = report["results"]
    print(
        f"[zpp_run] E_fus={r['E_fusion_MJ']:.4f} MJ | "
        f"Q_target={r['Q_target']:.4f} | Q_eng={r['Q_eng']:.4f} | "
        f"eta_wp={r['eta_wallplug']:.4f} | "
        f"tau_burn={r['tau_burn_ns']:.1f} ns | "
        f"lawson={r['lawson_nTtau_keVs_per_m3']:.3e} keV*s/m^3 [{r['lawson_class']}] | "
        f"P_stag={r['P_stag_GPa']:.1f} GPa | CR={r['convergence_ratio']:.1f}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
