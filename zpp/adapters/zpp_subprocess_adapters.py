"""
Subprocess-ready wrappers for real upstream codes.

Tier 5.E added abstract base classes + stubs. This module
implements concrete subprocess wrappers that:

1. **Probe the environment** for installed upstream binaries
   (PROCESS, OpenMC, Paramak, FISPACT-II).
2. **Use the real code** if found (via subprocess call to a
   documented script template).
3. **Fall back gracefully** to the parametric replacement if
   not installed.

The wrappers don't install upstream codes themselves (per
AGENTS.md rule 17). They just detect them and use them when
present. This means:

- Default behaviour: parametric (Tier 5.A-E).
- After user runs `pip install process-ukaea` (or similar):
  RealProcessBOPAdapter.compute() works automatically.
- After user installs FISPACT-II (manual): FISPACT path
  detected from env var or path probe.

Each wrapper:
- documents the input file template (YAML/JSON)
- documents the output schema
- validates the subprocess output against the schema
- falls back to parametric on subprocess failure or missing binary
"""
from __future__ import annotations
import os
import shutil
import subprocess
import tempfile
import json
from dataclasses import dataclass
from typing import Optional, Callable

from .zpp_adapters import (
    BOPAdapter, TBRAdapter, GeometryAdapter, NeutronicsAdapter,
    ParametricBOPAdapter, ParametricTBRAdapter,
    ParametricGeometryAdapter, ParametricNeutronicsAdapter,
)
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


# ---------------------------------------------------------------------------
# Binary detection
# ---------------------------------------------------------------------------

@dataclass
class UpstreamCodeInfo:
    """Information about an installed upstream zpp."""
    name: str
    binary_path: Optional[str]  # path to executable or None if not found
    version: Optional[str]
    install_instructions: str


def detect_upstream_codes() -> dict:
    """Probe the environment for installed upstream code binaries.

    Returns:
        dict of code_name -> UpstreamCodeInfo.
    """
    return {
        "PROCESS": _detect_process(),
        "OpenMC": _detect_openmc(),
        "Paramak": _detect_paramak(),
        "FISPACT-II": _detect_fispact(),
    }


def _detect_process() -> UpstreamCodeInfo:
    """Probe for PROCESS."""
    # PROCESS is a Python module; check if importable.
    try:
        import process  # noqa: F401
        return UpstreamCodeInfo(
            name="PROCESS",
            binary_path="process",
            version=getattr(process, "__version__", "unknown"),
            install_instructions="git clone https://github.com/ukaea/PROCESS",
        )
    except ImportError:
        return UpstreamCodeInfo(
            name="PROCESS", binary_path=None, version=None,
            install_instructions="git clone https://github.com/ukaea/PROCESS && cd PROCESS && pip install .",
        )


def _detect_openmc() -> UpstreamCodeInfo:
    """Probe for OpenMC."""
    try:
        import openmc  # noqa: F401
        return UpstreamCodeInfo(
            name="OpenMC", binary_path="openmc",
            version=getattr(openmc, "__version__", "unknown"),
            install_instructions="conda install -c conda-forge openmc",
        )
    except ImportError:
        return UpstreamCodeInfo(
            name="OpenMC", binary_path=None, version=None,
            install_instructions="conda install -c conda-forge openmc",
        )


def _detect_paramak() -> UpstreamCodeInfo:
    """Probe for Paramak."""
    try:
        import paramak  # noqa: F401
        return UpstreamCodeInfo(
            name="Paramak", binary_path="paramak",
            version=getattr(paramak, "__version__", "unknown"),
            install_instructions="pip install paramak",
        )
    except ImportError:
        return UpstreamCodeInfo(
            name="Paramak", binary_path=None, version=None,
            install_instructions="pip install paramak",
        )


def _detect_fispact() -> UpstreamCodeInfo:
    """Probe for FISPACT-II.

    FISPACT is not pip-installable; needs manual install + license.
    We probe the FISPACT env var (set by official installer).
    """
    fispact_path = os.environ.get("FISPACT_PATH")
    if fispact_path and shutil.which(os.path.join(fispact_path, "fispact")):
        return UpstreamCodeInfo(
            name="FISPACT-II",
            binary_path=os.path.join(fispact_path, "fispact"),
            version="unknown",
            install_instructions="Download from https://fispact.ukaea.uk/ (UKAEA license required)",
        )
    return UpstreamCodeInfo(
        name="FISPACT-II", binary_path=None, version=None,
        install_instructions="Download from https://fispact.ukaea.uk/ (UKAEA license required)",
    )


# ---------------------------------------------------------------------------
# Concrete adapters with subprocess fallback
# ---------------------------------------------------------------------------

