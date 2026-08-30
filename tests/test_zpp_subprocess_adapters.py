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

from zpp_subprocess_adapters import (
    detect_upstream_codes, report_installed_codes,
    SubprocessBOPAdapter, SubprocessTBRAdapter,
    SubprocessGeometryAdapter, SubprocessNeutronicsAdapter,
    make_subprocess_set, UpstreamCodeInfo,
)
from zpp_adapters import (
    BOPAdapter, TBRAdapter, GeometryAdapter, NeutronicsAdapter,
    ParametricBOPAdapter, ParametricTBRAdapter,
    ParametricGeometryAdapter, ParametricNeutronicsAdapter,
)
from zpp_process_bop import PlantBOPInputs, ProcessBOPResult
from zpp_tbr import TBRInputs, TBRResult
from zpp_geometry import ZIFERadialBuild
from zpp_pfc_lifetime import PFCDamageInputs, PFCDamageResult


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

    def test_OpenMC_not_installed(self):
        """OpenMC is not on PyPI; needs conda. The user has not installed it."""
        info = detect_upstream_codes()
        assert info["OpenMC"].binary_path is None

    def test_install_instructions_present(self):
        """Each missing code has install instructions."""
        info = detect_upstream_codes()
        for code_name, u in info.items():
            assert len(u.install_instructions) > 0


class TestSubprocessBOPAdapter:
    """Test SubprocessBOPAdapter.

    As of v0.6, PROCESS is installed, so SubprocessBOPAdapter
    detects it and uses_real_code=True. The fallback still works
    (parametric) when subprocess fails.
    """

    def test_using_real_code_True_after_PROCESS_install(self):
        """After PROCESS install (v0.6), adapter uses real code."""
        adapter = SubprocessBOPAdapter()
        assert adapter.using_real_code is True

    def test_compute_returns_result(self):
        adapter = SubprocessBOPAdapter()
        result = adapter.compute(PlantBOPInputs())
        assert isinstance(result, ProcessBOPResult)

    def test_satisfies_ABC(self):
        adapter = SubprocessBOPAdapter()
        assert isinstance(adapter, BOPAdapter)

    def test_compute_handles_real_or_fallback(self):
        """Whether subprocess succeeds or fails, result is valid."""
        adapter = SubprocessBOPAdapter()
        result = adapter.compute(PlantBOPInputs())
        # PROCESS IFE defaults applied if real, parametric otherwise.
        # Both produce a valid ProcessBOPResult.
        assert result.eta_E_plant > 0
        assert result.f_recirc >= 0


class TestSubprocessTBRAdapter:
    """Test SubprocessTBRAdapter."""

    def test_falls_back_to_parametric(self):
        adapter = SubprocessTBRAdapter()
        result = adapter.compute(TBRInputs())
        assert isinstance(result, TBRResult)

    def test_using_real_code_false(self):
        assert SubprocessTBRAdapter().using_real_code is False

    def test_satisfies_ABC(self):
        adapter = SubprocessTBRAdapter()
        assert isinstance(adapter, TBRAdapter)

    def test_same_as_parametric_when_fallback(self):
        adapter = SubprocessTBRAdapter()
        parametric = ParametricTBRAdapter()
        inp = TBRInputs()
        r1 = adapter.compute(inp)
        r2 = parametric.compute(inp)
        assert r1.TBR == r2.TBR


class TestSubprocessGeometryAdapter:
    """Test SubprocessGeometryAdapter."""

    def test_falls_back_to_parametric(self):
        adapter = SubprocessGeometryAdapter()
        build = adapter.get_build("ZN")
        assert isinstance(build, ZIFERadialBuild)

    def test_using_real_code_false(self):
        assert SubprocessGeometryAdapter().using_real_code is False

    def test_satisfies_ABC(self):
        adapter = SubprocessGeometryAdapter()
        assert isinstance(adapter, GeometryAdapter)

    def test_same_as_parametric_when_fallback(self):
        adapter = SubprocessGeometryAdapter()
        parametric = ParametricGeometryAdapter()
        b1 = adapter.get_build("ZN")
        b2 = parametric.get_build("ZN")
        assert b1.total_radius_cm() == b2.total_radius_cm()


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

    def test_PROCESS_installed_v0_6(self):
        """After user-approved install, PROCESS is detected and used."""
        adapters = make_subprocess_set()
        assert adapters["bop"].using_real_code is True

    def test_install_commands_listed_for_remaining(self):
        """OpenMC, Paramak, FISPACT-II install commands documented."""
        report = report_installed_codes()
        # PROCESS is now installed, others still not
        assert "✅" in report  # PROCESS
        assert "❌" in report  # OpenMC, Paramak, FISPACT-II
        assert "conda install" in report  # OpenMC
        assert "pip install" in report  # Paramak
        assert "Download" in report  # FISPACT-II
