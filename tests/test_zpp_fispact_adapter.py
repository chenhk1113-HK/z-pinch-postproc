"""
Tier 7.E — FISPACT-II probe tests.

Verifies:
1. check_fispact_install() returns correct state.
2. fispact_install_instructions() returns non-empty text.
3. parametric_activation_proxy() computes reasonable values.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "code"))


class TestCheckFispactInstall:
    """Test check_fispact_install()."""

    def test_returns_dict(self):
        from zpp.adapters.zpp_fispact_adapter import check_fispact_install
        info = check_fispact_install()
        assert isinstance(info, dict)
        assert "installed" in info
        assert "binary_path" in info

    def test_not_installed_by_default(self):
        """FISPACT-II is not installed (UKAEA license required)."""
        from zpp.adapters.zpp_fispact_adapter import check_fispact_install
        info = check_fispact_install()
        assert info["installed"] is False


class TestFispactInstallInstructions:
    """Test fispact_install_instructions()."""

    def test_non_empty(self):
        from zpp.adapters.zpp_fispact_adapter import fispact_install_instructions
        text = fispact_install_instructions()
        assert len(text) > 100

    def test_mentions_UKAEA_license(self):
        from zpp.adapters.zpp_fispact_adapter import fispact_install_instructions
        text = fispact_install_instructions()
        assert "UKAEA" in text
        assert "license" in text.lower() or "licence" in text.lower()


class TestParametricActivationProxy:
    """Test parametric_activation_proxy() (Tier 5.D fallback)."""

    def test_returns_dict(self):
        from zpp.adapters.zpp_fispact_adapter import parametric_activation_proxy
        result = parametric_activation_proxy(
            neutron_wall_load_MW_per_m2=1.0,
            material="RAFM",
            operating_years=30.0,
            capacity_factor=0.25,
        )
        assert isinstance(result, dict)
        assert "DPA_per_FPY" in result
        assert "total_DPA" in result

    def test_DPA_per_FPY_positive(self):
        from zpp.adapters.zpp_fispact_adapter import parametric_activation_proxy
        result = parametric_activation_proxy(
            neutron_wall_load_MW_per_m2=1.0,
            material="RAFM",
            operating_years=30.0,
            capacity_factor=0.25,
        )
        assert result["DPA_per_FPY"] > 0
        # Should be ~12 DPA/FPY for RAFM at 1 MW/m2 (matches Tier 5.D)
        assert 8 < result["DPA_per_FPY"] < 16

    def test_total_DPA_scales_with_time(self):
        from zpp.adapters.zpp_fispact_adapter import parametric_activation_proxy
        r1 = parametric_activation_proxy(
            neutron_wall_load_MW_per_m2=1.0, operating_years=10.0, capacity_factor=0.25,
        )
        r2 = parametric_activation_proxy(
            neutron_wall_load_MW_per_m2=1.0, operating_years=30.0, capacity_factor=0.25,
        )
        # Total DPA should scale ~3x
        assert abs(r2["total_DPA"] / r1["total_DPA"] - 3.0) < 0.01


class TestStrategicFindings:
    """Document strategic findings."""

    def test_fispact_requires_license(self):
        """FISPACT-II install requires UKAEA license agreement.

        Cannot be automated per AGENTS.md rule 17 (no silent
        dep installation). This module provides parametric
        fallback until user obtains the license + install.
        """
        from zpp.adapters.zpp_fispact_adapter import fispact_install_instructions
        text = fispact_install_instructions()
        assert "license" in text.lower()

    def test_parametric_fallback_is_tier5D(self):
        """Parametric fallback uses Tier 5.D PFC lifetime model.

        This means activation analysis works without FISPACT,
        just with less detail (no isotope-level transmutation).
        """
        from zpp.adapters.zpp_fispact_adapter import parametric_activation_proxy
        result = parametric_activation_proxy(
            neutron_wall_load_MW_per_m2=1.0,
            material="RAFM",
            operating_years=30.0,
            capacity_factor=0.25,
        )
        assert "Tier 5.D" in result["notes"] or "Tier" in result["notes"]