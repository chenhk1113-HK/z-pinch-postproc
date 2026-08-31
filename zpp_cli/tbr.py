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
        help="Blanket outer radius in cm (default: 80)",
    )
    parser.add_argument(
        "--Li6", type=float, default=0.90,
        help="Li-6 enrichment fraction 0-1 (default: 0.90)",
    )
    parser.add_argument(
        "--mult-inside", action="store_true",
        help="Place Be multiplier inside the LiPb (default: outside)",
    )
    parser.add_argument(
        "--R-be", type=float, default=None,
        help="Be multiplier outer radius (default: derived from R-blanket)",
    )
    args = parser.parse_args()

    # Lazy imports so the CLI works whether installed via pip or run
    # from source via `python zpp_cli/tbr.py`.
    try:
        from zpp.zpp_tbr import compute_TBR, TBRInputs
    except ImportError:
        # Source-mode: prepend code/ to sys.path
        sys.path.insert(0, "code")
        from zpp.zpp_tbr import compute_TBR, TBRInputs  # type: ignore

    inputs = TBRInputs(
        R_blanket_cm=args.R_blanket,
        Li6_enrichment_fraction=args.Li6,
        mult_inside=args.mult_inside,
        R_be_cm=args.R_be,
    )
    result = compute_TBR(inputs)
    print(f"TBR = {result.TBR:.4f}")
    print(f"  R_blanket = {args.R_blanket} cm")
    print(f"  Li-6 enrichment = {args.Li6 * 100:.1f}%")
    print(f"  mult_inside = {args.mult_inside}")
    return 0


if __name__ == "__main__":
    sys.exit(main())