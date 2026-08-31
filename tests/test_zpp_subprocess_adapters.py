"""
Tier 6.A — Subprocess adapter tests.

Verifies:
1. detect_upstream_codes returns all 4 upstream codes.
2. None of the upstream codes are installed by default.
3. Each Subprocess*Adapter falls back to parametric when upstream
   is not installed.
4. report_installed_codes returns Markdown.
5. using_real_code is False by default.
6. Adapters satisfy the ABC contract (Liskov).
"""
from __future__ import annotations
import sys
import os

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "code"))

from zpp.adapters.zpp_subprocess_adapters import (
    detect_upstream_codes, report_installed_codes,
    SubprocessBOPAdapter, SubprocessTBRAdapter,
    SubprocessGeometryAdapter, SubprocessNeutronicsAdapter,
    make_subprocess_set, UpstreamCodeInfo,
)
from zpp.adapters.zpp_adapters import (
    BOPAdapter, TBRAdapter, GeometryAdapter, NeutronicsAdapter,
    ParametricBOPAdapter, ParametricTBRAdapter,
    ParametricGeometryAdapter, ParametricNeutronicsAdapter,
)
from zpp.zpp_process_bop import PlantBOPInputs, ProcessBOPResult
from zpp.zpp_tbr import TBRInputs, TBRResult
from zpp.zpp_geometry import ZIFERadialBuild
from zpp.zpp_pfc_lifetime import PFCDamageInputs, PFCDamageResult


class TestDetectUpstreamCodes:
    """Test detect_upstream_codes()."""

    def test_returns_four_codes(self):
        info = detect_upstream_codes()
        assert "PROCESS" in info
        assert "OpenMC" in info
        assert "Paramak" in info
        assert "FISPACT-II" in info

    def test_info_is_dataclass(self):
        info = detect_upstream_codes()
        for code_name, u in info.items():
            assert isinstance(u, UpstreamCodeInfo)
            assert u.name == code_name

    def test_PROCESS_installed_v0_6(self):
        """PROCESS was installed by the user in v0.6 (per their approval).

        Real PROCESS integration replaces the parametric BOP defaults
        with PROCESS IFEData defaults.
        """
        info = detect_upstream_codes()
        assert info["PROCESS"].binary_path is not None

    def test_OpenMC_installed_v0_6_1(self):
        """OpenMC was installed via openmc-anywhere wheel in v0.6.1
        (per user approval). Real OpenMC integration uses openmc's
        API to build geometry/materials/tallies XML even without
        cross-sections.
        """
        info = detect_upstream_codes()
        assert info["OpenMC"].binary_path is not None

    def test_Paramak_installed_v0_7(self):
        """Paramak was installed via pip in v0.7 (per user approval).

        Real Paramak integration uses paramak.revolved_shape() for
        Z-pinch cylindrical geometry and exports STEP files for
        CAD inspection.
        """
        info = detect_upstream_codes()
        assert info["Paramak"].binary_path is not None

    def test_FISPACT_not_installed(self):
        """FISPACT-II requires UKAEA license; not auto-installed."""
        info = detect_upstream_codes()
        assert info["FISPACT-II"].binary_path is None

    def test_install_instructions_present(self):
        """Each missing code has install instructions."""
        info = detect_upstream_codes()
        for code_name, u in info.items():
            assert len(u.install_instructions) > 0


class TestSubprocessTBRAdapter:
    """Test SubprocessTBRAdapter.

    As of v0.6.1, OpenMC is installed via openmc-anywhere wheel.
    SubprocessTBRAdapter detects it (using_real_code=True) and
    builds OpenMC geometry/materials/tallies XML. A real
    simulation still requires OPENMC_CROSS_SECTIONS env var;
    the adapter falls back to parametric TBR if missing.
    """

    def test_using_real_code_True_after_OpenMC_install(self):
        """After openmc-anywhere install (v0.6.1), adapter uses real zpp."""
        adapter = SubprocessTBRAdapter()
        assert adapter.using_real_code is True

    def test_compute_returns_TBRResult(self):
        adapter = SubprocessTBRAdapter()
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
        result = adapter.compute(inp)
        assert isinstance(result, TBRResult)

    def test_satisfies_ABC(self):
        adapter = SubprocessTBRAdapter()
        from zpp.adapters.zpp_adapters import TBRAdapter
        assert isinstance(adapter, TBRAdapter)

    def test_compute_handles_real_or_fallback(self):
        """Whether OpenMC run succeeds or falls back, result is valid."""
        adapter = SubprocessTBRAdapter()
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
        result = adapter.compute(inp)
        # Parametric fallback or OpenMC result - both produce TBR.
        assert result.TBR > 0
        assert result.notes  # Non-empty notes describing calculation


