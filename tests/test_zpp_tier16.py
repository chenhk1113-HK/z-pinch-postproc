"""Tier 16 (2026-08-31) — tests for U-238 fission blanket support.

Tests that:
  1. U-238 material exists with correct composition.
  2. _build_zpinch_geometry accepts R_u238_cm parameter and creates
     a u238 cell between Be/blanket and Fe/structure.
  3. R_u238_cm=None (default) gives same geometry as Tier 13.
  4. R_u238_cm out of range raises ValueError.
  5. R_u238_cm + R_fe_cm together work in the right order:
     breeder -> U-238 -> Fe -> structure.
  6. run_real_openmc_tbr accepts R_u238_cm parameter.
  7. _build_tally includes U-238 in nuclide list when u238 cell present.
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "code"))


class TestTier16UMaterial:
    """Tier 16 — U-238 material."""

    def test_u238_in_materials(self):
        """_build_blanket_materials should include 'u238' key."""
        from zpp.zpp_real_openmc_transport import _build_blanket_materials
        mats = _build_blanket_materials(Li6_enrichment_fraction=0.90)
        assert "u238" in mats
        # Verify backward compat
        for k in ("lipb", "be", "rafm", "li6", "li7", "fe_reflector"):
            assert k in mats, f"Missing backward-compat key: {k}"

    def test_u238_density(self):
        """U-238 density should be 19.1 g/cm3 (depleted uranium)."""
        from zpp.zpp_real_openmc_transport import _build_blanket_materials
        mats = _build_blanket_materials()
        u = mats["u238"]
        assert abs(u.density - 19.1) < 0.01


class TestTier16Geometry:
    """Tier 16 — _build_zpinch_geometry with R_u238_cm."""

    def test_no_u238_backward_compat(self):
        """R_u238_cm=None (default) should give same cells as Tier 13
        (no u238 cell, no r_u238 surface)."""
        from zpp.zpp_real_openmc_transport import (
            _build_blanket_materials, _build_zpinch_geometry,
        )
        mats = _build_blanket_materials()
        geom, cells, surfaces = _build_zpinch_geometry(
            mats, R_plasma_cm=4.0, R_blanket_cm=80.0,
            R_be_cm=82.0, R_structure_cm=85.0,
            mult_inside=True,
        )
        assert "u238" not in cells
        assert "r_u238" not in surfaces

    def test_with_u238_mult_inside(self):
        """R_u238_cm set + mult_inside=True should add u238 cell
        between blanket and structure (no Fe)."""
        from zpp.zpp_real_openmc_transport import (
            _build_blanket_materials, _build_zpinch_geometry,
        )
        mats = _build_blanket_materials()
        geom, cells, surfaces = _build_zpinch_geometry(
            mats, R_plasma_cm=4.0, R_blanket_cm=80.0,
            R_be_cm=82.0, R_structure_cm=92.0,
            mult_inside=True,
            R_u238_cm=89.0,
        )
        assert "u238" in cells
        assert "r_u238" in surfaces
        # Order: plasma, be_mult, blanket, u238, structure
        assert set(cells.keys()) == {
            "plasma", "be_mult", "blanket", "u238", "structure"
        }

    def test_with_u238_mult_outside(self):
        """R_u238_cm set + mult_inside=False should add u238 cell
        between Be and structure."""
        from zpp.zpp_real_openmc_transport import (
            _build_blanket_materials, _build_zpinch_geometry,
        )
        mats = _build_blanket_materials()
        geom, cells, surfaces = _build_zpinch_geometry(
            mats, R_plasma_cm=4.0, R_blanket_cm=50.0,
            R_be_cm=52.0, R_structure_cm=62.0,
            mult_inside=False,
            R_u238_cm=57.0,
        )
        assert "u238" in cells
        assert set(cells.keys()) == {
            "plasma", "blanket", "be_mult", "u238", "structure"
        }

    def test_u238_and_fe_combined(self):
        """R_u238_cm + R_fe_cm should give correct order:
        breeder -> U-238 -> Fe -> structure."""
        from zpp.zpp_real_openmc_transport import (
            _build_blanket_materials, _build_zpinch_geometry,
        )
        mats = _build_blanket_materials()
        geom, cells, surfaces = _build_zpinch_geometry(
            mats, R_plasma_cm=4.0, R_blanket_cm=50.0,
            R_be_cm=52.0, R_structure_cm=65.0,
            mult_inside=True,
            R_u238_cm=58.0,
            R_fe_cm=62.0,
        )
        # Order: plasma, be_mult, blanket, u238, fe_reflector, structure
        assert set(cells.keys()) == {
            "plasma", "be_mult", "blanket", "u238",
            "fe_reflector", "structure",
        }
        assert "r_u238" in surfaces
        assert "r_fe" in surfaces
        # Verify U-238 fill
        assert cells["u238"].fill is not None
        assert cells["u238"].fill.name == "U238"

    def test_u238_out_of_range_raises(self):
        """R_u238_cm outside [R_be/R_blanket, R_structure/R_fe] should raise."""
        from zpp.zpp_real_openmc_transport import (
            _build_blanket_materials, _build_zpinch_geometry,
        )
        mats = _build_blanket_materials()
        # mult_inside=False: R_u238 must be in (R_be, R_structure) = (52, 62)
        with pytest.raises(ValueError, match="R_u238_cm"):
            _build_zpinch_geometry(
                mats, R_blanket_cm=50.0, R_be_cm=52.0,
                R_structure_cm=62.0,
                mult_inside=False,
                R_u238_cm=50.0,  # < R_be
            )
        with pytest.raises(ValueError, match="R_u238_cm"):
            _build_zpinch_geometry(
                mats, R_blanket_cm=50.0, R_be_cm=52.0,
                R_structure_cm=62.0,
                mult_inside=False,
                R_u238_cm=70.0,  # > R_structure
            )


class TestTier16RunRealOpenMCTBR:
    """Tier 16 — run_real_openmc_tbr accepts R_u238_cm."""

    def test_R_u238_cm_parameter_exists(self):
        """run_real_openmc_tbr should accept R_u238_cm parameter."""
        import inspect
        from zpp.zpp_real_openmc_transport import run_real_openmc_tbr
        sig = inspect.signature(run_real_openmc_tbr)
        assert "R_u238_cm" in sig.parameters
        # Default should be None (backward compat)
        assert sig.parameters["R_u238_cm"].default is None


class TestTier16Tally:
    """Tier 16 — _build_tally includes U-238 when present."""

    def test_tally_without_u238(self):
        """_build_tally without u238 cell should NOT include U238."""
        from zpp.zpp_real_openmc_transport import (
            _build_blanket_materials, _build_zpinch_geometry, _build_tally,
        )
        mats = _build_blanket_materials()
        geom, cells, surfaces = _build_zpinch_geometry(
            mats, R_blanket_cm=80.0, R_be_cm=82.0, R_structure_cm=85.0,
            mult_inside=True,
        )
        settings, tallies = _build_tally(geom, surfaces)
        # The tally should have Li6, Li7, Be9 but NOT U238
        for tally in tallies:
            assert "U238" not in tally.nuclides

    def test_tally_with_u238(self):
        """_build_tally WITH u238 cell should include U238 in nuclides."""
        from zpp.zpp_real_openmc_transport import (
            _build_blanket_materials, _build_zpinch_geometry, _build_tally,
        )
        mats = _build_blanket_materials()
        geom, cells, surfaces = _build_zpinch_geometry(
            mats, R_blanket_cm=80.0, R_be_cm=82.0, R_structure_cm=92.0,
            mult_inside=True,
            R_u238_cm=89.0,
        )
        settings, tallies = _build_tally(geom, surfaces)
        for tally in tallies:
            assert "U238" in tally.nuclides


class TestTier16BackwardCompat:
    """Tier 16 — backward compat with v1.3.0 (no U-238)."""

    def test_no_u238_same_cells_as_v1_3(self):
        """Without R_u238_cm, cells dict should match v1.3.0 exactly."""
        from zpp.zpp_real_openmc_transport import (
            _build_blanket_materials, _build_zpinch_geometry,
        )
        mats = _build_blanket_materials()
        # No R_u238, no R_fe
        geom, cells, _ = _build_zpinch_geometry(
            mats, R_plasma_cm=4.0, R_blanket_cm=80.0,
            R_be_cm=82.0, R_structure_cm=85.0,
            mult_inside=True,
        )
        assert set(cells.keys()) == {
            "plasma", "be_mult", "blanket", "structure"
        }
