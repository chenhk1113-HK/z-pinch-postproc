"""
CSV / JSON I/O for zpp_pipeline.

Supported input formats:
- CSV with columns: time_ns, ion_temp_keV, fuel_density_gcc [, radius_cm, rho_R_gccm]
- JSON with same fields as keys (arrays).

Output: always JSON, conforming to PLAN_v0.1.md §5.3 schema.
"""
from __future__ import annotations
import json
import csv
from pathlib import Path
from typing import Any
import numpy as np


def read_profile(path: str | Path) -> dict:
    """Read a 1D profile CSV or JSON.

    Returns
    -------
    dict with keys: time_ns, T_keV, rho_gcc, radius_cm (optional)
    All values are np.ndarray.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"profile file not found: {p}")
    if p.suffix.lower() == ".csv":
        return _read_csv(p)
    if p.suffix.lower() == ".json":
        return _read_json(p)
    raise ValueError(f"unsupported profile format: {p.suffix} (need .csv or .json)")


def _read_csv(p: Path) -> dict:
    with p.open("r", newline="") as f:
        reader = csv.DictReader(f)
        cols = {k: [] for k in (reader.fieldnames or [])}
        for row in reader:
            for k, v in row.items():
                cols[k].append(float(v))
    out: dict[str, np.ndarray] = {}
    # Required
    out["time_ns"] = np.array(cols.get("time_ns", cols.get("t_ns", [])), dtype=float)
    out["T_keV"] = np.array(
        cols.get("ion_temp_keV", cols.get("T_keV", cols.get("T", []))), dtype=float
    )
    out["rho_gcc"] = np.array(
        cols.get("fuel_density_gcc", cols.get("rho_gcc", cols.get("rho", []))),
        dtype=float,
    )
    # Optional
    if "radius_cm" in cols and len(cols["radius_cm"]) > 0:
        out["radius_cm"] = np.array(cols["radius_cm"], dtype=float)
    if "rho_R_gccm" in cols and len(cols["rho_R_gccm"]) > 0:
        out["rho_R_gccm"] = np.array(cols["rho_R_gccm"], dtype=float)
    return out


def _read_json(p: Path) -> dict:
    with p.open("r") as f:
        d = json.load(f)
    out: dict[str, np.ndarray] = {
        "time_ns": np.array(d["time_ns"], dtype=float),
        "T_keV": np.array(d["T_keV"], dtype=float),
        "rho_gcc": np.array(d["rho_gcc"], dtype=float),
    }
    if "radius_cm" in d and d["radius_cm"] is not None:
        out["radius_cm"] = np.array(d["radius_cm"], dtype=float)
    if "rho_R_gccm" in d and d["rho_R_gccm"] is not None:
        out["rho_R_gccm"] = np.array(d["rho_R_gccm"], dtype=float)
    return out


def write_report(report: dict, path: str | Path) -> None:
    """Write the engineering-metric report to a JSON file.

    Creates parent dirs if needed.
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w") as f:
        json.dump(report, f, indent=2, default=_json_default)
    return None


def _json_default(o: Any):
    """JSON serialiser fallback for numpy scalars / arrays."""
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    raise TypeError(f"not JSON serialisable: {type(o)}")
