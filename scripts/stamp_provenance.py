#!/usr/bin/env python3
"""Tier-result provenance stamper (v1.5.0 PATCH per drop-mcnp.docx §P1-A).

For every Tier result directory under `data/results/`, ensure the
JSON + Markdown summary files carry an explicit `provenance` block:

    {
      "openmc_version": "0.16.0",
      "endf_release":   "ENDF/B-VIII.0",
      "ace_source":     "openmc-anywhere / IAEA",
      "n_particles":    5000,
      "n_batches":      10,
      "n_inactive":     2,
      "timestamp":      "2026-09-01T10:30:00Z",
      "stamped_by":     "scripts/stamp_provenance.py"
    }

Without provenance, every Tier number is un-citeable as a "result"
because a reader cannot reproduce the cross-section set, the OpenMC
version, or the particle count.

Usage:
    python scripts/stamp_provenance.py               # stamp everything
    python scripts/stamp_provenance.py tier18b_li4sio4  # stamp one dir
    python scripts/stamp_provenance.py --list        # just list stamps
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = REPO_ROOT / "data" / "results"


def detect_openmc_version() -> str:
    """Return installed OpenMC version, e.g. '0.16.0'.

    Uses the venv python first (where OpenMC is actually installed),
    then falls back to system python.
    """
    venv_py = REPO_ROOT / ".venv" / "Scripts" / "python.exe"
    candidates = [str(venv_py)] if venv_py.exists() else []
    candidates.append(sys.executable)
    for py in candidates:
        try:
            out = subprocess.run(
                [py, "-c", "import openmc; print(openmc.__version__)"],
                capture_output=True, text=True, timeout=10,
            )
            if out.returncode == 0:
                return out.stdout.strip()
        except Exception:
            pass
    return "unknown"


def detect_endf_release(cross_sections_xml: Path) -> str:
    """Infer the ENDF release from the cross_sections.xml header comments.

    OpenMC's cross_sections.xml doesn't always carry an explicit ENDF tag,
    so we look at the directory layout and filenames for evidence. As a
    fallback we record 'ENDF/B-VIII.0' because that is the release the
    download_cross_sections.py script targets.
    """
    if not cross_sections_xml.exists():
        return "ENDF/B-VIII.0 (declared, not verified on disk)"
    # Look at the first ~50 lines for ENDF/JEFF/FENDL markers.
    head = cross_sections_xml.read_text(encoding="utf-8", errors="replace").splitlines()[:50]
    text = "\n".join(head)
    for tag in ["ENDF/B-VIII", "ENDF/B-VII", "JEFF-3", "FENDL-3", "TENDL"]:
        if tag in text:
            return tag
    # Fall back to the parent directory structure.
    parent = cross_sections_xml.parent
    if "viii" in parent.name.lower():
        return "ENDF/B-VIII.0 (inferred from directory)"
    return "ENDF/B-VIII.0 (declared)"


def detect_particle_count(result_dir: Path) -> dict:
    """Find the n_particles and n_batches used for this Tier.

    Strategy: look at the Tier source code under zpp/, scripts/, and
    tests/ that produced the result JSON. We do not execute the code
    (too slow / needs OpenMC installed); we just regex its function
    signatures and explicit call sites.

    Tier directory names like 'tier18b_li4sio4' or 'tier9_furuta' may
    have a non-numeric suffix (letter or word). We extract the digit
    prefix and try both 'tier<N>' and 'tier<N><suffix>' matches.

    Falls back to the central `run_real_openmc_tbr` defaults
    (n_particles=5000, n_batches=10) when no Tier-specific value is
    found in source — those are the project-wide defaults.
    """
    candidates = list(REPO_ROOT.glob("zpp/zpp_*.py"))
    candidates += list(REPO_ROOT.glob("scripts/run_*.py"))
    candidates += list(REPO_ROOT.glob("scripts/sweep_*.py"))
    candidates += list(REPO_ROOT.glob("tests/test_zpp_tier*.py"))
    candidates += list(REPO_ROOT.glob("tests/test_zpp_*sweep*.py"))
    found = {"n_particles": None, "n_batches": None, "n_inactive": None}
    tier_label = result_dir.name
    m = re.match(r"(tier\d+\w*)", tier_label)
    if m:
        tier_token = m.group(1)
        digit_part = re.match(r"tier(\d+)", tier_token).group(1)
        # Priority 1: explicit n_particles= in a Tier-specific file
        for c in candidates:
            text = c.read_text(encoding="utf-8", errors="replace")
            # Match by 'tierN' or 'Tier N' or 'tier_N' or filename tierN*.py
            if (f"Tier {digit_part}" not in text
                and f"tier{digit_part}" not in text
                and tier_token not in c.name
                and digit_part not in c.name):
                continue
            for key, pat in [
                ("n_particles", r"n_particles\s*=\s*(\d+)"),
                ("n_batches", r"n_batches\s*=\s*(\d+)"),
                ("n_inactive", r"n_inactive\s*=\s*(\d+)"),
            ]:
                mm = re.search(pat, text)
                if mm and found[key] is None:
                    found[key] = int(mm.group(1))
    # Fall back to the central run_real_openmc_tbr defaults.
    if found["n_particles"] is None:
        transport = REPO_ROOT / "zpp" / "zpp_real_openmc_transport.py"
        if transport.exists():
            text = transport.read_text(encoding="utf-8", errors="replace")
            mm = re.search(
                r"def\s+run_real_openmc_tbr\([^)]*n_particles\s*=\s*(\d+)",
                text,
            )
            if mm:
                found["n_particles"] = int(mm.group(1))
            mm = re.search(
                r"def\s+run_real_openmc_tbr\([^)]*n_batches\s*=\s*(\d+)",
                text,
            )
            if mm:
                found["n_batches"] = int(mm.group(1))
    # Last-resort project defaults (the run_real_openmc_tbr signature).
    if found["n_particles"] is None:
        found["n_particles"] = 5000
    if found["n_batches"] is None:
        found["n_batches"] = 10
    if found["n_inactive"] is None:
        found["n_inactive"] = 2  # OpenMC default
    return found


def make_provenance(result_dir: Path, openmc_version: str) -> dict:
    xs = REPO_ROOT / "data" / "nuclear_data" / "ace" / "cross_sections.xml"
    particles = detect_particle_count(result_dir)
    return {
        "openmc_version": openmc_version,
        "endf_release": detect_endf_release(xs),
        "ace_source": "openmc-anywhere / IAEA (per scripts/download_cross_sections.py)",
        "n_particles": particles["n_particles"],
        "n_batches": particles["n_batches"],
        "n_inactive": particles["n_inactive"],
        "timestamp": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "stamped_by": "scripts/stamp_provenance.py",
    }


def stamp_json(path: Path, provenance: dict) -> None:
    """Stamp a *sweep.json* with provenance (preserves other keys)."""
    data = json.loads(path.read_text(encoding="utf-8"))
    # Wrap in {'provenance': ..., 'results': [...]} if it's a bare list.
    if isinstance(data, list):
        data = {"provenance": provenance, "results": data}
    else:
        data["provenance"] = provenance
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def stamp_markdown(path: Path, provenance: dict) -> None:
    """Stamp a *sweep.md with a '## Provenance' section if not present."""
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")
    if "## Provenance" in text:
        # Replace existing provenance section.
        text = re.sub(
            r"## Provenance\n.*?(?=^## |\Z)",
            "## Provenance\n\n" + render_provenance_md(provenance) + "\n\n",
            text,
            flags=re.DOTALL | re.MULTILINE,
        )
    else:
        text = text.rstrip() + "\n\n## Provenance\n\n" + render_provenance_md(provenance) + "\n"
    path.write_text(text, encoding="utf-8")


def render_provenance_md(p: dict) -> str:
    return (
        f"- **OpenMC version:** `{p['openmc_version']}`\n"
        f"- **ENDF release:** {p['endf_release']}\n"
        f"- **Cross-section source:** {p['ace_source']}\n"
        f"- **Source particles / batch:** `{p['n_particles']}` "
        f"({p['n_batches']} batches, {p['n_inactive']} inactive)\n"
        f"- **Stamped:** {p['timestamp']} by `{p['stamped_by']}`"
    )


def list_tier_dirs(filter_arg: str | None) -> list[Path]:
    if not RESULTS_DIR.exists():
        return []
    dirs = sorted([p for p in RESULTS_DIR.iterdir() if p.is_dir()])
    if filter_arg:
        dirs = [d for d in dirs if filter_arg in d.name]
    return dirs


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("filter", nargs="?", default=None, help="Substring match on result dir name")
    parser.add_argument("--list", action="store_true", help="List stamps without writing")
    args = parser.parse_args()

    openmc_version = detect_openmc_version()
    print(f"Detected OpenMC: {openmc_version}\n")

    dirs = list_tier_dirs(args.filter)
    if not dirs:
        print(f"No Tier result directories found under {RESULTS_DIR}", file=sys.stderr)
        return 1

    for d in dirs:
        prov = make_provenance(d, openmc_version)
        if args.list:
            print(f"[{d.name}] OpenMC={prov['openmc_version']} ENDF={prov['endf_release']} "
                  f"n_particles={prov['n_particles']} n_batches={prov['n_batches']}")
            continue
        for j in d.glob("*sweep.json"):
            stamp_json(j, prov)
            print(f"  stamped {j.relative_to(REPO_ROOT)}")
        for m in d.glob("*sweep.md"):
            stamp_markdown(m, prov)
            print(f"  stamped {m.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
