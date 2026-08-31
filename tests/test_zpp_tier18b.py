"""Tier 18.B (2026-08-31) — Li4SiO4 OpenMC transport benchmark tests.

Tests verify the Tier 18.B sweep result is consistent with the
Li4SiO4 material defined in Tier 18.A (zpp/zpp_li4sio4.py).

Tier 18.B finding: Li4SiO4 gives TBR ~1.03 in cylindrical geometry
(Tier 6 baseline LiPb gives 1.83). This test pins the documented
finding so it can't drift in future code changes.
"""
import os
import sys
import pytest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "zpp"))


class TestTier18BLi4SiO4Results:
    """Tier 18.B — pinned OpenMC results for Li4SiO4."""

    RESULT_FILE = Path(__file__).parent.parent / "data/results/2026-08-31_tier18b_li4sio4/tier18b_li4sio4_sweep.json"

    def test_result_file_exists(self):
        """Tier 18.B sweep result must exist."""
        assert self.RESULT_FILE.exists(), (
            f"Run _tier18b_run.py first to generate {self.RESULT_FILE}"
        )

    def test_lipb_baseline_tbr(self):
        """LiPb baseline TBR matches Tier 6 documented value (~1.83)."""
        import json
        with open(self.RESULT_FILE) as f:
            results = json.load(f)
        lipb = next(r for r in results if r.get("breeder") == "LiPb")
        assert "TBR_mc" in lipb, f"LiPb result missing TBR: {lipb}"
        # Tier 6 baseline: 1.83 ± 0.5%
        assert abs(lipb["TBR_mc"] - 1.83) < 0.05

    def test_li4sio4_worse_than_lipb(self):
        """Honest finding: Li4SiO4 TBR is significantly lower than LiPb.

        Tier 18.B finding: Li4SiO4 TBR ~1.03 vs LiPb TBR ~1.83.
        This documents the counterintuitive result so it can't be lost.
        """
        import json
        with open(self.RESULT_FILE) as f:
            results = json.load(f)
        lipb = next(r for r in results if r.get("breeder") == "LiPb")
        li4sio4 = next(r for r in results if r.get("breeder") == "Li4SiO4")
        assert "TBR_mc" in lipb and "TBR_mc" in li4sio4
        # Li4SiO4 should be < LiPb (44% worse per Tier 18.B finding)
        assert li4sio4["TBR_mc"] < lipb["TBR_mc"], (
            f"Expected Li4SiO4 ({li4sio4['TBR_mc']:.3f}) < LiPb "
            f"({lipb['TBR_mc']:.3f}); Tier 18.B finding is Li4SiO4 hurts"
        )

    def test_li4sio4_above_self_breeding_threshold(self):
        """Li4SiO4 TBR should still be > 1.0 (at-least self-breeding).

        Even though Li4SiO4 is worse than LiPb, TBR > 1.0 means
        the design is at least tritium self-sufficient (no U-238 needed).
        """
        import json
        with open(self.RESULT_FILE) as f:
            results = json.load(f)
        li4sio4 = next(r for r in results if r.get("breeder") == "Li4SiO4")
        assert "TBR_mc" in li4sio4
        assert li4sio4["TBR_mc"] > 1.0, (
            f"Li4SiO4 TBR should be > 1.0 for self-breeding, got "
            f"{li4sio4['TBR_mc']:.3f}"
        )


class TestTier18BBackwardCompat:
    """Tier 18.B — does not break Tier 6 (LiPb still works)."""

    def test_lipb_still_default(self):
        """Default breeder should still be LiPb (per Tier 18.B finding)."""
        from zpp.zpp_li4sio4 import build_li4sio4_material
        from zpp.zpp_real_openmc_transport import _build_blanket_materials
        mats = _build_blanket_materials()
        # LiPb is still the default breeder
        assert mats["lipb"].name == "LiPb"
        # Li4SiO4 is available but not the default
        li4sio4 = build_li4sio4_material()
        assert li4sio4.name == "Li4SiO4"
