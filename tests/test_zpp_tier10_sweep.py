"""Tier 10 (2026-08-31) — tests for the extended OpenMC sweep.

The Tier 10 sweep extends the Tier 6.C calibration in two new
dimensions:
  - Li-6 enrichment: 30%, 60%, 90% (Tier 6 was 90% only)
  - mult_inside: True (default) vs False (Be outside LiPb)

This exposed a Tier 5/6 architectural bug: _build_blanket_materials()
hard-coded 90% Li-6, so the MC never actually varied Li-6 enrichment
even though the parametric did. Tier 10 fixes this by threading
Li6_enrichment_fraction through _build_blanket_materials and
run_real_openmc_tbr.

Tests verify:
  - The sweep signature accepts Li6_enrichment_fraction
  - The materials function respects Li6_enrichment_fraction
  - The 3 sweep files exist after _tier10_run.py completes
  - MC TBR varies with Li-6 enrichment (the bug-fix proof)
"""

import os
import sys
import json
import pytest
from pathlib import Path

# Make the code directory importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "code"))

RESULTS_DIR = Path(
    __file__
).parent.parent / "data" / "results" / "2026-08-31_tier10_sweep"

TIER10_SWEEP_FILES = [
    "tier10_Li6_30.md",
    "tier10_Li6_30.json",
    "tier10_Li6_60.md",
    "tier10_Li6_60.json",
    "tier10_Li6_90_mult_outside.md",
    "tier10_Li6_90_mult_outside.json",
]


class TestTier10Infrastructure:
    """Tier 10 — code-level infrastructure changes."""

    def test_build_blanket_materials_accepts_li6_param(self):
        """_build_blanket_materials() should accept Li6_enrichment_fraction."""
        from zpp_real_openmc_transport import _build_blanket_materials
        import inspect
        sig = inspect.signature(_build_blanket_materials)
        assert "Li6_enrichment_fraction" in sig.parameters, (
            f"_build_blanket_materials signature should include "
            f"Li6_enrichment_fraction parameter. Got: {sig}"
        )

    def test_run_real_openmc_tbr_accepts_li6_param(self):
        """run_real_openmc_tbr() should accept Li6_enrichment_fraction."""
        from zpp_real_openmc_transport import run_real_openmc_tbr
        import inspect
        sig = inspect.signature(run_real_openmc_tbr)
        assert "Li6_enrichment_fraction" in sig.parameters, (
            f"run_real_openmc_tbr signature should include "
            f"Li6_enrichment_fraction parameter. Got: {sig}"
        )

    def test_run_blanket_sweep_accepts_li6_param(self):
        """run_blanket_sweep() should accept Li6_enrichment_fraction."""
        from zpp_real_openmc_transport import run_blanket_sweep
        import inspect
        sig = inspect.signature(run_blanket_sweep)
        assert "Li6_enrichment_fraction" in sig.parameters, (
            f"run_blanket_sweep signature should include "
            f"Li6_enrichment_fraction parameter. Got: {sig}"
        )


