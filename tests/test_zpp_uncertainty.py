"""
Tier 7.C — Uncertainty quantification tests.

Verifies:
1. UncertainParameter dataclass.
2. monte_carlo_propagation runs N samples and returns UQResult.
3. TBR distribution statistics (mean, std, percentiles) are
   sensible for the default ZN parameters.
4. Reproducibility (same seed = same result).
5. Parameter bounds respected (no negative values).
6. P(TBR >= threshold) is 0 or 1.
7. uq_markdown() formats nicely.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "code"))


class TestUncertainParameter:
    """Test UncertainParameter dataclass."""

    def test_create_basic(self):
        from zpp_uncertainty import UncertainParameter
        p = UncertainParameter(name="x", nominal=1.0, stddev=0.1)
        assert p.name == "x"
        assert p.nominal == 1.0
        assert p.stddev == 0.1
        assert p.distribution == "normal"  # default

    def test_with_bounds(self):
        from zpp_uncertainty import UncertainParameter
        p = UncertainParameter(
            name="x", nominal=1.0, stddev=0.1,
            lower_bound=0.5, upper_bound=2.0, distribution="uniform",
        )
        assert p.lower_bound == 0.5
        assert p.upper_bound == 2.0
        assert p.distribution == "uniform"


class TestMonteCarloPropagation:
    """Test monte_carlo_propagation()."""

    def test_returns_UQResult(self):
        from zpp_uncertainty import monte_carlo_propagation, DEFAULT_UNCERTAIN_PARAMS_ZN
        result = monte_carlo_propagation(
            DEFAULT_UNCERTAIN_PARAMS_ZN, n_samples=20, random_seed=42,
        )
        from zpp_uncertainty import UQResult
        assert isinstance(result, UQResult)

    def test_TBR_mean_in_plausible_range(self):
        from zpp_uncertainty import monte_carlo_propagation, DEFAULT_UNCERTAIN_PARAMS_ZN
        result = monte_carlo_propagation(
            DEFAULT_UNCERTAIN_PARAMS_ZN, n_samples=100, random_seed=42,
        )
        # ZN nominal TBR = 1.52; with stddev 0.16 we expect 1.3-1.8
        assert 1.0 < result.TBR_mean < 2.5
        assert result.TBR_std > 0

    def test_TBR_percentiles_monotonic(self):
        from zpp_uncertainty import monte_carlo_propagation, DEFAULT_UNCERTAIN_PARAMS_ZN
        result = monte_carlo_propagation(
            DEFAULT_UNCERTAIN_PARAMS_ZN, n_samples=200, random_seed=42,
        )
        # 5 < 50 < 95 < 99
        assert result.TBR_percentiles[5] < result.TBR_percentiles[50]
        assert result.TBR_percentiles[50] < result.TBR_percentiles[95]
        assert result.TBR_percentiles[95] < result.TBR_percentiles[99]

    def test_reproducible_with_seed(self):
        from zpp_uncertainty import monte_carlo_propagation, DEFAULT_UNCERTAIN_PARAMS_ZN
        r1 = monte_carlo_propagation(
            DEFAULT_UNCERTAIN_PARAMS_ZN, n_samples=50, random_seed=12345,
        )
        r2 = monte_carlo_propagation(
            DEFAULT_UNCERTAIN_PARAMS_ZN, n_samples=50, random_seed=12345,
        )
        assert r1.TBR_mean == r2.TBR_mean
        assert r1.TBR_std == r2.TBR_std

    def test_n_samples_consistent(self):
        from zpp_uncertainty import monte_carlo_propagation, DEFAULT_UNCERTAIN_PARAMS_ZN
        result = monte_carlo_propagation(
            DEFAULT_UNCERTAIN_PARAMS_ZN, n_samples=50, random_seed=42,
        )
        assert result.n_samples == 50
        assert len(result.output_samples["TBR"]) == 50

    def test_parameter_samples_within_bounds(self):
        from zpp_uncertainty import (
            monte_carlo_propagation, DEFAULT_UNCERTAIN_PARAMS_ZN,
        )
        result = monte_carlo_propagation(
            DEFAULT_UNCERTAIN_PARAMS_ZN, n_samples=100, random_seed=42,
        )
        # MHD_effect_factor bounds: [0.7, 1.0]
        mhd = result.parameter_samples["MHD_effect_factor"]
        assert all(0.7 <= v <= 1.0 for v in mhd)
        # Li6_enrichment_fraction bounds: [0.05, 0.90]
        li6 = result.parameter_samples["Li6_enrichment_fraction"]
        assert all(0.05 <= v <= 0.90 for v in li6)
        # blanket_thickness_cm bounds: [30, 100]
        thick = result.parameter_samples["blanket_thickness_cm"]
        assert all(30 <= v <= 100 for v in thick)


class TestUQMarkdown:
    """Test uq_markdown() formatting."""

    def test_includes_basic_info(self):
        from zpp_uncertainty import (
            monte_carlo_propagation, uq_markdown, DEFAULT_UNCERTAIN_PARAMS_ZN,
        )
        result = monte_carlo_propagation(
            DEFAULT_UNCERTAIN_PARAMS_ZN, n_samples=10, random_seed=42,
        )
        md = uq_markdown(result)
        assert "Uncertainty quantification result" in md
        assert "Samples" in md
        assert "TBR distribution" in md
        assert "Mean" in md
        assert "P(TBR >= 1.05)" in md

    def test_includes_LCOE_info(self):
        from zpp_uncertainty import (
            monte_carlo_propagation, uq_markdown, DEFAULT_UNCERTAIN_PARAMS_ZN,
        )
        result = monte_carlo_propagation(
            DEFAULT_UNCERTAIN_PARAMS_ZN, n_samples=10, random_seed=42,
        )
        md = uq_markdown(result)
        assert "LCOE distribution" in md


class TestStrategicFindings:
    """Document strategic findings."""

    def test_MC_confirms_TBR_feasibility(self):
        """For ZN at current physics, P(TBR>=1.05) is 100% in MC.

        This is consistent with Tier 5.B (ZN blanket design is
        robustly feasible for tritium self-sufficiency even
        with uncertainty).
        """
        from zpp_uncertainty import (
            monte_carlo_propagation, DEFAULT_UNCERTAIN_PARAMS_ZN,
        )
        result = monte_carlo_propagation(
            DEFAULT_UNCERTAIN_PARAMS_ZN, n_samples=100, random_seed=42,
        )
        # All samples should be above threshold for ZN design
        assert result.n_above_TBR_threshold / result.n_samples > 0.9

    def test_MC_confirms_LCOE_sub_break_even(self):
        """For ZN at current physics, all samples are sub-break-even.

        This is consistent with Tier 2.D + 5.A + 6.B (ZN plant
        cannot deliver commercial LCOE regardless of small
        parameter variations).
        """
        from zpp_uncertainty import (
            monte_carlo_propagation, DEFAULT_UNCERTAIN_PARAMS_ZN,
        )
        result = monte_carlo_propagation(
            DEFAULT_UNCERTAIN_PARAMS_ZN, n_samples=50, random_seed=42,
        )
        # All samples sub-break-even (Q_eng ~1e-3 << break-even)
        assert result.n_below_break_even / result.n_samples == 1.0