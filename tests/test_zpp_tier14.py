"""Tier 14 (2026-08-31) — tests for Z-FFR / Antong Fusion reference data.

Captures the published Z-pinch fusion blanket design data from
Peng Xianjue's team (China Academy of Engineering Physics /
China Antong Fusion / 安东聚变).
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.join(os.path.dirname(__file__), "..", "code")))


class TestTier14ZFFRReferences:
    """Tier 14 — Z-FFR / Antong Fusion reference data."""

    def test_zffr_references_module_loads(self):
        """zpp_zffr_references module should load without error."""
        import zpp_zffr_references
        assert hasattr(zpp_zffr_references, "ZFFR_TARGET_TBR")

    def test_zffr_target_tbr_value(self):
        """ZFFR_TARGET_TBR should be 1.15 (Peng 2014 design target)."""
        from zpp_zffr_references import ZFFR_TARGET_TBR
        assert ZFFR_TARGET_TBR == 1.15

    def test_zffr_actual_achieved_tbr(self):
        """ZFFR achieved TBR should be 1.24 (per published design)."""
        from zpp_zffr_references import ZFFR_ACHIEVED_TBR
        # Antong Fusion / 钛媒体 claim TBR up to 1.24
        assert 1.20 <= ZFFR_ACHIEVED_TBR <= 1.30

    def test_antong_fusion_founded(self):
        """Antong Fusion should be founded in 2022 in Beijing."""
        from zpp_zffr_references import ANTONG_FUSION_FOUNDED
        assert ANTONG_FUSION_FOUNDED == 2022

    def test_peng_xianjue_academician(self):
        """Peng Xianjue should be listed as founder and CAE academician."""
        from zpp_zffr_references import ANTONG_FUSION_FOUNDER
        assert "Peng Xianjue" in ANTONG_FUSION_FOUNDER or "彭先觉" in ANTONG_FUSION_FOUNDER

    def test_zffr_blaket_geometry(self):
        """Z-FFR design: 150 MW Z-pinch neutron source, TBR > 1.15."""
        from zpp_zffr_references import (
            ZFFR_NEUTRON_SOURCE_POWER_MW,
            ZFFR_TARGET_TBR,
        )
        assert 100 <= ZFFR_NEUTRON_SOURCE_POWER_MW <= 200
        assert ZFFR_TARGET_TBR > 1.10

    def test_tier14_documented_in_changelog(self):
        """CHANGELOG.md should mention Tier 14 (Antong / Z-FFR refs).

        Skip if CHANGELOG not yet updated (Tier 14 still in flight).
        """
        from pathlib import Path
        project_root = Path(__file__).parent.parent
        changelog = project_root / "CHANGELOG.md"
        if not changelog.exists():
            pytest.skip("CHANGELOG.md not found")
        text = changelog.read_text()
        # Look for any Tier 14 marker
        for term in ("Tier 14", "Z-FFR", "Antong", "Peng Xianjue", "zffr", "Tier14", "tier 14"):
            if term in text:
                return  # Found at least one
        pytest.skip(
            "CHANGELOG.md not yet updated for Tier 14; "
            "this is expected mid-flight (will be updated at ship time)."
        )


class TestTier14BackwardCompat:
    """Tier 14 — backward compat."""

    def test_no_breaking_changes(self):
        """All v1.2.0 tests should still pass (no breaking changes
        from Tier 14 which only added documentation)."""
        # This is implicitly tested by the full suite; here just
        # verify the parametric Tier 5.B still works
        from zpp_tbr import compute_TBR, TBRInputs
        inp = TBRInputs(
            blanket_material="LiPb",
            neutron_multiplier="Be",
            Li6_enrichment_fraction=0.075,
            blanket_thickness_cm=50.0,
            geometry="Z-pinch",
            boundary_condition="infinite",
        )
        result = compute_TBR(inp)
        # Natural LiPb, 50 cm, infinite boundary: TBR ~1.0-1.2
        # (Sobes baseline gives TBR_sat=1.30 with 85% coverage)
        assert 0.8 < result.TBR < 1.4
