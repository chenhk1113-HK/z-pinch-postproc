"""
Tests for the burn-weighted Lawson triple product.
"""
import sys
from pathlib import Path

import numpy as np
import pytest

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent / "code"))

from zpp.zpp_lawson import burn_weighted_lawson, lawson_criterion_classic_DT


def test_lawson_constant_profile():
    """Constant T=10 keV, rho=1 g/cc, 10 ns burn -> analytic check."""
    t = np.linspace(0, 10, 11)
    T = np.full_like(t, 10.0)
    rho = np.full_like(t, 1.0)
    r = burn_weighted_lawson(T, rho, t)
    # n = 1 * 6.022e23 / 2.5 = 2.409e23 atoms/cm^3
    # nT = 2.409e24 atoms/cm^3 * keV
    # Integral over 10 ns = 10e-9 s:
    # nT_tau (atoms/cm^3 * keV * s) = 2.409e24 * 10e-9 = 2.409e16
    # nT_tau (m^-3 * keV * s) = 2.409e16 * 1e6 = 2.409e22
    assert abs(r["lawson_nTtau_atoms_cm3_keV_s"] - 2.409e16) < 1e14
    assert abs(r["lawson_nTtau_keVs_per_m3"] - 2.409e22) < 1e20
    assert r["tau_burn_ns"] == pytest.approx(10.0)
    assert r["n_samples_in_burn"] == 11
    assert r["T_peak_keV"] == 10.0
    assert r["rho_peak_gcc"] == 1.0


def test_lawson_zero_burn_window():
    """All T below threshold -> zero Lawson."""
    t = np.linspace(0, 5, 6)
    T = np.full_like(t, 0.5)  # below 1 keV threshold
    rho = np.full_like(t, 1.0)
    r = burn_weighted_lawson(T, rho, t)
    assert r["lawson_nTtau_keVs_per_m3"] == 0.0
    assert r["lawson_nTtau_atoms_cm3_keV_s"] == 0.0
    assert r["n_samples_in_burn"] == 0


def test_lawson_partial_burn():
    """First half below threshold, second half above."""
    t = np.linspace(0, 10, 11)
    T = np.where(t < 5, 0.5, 5.0)  # 0-5 ns: 0.5 keV, 5-10 ns: 5 keV
    rho = np.full_like(t, 1.0)
    r = burn_weighted_lawson(T, rho, t)
    # Only samples with t >= 5 are in burn: t = 5, 6, 7, 8, 9, 10 (6 samples)
    assert r["n_samples_in_burn"] == 6
    assert r["tau_burn_ns"] == pytest.approx(5.0)


def test_classification_thresholds():
    """Verify the 3-tier classification."""
    assert lawson_criterion_classic_DT(2.0e21) == "ignition-class"  # >= 0.5 * 3e21
    assert lawson_criterion_classic_DT(0.5e21) == "break-even"      # 0.05 - 0.5
    assert lawson_criterion_classic_DT(1.0e20) == "below-break-even"