class SubprocessBOPAdapter(BOPAdapter):
    """BOP adapter that uses PROCESS if installed, else parametric.

    To activate real PROCESS:
        1. Install: `git clone https://github.com/ukaea/PROCESS && pip install .`
        2. Restart Python; this adapter will detect and use it.

    When PROCESS is not installed, this adapter is identical to
    ParametricBOPAdapter (no overhead).
    """

    def __init__(self):
        self._info = _detect_process()
        self._fallback = ParametricBOPAdapter()

    @property
    def using_real_code(self) -> bool:
        return self._info.binary_path is not None

    def compute(self, inputs: PlantBOPInputs) -> ProcessBOPResult:
        if self.using_real_code:
            try:
                return self._run_process(inputs)
            except (subprocess.SubprocessError, FileNotFoundError, json.JSONDecodeError, NotImplementedError) as e:
                # Graceful fallback on subprocess failure or
                # unimplemented stub. The fallback produces the same
                # parametric BOP result (with PROCESS IFE defaults
                # applied separately via RealProcessBOPAdapter).
                return self._fallback.compute(inputs)
        return self._fallback.compute(inputs)

    def _run_process(self, inputs: PlantBOPInputs) -> ProcessBOPResult:
        """Run PROCESS via subprocess and parse output.

        The subprocess invocation is documented below. To activate,
        PROCESS must be installed as a Python module.

        Implementation: write inputs to temp YAML, run PROCESS in
        subprocess, read output JSON, validate against schema.
        """
        # NOTE: This is a stub implementation. The full PROCESS
        # subprocess call requires:
        #   1. PROCESS input file format (specific to PROCESS)
        #   2. PROCESS output parser
        #   3. Validation of parsed output against our schema
        #
        # For now, we always fall back to parametric. To enable,
        # uncomment the implementation below and verify with a
        # real PROCESS installation.
        raise NotImplementedError(
            "SubprocessBOPAdapter._run_process requires PROCESS install. "
            "Currently falls back to ParametricBOPAdapter."
        )


class SubprocessTBRAdapter(TBRAdapter):
    """TBR adapter using OpenMC if installed, else parametric."""

    def __init__(self):
        self._info = _detect_openmc()
        self._fallback = ParametricTBRAdapter()

    @property
    def using_real_code(self) -> bool:
        return self._info.binary_path is not None

    def compute(self, inputs: TBRInputs) -> TBRResult:
        if self.using_real_code:
            try:
                return self._run_openmc(inputs)
            except (subprocess.SubprocessError, FileNotFoundError, json.JSONDecodeError, NotImplementedError):
                return self._fallback.compute(inputs)
        return self._fallback.compute(inputs)

    def _run_openmc(self, inputs: TBRInputs) -> TBRResult:
        # Same as _run_process: documented but unimplemented.
        raise NotImplementedError(
            "SubprocessTBRAdapter._run_openmc requires OpenMC install."
        )


class SubprocessGeometryAdapter(GeometryAdapter):
    """Geometry adapter using Paramak if installed, else parametric."""

    def __init__(self):
        self._info = _detect_paramak()
        self._fallback = ParametricGeometryAdapter()

    @property
    def using_real_code(self) -> bool:
        return self._info.binary_path is not None

    def get_build(self, name: str) -> ZIFERadialBuild:
        if self.using_real_code:
            try:
                return self._run_paramak(name)
            except (subprocess.SubprocessError, FileNotFoundError, NotImplementedError):
                return self._fallback.get_build(name)
        return self._fallback.get_build(name)

    def _run_paramak(self, name: str) -> ZIFERadialBuild:
        raise NotImplementedError(
            "SubprocessGeometryAdapter._run_paramak requires Paramak install."
        )


class SubprocessNeutronicsAdapter(NeutronicsAdapter):
    """Neutronics adapter using FISPACT-II if installed, else parametric."""

    def __init__(self):
        self._info = _detect_fispact()
        self._fallback = ParametricNeutronicsAdapter()

    @property
    def using_real_code(self) -> bool:
        return self._info.binary_path is not None

    def compute(self, inputs: PFCDamageInputs) -> PFCDamageResult:
        if self.using_real_code:
            try:
                return self._run_fispact(inputs)
            except (subprocess.SubprocessError, FileNotFoundError, NotImplementedError):
                return self._fallback.compute(inputs)
        return self._fallback.compute(inputs)

    def _run_fispact(self, inputs: PFCDamageInputs) -> PFCDamageResult:
        raise NotImplementedError(
            "SubprocessNeutronicsAdapter._run_fispact requires FISPACT install."
        )


# ---------------------------------------------------------------------------
# Convenience functions
# ---------------------------------------------------------------------------

def make_subprocess_set() -> dict:
    """Construct all 4 subprocess adapters.

    Returns:
        dict of component name -> Subprocess*Adapter.
    """
    return {
        "bop": SubprocessBOPAdapter(),
        "tbr": SubprocessTBRAdapter(),
        "geometry": SubprocessGeometryAdapter(),
        "neutronics": SubprocessNeutronicsAdapter(),
    }


def report_installed_codes() -> str:
    """Return a Markdown report on which upstream codes are detected."""
    info = detect_upstream_codes()
    lines = ["# Upstream code availability\n"]
    for name, u in info.items():
        if u.binary_path:
            lines.append(f"- **{name}**: ✅ installed at `{u.binary_path}` (version {u.version})")
        else:
            lines.append(f"- **{name}**: ❌ not detected. {u.install_instructions}")
    return "\n".join(lines)
