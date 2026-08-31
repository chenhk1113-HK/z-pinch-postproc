"""
Tier 5.E — Adapter interface tests.

Verifies:
1. Parametric adapters work (BOP, TBR, geometry, neutronics).
2. Real adapter stubs raise NotImplementedError with helpful messages.
3. AdapterSet defaults to parametric.
4. swap_adapter creates a new set with one component swapped.
5. list_install_instructions returns all 4 upstream codes.
6. ABC inheritance enforces the abstract interface.
"""
from __future__ import annotations
import sys
import os

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "code"))

from zpp.adapters.zpp_adapters import (
    BOPAdapter, TBRAdapter, GeometryAdapter, NeutronicsAdapter,
    ParametricBOPAdapter, RealProcessBOPAdapter,
    ParametricTBRAdapter, RealOpenMCTBRAdapter,
    ParametricGeometryAdapter, RealParamakGeometryAdapter,
    ParametricNeutronicsAdapter, RealFISPACTNeutronicsAdapter,
    AdapterSet, make_parametric_set, swap_adapter, list_install_instructions,
)
from zpp.zpp_process_bop import PlantBOPInputs, ProcessBOPResult
from zpp.zpp_tbr import TBRInputs, TBRResult
from zpp.zpp_geometry import ZIFERadialBuild
from zpp.zpp_pfc_lifetime import PFCDamageInputs, PFCDamageResult


class TestParametricAdapters:
    """Test the parametric adapters (default implementations)."""

    def test_parametric_BOP(self):
        adapter = ParametricBOPAdapter()
        result = adapter.compute(PlantBOPInputs())
        assert isinstance(result, ProcessBOPResult)
        assert 0.0 < result.eta_E_plant < 1.0

    def test_parametric_TBR(self):
        adapter = ParametricTBRAdapter()
        result = adapter.compute(TBRInputs())
        assert isinstance(result, TBRResult)
        assert result.TBR > 0.0

    def test_parametric_geometry(self):
        adapter = ParametricGeometryAdapter()
        build = adapter.get_build("ZN")
        assert isinstance(build, ZIFERadialBuild)

    def test_parametric_neutronics(self):
        adapter = ParametricNeutronicsAdapter()
        result = adapter.compute(PFCDamageInputs())
        assert isinstance(result, PFCDamageResult)
        assert result.dpa_per_FPY > 0.0


class TestRealAdapters:
    """Test the real adapter stubs (must raise NotImplementedError)."""

    def test_real_BOP_raises(self):
        adapter = RealProcessBOPAdapter()
        with pytest.raises(NotImplementedError) as exc_info:
            adapter.compute(PlantBOPInputs())
        assert "PROCESS" in str(exc_info.value)

    def test_real_TBR_raises(self):
        adapter = RealOpenMCTBRAdapter()
        with pytest.raises(NotImplementedError) as exc_info:
            adapter.compute(TBRInputs())
        assert "OpenMC" in str(exc_info.value)

    def test_real_geometry_raises(self):
        adapter = RealParamakGeometryAdapter()
        with pytest.raises(NotImplementedError) as exc_info:
            adapter.get_build("ZN")
        assert "Paramak" in str(exc_info.value)

    def test_real_neutronics_raises(self):
        adapter = RealFISPACTNeutronicsAdapter()
        with pytest.raises(NotImplementedError) as exc_info:
            adapter.compute(PFCDamageInputs())
        assert "FISPACT" in str(exc_info.value)


class TestABCEnforcement:
    """Test that ABCs cannot be instantiated directly."""

    def test_BOPAdapter_is_abstract(self):
        with pytest.raises(TypeError):
            BOPAdapter()

    def test_TBRAdapter_is_abstract(self):
        with pytest.raises(TypeError):
            TBRAdapter()

    def test_GeometryAdapter_is_abstract(self):
        with pytest.raises(TypeError):
            GeometryAdapter()

    def test_NeutronicsAdapter_is_abstract(self):
        with pytest.raises(TypeError):
            NeutronicsAdapter()


class TestAdapterSet:
    """Test the AdapterSet bundle."""

    def test_default_set_is_parametric(self):
        s = make_parametric_set()
        assert isinstance(s.bop, ParametricBOPAdapter)
        assert isinstance(s.tbr, ParametricTBRAdapter)
        assert isinstance(s.geometry, ParametricGeometryAdapter)
        assert isinstance(s.neutronics, ParametricNeutronicsAdapter)

    def test_AdapterSet_defaults(self):
        s = AdapterSet()
        assert isinstance(s.bop, ParametricBOPAdapter)

    def test_swap_adapter_bop(self):
        s = make_parametric_set()
        new_bop = ParametricBOPAdapter()  # for test, swap with same
        new_s = swap_adapter(s, "bop", new_bop)
        assert isinstance(new_s.bop, ParametricBOPAdapter)
        # Original unchanged
        assert s is not new_s

    def test_swap_adapter_preserves_others(self):
        s = make_parametric_set()
        original_tbr = s.tbr
        new_s = swap_adapter(s, "bop", ParametricBOPAdapter())
        assert new_s.tbr is original_tbr


class TestInstallInstructions:
    """Test the install instructions dict."""

    def test_returns_dict(self):
        inst = list_install_instructions()
        assert isinstance(inst, dict)

    def test_all_four_upstream_codes(self):
        inst = list_install_instructions()
        assert "PROCESS" in inst
        assert "OpenMC" in inst
        assert "Paramak" in inst
        assert "FISPACT-II" in inst

    def test_all_require_approval(self):
        """Per AGENTS.md rule 17, all installs require approval."""
        inst = list_install_instructions()
        for code_name, info in inst.items():
            assert info["requires_approval"] is True
            assert "install_command" in info
            assert "license" in info


class TestSubstitutability:
    """Test that parametric and real adapters are interchangeable."""

    def test_parametric_BOP_satisfies_protocol(self):
        """ParametricBOPAdapter is a BOPAdapter (Liskov substitution)."""
        assert issubclass(ParametricBOPAdapter, BOPAdapter)

    def test_real_BOP_satisfies_protocol(self):
        """RealProcessBOPAdapter is a BOPAdapter."""
        assert issubclass(RealProcessBOPAdapter, BOPAdapter)

    def test_parametric_TBR_satisfies_protocol(self):
        assert issubclass(ParametricTBRAdapter, TBRAdapter)

    def test_real_TBR_satisfies_protocol(self):
        assert issubclass(RealOpenMCTBRAdapter, TBRAdapter)

    def test_parametric_geometry_satisfies_protocol(self):
        assert issubclass(ParametricGeometryAdapter, GeometryAdapter)

    def test_real_geometry_satisfies_protocol(self):
        assert issubclass(RealParamakGeometryAdapter, GeometryAdapter)

    def test_parametric_neutronics_satisfies_protocol(self):
        assert issubclass(ParametricNeutronicsAdapter, NeutronicsAdapter)

    def test_real_neutronics_satisfies_protocol(self):
        assert issubclass(RealFISPACTNeutronicsAdapter, NeutronicsAdapter)
