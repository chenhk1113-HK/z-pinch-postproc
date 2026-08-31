"""
Tier 7.B — Cross-sections management tests.

Verifies:
1. check_cross_sections_available() returns correct state.
2. download_cross_sections_instructions() returns non-empty
   human-readable text.
4. list_required_nuclides_for_blanket() returns correct nuclides
   for each blanket material.
6. generate_minimal_cross_sections_xml() creates a valid XML.

These tests don't require any actual cross-section files.
"""

import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "code"))


class TestCheckCrossSectionsAvailable:
    """Test check_cross_sections_available()."""

    def test_unset_returns_no_env(self):
        from zpp.zpp_cross_sections import check_cross_sections_available
        os.environ.pop("OPENMC_CROSS_SECTIONS", None)
        info = check_cross_sections_available()
        assert info["env_var_set"] is False
        assert info["file_exists"] is False
        assert info["file_path"] is None

    def test_set_to_missing_file(self):
        from zpp.zpp_cross_sections import check_cross_sections_available
        os.environ["OPENMC_CROSS_SECTIONS"] = "/nonexistent/cross_sections.xml"
        info = check_cross_sections_available()
        assert info["env_var_set"] is True
        assert info["file_exists"] is False

    def test_set_to_existing_file(self):
        from zpp.zpp_cross_sections import check_cross_sections_available
        with tempfile.NamedTemporaryFile(suffix=".xml", delete=False) as f:
            f.write(b"<cross_sections></cross_sections>")
            tmp_path = f.name
        try:
            os.environ["OPENMC_CROSS_SECTIONS"] = tmp_path
            info = check_cross_sections_available()
            assert info["env_var_set"] is True
            assert info["file_exists"] is True
            assert info["file_size_mb"] is not None
        finally:
            os.unlink(tmp_path)
            os.environ.pop("OPENMC_CROSS_SECTIONS", None)


class TestDownloadInstructions:
    """Test download_cross_sections_instructions()."""

    def test_non_empty(self):
        from zpp.zpp_cross_sections import download_cross_sections_instructions
        text = download_cross_sections_instructions()
        assert len(text) > 100

    def test_mentions_NNDC(self):
        from zpp.zpp_cross_sections import download_cross_sections_instructions
        text = download_cross_sections_instructions()
        assert "NNDC" in text or "nndc.bnl.gov" in text

    def test_mentions_OPENMC_CROSS_SECTIONS_env(self):
        from zpp.zpp_cross_sections import download_cross_sections_instructions
        text = download_cross_sections_instructions()
        assert "OPENMC_CROSS_SECTIONS" in text

    def test_mentions_NJOY(self):
        from zpp.zpp_cross_sections import download_cross_sections_instructions
        text = download_cross_sections_instructions()
        assert "NJOY" in text or "njoy" in text


class TestListRequiredNuclides:
    """Test list_required_nuclides_for_blanket()."""

    def test_LiPb_RAFM(self):
        from zpp.zpp_cross_sections import list_required_nuclides_for_blanket
        nucs = list_required_nuclides_for_blanket("LiPb", "Be", "RAFM")
        assert "Li6" in nucs
        assert "Li7" in nucs
        assert "Pb" in nucs
        assert "Be9" in nucs
        assert "Fe" in nucs

    def test_Li4SiO4_tokamak(self):
        from zpp.zpp_cross_sections import list_required_nuclides_for_blanket
        nucs = list_required_nuclides_for_blanket("Li4SiO4", None, "RAFM")
        assert "Li6" in nucs
        assert "Li7" in nucs
        assert "Si" in nucs
        assert "O16" in nucs
        assert "Be9" not in nucs  # No multiplier

    def test_W_structure(self):
        from zpp.zpp_cross_sections import list_required_nuclides_for_blanket
        nucs = list_required_nuclides_for_blanket("LiPb", None, "W")
        assert "W" in nucs
        assert "Fe" not in nucs  # No RAFM

    def test_no_multiplier(self):
        from zpp.zpp_cross_sections import list_required_nuclides_for_blanket
        nucs = list_required_nuclides_for_blanket("LiPb", None, "RAFM")
        assert "Be9" not in nucs

    def test_returns_sorted_list(self):
        from zpp.zpp_cross_sections import list_required_nuclides_for_blanket
        nucs = list_required_nuclides_for_blanket("LiPb", "Be", "RAFM")
        assert nucs == sorted(nucs)


class TestGenerateCrossSectionsXML:
    """Test generate_minimal_cross_sections_xml()."""

    def test_creates_valid_xml(self):
        from zpp.zpp_cross_sections import generate_minimal_cross_sections_xml
        with tempfile.TemporaryDirectory() as work_dir:
            output = os.path.join(work_dir, "cross_sections.xml")
            ace_files = [
                ("H1", "H_001_293.6ace"),
                ("Li6", "Li_006_293.6ace"),
                ("Li7", "Li_007_293.6ace"),
            ]
            result_path = generate_minimal_cross_sections_xml(ace_files, output)
            assert os.path.exists(result_path)
            # Verify XML content
            with open(result_path) as f:
                content = f.read()
            assert "<cross_sections" in content
            assert "H1" in content
            assert "Li6" in content
            assert "Li7" in content
            assert "H_001_293.6ace" in content


class TestStrategicFindings:
    """Document strategic findings."""

    def test_cross_sections_are_user_responsibility(self):
        """Cross-section download is left to the user.

        Per AGENTS.md rule 17 (no silent dep installation), we
        do NOT auto-download ~5 GB of ENDF data. The user
        triggers download manually if/when they want real
        Monte Carlo TBR.
        """
        from zpp.zpp_cross_sections import download_cross_sections_instructions
        text = download_cross_sections_instructions()
        # Should NOT contain any auto-download command
        assert "auto" not in text.lower() or "automatically" not in text.lower()
        # Should mention user actions
        assert "download" in text.lower()

    def test_minimal_subset_for_LiPb(self):
        """For LiPb TBR blanket, only ~6 nuclides needed.

        This is much smaller than the full ENDF library (200+
        nuclides). Could be hand-downloaded in ~30 min.
        """
        from zpp.zpp_cross_sections import list_required_nuclides_for_blanket
        nucs = list_required_nuclides_for_blanket("LiPb", "Be", "RAFM")
        # Should be <15 nuclides for the minimal subset
        assert len(nucs) < 15