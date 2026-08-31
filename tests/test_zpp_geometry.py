"""
Tier 4.C — Paramak-equivalent radial build geometry tests.

Verifies:
1. RadialBuildLayer dataclass.
2. ZIFERadialBuild total_radius = R_plasma + sum of layer thicknesses.
3. plasma_volume_cm3 = π R² L.
4. first_wall_area_cm2 = lateral + 2 end caps.
5. coverage_fraction gives reasonable values per geometry.
6. Pre-defined builds have sensible total radii.
7. summary() returns all expected keys.
"""
from __future__ import annotations
import sys
import os

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "code"))

from zpp.zpp_geometry import (
    RadialBuildLayer,
    ZIFERadialBuild,
    ZN_radial_build,
    tokamak_radial_build,
    GF_MTF_radial_build,
    Zap_SFZ_radial_build,
    get_build,
    ALL_BUILDS,
)


class TestRadialBuildLayer:
    """Test the RadialBuildLayer dataclass."""

    def test_layer_fields(self):
        layer = RadialBuildLayer(
            name="First wall",
            material="Tungsten",
            thickness_cm=1.0,
            role="first_wall",
        )
        assert layer.name == "First wall"
        assert layer.material == "Tungsten"
        assert layer.thickness_cm == 1.0
        assert layer.role == "first_wall"


class TestZIFERadialBuild:
    """Test the ZIFERadialBuild class."""

    def test_default_build(self):
        b = ZIFERadialBuild()
        assert b.R_plasma_cm == 50.0
        assert len(b.layers) == 0  # default empty
        assert b.total_radius_cm() == 50.0  # just the plasma

    def test_total_radius_sum(self):
        b = ZIFERadialBuild(
            R_plasma_cm=50.0,
            layers=[
                RadialBuildLayer("a", "W", 1.0, "first_wall"),
                RadialBuildLayer("b", "LiPb", 50.0, "blanket"),
                RadialBuildLayer("c", "Steel", 8.0, "structure"),
            ],
        )
        assert b.total_radius_cm() == pytest.approx(50.0 + 1.0 + 50.0 + 8.0, abs=1e-9)

    def test_plasma_volume_cylindrical(self):
        b = ZIFERadialBuild(R_plasma_cm=10.0, axial_length_cm=100.0)
        expected = np.pi * 10.0 ** 2 * 100.0
        assert b.plasma_volume_cm3() == pytest.approx(expected, rel=1e-9)

    def test_first_wall_area_cylinder_plus_caps(self):
        b = ZIFERadialBuild(R_plasma_cm=10.0, axial_length_cm=100.0)
        lateral = 2 * np.pi * 10.0 * 100.0
        end_caps = 2 * np.pi * 10.0 ** 2
        expected = lateral + end_caps
        assert b.first_wall_area_cm2() == pytest.approx(expected, rel=1e-9)

    def test_blanket_volume_only_blanket_layers(self):
        b = ZIFERadialBuild(
            R_plasma_cm=50.0,
            axial_length_cm=100.0,
            layers=[
                RadialBuildLayer("a", "W", 1.0, "first_wall"),
                RadialBuildLayer("b", "LiPb", 50.0, "blanket"),
                RadialBuildLayer("c", "Steel", 8.0, "structure"),
            ],
        )
        # Blanket volume: 2πL ∫[R=51, R=101] r dr = πL (101² - 51²)
        expected = np.pi * 100.0 * (101.0 ** 2 - 51.0 ** 2)
        assert b.blanket_volume_cm3() == pytest.approx(expected, rel=1e-9)


