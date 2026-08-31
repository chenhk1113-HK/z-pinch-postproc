"""
Tier 3.C — Extended ZN sweep at 65 MA tests.

Verifies:
1. zn_65_sweep returns 125 points (5 I * 5 B * 5 E_laser).
2. Default sweep runs in <5 seconds.
3. Q_eng increases monotonically with I_peak at fixed (B, E_laser).
4. mix_aware_pareto returns the highest-Q_eng points.
5. scaling_law_regression returns a dict with slope/intercept/R^2.
6. zn_65_summary returns expected keys and finds the design point.
7. The ZN design point at 65 MA still doesn't break even (Tier 2.D finding).
"""
from __future__ import annotations
import sys
import os
import time

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "code"))

from zpp.zpp_zn65 import (
    ZN_65_DEFAULTS,
    zn_65_sweep,
    fine_grained_sweep,
    mix_aware_pareto,
    scaling_law_regression,
    zn_65_summary,
)


class TestZn65Sweep:
    """Test zn_65_sweep."""

    def test_default_sweep_has_125_points(self):
        """5 I_peak * 5 B_z0 * 5 E_laser = 125."""
        results = zn_65_sweep()
        assert len(results) == 125

    def test_sweep_runs_quickly(self):
        """125-point sweep should run in <5 seconds."""
        t0 = time.time()
        zn_65_sweep()
        elapsed = time.time() - t0
        assert elapsed < 5.0, f"Sweep took {elapsed:.1f}s (expected <5s)"

    def test_sweep_includes_design_point(self):
        """The ZN-65 design point (65 MA, 30 T, 8 kJ) should be in the sweep."""
        results = zn_65_sweep()
        found = any(
            r.I_peak_MA == 65.0 and r.B_z0_T == 30.0 and r.E_laser_kJ == 8.0
            for r in results
        )
        assert found

    def test_Q_eng_increases_with_I_peak(self):
        """At fixed (B=30, E_laser=8), Q_eng increases with I_peak."""
        results = zn_65_sweep()
        # Filter to B=30, E_laser=8
        filtered = [r for r in results if r.B_z0_T == 30.0 and r.E_laser_kJ == 8.0]
        # Should have 5 points (one per I_peak value)
        assert len(filtered) == 5
        Q_values = [r.Q_eng for r in filtered]
        for i in range(1, len(Q_values)):
            assert Q_values[i] > Q_values[i - 1], (
                f"Q_eng should increase with I_peak; got {Q_values}"
            )

    def test_eta_mix_increases_with_B_z0(self):
        """At fixed I, E_laser, eta_mix increases with B_z0 (B stabilizes MRT)."""
        results = zn_65_sweep()
        filtered = [r for r in results if r.I_peak_MA == 65.0 and r.E_laser_kJ == 8.0]
        assert len(filtered) == 5
        eta_values = [r.eta_mix for r in filtered]
        for i in range(1, len(eta_values)):
            assert eta_values[i] > eta_values[i - 1]


class TestFineGrainedSweep:
    """Test fine_grained_sweep."""

    def test_custom_center(self):
        """Default center is ZN design (65, 30, 8)."""
        results = fine_grained_sweep(n_per_axis=3)
        # 3^3 = 27
        assert len(results) == 27
        # Center should be (65, 30, 8)
        found = any(
            abs(r.I_peak_MA - 65.0) < 1e-6
            and abs(r.B_z0_T - 30.0) < 1e-6
            and abs(r.E_laser_kJ - 8.0) < 1e-6
            for r in results
        )
        assert found


class TestMixAwarePareto:
    """Test mix_aware_pareto."""

    def test_returns_top_n_by_Q_eng(self):
        results = zn_65_sweep()
        top = mix_aware_pareto(results, top_n=5)
        assert len(top) == 5
        # Top points should have the highest Q_eng
        Q_top = [r.Q_eng for r in top]
        for i in range(1, len(Q_top)):
            assert Q_top[i] <= Q_top[i - 1]

    def test_default_top_n(self):
        results = zn_65_sweep()
        top = mix_aware_pareto(results)
        assert len(top) == 10  # default top_n=10


