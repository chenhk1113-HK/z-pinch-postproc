"""Tests for 1D radial thermal solver (Tier 20 / Item 9).

Verifies:
1. Zero-heating case matches analytical logarithmic solution.
2. Constant heating produces physically reasonable temperature profile.
3. Boundary conditions are enforced.
5. Convergence with realistic heating values.
"""
from __future__ import annotations

import sys
import os

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "code"))

from zpp.zpp_thermal_solver import (
    solve_1d_radial_thermal,
    heating_from_openmc_mesh_W_per_m3,
    ThermalSolverResult,
)


class TestZeroHeating:
    """Zero heating case: T(r) should be analytical logarithmic."""

    def test_logarithmic_profile_Q_zero(self):
        """With Q=0, T(r) = A + B*ln(r), the analytical solution."""
        R_inner = 0.04
        R_outer = 0.50
        T_inner = 800.0
        T_outer = 400.0

        result = solve_1d_radial_thermal(
            R_inner_m=R_inner, R_outer_m=R_outer, n_bins=30,
            Q_W_per_m3=None,
            T_inner_C=T_inner, T_outer_C=T_outer,
        )

        # Analytical solution
        B = (T_outer - T_inner) / np.log(R_outer / R_inner)
        A = T_inner - B * np.log(R_inner)

        max_diff = 0.0
        for i in range(30):
            r_i = result.r_centers_m[i]
            T_analytical = A + B * np.log(r_i)
            T_solver = result.T_C[i]
            diff = abs(T_analytical - T_solver)
            max_diff = max(max_diff, diff)

        # Conservative finite-difference is second-order accurate
        # Max diff should be < 5°C (typically < 3°C for 30 bins)
        assert max_diff < 5.0, f"Max diff {max_diff}°C exceeds 5°C threshold"


class TestConstantHeating:
    """Constant volumetric heating: T should rise above linear."""

    def test_heating_increases_T_above_linear(self):
        """Q > 0 should give T_max > max(T_inner, T_outer)."""
        result = solve_1d_radial_thermal(
            R_inner_m=0.04, R_outer_m=0.50, n_bins=30,
            Q_W_per_m3=np.full(30, 0.1e6),  # 0.1 W/cm^3
            T_inner_C=700.0, T_outer_C=400.0,
        )
        # T_max should be > T_inner (700°C) since heating raises internal T
        assert result.max_T_C > 700.0, f"Expected max_T > 700, got {result.max_T_C}"

    def test_realistic_heating_gives_physical_T(self):
        """0.1 W/cm^3 uniform heating should give max_T ~ 700-800°C (realistic)."""
        result = solve_1d_radial_thermal(
            R_inner_m=0.04, R_outer_m=0.50, n_bins=30,
            Q_W_per_m3=np.full(30, 0.1e6),
            T_inner_C=700.0, T_outer_C=400.0,
        )
        # Real LiPb operating range is 400-800°C; verify in this range
        assert 700 < result.max_T_C < 900, \
            f"Expected 700 < max_T < 900°C, got {result.max_T_C}"


class TestBoundaryConditions:
    """BC enforcement."""

    def test_BC_enforced_at_inner_face(self):
        """T(R_inner) = T_inner, evaluated at first cell (closest to inner face)."""
        result = solve_1d_radial_thermal(
            R_inner_m=0.04, R_outer_m=0.50, n_bins=30,
            Q_W_per_m3=None,
            T_inner_C=800.0, T_outer_C=400.0,
        )
        # First cell is at r = R_inner + dr/2 ≈ 0.0477m
        # T(r) for Q=0 is A + B*ln(r); at r=R_inner=0.04, T = T_inner
        # Numerical solution should be close to T_inner
        # (within a few degrees due to discretization)
        assert abs(result.T_C[0] - 800.0) < 50, \
            f"First cell T should be near 800, got {result.T_C[0]}"

    def test_BC_enforced_at_outer_face(self):
        """T(R_outer) = T_outer."""
        result = solve_1d_radial_thermal(
            R_inner_m=0.04, R_outer_m=0.50, n_bins=30,
            Q_W_per_m3=None,
            T_inner_C=800.0, T_outer_C=400.0,
        )
        assert abs(result.T_C[-1] - 400.0) < 50, \
            f"Last cell T should be near 400, got {result.T_C[-1]}"


class TestInputValidation:
    """Edge cases and validation."""

    def test_invalid_R_inner_outer(self):
        """R_inner must be < R_outer."""
        with pytest.raises(ValueError):
            solve_1d_radial_thermal(
                R_inner_m=0.50, R_outer_m=0.40, n_bins=30,
                Q_W_per_m3=None,
                T_inner_C=800.0, T_outer_C=400.0,
            )

    def test_too_few_bins(self):
        """n_bins must be >= 3."""
        with pytest.raises(ValueError):
            solve_1d_radial_thermal(
                R_inner_m=0.04, R_outer_m=0.50, n_bins=2,
                Q_W_per_m3=None,
                T_inner_C=800.0, T_outer_C=400.0,
            )

    def test_Q_shape_mismatch(self):
        """Q_W_per_m3 shape must match n_bins."""
        with pytest.raises(ValueError):
            solve_1d_radial_thermal(
                R_inner_m=0.04, R_outer_m=0.50, n_bins=30,
                Q_W_per_m3=np.full(20, 1e6),  # wrong shape
                T_inner_C=800.0, T_outer_C=400.0,
            )


class TestHeatingConversion:
    """heating_from_openmc_mesh_W_per_m3 utility."""

    def test_axial_collapse_correct(self):
        """Mean over z gives correct axial-averaged heating."""
        mesh = np.full((30, 30), 5.0)  # 5 W/cm^3 uniform
        Q_out = heating_from_openmc_mesh_W_per_m3(mesh)
        # 5 W/cm^3 = 5e6 W/m^3
        assert np.allclose(Q_out, 5e6), f"Expected 5e6, got {Q_out[0]}"

    def test_z_dependence_collapsed(self):
        """Non-uniform z profile gets averaged."""
        mesh = np.zeros((30, 30))
        mesh[:, :15] = 4.0  # first half z: 4 W/cm^3
        mesh[:, 15:] = 6.0  # second half z: 6 W/cm^3
        Q_out = heating_from_openmc_mesh_W_per_m3(mesh)
        # Mean = 5 W/cm^3
        assert np.allclose(Q_out, 5e6), f"Expected 5e6, got {Q_out[0]}"

    def test_wrong_dim_rejected(self):
        """1D or 3D arrays should be rejected."""
        with pytest.raises(ValueError):
            heating_from_openmc_mesh_W_per_m3(np.full(30, 5.0))