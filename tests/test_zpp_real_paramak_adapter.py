"""
Tier 7.A — Real Paramak adapter tests.

Verifies:
1. check_paramak_install() reports Paramak status.
2. get_paramak_info() returns package metadata.
3. build_paramak_zpinch() builds 3D CAD geometry for ZN.
4. STEP file export works.
5. All 4 pre-defined radial builds (ZN, Tokamak, GF-MTF, Zap-SFZ)
   produce valid geometry.
6. Geometry result matches radial build metadata (sanity check).
"""

import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "code"))


def _paramak_available() -> bool:
    try:
        import paramak  # noqa: F401
        return True
    except ImportError:
        return False


pytestmark = pytest.mark.skipif(
    not _paramak_available(),
    reason="paramak not installed",
)


class TestCheckParamakInstall:
    """Test check_paramak_install()."""

    def test_installed(self):
        from zpp.adapters.zpp_real_paramak_adapter import check_paramak_install
        info = check_paramak_install()
        assert info["installed"] is True

    def test_version(self):
        from zpp.adapters.zpp_real_paramak_adapter import check_paramak_install
        info = check_paramak_install()
        assert info["version"] is not None
        # 0.9.x
        assert info["version"].startswith("0.9")


class TestGetParamakInfo:
    """Test get_paramak_info() metadata."""

    def test_returns_dict(self):
        from zpp.adapters.zpp_real_paramak_adapter import get_paramak_info
        info = get_paramak_info()
        assert info["name"] == "paramak"

    def test_location(self):
        from zpp.adapters.zpp_real_paramak_adapter import get_paramak_info
        info = get_paramak_info()
        assert info["location"] is not None
        assert ".venv" in info["location"] or "site-packages" in info["location"]


class TestBuildParamakZpinch:
    """Test build_paramak_zpinch() for the 4 pre-defined builds."""

    def test_zn_build(self):
        from zpp.adapters.zpp_real_paramak_adapter import build_paramak_zpinch
        from zpp.zpp_geometry import ZN_radial_build
        build = ZN_radial_build()
        with tempfile.TemporaryDirectory() as work_dir:
            result = build_paramak_zpinch(build, work_dir, export_step=False)
            assert result.paramak_installed is True
            assert result.total_radius_cm > 0
            assert result.plasma_height_cm > 0
            assert result.blanket_volume_cm3 > 0

    def test_zn_step_file_generated(self):
        from zpp.adapters.zpp_real_paramak_adapter import build_paramak_zpinch
        from zpp.zpp_geometry import ZN_radial_build
        build = ZN_radial_build()
        with tempfile.TemporaryDirectory() as work_dir:
            result = build_paramak_zpinch(build, work_dir, export_step=True)
            assert result.step_file_generated is True
            assert result.step_file_path is not None
            assert os.path.exists(result.step_file_path)
            assert os.path.getsize(result.step_file_path) > 1000  # STEP file

    def test_tokamak_build(self):
        from zpp.adapters.zpp_real_paramak_adapter import build_paramak_zpinch
        from zpp.zpp_geometry import tokamak_radial_build
        build = tokamak_radial_build()
        with tempfile.TemporaryDirectory() as work_dir:
            result = build_paramak_zpinch(build, work_dir, export_step=False)
            assert result.build_name.startswith("ITER") or "tokamak" in result.build_name.lower()

    def test_gf_mtf_build(self):
        from zpp.adapters.zpp_real_paramak_adapter import build_paramak_zpinch
        from zpp.zpp_geometry import GF_MTF_radial_build
        build = GF_MTF_radial_build()
        with tempfile.TemporaryDirectory() as work_dir:
            result = build_paramak_zpinch(build, work_dir, export_step=False)
            assert result.total_radius_cm > 0

    def test_zap_sfz_build(self):
        from zpp.adapters.zpp_real_paramak_adapter import build_paramak_zpinch
        from zpp.zpp_geometry import Zap_SFZ_radial_build
        build = Zap_SFZ_radial_build()
        with tempfile.TemporaryDirectory() as work_dir:
            result = build_paramak_zpinch(build, work_dir, export_step=False)
            assert result.total_radius_cm > 0

    def test_radius_consistent_with_radial_build(self):
        """total_radius from Paramak matches sum of layer thicknesses."""
        from zpp.adapters.zpp_real_paramak_adapter import build_paramak_zpinch
        from zpp.zpp_geometry import ZN_radial_build
        build = ZN_radial_build()
        expected_radius = sum(l.thickness_cm for l in build.layers)
        with tempfile.TemporaryDirectory() as work_dir:
            result = build_paramak_zpinch(build, work_dir, export_step=False)
            assert abs(result.total_radius_cm - expected_radius) < 0.01

    def test_blanket_volume_scales_with_height(self):
        """Blanket volume scales linearly with axial_length."""
        from zpp.adapters.zpp_real_paramak_adapter import build_paramak_zpinch
        from zpp.zpp_geometry import ZIFERadialBuild, RadialBuildLayer
        layers = [
            RadialBuildLayer(name="FW", material="RAFM", thickness_cm=2.0, role="FW"),
            RadialBuildLayer(name="blanket", material="LiPb", thickness_cm=50.0, role="blanket"),
            RadialBuildLayer(name="shield", material="WC", thickness_cm=20.0, role="shield"),
        ]
        b1 = ZIFERadialBuild(name="short", R_plasma_cm=1.0, layers=layers, axial_length_cm=100.0)
        b2 = ZIFERadialBuild(name="tall", R_plasma_cm=1.0, layers=layers, axial_length_cm=200.0)
        with tempfile.TemporaryDirectory() as work_dir:
            r1 = build_paramak_zpinch(b1, work_dir, export_step=False)
            r2 = build_paramak_zpinch(b2, work_dir, export_step=False)
            # Volume should scale 2x
            assert abs(r2.blanket_volume_cm3 / r1.blanket_volume_cm3 - 2.0) < 0.01