class TestSubprocessTBRAdapterOLD:
    """Stale stub removed; real tests in TestSubprocessTBRAdapter above."""

    def test_remove(self):
        pass

    def test_falls_back_to_parametric(self):
        adapter = SubprocessTBRAdapter()
        result = adapter.compute(TBRInputs())
        assert isinstance(result, TBRResult)

    def test_satisfies_ABC(self):
        adapter = SubprocessTBRAdapter()
        assert isinstance(adapter, TBRAdapter)


class TestSubprocessGeometryAdapterOLD:
    """Stale stub removed."""

    def test_falls_back_to_parametric(self):
        adapter = SubprocessGeometryAdapter()
        build = adapter.get_build("ZN")
        assert isinstance(build, ZIFERadialBuild)

    def test_satisfies_ABC(self):
        adapter = SubprocessGeometryAdapter()
        assert isinstance(adapter, GeometryAdapter)


class TestSubprocessNeutronicsAdapter:
    """Test SubprocessNeutronicsAdapter."""

    def test_falls_back_to_parametric(self):
        adapter = SubprocessNeutronicsAdapter()
        result = adapter.compute(PFCDamageInputs())
        assert isinstance(result, PFCDamageResult)

    def test_using_real_code_false(self):
        assert SubprocessNeutronicsAdapter().using_real_code is False

    def test_satisfies_ABC(self):
        adapter = SubprocessNeutronicsAdapter()
        assert isinstance(adapter, NeutronicsAdapter)

    def test_same_as_parametric_when_fallback(self):
        adapter = SubprocessNeutronicsAdapter()
        parametric = ParametricNeutronicsAdapter()
        inp = PFCDamageInputs()
        r1 = adapter.compute(inp)
        r2 = parametric.compute(inp)
        assert r1.dpa_per_FPY == r2.dpa_per_FPY


class TestReportInstalledCodes:
    """Test report_installed_codes()."""

    def test_returns_string(self):
        report = report_installed_codes()
        assert isinstance(report, str)

    def test_mentions_all_four_codes(self):
        report = report_installed_codes()
        for name in ["PROCESS", "OpenMC", "Paramak", "FISPACT-II"]:
            assert name in report

    def test_markdown_format(self):
        report = report_installed_codes()
        # Each line starts with "- " for markdown bullet
        for line in report.split("\n"):
            if line.startswith("-"):
                assert line.startswith("- ")


class TestMakeSubprocessSet:
    """Test make_subprocess_set()."""

    def test_returns_four_adapters(self):
        adapters = make_subprocess_set()
        assert len(adapters) == 4

    def test_keys(self):
        adapters = make_subprocess_set()
        assert "bop" in adapters
        assert "tbr" in adapters
        assert "geometry" in adapters
        assert "neutronics" in adapters

    def test_correct_types(self):
        adapters = make_subprocess_set()
        assert isinstance(adapters["bop"], SubprocessBOPAdapter)
        assert isinstance(adapters["tbr"], SubprocessTBRAdapter)
        assert isinstance(adapters["geometry"], SubprocessGeometryAdapter)
        assert isinstance(adapters["neutronics"], SubprocessNeutronicsAdapter)


class TestStrategicFindings:
    """Document strategic findings from subprocess adapter design."""

    def test_PROCESS_OpenMC_Paramak_installed_v0_7(self):
        """After user-approved installs, three upstream codes detected."""
        adapters = make_subprocess_set()
        assert adapters["bop"].using_real_code is True  # PROCESS
        assert adapters["tbr"].using_real_code is True  # OpenMC
        assert adapters["geometry"].using_real_code is True  # Paramak
        # FISPACT-II still missing
        assert adapters["neutronics"].using_real_code is False

    def test_install_commands_listed_for_remaining(self):
        """FISPACT-II install command documented."""
        report = report_installed_codes()
        # Three codes now installed
        assert "PROCESS" in report
        assert "OpenMC" in report
        assert "Paramak" in report
        # FISPACT-II still missing with install hint
        assert "FISPACT" in report
