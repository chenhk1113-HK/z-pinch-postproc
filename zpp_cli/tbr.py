"""zpp TBR CLI — run a parametric TBR sweep from the command line.

Usage:
    zpp-tbr --R-blanket 80 --Li6 0.90 --mult-inside
    zpp-tbr --help
"""
import argparse
import sys


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="zpp-tbr",
        description="Compute Z-pinch blanket TBR (parametric formula, fast).",
    )
    parser.add_argument(
        "--R-blanket", type=float, default=80.0,
        help="Blanket thickness in cm (default: 80)",
    )
    parser.add_argument(
        "--Li6", type=float, default=0.90,
        help="Li-6 enrichment fraction 0-1 (default: 0.90)",
    )
    parser.add_argument(
        "--blanket", type=str, default="LiPb",
        help="Blanket breeder material: 'LiPb' or 'Li' (default: LiPb)",
    )
    parser.add_argument(
        "--geometry", type=str, default="Z-pinch",
        help="Reactor geometry (default: Z-pinch)",
    )
    args = parser.parse_args()

    # Lazy import so the CLI works whether installed via pip or run
    # from source via `python zpp_cli/tbr.py`.
    from zpp.zpp_tbr import compute_TBR, TBRInputs

    inputs = TBRInputs(
        blanket_material=args.blanket,
        Li6_enrichment_fraction=args.Li6,
        blanket_thickness_cm=args.R_blanket,
        geometry=args.geometry,
    )
    result = compute_TBR(inputs)
    print(f"TBR = {result.TBR:.4f}")
    print(f"  blanket = {args.blanket}")
    print(f"  thickness = {args.R_blanket} cm")
    print(f"  Li-6 enrichment = {args.Li6 * 100:.1f}%")
    print(f"  geometry = {args.geometry}")
    return 0


if __name__ == "__main__":
    sys.exit(main())