"""
Tests for the CSV / JSON I/O layer.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pytest

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent / "code"))

from zpp.zpp_io import read_profile, write_report


def test_read_csv_basic(tmp_path):
    p = tmp_path / "test.csv"
    p.write_text(
        "time_ns,ion_temp_keV,fuel_density_gcc,radius_cm\n"
        "0.0,1.0,0.5,0.5\n"
        "1.0,2.0,1.0,0.3\n"
        "2.0,3.0,2.0,0.1\n"
    )
    prof = read_profile(p)
    assert "time_ns" in prof
    assert "T_keV" in prof
    assert "rho_gcc" in prof
    assert "radius_cm" in prof
    assert len(prof["time_ns"]) == 3
    assert prof["T_keV"][1] == 2.0
    assert prof["rho_gcc"][2] == 2.0
    assert prof["radius_cm"][2] == 0.1


def test_read_csv_alternate_column_names(tmp_path):
    """Accept T_keV / T / ion_temp_keV as synonyms."""
    p = tmp_path / "test.csv"
    p.write_text(
        "time_ns,T,rho\n0.0,1.0,0.5\n1.0,2.0,1.0\n"
    )
    prof = read_profile(p)
    assert "T_keV" in prof
    assert "rho_gcc" in prof
    assert prof["T_keV"][0] == 1.0
    assert prof["rho_gcc"][1] == 1.0


def test_read_json_basic(tmp_path):
    p = tmp_path / "test.json"
    p.write_text(json.dumps({
        "time_ns": [0.0, 1.0, 2.0],
        "T_keV": [1.0, 2.0, 3.0],
        "rho_gcc": [0.5, 1.0, 2.0],
        "radius_cm": [0.5, 0.3, 0.1],
    }))
    prof = read_profile(p)
    assert len(prof["time_ns"]) == 3
    assert prof["T_keV"][2] == 3.0
    assert "radius_cm" in prof


def test_write_report_creates_parent_dirs(tmp_path):
    out = tmp_path / "nested" / "subdir" / "report.json"
    report = {
        "input_provenance": {"shot_id": "test"},
        "results": {"E_fusion_J": 1.23e5, "Q_eng": 0.01},
        "derived": {},
    }
    write_report(report, out)
    assert out.exists()
    d = json.loads(out.read_text())
    assert d["results"]["E_fusion_J"] == 1.23e5
