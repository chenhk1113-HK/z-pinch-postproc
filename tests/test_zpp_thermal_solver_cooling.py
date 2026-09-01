"""Tests for solve_1d_radial_thermal_with_cooling (Tier 22).

Verifies:
1. h=0 reduces to no-cooling behavior.
2. Cooling lowers T_max vs no-cooling.
3. Larger h gives smaller T_max.
4. Higher T_coolant raises T.
5. Input validation.
"""
from __future__ import annotations
import sys
import os
import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "code"))

from zpp.zpp_thermal_solver import (
    solve_1d_radial_thermal,
    solve_1d_radial_thermal_with_cooling,
)


class TestCoolingBackwardCompat:
    """h=0 should match no-cooling."""

    def test_h_zero_matches_no_cooling(self):
        """With h=0, the cooling solver should give the same T as the no-cooling solver."""
        Q = np.full(30, 5e6)  # 5 W/cm^3
        r_no = solve_1d_radial_thermal(0.04, 0.50, 30, Q, 600.0, 400.0)
        r_cool = solve_1d_radial_thermal_with_cooling(
            0.04, 0.50, 30, Q, 600.0, 400.0, h_W_per_m2K=0.0,
        )
        assert abs(r_no.max_T_C - r_cool.max_T_C) < 1e-6


class TestCoolingLowersT:
    """Active cooling should lower peak temperature."""

    def test_cooling_lowers_T_max(self):
        """h=10000 should give lower T_max than no cooling."""
        Q = np.full(30, 5e6)
        r_no = solve_1d_radial_thermal(0.04, 0.50, 30, Q, 600.0, 400.0)
        r_cool = solve_1d_radial_thermal_with_cooling(
            0.04, 0.50, 30, Q, 600.0, 400.0,
            h_W_per_m2K=10000.0, T_coolant_C=400.0,
        )
        assert r_cool.max_T_C < r_no.max_T_C
        # With strong cooling, T_max should be physically reasonable (< 700 C)
        assert r_cool.max_T_C < 700.0, f"Expected T_max < 700C with cooling, got {r_cool.max_T_C}"

    def test_larger_h_gives_lower_T(self):
        """Higher h means more heat extraction -> lower T."""
        Q = np.full(30, 5e6)
        r_h5k = solve_1d_radial_thermal_with_cooling(
            0.04, 0.50, 30, Q, 600.0, 400.0,
            h_W_per_m2K=5000.0, T_coolant_C=400.0,
        )
        r_h10k = solve_1d_radial_thermal_with_cooling(
            0.04, 0.50, 30, Q, 600.0, 400.0,
            h_W_per_m2K=10000.0, T_coolant_C=400.0,
        )
        assert r_h10k.max_T_C < r_h5k.max_T_C

    def test_higher_T_coolant_raises_T(self):
        """Higher coolant T -> less heat extraction -> higher breeder T."""
        Q = np.full(30, 5e6)
        r_cool_400 = solve_1d_radial_thermal_with_cooling(
            0.04, 0.50, 30, Q, 600.0, 400.0,
            h_W_per_m2K=10000.0, T_coolant_C=400.0,
        )
        r_cool_500 = solve_1d_radial_thermal_with_cooling(
            0.04, 0.50, 30, Q, 600.0, 400.0,
            h_W_per_m2K=10000.0, T_coolant_C=500.0,
        )
        assert r_cool_500.max_T_C > r_cool_400.max_T_C


class TestCoolingInputValidation:
    """Input edge cases."""

    def test_negative_h_rejected(self):
        """h_W_per_m2K must be non-negative."""
        with pytest.raises(ValueError):
            solve_1d_radial_thermal_with_cooling(
                0.04, 0.50, 30, np.full(30, 1e6),
                600.0, 400.0, h_W_per_m2K=-100.0,
            )

    def test_invalid_geometry(self):
        """R_inner must be < R_outer."""
        with pytest.raises(ValueError):
            solve_1d_radial_thermal_with_cooling(
                0.50, 0.40, 30, np.full(30, 1e6),
                600.0, 400.0,
            )

    def test_too_few_bins(self):
        """n_bins must be >= 3."""
        with pytest.raises(ValueError):
            solve_1d_radial_thermal_with_cooling(
                0.04, 0.50, 2, np.full(2, 1e6),
                600.0, 400.0,
            )


class TestCoolingPhysics:
    """Physical consistency checks."""

    def test_equilibrium_T_with_cooling(self):
        """For uniform Q with cooling, T_max ~ T_c + Q/h_eff (where h_eff is the
        effective volumetric HTC after packing_fraction)."""
        Q = np.full(30, 1e6)  # 1 W/cm^3 (low for clean test)
        h = 10000.0
        delta = 0.005
        pack = 0.1
        h_eff = h / delta * pack  # 2e5 W/m^3/K
        T_c = 400.0
        T_expected = T_c + Q.mean() / h_eff  # 400 + 5 = 405 C

        r = solve_1d_radial_thermal_with_cooling(
            0.04, 0.50, 30, Q, T_c, T_c,  # T_inner=T_c for cleanest case
            h_W_per_m2K=h, T_coolant_C=T_c, delta_wall_m=delta,
        )
        # Allow some conduction correction; should be close to T_expected
        assert abs(r.max_T_C - T_expected) < 50, \
            f"Expected T_max ~{T_expected}C, got {r.max_T_C}"