class TestScalingLawRegression:
    """Test scaling_law_regression."""

    def test_returns_expected_keys(self):
        results = zn_65_sweep()
        s = scaling_law_regression(results, "I_peak_MA")
        assert "slope" in s
        assert "intercept" in s
        assert "R_squared" in s
        assert "n_points" in s
        assert "fixed_values" in s
        assert "parameter" in s

    def test_I_peak_regression_high_R_squared(self):
        """Q_eng should scale strongly linearly with I_peak."""
        results = zn_65_sweep()
        s = scaling_law_regression(results, "I_peak_MA")
        assert s["R_squared"] > 0.9, f"R^2={s['R_squared']:.3f} (expected >0.9)"

    def test_regression_positive_slope_for_I_peak(self):
        """Q_eng increases with I_peak -> positive slope."""
        results = zn_65_sweep()
        s = scaling_law_regression(results, "I_peak_MA")
        assert s["slope"] > 0

    def test_regression_invalid_parameter_raises(self):
        results = zn_65_sweep()
        with pytest.raises(ValueError):
            scaling_law_regression(results, "T_stag_keV")  # not a sweep param


class TestZn65Summary:
    """Test zn_65_summary."""

    def test_returns_expected_keys(self):
        s = zn_65_summary()
        assert "n_points" in s
        assert "best_mix_aware_point" in s
        assert "design_point_65_30_8" in s
        assert "scaling_laws" in s
        assert "max_Q_eng_in_sweep" in s

    def test_design_point_Q_eng_below_break_even(self):
        """ZN design at 65 MA still doesn't break even with McBride 1D + 2D mix.

        This is consistent with Tier 2.D's finding: the McBride model
        cannot reach break-even for current ZN design parameters.
        """
        s = zn_65_summary()
        design = s["design_point_65_30_8"]
        assert design["Q_eng"] < 0.01, (
            f"ZN-65 design Q_eng {design['Q_eng']:.4f} (expected <0.01; "
            f"McBride 1D + 2D mix cannot reach break-even)."
        )

    def test_best_point_has_higher_Q_eng_than_design(self):
        """The mix-aware best point should beat the ZN design point."""
        s = zn_65_summary()
        best = s["best_mix_aware_point"]
        design = s["design_point_65_30_8"]
        assert best["Q_eng"] >= design["Q_eng"]

    def test_scaling_laws_in_summary(self):
        s = zn_65_summary()
        sl = s["scaling_laws"]
        assert "Q_eng_vs_I_peak_MA" in sl
        assert "Q_eng_vs_B_z0_T" in sl
        assert "Q_eng_vs_E_laser_kJ" in sl

    def test_n_points_matches_sweep_size(self):
        s = zn_65_summary()
        assert s["n_points"] == 125

    def test_max_Q_eng_in_sweep_is_actual_max(self):
        results = zn_65_sweep()
        s = zn_65_summary(results)
        actual_max = max(r.Q_eng for r in results)
        assert s["max_Q_eng_in_sweep"] == pytest.approx(actual_max, rel=1e-9)


class TestStrategicFindings:
    """Document the tier 3.C strategic findings."""

    def test_ZN65_design_below_break_even(self):
        """Document that the McBride 1D + 2D-mix model predicts ZN-65
        stays below break-even even at the design point. The
        strategic conclusion (Tier 2.D) is unchanged at the higher
        ZN current (65 MA vs 60 MA).
        """
        s = zn_65_summary()
        # Best point in the 125-point sweep: still sub-break-even
        assert s["best_mix_aware_point"]["Q_eng"] < 0.01

    def test_higher_I_peak_helps_but_not_enough(self):
        """Q_eng increases with I_peak (strong scaling), but not
        enough to reach break-even at any point in the 55-75 MA range.
        """
        s = zn_65_summary()
        # Even the best point (highest I, B, E) is sub-break-even
        # break-even requires Q_eng * eta_wp * eta_E > 1
        # ZN eta_wp = 0.09, eta_E = 0.40, so Q_eng > 27.8
        assert s["max_Q_eng_in_sweep"] < 1.0  # still < break-even (which is 27.8 here)
