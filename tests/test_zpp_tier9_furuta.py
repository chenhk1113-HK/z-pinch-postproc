"""Tier 9 (2026-08-31) — tests for the Furuta 1987 validation result.

Furuta et al. 1987 (J. Nucl. Sci. Technol. 24(4)) published reference
neutron-leakage data for 50 cm radius natural-Li, Fe, Fe+H2O, and
double-layer Li+Fe spheres with 14 MeV D-T source at center.

We ran the natural-Li benchmark and got TBR=0.6565 ± 0.09% (rel).
This is the TOTAL (n,T) reaction rate in natural Li (Li-6 + Li-7).

These tests verify the result is sensible and document the
applicability limit: Tier 8's closed-form was calibrated for
LiPb+Be Z-pinch geometry, NOT for pure-Li spheres.
"""

import os
import sys
import json
import pytest
from pathlib import Path

# Make the code directory importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "code"))

# Path to the Furuta result file (must exist for tests to run)
FURUTA_JSON = Path(
    __file__
).parent.parent / "data" / "results" / "2026-08-31_tier9_furuta" / "furuta_50cm_li.json"


@pytest.fixture(scope="module")
def furuta_result():
    """Load the Furuta 1987 benchmark result (50 cm natural-Li sphere)."""
    if not FURUTA_JSON.exists():
        pytest.skip(
            f"Furuta result file not found at {FURUTA_JSON}. "
            f"Run _tier9_run.py to generate it."
        )
    with open(FURUTA_JSON) as f:
        return json.load(f)


class TestFurutaBenchmark:
    """Tier 9 — Furuta 1987 50 cm natural-Li sphere benchmark."""

    def test_result_file_exists(self):
        """The Tier 9 result file must exist after running the benchmark."""
        assert FURUTA_JSON.exists(), (
            f"Tier 9 Furuta result missing at {FURUTA_JSON}. "
            f"Run _tier9_run.py to generate it."
        )

    def test_neutron_leakage_is_high(self, furuta_result):
        """Natural Li is a poor reflector — most neutrons should leak."""
        leakage = furuta_result["leakage_fraction"]
        assert leakage > 0.85, (
            f"Neutron leakage from 50 cm natural-Li sphere should be > 85% "
            f"(natural Li has high (n,elastic) cross-section but no "
            f"reflector). Got {leakage:.4f}. Furuta 1987 reports "
            f"~95% for this geometry."
        )
        assert leakage < 1.0, (
            f"Leakage cannot exceed 1.0 (it's a fraction). "
            f"Got {leakage:.4f}"
        )

    def test_li7_dominates_in_natural_li(self, furuta_result):
        """For natural Li with 14 MeV neutrons, Li-7 (n,T) is significant
        because Li-7 (n,n'α)T threshold (~2.8 MeV) catches many fast
        neutrons that miss Li-6 (n,T) (which prefers thermal).
        Furuta 1987 noted this."""
        li6 = furuta_result["li6_t_rate"]
        li7 = furuta_result["li7_t_rate"]
        assert li7 > li6, (
            f"Li-7 (n,T) rate ({li7:.4f}) should exceed Li-6 (n,T) "
            f"({li6:.4f}) for 14 MeV neutrons in natural Li. "
            f"Furuta 1987 explicitly notes Li-7 dominates above "
            f"~5 MeV neutron energies."
        )

    def test_total_tbr_in_reasonable_range(self, furuta_result):
        """Total TBR for 50 cm natural-Li sphere should be in [0.5, 1.0]
        range. Below 1.0 = self-sufficient is not met (expected, since
        natural Li at 50 cm is too thin and too leaky)."""
        tbr = furuta_result["TBR_total"]
        assert 0.5 < tbr < 1.0, (
            f"Total TBR for 50 cm natural-Li sphere expected in "
            f"[0.5, 1.0] range. Got {tbr:.4f}. Below 1.0 = blanket "
            f"is not self-sufficient (expected for natural Li)."
        )

    def test_low_statistical_uncertainty(self, furuta_result):
        """Tier 9 should have low relative statistical uncertainty."""
        rel_std = furuta_result["TBR_total_rel_stddev"]
        assert rel_std < 0.01, (
            f"Tier 9 TBR rel stddev should be < 1% (we ran 20k particles "
            f"x 20 batches). Got {rel_std*100:.2f}%"
        )


class TestTier8ApplicabilityLimit:
    """Tier 9 — document that the Tier 8 closed-form is calibrated for
    LiPb+Be Z-pinch geometry, NOT for pure-Li spheres.

    This is honest negative validation: the Tier 8 closed-form
    overshoots by ~100% for pure-Li spheres because it was fitted
    against Z-pinch LiPb+Be Monte Carlo data with different physics
    (Be multiplier saturation, Pb scattering, structural material).
    """

    def test_tier8_overshoots_pure_li_sphere(self, furuta_result):
        """The Tier 8 closed-form (calibrated for LiPb+Be Z-pinch) does
        NOT match pure-Li sphere TBR. This is the honest finding."""
        from zpp_tbr import compute_TBR, TBRInputs
        inp = TBRInputs(
            blanket_material="LiPb",  # closest match; pure Li unavailable
            neutron_multiplier="Be",  # no Be in pure Li
            Li6_enrichment_fraction=0.075,  # natural
            blanket_thickness_cm=50.0,
            first_wall_coverage_fraction=1.0,
            geometry="cylindrical",
            MHD_effect_factor=1.0,
            temperature_factor=1.0,
            boundary_condition="infinite",
        )
        tier8_pred = compute_TBR(inp).TBR
        mc_tbr = furuta_result["TBR_total"]
        delta_pct = abs((tier8_pred - mc_tbr) / mc_tbr)
        assert delta_pct > 0.30, (
            f"Tier 8 should overshoot pure-Li sphere by > 30% (it's "
            f"calibrated for LiPb+Be Z-pinch, not pure Li). "
            f"Got delta_pct={delta_pct*100:.2f}%. If this assertion "
            f"fails, Tier 8 has accidentally become geometry-agnostic "
            f"and we should re-validate against Furuta more carefully."
        )

    def test_applicability_documented(self):
        """The MODEL_ASSUMPTIONS file should document the Tier 8
        applicability limit."""
        model_assumptions = (
            Path(__file__).parent.parent / "MODEL_ASSUMPTIONS_AND_LIMITATIONS.md"
        )
        content = model_assumptions.read_text()
        assert "Furuta" in content or "Tier 9" in content, (
            f"MODEL_ASSUMPTIONS_AND_LIMITATIONS.md should document the "
            f"Tier 9 Furuta 1987 validation. Current file does not "
            f"mention Furuta or Tier 9."
        )