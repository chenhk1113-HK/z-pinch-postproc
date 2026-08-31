"""
Tier 6.F — Real OpenMC adapter tests.

Verifies:
1. check_openmc_install() reports install info correctly.
2. get_openmc_anywhere_info() returns package metadata.
3. real_openmc_tbr_calculation() handles cross-sections
   missing case gracefully (falls back to parametric).
4. real_openmc_tbr_calculation() handles TBRInputs correctly.
5. build_openmc_tbr_model() builds valid OpenMC geometry
   (XML files generated in work directory).
7. OPENMC_CROSS_SECTIONS env var is checked.
8. real_openmc_markdown() formats output nicely.

Tests are gated on openmc-anywhere being installed; if
not installed, the entire module is skipped.
"""

import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "code"))


def _openmc_available() -> bool:
    try:
        import openmc  # noqa: F401
        return True
    except ImportError:
        return False


pytestmark = pytest.mark.skipif(
    not _openmc_available(),
    reason="openmc-anywhere not installed",
)


class TestCheckOpenMCInstall:
    """Test check_openmc_install() reporting."""

    def test_returns_dict(self):
        from zpp.adapters.zpp_real_openmc_adapter import check_openmc_install
        info = check_openmc_install()
        assert isinstance(info, dict)
        assert "installed" in info
        assert "version" in info
        assert "binary_path" in info
        assert "cross_sections" in info
        assert "cross_sections_ready" in info

    def test_installed_is_true(self):
        from zpp.adapters.zpp_real_openmc_adapter import check_openmc_install
        info = check_openmc_install()
        assert info["installed"] is True

    def test_version_is_openmc_anywhere(self):
        from zpp.adapters.zpp_real_openmc_adapter import check_openmc_install
        info = check_openmc_install()
        assert info["version"] == "0.16.0.0"

    def test_binary_path_is_set(self):
        from zpp.adapters.zpp_real_openmc_adapter import check_openmc_install
        info = check_openmc_install()
        assert info["binary_path"] is not None

    def test_cross_sections_initially_unset(self):
        from zpp.adapters.zpp_real_openmc_adapter import check_openmc_install
        # Ensure env var is not set
        os.environ.pop("OPENMC_CROSS_SECTIONS", None)
        info = check_openmc_install()
        assert info["cross_sections"] is None
        assert info["cross_sections_ready"] is False


class TestGetOpenMCAnywhereInfo:
    """Test get_openmc_anywhere_info() package metadata."""

    def test_returns_dict(self):
        from zpp.adapters.zpp_real_openmc_adapter import get_openmc_anywhere_info
        info = get_openmc_anywhere_info()
        assert isinstance(info, dict)
        assert info["name"] == "openmc-anywhere"

    def test_version(self):
        from zpp.adapters.zpp_real_openmc_adapter import get_openmc_anywhere_info
        info = get_openmc_anywhere_info()
        assert info["version"] == "0.16.0.0"

    def test_location_is_in_venv(self):
        from zpp.adapters.zpp_real_openmc_adapter import get_openmc_anywhere_info
        info = get_openmc_anywhere_info()
        assert info["location"] is not None
        assert ".venv" in info["location"] or "site-packages" in info["location"]


class TestRealOpenMCTBRCalculation:
    """Test real_openmc_tbr_calculation() behavior."""

    def test_zn_default_returns_result(self):
        from zpp.adapters.zpp_real_openmc_adapter import real_openmc_tbr_calculation
        from zpp.zpp_tbr import TBRInputs
        inp = TBRInputs(
            blanket_material="LiPb",
            neutron_multiplier="Be",
            blanket_thickness_cm=50.0,
            Li6_enrichment_fraction=0.30,
            first_wall_coverage_fraction=0.83,
            geometry="Z-pinch",
            MHD_effect_factor=0.9,
        )
        result = real_openmc_tbr_calculation(inp)
        assert result.openmc_installed is True

    def test_parametric_tbr_always_computed(self):
        from zpp.adapters.zpp_real_openmc_adapter import real_openmc_tbr_calculation
        from zpp.zpp_tbr import TBRInputs
        inp = TBRInputs(
            blanket_material="LiPb",
            neutron_multiplier="Be",
            blanket_thickness_cm=50.0,
            Li6_enrichment_fraction=0.30,
            first_wall_coverage_fraction=0.83,
            geometry="Z-pinch",
            MHD_effect_factor=0.9,
        )
        result = real_openmc_tbr_calculation(inp)
        # Parametric TBR is always computed (fallback).
        assert result.parametric_TBR > 0
        # ZN LiPb+Be, 30% Li-6, MHD=0.9 -> TBR ~1.5 (from tier 5.B)
        assert 1.0 < result.parametric_TBR < 2.5

    def test_xml_generated_even_without_cross_sections(self):
        from zpp.adapters.zpp_real_openmc_adapter import real_openmc_tbr_calculation
        from zpp.zpp_tbr import TBRInputs
        # Make sure cross-sections are NOT set
        os.environ.pop("OPENMC_CROSS_SECTIONS", None)
        inp = TBRInputs(
            blanket_material="LiPb",
            neutron_multiplier="Be",
            blanket_thickness_cm=50.0,
            Li6_enrichment_fraction=0.30,
            first_wall_coverage_fraction=0.83,
            geometry="Z-pinch",
            MHD_effect_factor=0.9,
        )
        result = real_openmc_tbr_calculation(inp)
        # XML should be generated even if cross-sections are missing
        assert result.model_xml_generated is True
        assert result.tally_xml_generated is True

    def test_run_skipped_without_cross_sections(self):
        from zpp.adapters.zpp_real_openmc_adapter import real_openmc_tbr_calculation
        from zpp.zpp_tbr import TBRInputs
        os.environ.pop("OPENMC_CROSS_SECTIONS", None)
        inp = TBRInputs(
            blanket_material="LiPb",
            neutron_multiplier="Be",
            blanket_thickness_cm=50.0,
            Li6_enrichment_fraction=0.30,
            first_wall_coverage_fraction=0.83,
            geometry="Z-pinch",
            MHD_effect_factor=0.9,
        )
        result = real_openmc_tbr_calculation(inp)
        assert result.run_completed is False
        assert result.openmc_TBR is None

    def test_fispact_blanket(self):
        from zpp.adapters.zpp_real_openmc_adapter import real_openmc_tbr_calculation
        from zpp.zpp_tbr import TBRInputs
        # Test with Li4SiO4 (FISPACT-relevant ceramic)
        inp = TBRInputs(
            blanket_material="Li4SiO4",
            neutron_multiplier="Be",
            blanket_thickness_cm=60.0,
            Li6_enrichment_fraction=0.60,
            first_wall_coverage_fraction=0.80,
            geometry="tokamak",
            MHD_effect_factor=0.95,
        )
        result = real_openmc_tbr_calculation(inp)
        assert result.parametric_TBR > 0


