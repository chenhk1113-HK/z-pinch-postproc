"""
Adapter interfaces for real upstream codes.

The v0.4-v0.5 modules (zpp_process_bop, zpp_tbr, zpp_geometry,
zpp_pfc_lifetime) are **parametric replacements** for real
PROCESS, OpenMC, Paramak, and FISPACT codes. This module
documents how to swap them for real upstream calls.

Per AGENTS.md rule 17, no new dependencies are installed without
explicit user approval. When the user approves installing
PROCESS/OpenMC, the stubs here can be implemented to use them.

Reference adapters:
- BOPAdapter: interface for BOP model. Default impl: zpp_process_bop.
- TBRAdapter: interface for TBR model. Default impl: zpp_tbr.
- GeometryAdapter: interface for geometry. Default impl: zpp_geometry.
- NeutronicsAdapter: interface for DPA / activation. Default
  impl: zpp_pfc_lifetime.

To swap in real PROCESS:
    from process.io import process_main
    class RealProcessBOPAdapter(BOPAdapter):
        def compute(self, inputs):
            # Run PROCESS in subprocess, parse output
            result_dict = process_main.main(...)
            return ProcessBOPResult(...)

To swap in real OpenMC:
    import openmc
    class RealOpenMCTBRAdapter(TBRAdapter):
        def compute(self, inputs):
            model = openmc.Model(...)
            sp = openmc.StatePoint(...)
            tbr = sp.get_tally(...).mean
            return TBRResult(...)

See the README for installation instructions for each upstream zpp.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from zpp.zpp_process_bop import (
    PlantBOPInputs, compute_process_bop, ProcessBOPResult,
)
from zpp.zpp_tbr import (
    TBRInputs, compute_TBR, TBRResult,
)
from zpp.zpp_geometry import (
    ZIFERadialBuild, get_build,
)
from zpp.zpp_pfc_lifetime import (
    PFCDamageInputs, first_wall_lifetime, PFCDamageResult,
)


class BOPAdapter(ABC):
    """Abstract interface for BOP (balance-of-plant) models.

    Default implementation: zpp_process_bop.compute_process_bop.
    Real implementation: PROCESS (UKAEA, MIT license).
    """

    @abstractmethod
    def compute(self, inputs: PlantBOPInputs) -> ProcessBOPResult:
        """Run BOP model and return ProcessBOPResult."""
        ...


class ParametricBOPAdapter(BOPAdapter):
    """Default BOP adapter using the parametric model (v0.4-A)."""

    def compute(self, inputs: PlantBOPInputs) -> ProcessBOPResult:
        return compute_process_bop(inputs)


# Stub for real PROCESS adapter. Per AGENTS.md rule 17,
# implementation requires explicit user approval.
class RealProcessBOPAdapter(BOPAdapter):
    """Stub for real PROCESS adapter.

    To implement: install PROCESS, then wrap subprocess call:
        from process.io import process_main
    See https://github.com/ukaea/PROCESS for installation.
    """

    def compute(self, inputs: PlantBOPInputs) -> ProcessBOPResult:
        raise NotImplementedError(
            "RealProcessBOPAdapter requires PROCESS to be installed. "
            "Per AGENTS.md rule 17, install requires explicit user approval. "
            "Use ParametricBOPAdapter for the parametric replacement, or "
            "approve installing PROCESS via 'pip install process-ukaea' "
            "(check upstream for current install command)."
        )


class TBRAdapter(ABC):
    """Abstract interface for TBR (tritium breeding ratio) models.

    Default implementation: zpp_tbr.compute_TBR.
    Real implementation: OpenMC (MIT license).
    """

    @abstractmethod
    def compute(self, inputs: TBRInputs) -> TBRResult:
        """Run TBR model and return TBRResult."""
        ...


class ParametricTBRAdapter(TBRAdapter):
    """Default TBR adapter using the parametric model (v0.4-B)."""

    def compute(self, inputs: TBRInputs) -> TBRResult:
        return compute_TBR(inputs)


class RealOpenMCTBRAdapter(TBRAdapter):
    """Stub for real OpenMC adapter.

    To implement: install OpenMC, then use the openmc.Model API:
        import openmc
    See https://openmc.org for installation.
    """

    def compute(self, inputs: TBRInputs) -> TBRResult:
        raise NotImplementedError(
            "RealOpenMCTBRAdapter requires OpenMC to be installed. "
            "Per AGENTS.md rule 17, install requires explicit user approval. "
            "Use ParametricTBRAdapter for the parametric replacement, or "
            "approve installing OpenMC via 'conda install -c conda-forge openmc' "
            "(check upstream for current install command)."
        )


class GeometryAdapter(ABC):
    """Abstract interface for radial-build geometry models.

    Default implementation: zpp_geometry (cylindrical parametric).
    Real implementation: Paramak (MIT license, fusion-energy/paramak).
    """

    @abstractmethod
    def get_build(self, name: str) -> ZIFERadialBuild:
        """Get a radial build by name."""
        ...


class ParametricGeometryAdapter(GeometryAdapter):
    """Default geometry adapter using the parametric model (v0.4-C)."""

    def get_build(self, name: str) -> ZIFERadialBuild:
        return get_build(name)


class RealParamakGeometryAdapter(GeometryAdapter):
    """Stub for real Paramak adapter.

    To implement: install Paramak, then use the Paramak API:
        from paramak import TokamakFromNeutronics
    See https://github.com/fusion-energy/paramak for installation.
    """

    def get_build(self, name: str) -> ZIFERadialBuild:
        raise NotImplementedError(
            "RealParamakGeometryAdapter requires Paramak to be installed. "
            "Per AGENTS.md rule 17, install requires explicit user approval. "
            "Use ParametricGeometryAdapter for the parametric replacement, or "
            "approve installing Paramak via 'pip install paramak' "
            "(check upstream for current install command)."
        )


class NeutronicsAdapter(ABC):
    """Abstract interface for PFC damage / neutronics models.

    Default implementation: zpp_pfc_lifetime (NRT + MHD power-law).
    Real implementation: FISPACT-II (UKAEA, BSD license).
    """

    @abstractmethod
    def compute(self, inputs: PFCDamageInputs) -> PFCDamageResult:
        """Run neutronics model and return PFCDamageResult."""
        ...


class ParametricNeutronicsAdapter(NeutronicsAdapter):
    """Default neutronics adapter using the parametric model (v0.5-D)."""

    def compute(self, inputs: PFCDamageInputs) -> PFCDamageResult:
        return first_wall_lifetime(inputs)


class RealFISPACTNeutronicsAdapter(NeutronicsAdapter):
    """Stub for real FISPACT-II adapter.

    To implement: install FISPACT-II (UKAEA, requires licence):
        # FISPACT is not pip-installable; needs manual install.
    See https://fispact.ukaea.uk/ for installation.
    """

    def compute(self, inputs: PFCDamageInputs) -> PFCDamageResult:
        raise NotImplementedError(
            "RealFISPACTNeutronicsAdapter requires FISPACT-II to be installed. "
            "FISPACT requires a UKAEA license; not pip-installable. "
            "Use ParametricNeutronicsAdapter for the parametric replacement."
        )


# ---------------------------------------------------------------------------
# Adapter registry for the integrated simulation
# ---------------------------------------------------------------------------

@dataclass
class AdapterSet:
    """Bundle of all upstream adapters for the integrated simulation.

    Defaults: all parametric. To swap in real upstream codes,
    override the relevant field with a real adapter (after
    installation approval).
    """
    bop: BOPAdapter = None
    tbr: TBRAdapter = None
    geometry: GeometryAdapter = None
    neutronics: NeutronicsAdapter = None

    def __post_init__(self):
        if self.bop is None:
            self.bop = ParametricBOPAdapter()
        if self.tbr is None:
            self.tbr = ParametricTBRAdapter()
        if self.geometry is None:
            self.geometry = ParametricGeometryAdapter()
        if self.neutronics is None:
            self.neutronics = ParametricNeutronicsAdapter()


def make_parametric_set() -> AdapterSet:
    """Convenience function: all parametric adapters."""
    return AdapterSet()


def swap_adapter(
    adapter_set: AdapterSet,
    component: str,
    new_adapter,
) -> AdapterSet:
    """Return a new AdapterSet with one component swapped.

    Args:
        adapter_set: Original set.
        component: One of "bop", "tbr", "geometry", "neutronics".
        new_adapter: The new adapter instance.

    Returns:
        New AdapterSet with the swap applied.
    """
    import dataclasses
    new_set = dataclasses.replace(adapter_set, **{component: new_adapter})
    return new_set


def list_install_instructions() -> dict:
    """Document the install commands for real upstream codes.

    Per AGENTS.md rule 17, none of these should be run without
    explicit user approval. Use this dict as a reference.
    """
    return {
        "PROCESS": {
            "url": "https://github.com/ukaea/PROCESS",
            "license": "MIT",
            "install_command": "git clone https://github.com/ukaea/PROCESS && cd PROCESS && pip install .",
            "requires_approval": True,
        },
        "OpenMC": {
            "url": "https://openmc.org",
            "license": "MIT",
            "install_command": "conda install -c conda-forge openmc",
            "requires_approval": True,
        },
        "Paramak": {
            "url": "https://github.com/fusion-energy/paramak",
            "license": "MIT",
            "install_command": "pip install paramak",
            "requires_approval": True,
        },
        "FISPACT-II": {
            "url": "https://fispact.ukaea.uk/",
            "license": "UKAEA license (free for academic use)",
            "install_command": "Manual download + license from UKAEA; not pip-installable.",
            "requires_approval": True,
        },
    }