class TestParamakGeometryMarkdown:
    """Test paramak_geometry_markdown() formatting."""

    def test_includes_install_status(self):
        from zpp.adapters.zpp_real_paramak_adapter import (
            paramak_geometry_markdown, ParamakGeometryResult,
        )
        result = ParamakGeometryResult(
            paramak_installed=True,
            paramak_version="0.9.11",
            build_name="ZN",
            total_radius_cm=149.0,
            plasma_height_cm=100.0,
            blanket_volume_cm3=3.08e6,
            step_file_generated=True,
            step_file_path="/tmp/zn.step",
            notes="test notes",
        )
        md = paramak_geometry_markdown(result)
        assert "Paramak geometry result" in md
        assert "Paramak installed" in md
        assert "ZN" in md
        assert "149.00" in md
        assert "STEP path" in md


class TestStrategicFindings:
    """Document strategic findings from Paramak integration."""

    def test_paramak_is_tokamak_centric(self):
        """Paramak's strength is tokamaks; Z-pinch uses revolved_shape.

        This is honest disclosure - we use Paramak's primitive
        revolved_shape() for cylindrical Z-pinch geometry, NOT
        the tokamak_from_plasma() which assumes D-shape plasma.
        """
        import paramak
        # Tokamak-from-plasma assumes D-shape (triangularity)
        # We use revolved_shape for Z-pinch's cylindrical plasma
        assert hasattr(paramak, "revolved_shape")
        assert hasattr(paramak, "tokamak_from_plasma")  # not used

    def test_paramak_handles_cad_export(self):
        """Paramak uses CadQuery for STEP file export.

        STEP files are standard CAD exchange format; can be
        imported into Fusion 360, FreeCAD, etc.
        """
        import paramak
        # CadQuery is a dep
        import cadquery
        assert cadquery is not None