class TestCoverageFraction:
    """Test the coverage_fraction method."""

    def test_Z_pinch_coverage_in_valid_range(self):
        b = ZN_radial_build()
        cov = b.coverage_fraction("Z-pinch")
        assert 0.5 <= cov <= 0.99

    def test_tokamak_coverage_around_92pct(self):
        b = tokamak_radial_build()
        cov = b.coverage_fraction("tokamak")
        assert 0.85 <= cov <= 0.95

    def test_MTF_coverage_around_85pct(self):
        b = GF_MTF_radial_build()
        cov = b.coverage_fraction("MTF")
        assert 0.80 <= cov <= 0.90

    def test_unknown_geometry_uses_default(self):
        b = ZN_radial_build()
        cov = b.coverage_fraction("unknown")
        assert 0.5 <= cov <= 0.99


class TestPreDefinedBuilds:
    """Test the pre-defined radial builds."""

    def test_all_four_builds_construct(self):
        for name in ["ZN", "Tokamak", "GF-MTF", "Zap-SFZ"]:
            build_fn = ALL_BUILDS[name]
            b = build_fn()
            assert isinstance(b, ZIFERadialBuild)
            assert b.total_radius_cm() > b.R_plasma_cm  # at least one layer

    def test_ZN_total_radius_sensible(self):
        """ZN total radius should be 1-2 m."""
        b = ZN_radial_build()
        assert 100.0 <= b.total_radius_cm() <= 200.0  # 1-2 m

    def test_tokamak_total_radius_larger(self):
        """Tokamak should be larger than Z-IFE (3+ m)."""
        b_t = tokamak_radial_build()
        b_z = ZN_radial_build()
        assert b_t.total_radius_cm() > b_z.total_radius_cm()

    def test_tokamak_plasma_volume_larger_than_Z(self):
        """Tokamak plasma volume >> Z-pinch."""
        b_t = tokamak_radial_build()
        b_z = ZN_radial_build()
        assert b_t.plasma_volume_cm3() > b_z.plasma_volume_cm3() * 10

    def test_ZN_first_wall_area_smaller_than_tokamak(self):
        b_z = ZN_radial_build()
        b_t = tokamak_radial_build()
        assert b_t.first_wall_area_cm2() > b_z.first_wall_area_cm2() * 5


class TestGetBuild:
    """Test the get_build convenience function."""

    def test_returns_build_for_known_name(self):
        for name in ["ZN", "Tokamak", "GF-MTF", "Zap-SFZ"]:
            b = get_build(name)
            assert isinstance(b, ZIFERadialBuild)

    def test_unknown_build_raises(self):
        with pytest.raises(ValueError):
            get_build("WarpDrive")


class TestSummary:
    """Test the summary method."""

    def test_summary_returns_expected_keys(self):
        b = ZN_radial_build()
        s = b.summary()
        expected = {
            "name", "R_plasma_cm", "axial_length_cm", "n_layers",
            "layer_summary", "total_radius_cm", "plasma_volume_L",
            "first_wall_area_m2", "blanket_volume_m3",
            "coverage_fraction_Z_pinch",
        }
        assert expected.issubset(set(s.keys()))

    def test_summary_layer_count_matches(self):
        b = ZN_radial_build()
        s = b.summary()
        assert s["n_layers"] == len(b.layers)

    def test_summary_layer_details(self):
        b = ZN_radial_build()
        s = b.summary()
        assert len(s["layer_summary"]) == len(b.layers)
        for i, layer_dict in enumerate(s["layer_summary"]):
            assert layer_dict["name"] == b.layers[i].name
            assert layer_dict["thickness_cm"] == b.layers[i].thickness_cm


class TestEndToEndZNBuild:
    """End-to-end: ZN radial build for downstream models."""

    def test_ZN_plasma_volume_in_litres(self):
        """ZN plasma volume should be a few hundred litres
        (100 cm axial, 50 cm radius = 785 L)."""
        b = ZN_radial_build()
        assert 700 < b.summary()["plasma_volume_L"] < 900

    def test_ZN_total_volume_includes_blanket(self):
        """ZN total radius includes the 50 cm blanket layer."""
        b = ZN_radial_build()
        assert b.total_radius_cm() > 50.0 + 50.0  # plasma + blanket
