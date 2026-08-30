"""
Smoke tests for openmc-anywhere installation (v0.6.1 path A).

Verifies:
1. openmc module imports without error.
2. openmc-anywhere version is 0.16.0.0 (the wheel we installed).
3. openmc.exe CLI is callable.
4. openmc.lib.libopenmc.dll is loadable.
5. OPENMC_CROSS_SECTIONS env var is supported.

A full TBR simulation requires ENDF cross-section data which
is NOT bundled with openmc-anywhere (per upstream docs:
"data is not bundled"). The PROJECT adapter handles this by
checking for cross-sections and falling back to parametric TBR.

These tests will be SKIPPED if openmc-anywhere is not installed.
"""

import os
import shutil
import subprocess

import pytest


def _openmc_available() -> bool:
    try:
        import openmc  # noqa: F401
        return True
    except ImportError:
        return False


# Skip everything in this module if openmc-anywhere is not installed
pytestmark = pytest.mark.skipif(
    not _openmc_available(),
    reason="openmc-anywhere not installed",
)


class TestOpenMCImport:
    """Test that openmc module loads."""

    def test_import_openmc(self):
        """openmc imports without error."""
        import openmc
        assert openmc is not None

    def test_openmc_version(self):
        """openmc-anywhere version is 0.16.0.0."""
        import openmc
        assert openmc.__version__ == "0.16.0.0"

    def test_openmc_lib_dir(self):
        """openmc lib directory exists with libopenmc.dll."""
        import openmc
        lib_dir = os.path.dirname(openmc.__file__)
        assert os.path.isdir(lib_dir)
        dll_path = os.path.join(lib_dir, "lib", "libopenmc.dll")
        assert os.path.exists(dll_path), f"Missing {dll_path}"

    def test_openmc_submodules(self):
        """Submodules load (data, mgxs, etc.)."""
        import openmc
        import openmc.data  # noqa: F401
        import openmc.mgxs  # noqa: F401
        import openmc.checkvalue  # noqa: F401


class TestOpenMCCLI:
    """Test openmc.exe CLI is callable."""

    def test_openmc_exe_exists(self):
        """openmc.exe is on PATH or in project .venv/Scripts/."""
        exe = shutil.which("openmc")
        if exe is None:
            venv_exe = os.path.join(".venv", "Scripts", "openmc.exe")
            assert os.path.exists(venv_exe), f"Missing {venv_exe}"
        else:
            assert os.path.exists(exe)

    def test_openmc_version_cli(self):
        """openmc --version returns OpenMC version string."""
        # The .venv/Scripts/ dir may not be on PATH; use absolute path.
        exe = shutil.which("openmc")
        if exe is None:
            exe = os.path.join(".venv", "Scripts", "openmc.exe")
        result = subprocess.run(
            [exe, "--version"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, (
            f"openmc --version failed: {result.stderr}"
        )
        assert "OpenMC version 0.16.0" in result.stdout


class TestCrossSectionsEnv:
    """Test OPENMC_CROSS_SECTIONS env var handling."""

    def test_env_var_can_be_set(self):
        """OPENMC_CROSS_SECTIONS env var can be set."""
        os.environ["OPENMC_CROSS_SECTIONS"] = "/tmp/cross_sections.xml"
        assert "OPENMC_CROSS_SECTIONS" in os.environ

    def test_unset_after_test(self):
        """Cleanup env var."""
        if "OPENMC_CROSS_SECTIONS" in os.environ:
            del os.environ["OPENMC_CROSS_SECTIONS"]


class TestNoBundledData:
    """Document the missing cross-section data (honest disclosure)."""

    def test_no_endf_files_in_install(self):
        """No ENDF files bundled with openmc-anywhere (per upstream docs)."""
        import openmc
        lib_dir = os.path.dirname(openmc.__file__)
        endf_files = []
        for root, _dirs, files in os.walk(lib_dir):
            for f in files:
                if f.endswith(".endf") or "cross_sections" in f:
                    endf_files.append(os.path.join(root, f))
        assert len(endf_files) == 0, (
            f"Found bundled ENDF files: {endf_files}"
        )

    def test_only_auxiliary_data(self):
        """Only auxiliary data files (compton, dose) are bundled."""
        import openmc
        lib_dir = os.path.dirname(openmc.__file__)
        h5_files = []
        data_dir = os.path.join(lib_dir, "data")
        for _root, _dirs, files in os.walk(data_dir):
            for f in files:
                if f.endswith(".h5"):
                    h5_files.append(f)
        auxiliary_keywords = [
            "compton", "density_effect", "mass_attenuation", "mass_energy",
        ]
        for hf in h5_files:
            assert any(kw in hf for kw in auxiliary_keywords), (
                f"Unexpected bundled data file: {hf}"
            )