class TestBuildOpenMCTBRModel:
    """Test build_openmc_tbr_model() geometry building."""

    def test_xml_files_written(self):
        from zpp.adapters.zpp_real_openmc_adapter import build_openmc_tbr_model
        from zpp.zpp_tbr import TBRInputs
        inp = TBRInputs(
            blanket_material="LiPb",
            neutron_multiplier="Be",
            blanket_thickness_cm=50.0,
            Li6_enrichment_fraction=0.30,
            first_wall_coverage_fraction=0.83,
            geometry="Z-pinch",
            MHD_effect_factor=0.9,
        )
        with tempfile.TemporaryDirectory() as work_dir:
            model, geom_xml, mat_xml = build_openmc_tbr_model(inp, work_dir)
            assert os.path.exists(geom_xml)
            assert os.path.exists(mat_xml)
            # Other OpenMC XML files
            assert os.path.exists(os.path.join(work_dir, "settings.xml"))
            assert os.path.exists(os.path.join(work_dir, "tallies.xml"))

    def test_model_is_openmc_model(self):
        from zpp.adapters.zpp_real_openmc_adapter import build_openmc_tbr_model
        from zpp.zpp_tbr import TBRInputs
        import openmc
        inp = TBRInputs(
            blanket_material="LiPb",
            neutron_multiplier="Be",
            blanket_thickness_cm=50.0,
            Li6_enrichment_fraction=0.30,
            first_wall_coverage_fraction=0.83,
            geometry="Z-pinch",
            MHD_effect_factor=0.9,
        )
        with tempfile.TemporaryDirectory() as work_dir:
            model, _, _ = build_openmc_tbr_model(inp, work_dir)
            assert isinstance(model, openmc.Model)


class TestRealOpenMCMarkdown:
    """Test real_openmc_markdown() formatting."""

    def test_includes_install_status(self):
        from zpp.adapters.zpp_real_openmc_adapter import real_openmc_markdown, OpenMCNeutronicsResult
        result = OpenMCNeutronicsResult(
            openmc_installed=True,
            openmc_version="0.16.0.0",
            cross_sections_available=False,
            model_xml_generated=True,
            tally_xml_generated=True,
            run_completed=False,
            parametric_TBR=1.5,
            openmc_TBR=None,
            openmc_TBR_std=None,
            notes="test notes",
        )
        md = real_openmc_markdown(result)
        assert "Real OpenMC neutronics result" in md
        assert "openmc-anywhere installed" in md
        assert "Parametric TBR" in md
        assert "1.5000" in md

    def test_includes_openmc_tbr_when_available(self):
        from zpp.adapters.zpp_real_openmc_adapter import real_openmc_markdown, OpenMCNeutronicsResult
        result = OpenMCNeutronicsResult(
            openmc_installed=True,
            openmc_version="0.16.0.0",
            cross_sections_available=True,
            model_xml_generated=True,
            tally_xml_generated=True,
            run_completed=True,
            parametric_TBR=1.5,
            openmc_TBR=1.42,
            openmc_TBR_std=0.05,
            notes="real TBR computed",
        )
        md = real_openmc_markdown(result)
        assert "1.4200" in md
        assert "0.0500" in md


class TestStrategicFindings:
    """Document strategic findings from openmc-anywhere integration."""

    def test_openmc_anywhere_unofficial_pypi_wheel(self):
        """openmc-anywhere is the unofficial PyPI wheel workaround
        for installing OpenMC without conda on Windows.
        """
        from zpp.adapters.zpp_real_openmc_adapter import get_openmc_anywhere_info
        info = get_openmc_anywhere_info()
        # The wheel name proves the unofficial nature
        assert info["name"] == "openmc-anywhere"

    def test_cross_sections_must_be_downloaded_separately(self):
        """OPENMC_CROSS_SECTIONS env var must be set with valid
        path to cross_sections.xml for a real simulation.
        """
        from zpp.adapters.zpp_real_openmc_adapter import check_openmc_install
        os.environ.pop("OPENMC_CROSS_SECTIONS", None)
        info = check_openmc_install()
        # Without env var, cross_sections_ready is False
        assert info["cross_sections_ready"] is False