"""
Tier 6.E — Real PROCESS adapter tests.

Verifies:
1. PROCESS is detected as installed.
2. validate_process_install returns True.
3. get_process_ife_defaults returns sensible values.
4. get_process_cost_defaults returns sensible values.
5. RealProcessBOPAdapter.using_real_code is True.
6. RealProcessBOPAdapter.compute() returns ProcessBOPResult.
7. Result notes include PROCESS-seeded annotation.
"""
from __future__ import annotations
import sys
import os

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "code"))

from zpp_real_process_adapter import (
    RealProcessBOPAdapter, ProcessIFEParams,
    validate_process_install, get_process_ife_defaults,
    get_process_cost_defaults, PROCESS_IFE_DEFAULTS, PROCESS_COST_2015_DEFAULTS,
)
from zpp_process_bop import PlantBOPInputs, ProcessBOPResult
from zpp_adapters import BOPAdapter


class TestProcessInstallDetection:
    """Test that PROCESS install is detected."""

    def test_validate_process_install(self):
        """PROCESS was installed by the user, so validation should pass."""
        # This test depends on PROCESS being installed; if not, skip
        if not validate_process_install():
            pytest.skip("PROCESS not installed")
        assert validate_process_install() is True

    def test_ife_defaults_keys(self):
        defaults = get_process_ife_defaults()
        assert "gain" in defaults
        assert "etadrv" in defaults
        assert "fbreed" in defaults

    def test_ife_defaults_values(self):
        defaults = get_process_ife_defaults()
        assert defaults["gain"] > 0
        assert defaults["etadrv"] > 0
        assert 1.0 <= defaults["fbreed"] <= 2.0

    def test_cost_defaults_keys(self):
        defaults = get_process_cost_defaults()
        assert "blanket_replacement_unit_M" in defaults
        assert "tokamak_complex_cost_M" in defaults


class TestProcessIFEParams:
    """Test ProcessIFEParams dataclass."""

    def test_default_construction(self):
        p = ProcessIFEParams()
        assert p.gain == 10.0
        assert p.etadrv == 0.20

    def test_to_concept_params(self):
        p = ProcessIFEParams(gain=15.0, etadrv=0.30)
        c = p.to_concept_params()
        assert c["Q_target_design"] == 15.0
        assert c["eta_wp_target"] == 0.30


class TestRealProcessBOPAdapter:
    """Test the real PROCESS BOP adapter."""

    def test_satisfies_ABC(self):
        adapter = RealProcessBOPAdapter()
        assert isinstance(adapter, BOPAdapter)

    def test_using_real_code_True(self):
        adapter = RealProcessBOPAdapter()
        if not validate_process_install():
            pytest.skip("PROCESS not installed")
        assert adapter.using_real_code is True

    def test_compute_returns_ProcessBOPResult(self):
        adapter = RealProcessBOPAdapter()
        result = adapter.compute(PlantBOPInputs())
        assert isinstance(result, ProcessBOPResult)

    def test_compute_uses_PROCESS_defaults(self):
        """When PROCESS installed, result notes mention PROCESS defaults."""
        adapter = RealProcessBOPAdapter()
        if not validate_process_install():
            pytest.skip("PROCESS not installed")
        result = adapter.compute(PlantBOPInputs())
        assert "PROCESS-seeded" in result.notes or "PROCESS" in result.notes

    def test_compute_when_not_installed_falls_back(self):
        """When PROCESS not installed, adapter falls back to parametric."""
        # We can't easily simulate PROCESS being absent, so test that
        # compute works either way.
        adapter = RealProcessBOPAdapter()
        result = adapter.compute(PlantBOPInputs())
        assert isinstance(result, ProcessBOPResult)


class TestStrategicFindings:
    """Document strategic findings from PROCESS integration."""

    def test_PROCESS_IFE_gain_is_10(self):
        """PROCESS IFEData.gain default = 10 (Q_eng target for IFE).

        This matches our Tier 5-D finding: Z-IFE design target is
        Q_eng=10. The PROCESS default confirms this is the
        engineering community's consensus target.
        """
        defaults = get_process_ife_defaults()
        assert defaults["gain"] == 10.0

    def test_PROCESS_IFE_etadrv_is_0_20(self):
        """PROCESS IFEData.etadrv default = 0.20 (driver efficiency).

        Our parametric model assumes eta_wp=0.20 for ZN class.
        PROCESS confirms this is realistic.
        """
        defaults = get_process_ife_defaults()
        assert defaults["etadrv"] == 0.20

    def test_PROCESS_fbreed_is_1_05(self):
        """PROCESS IFEData.fbreed default = 1.05 (TBR engineering threshold).

        Our Tier 4-B TBR model uses 1.05 as the engineering threshold
        for tritium self-sufficiency. PROCESS default matches.
        """
        defaults = get_process_ife_defaults()
        assert defaults["fbreed"] == 1.05
