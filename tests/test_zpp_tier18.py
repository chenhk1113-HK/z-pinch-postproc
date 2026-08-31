"""Tier 18 (2026-08-31) — tests for Li4SiO4 ceramic breeder material.

Tests verify the Li4SiO4 material is constructed with correct atomic
densities and composition. Cross-section availability tests are
separate (Tier 18.B will gate on Si/O cross sections being available).

Tests:
  1. Li4SiO4 material is created with correct name.
  2. Atomic densities sum to total atom density (4 Li + 1 Si + 4 O per molecule).
  3. Li-6 enrichment propagates correctly.
  4. Theoretical density matches literature (2.40 g/cm3).
  5. Material uses Si-28/29/30 and O-16 nuclides.
  6. Backward compat: LiPb still works.
"""
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "code"))


def _nuclide_dict(material):
    """Convert openmc Material.nuclides list to {name: percent} dict.

    openmc.Material.nuclides returns a list of NuclideTuple objects.
    Each NuclideTuple has .name and .percent (atom density in at/cm3).
    """
    return {n.name: n.percent for n in material.nuclides}


class TestTier18Li4SiO4:
    """Tier 18 — Li4SiO4 ceramic breeder material."""

    def test_material_creates_with_correct_name(self):
        """build_li4sio4_material() returns openmc.Material named 'Li4SiO4'."""
        from zpp.zpp_li4sio4 import build_li4sio4_material
        m = build_li4sio4_material()
        assert m.name == "Li4SiO4"

    def test_atomic_density_conservation(self):
        """Sum of nuclide densities = total atom density (4+1+4 per molecule)."""
        from zpp.zpp_li4sio4 import build_li4sio4_material
        m = build_li4sio4_material(Li6_enrichment_fraction=0.5)
        densities = _nuclide_dict(m)
        total = sum(densities.values())
        # Total atoms per cm3 should match: rho * N_A * 9 / M
        # rho = 2.40 g/cm3, N_A = 6.022e23, M = 119.84 g/mol
        # Total atoms = 2.40 * 6.022e23 * 9 / 119.84 = ~1.085e23 atoms/cm3
        assert 0.9e23 < total < 1.2e23

    def test_li6_enrichment_propagates(self):
        """Li-6 enrichment fraction should be in Li6/Li7 ratio."""
        from zpp.zpp_li4sio4 import build_li4sio4_material
        m_50 = build_li4sio4_material(Li6_enrichment_fraction=0.50)
        m_90 = build_li4sio4_material(Li6_enrichment_fraction=0.90)

        d_50 = _nuclide_dict(m_50)
        d_90 = _nuclide_dict(m_90)

        li6_50 = d_50.get("Li6", 0)
        li7_50 = d_50.get("Li7", 0)
        li6_90 = d_90.get("Li6", 0)
        li7_90 = d_90.get("Li7", 0)

        # Ratio of Li6/(Li6+Li7) should equal enrichment fraction
        if li6_50 + li7_50 > 0:
            ratio_50 = li6_50 / (li6_50 + li7_50)
            assert abs(ratio_50 - 0.50) < 0.01
        if li6_90 + li7_90 > 0:
            ratio_90 = li6_90 / (li6_90 + li7_90)
            assert abs(ratio_90 - 0.90) < 0.01

    def test_density_matches_literature(self):
        """Theoretical density should be 2.40 g/cm3 (Li4SiO4 literature)."""
        from zpp.zpp_li4sio4 import build_li4sio4_material, LI4SIO4_MOLAR_MASS
        m = build_li4sio4_material()
        rho = 2.40
        # Check by summing atom densities and comparing to expected
        total_atoms_per_cm3 = rho * 6.022e23 * 9 / LI4SIO4_MOLAR_MASS
        densities = _nuclide_dict(m)
        total = sum(densities.values())
        assert abs(total - total_atoms_per_cm3) / total_atoms_per_cm3 < 0.01

    def test_uses_si_and_o_nuclides(self):
        """Material must include Si-28/29/30 and O-16 nuclides."""
        from zpp.zpp_li4sio4 import build_li4sio4_material
        m = build_li4sio4_material()
        nuclides = set(_nuclide_dict(m).keys())
        assert "Si28" in nuclides
        assert "Si29" in nuclides
        assert "Si30" in nuclides
        assert "O16" in nuclides
        assert "Li6" in nuclides
        assert "Li7" in nuclides


class TestTier18BackwardCompat:
    """Tier 18 — does not break Tier 6-17 (LiPb still works)."""

    def test_lipb_still_works(self):
        """Existing LiPb material definition should still work."""
        from zpp.zpp_real_openmc_transport import _build_blanket_materials
        mats = _build_blanket_materials(Li6_enrichment_fraction=0.90)
        assert "lipb" in mats
        assert mats["lipb"].name == "LiPb"

class TestTier18BackwardCompatToB:
    """Tier 18.B — Tier 18.A material still works after Tier 18.B sweep."""

    def test_li4sio4_material_not_modified_by_b_sweep(self):
        """Tier 18.B sweep must not modify the Tier 18.A material definition."""
        from zpp.zpp_li4sio4 import build_li4sio4_material, LI4SIO4_MOLAR_MASS
        m = build_li4sio4_material(Li6_enrichment_fraction=0.90)
        # Same properties as Tier 18.A test_density_matches_literature
        rho = 2.40
        total_atoms = rho * 6.022e23 * 9 / LI4SIO4_MOLAR_MASS
        total = sum(n.percent for n in m.nuclides)
        assert abs(total - total_atoms) / total_atoms < 0.01
