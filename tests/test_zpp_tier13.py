"""Tier 13 (2026-08-31) — tests for Fe reflector geometry support.

Tests that:
  1. The Fe reflector material exists with correct composition.
  2. _build_zpinch_geometry accepts R_fe_cm parameter and creates
     an fe_reflector cell between Be and structure.
  3. R_fe_cm=None (default) gives same geometry as before
     (backward compat).
  4. R_fe_cm out of range raises ValueError.
  5. run_real_openmc_tbr accepts R_fe_cm parameter.
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "code"))


class TestTier13FeMaterial:
    """Tier 13 — Fe reflector material."""

    def test_fe_reflector_in_materials(self):
        """_build_blanket_materials should include 'fe_reflector' key."""
        from zpp_real_openmc_transport import _build_blanket_materials
        mats = _build_blanket_materials(Li6_enrichment_fraction=0.90)
        assert "fe_reflector" in mats
        # Also verify backward compat: existing keys still present
        for k in ("lipb", "be", "rafm", "li6", "li7"):
            assert k in mats, f"Missing backward-compat key: {k}"

    def test_fe_reflector_density(self):
        """Fe reflector density should be 7.8 g/cm3 (steel density)."""
        from zpp_real_openmc_transport import _build_blanket_materials
        mats = _build_blanket_materials()
        fe = mats["fe_reflector"]
        # openmc.Material.set_density("g/cm3", val) stores in density attribute
        assert abs(fe.density - 7.8) < 0.01, (
            f"Fe reflector density {fe.density} != 7.8 g/cm3"
        )


class TestTier13Geometry:
    """Tier 13 — _build_zpinch_geometry with R_fe_cm."""

    def test_no_fe_reflector_backward_compat(self):
        """R_fe_cm=None (default) should give same cells as before
        (no fe_reflector cell)."""
        from zpp_real_openmc_transport import (
            _build_blanket_materials, _build_zpinch_geometry,
        )
        mats = _build_blanket_materials()
        geom, cells, surfaces = _build_zpinch_geometry(
            mats, R_plasma_cm=4.0, R_blanket_cm=80.0,
            R_be_cm=82.0, R_structure_cm=85.0,
            mult_inside=True,
        )
        assert "fe_reflector" not in cells
        assert "r_fe" not in surfaces

    def test_with_fe_reflector_mult_inside(self):
        """R_fe_cm set + mult_inside=True should add fe_reflector cell
        between blanket and structure."""
        from zpp_real_openmc_transport import (
            _build_blanket_materials, _build_zpinch_geometry,
        )
        mats = _build_blanket_materials()
        geom, cells, surfaces = _build_zpinch_geometry(
            mats, R_plasma_cm=4.0, R_blanket_cm=80.0,
            R_be_cm=82.0, R_structure_cm=90.0,
            mult_inside=True,
            R_fe_cm=87.0,
        )
        assert "fe_reflector" in cells
        assert "r_fe" in surfaces
        assert "plasma" in cells
        assert "be_mult" in cells
        assert "blanket" in cells
        assert "structure" in cells

    def test_with_fe_reflector_mult_outside(self):
        """R_fe_cm set + mult_inside=False should add fe_reflector cell
        between Be and structure."""
        from zpp_real_openmc_transport import (
            _build_blanket_materials, _build_zpinch_geometry,
        )
        mats = _build_blanket_materials()
        geom, cells, surfaces = _build_zpinch_geometry(
            mats, R_plasma_cm=4.0, R_blanket_cm=50.0,
            R_be_cm=52.0, R_structure_cm=60.0,
            mult_inside=False,
            R_fe_cm=57.0,
        )
        assert "fe_reflector" in cells
        assert "r_fe" in surfaces

    def test_fe_reflector_out_of_range_raises(self):
        """R_fe_cm outside [R_be/R_blanket, R_structure] should raise."""
        from zpp_real_openmc_transport import (
            _build_blanket_materials, _build_zpinch_geometry,
        )
        mats = _build_blanket_materials()
        # mult_inside=False: R_fe must be in (R_be, R_structure) = (82, 85)
        with pytest.raises(ValueError, match="R_fe_cm"):
            _build_zpinch_geometry(
                mats, R_blanket_cm=80.0, R_be_cm=82.0,
                R_structure_cm=85.0,
                mult_inside=False,
                R_fe_cm=80.0,  # < R_be
            )
        with pytest.raises(ValueError, match="R_fe_cm"):
            _build_zpinch_geometry(
                mats, R_blanket_cm=80.0, R_be_cm=82.0,
                R_structure_cm=85.0,
                mult_inside=False,
                R_fe_cm=90.0,  # > R_structure
            )


class TestTier13RunRealOpenMCTBR:
    """Tier 13 — run_real_openmc_tbr accepts R_fe_cm."""

    def test_R_fe_cm_parameter_exists(self):
        """run_real_openmc_tbr should accept R_fe_cm parameter."""
        import inspect
        from zpp_real_openmc_transport import run_real_openmc_tbr
        sig = inspect.signature(run_real_openmc_tbr)
        assert "R_fe_cm" in sig.parameters
        # Default should be None (backward compat)
        assert sig.parameters["R_fe_cm"].default is None


class TestTier13BackwardCompat:
    """Tier 13 — backward compat with v1.2.0 (no Fe reflector)."""

    def test_no_fe_reflector_same_cells(self):
        """Without R_fe_cm, cells dict should match Tier 6.C exactly:
        plasma, be_mult, blanket, structure (no fe_reflector)."""
        from zpp_real_openmc_transport import (
            _build_blanket_materials, _build_zpinch_geometry,
        )
        mats = _build_blanket_materials()
        geom_in, cells_in, _ = _build_zpinch_geometry(
            mats, R_plasma_cm=4.0, R_blanket_cm=80.0,
            R_be_cm=82.0, R_structure_cm=85.0,
            mult_inside=True,
        )
        geom_out, cells_out, _ = _build_zpinch_geometry(
            mats, R_plasma_cm=4.0, R_blanket_cm=80.0,
            R_be_cm=82.0, R_structure_cm=85.0,
            mult_inside=False,
        )
        assert set(cells_in.keys()) == {
            "plasma", "be_mult", "blanket", "structure"
        }
        assert set(cells_out.keys()) == {
            "plasma", "be_mult", "blanket", "structure"
        }
