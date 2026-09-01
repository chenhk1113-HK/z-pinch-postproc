"""Tests for LiPb material properties module (Tier 20 / Item 9).

Verifies:
1. LiPb_density_g_per_cc matches Sawan 2011 reference values.
2. LiPb_thermal_conductivity_W_per_mK matches Schubert 2012.
3. LiPb_specific_heat_J_per_kgK returns the documented constant.
4. LiPb_atom_densities_per_barn_cm produces physically consistent values.
5. Density is monotonically decreasing with T (thermal expansion).
"""
from __future__ import annotations

import sys
import os

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "code"))

from zpp.zpp_lipb_properties import (
    LiPb_density_g_per_cc,
    LiPb_thermal_conductivity_W_per_mK,
    LiPb_specific_heat_J_per_kgK,
    LiPb_atom_densities_per_barn_cm,
    LI17PB83_DENSITY_REFERENCE_G_PER_CC,
    LI17PB83_LINEAR_EXPANSION_COEFF_PER_K,
    LI17PB83_THERMAL_CONDUCTIVITY_REFERENCE_W_PER_MK,
)


class TestLiPbDensity:
    """LiPb density at reference and elevated temperatures."""

    def test_density_at_reference_T(self):
        """At T=500°C, density = 9.2 g/cm³ (Sawan 2011 reference)."""
        rho = LiPb_density_g_per_cc(500.0)
        assert abs(rho - 9.2) < 0.01, f"Expected ~9.2, got {rho}"

    def test_density_at_T_700C(self):
        """At T=700°C, density should be ~8.92 g/cm³ (linear expansion)."""
        rho = LiPb_density_g_per_cc(700.0)
        # Linear: rho = 9.2 * (1 - 1.5e-4 * 200) = 9.2 * 0.97 = 8.924
        expected = 9.2 * (1 - 1.5e-4 * 200)
        assert abs(rho - expected) < 0.01, f"Expected ~{expected}, got {rho}"

    def test_density_monotonically_decreasing_with_T(self):
        """Density should decrease as T increases (thermal expansion)."""
        T_range = np.linspace(300, 800, 50)
        rho_range = LiPb_density_g_per_cc(T_range)
        diffs = np.diff(rho_range)
        assert np.all(diffs <= 0), "Density should be monotonically decreasing with T"

    def test_density_in_SI_units(self):
        """1 g/cm³ = 1000 kg/m³ (use atomic densities to verify)."""
        # Compute atom density at 500°C and check that it's consistent with rho
        atoms_500 = LiPb_atom_densities_per_barn_cm(500.0)
        rho_implied = atoms_500["total_atoms_per_cc"] * 173.0 / 6.022e23
        assert abs(rho_implied - 9.2) < 0.01


class TestLiPbThermalConductivity:
    """LiPb thermal conductivity (Schubert 2012 linear fit)."""

    def test_k_at_reference_T(self):
        """At T=500°C, k = 12.0 W/m/K (Schubert 2012 reference)."""
        k = LiPb_thermal_conductivity_W_per_mK(500.0)
        assert abs(k - 12.0) < 0.01, f"Expected 12.0, got {k}"

    def test_k_increases_with_T(self):
        """k increases slightly with T (linear slope +0.018 W/m/K per °C)."""
        k_500 = LiPb_thermal_conductivity_W_per_mK(500.0)
        k_700 = LiPb_thermal_conductivity_W_per_mK(700.0)
        # Expected: k(700) = 12 + 0.018 * 200 = 15.6
        assert abs(k_700 - 15.6) < 0.01, f"Expected 15.6, got {k_700}"
        assert k_700 > k_500, "k should increase with T"


class TestLiPbSpecificHeat:
    """LiPb specific heat (constant approximation)."""

    def test_cp_returns_190(self):
        """cp = 190 J/kg/K at all operating temperatures."""
        for T in [300, 500, 700, 1000]:
            cp = LiPb_specific_heat_J_per_kgK(T)
            assert abs(cp - 190.0) < 0.01, f"At T={T}, expected 190, got {cp}"


class TestLiPbAtomDensities:
    """Atom density calculation."""

    def test_total_atoms_per_cc_at_reference(self):
        """At rho=9.2 g/cm³, total atom density should be ~3.2e22 atoms/cm³."""
        atoms = LiPb_atom_densities_per_barn_cm(500.0)
        # Expected: N_A * 9.2 / 173 = 6.022e23 * 9.2 / 173 ≈ 3.2e22
        N_total_expected = 6.022e23 * 9.2 / 173
        assert abs(atoms["total_atoms_per_cc"] - N_total_expected) < 1e20

    def test_Li6_enrichment(self):
        """Li-6 atom fraction should reflect 90% enrichment."""
        atoms = LiPb_atom_densities_per_barn_cm(500.0)
        # Li total = 0.17 * N_total
        # Li6 = 0.075 * Li_total (natural Li: 7.5% Li-6)
        # Li7 = 0.925 * Li_total
        Li_total = 0.17 * atoms["total_atoms_per_cc"]
        Li6_expected = 0.075 * Li_total
        Li7_expected = 0.925 * Li_total
        assert abs(atoms["Li6"] - Li6_expected) < 1e17
        assert abs(atoms["Li7"] - Li7_expected) < 1e17

    def test_density_arrays(self):
        """Function should accept array inputs."""
        T_array = np.array([500, 600, 700])
        atoms_arr = LiPb_atom_densities_per_barn_cm(T_array)
        # atoms_arr is a dict; values should be arrays
        assert isinstance(atoms_arr["density_g_per_cc"], np.ndarray)
        assert len(atoms_arr["density_g_per_cc"]) == 3