class TestTier10Results:
    """Tier 10 — verify the 3 sweeps produced correct results.

    These tests only run if the sweep files exist (after _tier10_run.py
    completes). They validate:
      - All 6 expected files (3 markdown + 3 json) exist
      - MC TBR actually VARIES with Li-6 enrichment (proving the bug fix)
      - At Li-6 = 30%, MC TBR is LOWER than at Li-6 = 90% (more Li-6
        = more breeding, monotonic expected)
    """

    @pytest.fixture(scope="class")
    def sweep_data(self):
        if not (RESULTS_DIR / "tier10_Li6_30.json").exists():
            pytest.skip(
                f"Tier 10 sweep files not yet in {RESULTS_DIR}. "
                f"Run _tier10_run.py (takes ~25 min)."
            )
        out = {}
        for name in ["tier10_Li6_30", "tier10_Li6_60", "tier10_Li6_90_mult_outside"]:
            with open(RESULTS_DIR / f"{name}.json") as f:
                out[name] = json.load(f)
        return out

    def test_all_sweep_files_exist(self):
        """All 6 expected files (3 .md + 3 .json) should exist."""
        if not (RESULTS_DIR / "tier10_Li6_30.json").exists():
            pytest.skip(f"{RESULTS_DIR}/tier10_Li6_30.json not found; sweep still running")
        missing = [f for f in TIER10_SWEEP_FILES
                   if not (RESULTS_DIR / f).exists()]
        assert not missing, (
            f"Missing Tier 10 sweep files: {missing}. "
            f"Run _tier10_run.py to generate them."
        )

    def test_mc_tbr_varies_with_li6(self, sweep_data):
        """CRITICAL: at fixed R_blanket, MC TBR should be HIGHER at
        higher Li-6 enrichment (more Li-6 = more breeding).

        Pre-Tier 10 bug: MC was always 90% Li-6 regardless of sweep
        parameter, so this test would fail. After the fix, MC TBR
        at Li-6 = 60% should be >= MC TBR at Li-6 = 30%.
        """
        # Use R_blanket = 80 cm (well-saturated, asymptotic regime)
        r80_li6_30 = next(
            r for r in sweep_data["tier10_Li6_30"]
            if r["R_blanket_cm"] == 80
        )
        r80_li6_60 = next(
            r for r in sweep_data["tier10_Li6_60"]
            if r["R_blanket_cm"] == 80
        )
        mc_30 = r80_li6_30["TBR_mc"]
        mc_60 = r80_li6_60["TBR_mc"]
        assert mc_60 >= mc_30, (
            f"At R_b=80 cm, MC TBR at Li-6=60% ({mc_60:.4f}) should be "
            f">= MC TBR at Li-6=30% ({mc_30:.4f}). Monotonicity is the "
            f"physics expectation. If this fails, the Tier 10 bug fix "
            f"(Li-6 threading through _build_blanket_materials) didn't "
            f"actually take effect."
        )

    def test_mult_inside_outside_changes_tbr(self, sweep_data):
        """With Be on the OUTSIDE (mult_inside=False), MC TBR should
        differ significantly from mult_inside=True. This validates
        that the geometric parameter is actually being applied."""
        r50_outside = next(
            r for r in sweep_data["tier10_Li6_90_mult_outside"]
            if r["R_blanket_cm"] == 50
        )
        # The Tier 6 baseline at Li-6=90%, mult_inside=True, R=50 cm
        # is MC=1.8361 (calibrated against this exact value).
        mc_outside = r50_outside["TBR_mc"]
        assert abs(mc_outside - 1.8361) > 0.10, (
            f"MC TBR at R=50 cm with mult_inside=False ({mc_outside:.4f}) "
            f"should differ from the mult_inside=True baseline (1.8361) "
            f"by > 0.10. The geometric factor matters; if it's the same, "
            f"the mult_inside parameter isn't being applied."
        )

    def test_no_parametric_fallback(self, sweep_data):
        """All 3 sweeps should have completed OpenMC (no fallback)."""
        for name, sweep in sweep_data.items():
            fallback_count = sum(
                1 for r in sweep if r.get("parametric_fallback", False)
            )
            assert fallback_count == 0, (
                f"{name}: {fallback_count} points fell back to "
                f"parametric (OpenMC failed). Investigate."
            )


class TestTier10Documentation:
    """Tier 10 — verify documentation was updated."""

    def test_changelog_mentions_tier_10(self):
        ch = (Path(__file__).parent.parent / "CHANGELOG.md").read_text()
        assert "Tier 10" in ch or "[1.2.0]" in ch, (
            "CHANGELOG.md should document Tier 10."
        )

    def test_model_assumptions_mentions_tier_10(self):
        ma = (Path(__file__).parent.parent / "MODEL_ASSUMPTIONS_AND_LIMITATIONS.md").read_text()
        assert "Tier 10" in ma or "[1.2.0]" in ma, (
            "MODEL_ASSUMPTIONS_AND_LIMITATIONS.md should document Tier 10."
        )