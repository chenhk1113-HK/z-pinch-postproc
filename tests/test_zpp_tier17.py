"""Tier 17 (2026-08-31) — tests for Z-FFR spherical geometry.

Builds a 1D spherical geometry for the Z-FFR design from Peng 2014,
following the published design parameters.

Tests that:
  1. _build_zffr_spherical_geometry creates a valid spherical geometry
     with the right layers (Be, LiPb, U-238, Fe, RAFM).
  2. The 'blanket' cell (used by _build_tally) maps to LiPb.
  3. include_fe=False and include_u238=False work as expected.
  4. Out-of-range parameters raise ValueError.
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "code"))


class TestTier17ZFFRGeometry:
    """Tier 17 — _build_zffr_spherical_geometry."""

    def test_default_geometry_loads(self):
        """Default Peng 2014 parameters should build without error."""
        from zpp.zpp_zffr_spherical import _build_zffr_spherical_geometry
        from zpp.zpp_real_openmc_transport import _build_blanket_materials
        materials = _build_blanket_materials(Li6_enrichment_fraction=0.90)
        geom, cells, surfaces = _build_zffr_spherical_geometry(materials)
        # Should have plasma, be_mult, blanket, u238, fe_reflector, structure
        assert "plasma" in cells
        assert "be_mult" in cells
        assert "blanket" in cells
        assert "u238" in cells
        assert "fe_reflector" in cells
        assert "structure" in cells
        # All radii are spheres
        assert "r_be" in surfaces
        assert "r_blanket" in surfaces
        assert "r_u238" in surfaces
        assert "r_fe" in surfaces
        assert "r_struct" in surfaces

    def test_blanket_cell_is_lipb(self):
        """The 'blanket' cell (used by tally) should be filled with LiPb."""
        from zpp.zpp_zffr_spherical import _build_zffr_spherical_geometry
        from zpp.zpp_real_openmc_transport import _build_blanket_materials
        materials = _build_blanket_materials(Li6_enrichment_fraction=0.90)
        geom, cells, surfaces = _build_zffr_spherical_geometry(materials)
        assert cells["blanket"].fill is not None
        assert cells["blanket"].fill.name == "LiPb"

    def test_no_u238(self):
        """include_u238=False should remove the u238 cell."""
        from zpp.zpp_zffr_spherical import _build_zffr_spherical_geometry
        from zpp.zpp_real_openmc_transport import _build_blanket_materials
        materials = _build_blanket_materials(Li6_enrichment_fraction=0.90)
        geom, cells, surfaces = _build_zffr_spherical_geometry(
            materials, include_u238=False,
        )
        assert "u238" not in cells
        assert "r_u238" not in surfaces
        # LiPb blanket now extends to Fe (or structure)
        assert "fe_reflector" in cells

    def test_no_fe(self):
        """include_fe=False should remove the fe_reflector cell."""
        from zpp.zpp_zffr_spherical import _build_zffr_spherical_geometry
        from zpp.zpp_real_openmc_transport import _build_blanket_materials
        materials = _build_blanket_materials(Li6_enrichment_fraction=0.90)
        geom, cells, surfaces = _build_zffr_spherical_geometry(
            materials, include_fe=False,
        )
        assert "fe_reflector" not in cells
        assert "r_fe" not in surfaces

    def test_neither_u238_nor_fe(self):
        """Both include_u238=False and include_fe=False should leave
        only Be/LiPb/RAFM cells."""
        from zpp.zpp_zffr_spherical import _build_zffr_spherical_geometry
        from zpp.zpp_real_openmc_transport import _build_blanket_materials
        materials = _build_blanket_materials(Li6_enrichment_fraction=0.90)
        geom, cells, surfaces = _build_zffr_spherical_geometry(
            materials, include_u238=False, include_fe=False,
        )
        assert set(cells.keys()) == {
            "plasma", "be_mult", "blanket", "structure",
        }

    def test_invalid_R_blanket_raises(self):
        """R_blanket_cm <= R_be_cm should raise."""
        from zpp.zpp_zffr_spherical import _build_zffr_spherical_geometry
        from zpp.zpp_real_openmc_transport import _build_blanket_materials
        materials = _build_blanket_materials()
        with pytest.raises(ValueError, match="R_be"):
            _build_zffr_spherical_geometry(
                materials, R_be_cm=10.0, R_blanket_cm=5.0,
            )

    def test_invalid_R_u238_raises(self):
        """R_u238_cm out of range should raise."""
        from zpp.zpp_zffr_spherical import _build_zffr_spherical_geometry
        from zpp.zpp_real_openmc_transport import _build_blanket_materials
        materials = _build_blanket_materials()
        with pytest.raises(ValueError, match="R_u238_cm"):
            _build_zffr_spherical_geometry(
                materials, R_u238_cm=100.0,  # > R_structure_cm=85
            )

    def test_invalid_R_fe_raises(self):
        """R_fe_cm out of range should raise."""
        from zpp.zpp_zffr_spherical import _build_zffr_spherical_geometry
        from zpp.zpp_real_openmc_transport import _build_blanket_materials
        materials = _build_blanket_materials()
        with pytest.raises(ValueError, match="R_fe_cm"):
            _build_zffr_spherical_geometry(
                materials, R_fe_cm=10.0,  # < R_u238_cm=65
            )


class TestTier17BackwardCompat:
    """Tier 17 — does not break Tier 13/14/15/16."""

    def test_cylindrical_geometry_unaffected(self):
        """_build_zpinch_geometry should still work as in v1.3.0."""
        from zpp.zpp_real_openmc_transport import (
            _build_blanket_materials, _build_zpinch_geometry,
        )
        mats = _build_blanket_materials()
        # Cylindrical Z-pinch with Fe reflector (Tier 13 default)
        geom, cells, _ = _build_zpinch_geometry(
            mats, R_plasma_cm=4.0, R_blanket_cm=80.0,
            R_be_cm=82.0, R_structure_cm=85.0,
            mult_inside=True,
            R_fe_cm=84.0,
        )
        assert "fe_reflector" in cells
        assert "u238" not in cells  # Tier 17 not used here
