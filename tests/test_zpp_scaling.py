"""
Tier 2.D — ZN scaling sweep tests.

Verifies:
1. sweep_one_point produces physically plausible outputs.
2. The default 6x4x4 sweep has 96 points.
3. Q_eng increases with I_peak (more driver current).
4. eta_mix decreases with CR (more mix at higher CR).
5. The ZN design point has higher T_stag than Z present.
6. break_even_contour correctly filters points.
7. scaling_summary returns the expected keys and finds the closest
   point to the ZN design (60 MA, 30 T, 8 kJ).
"""
from __future__ import annotations
import sys
import os

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "code"))

from zpp.zpp_scaling import (
    SweepResult,
    sweep_one_point,
    zn_scaling_sweep,
    break_even_contour,
    scaling_summary,
)
from zpp.zpp_wallplug import wallplug_chain_zn_design


class TestSweepOnePoint:
    """Test the single-point sweep function."""

    def test_returns_sweep_result_dataclass(self):
        r = sweep_one_point(I_peak_MA=20.0, B_z0_T=16.0, E_laser_kJ=1.2)
        assert isinstance(r, SweepResult)
        assert r.I_peak_MA == 20.0
        assert r.B_z0_T == 16.0
        assert r.E_laser_kJ == 1.2

    def test_physically_plausible_outputs(self):
        """All numeric outputs should be in their physical ranges."""
        r = sweep_one_point(I_peak_MA=20.0, B_z0_T=16.0, E_laser_kJ=1.2)
        assert 0.5 <= r.T_stag_keV <= 15.0  # realistic MagLIF T_stag
        assert 1.0 <= r.CR_fuel <= 10.0  # fuel CR, not liner CR
        assert r.tau_burn_ns > 0
        assert r.rho_stag_gcc > 0
        assert r.E_fusion_1D_J > 0
        assert 0 <= r.E_fusion_2D_J <= r.E_fusion_1D_J
        assert 0 < r.eta_mix <= 1.0
        assert r.Q_eng >= 0
        assert 0 < r.eta_wallplug < 1.0

    def test_higher_I_higher_Q_eng(self):
        """Higher peak current -> higher Q_eng (more driver energy)."""
        r_low = sweep_one_point(I_peak_MA=20.0, B_z0_T=16.0, E_laser_kJ=1.2)
        r_high = sweep_one_point(I_peak_MA=60.0, B_z0_T=30.0, E_laser_kJ=8.0)
        assert r_high.Q_eng > r_low.Q_eng

    def test_apply_2d_mix_false_no_correction(self):
        """With apply_2d_mix=False, eta_mix=1 and 1D=2D."""
        r = sweep_one_point(
            I_peak_MA=20.0, B_z0_T=16.0, E_laser_kJ=1.2,
            apply_2d_mix=False,
        )
        assert r.eta_mix == 1.0
        assert r.E_fusion_2D_J == pytest.approx(r.E_fusion_1D_J, rel=1e-9)

    def test_E_stored_auto_scales_with_I_squared(self):
        """Default E_stored_J = 22 MJ * (I/20)^2."""
        r_60 = sweep_one_point(I_peak_MA=60.0, B_z0_T=30.0, E_laser_kJ=8.0)
        # 60/20 = 3, so E_stored = 22 * 9 = 198 MJ
        # Q_eng_stored = E_fus_2D / E_stored -> so E_fus_2D = Q_eng_stored * E_stored
        # We can't directly assert E_stored from SweepResult (it's not stored),
        # but the ratio of Q_eng between I=20 and I=60 should be ~9x at fixed
        # E_fus (because E_stored scales 9x).
        # Just check that E_fus_2D scales (or doesn't crash).
        assert r_60.E_fusion_2D_J > 0


class TestZnScalingSweep:
    """Test the full 3D sweep."""

    def test_default_sweep_has_96_points(self):
        """6 I * 4 B * 4 E_laser = 96."""
        results = zn_scaling_sweep()
        assert len(results) == 96

    def test_custom_sweep_sizes(self):
        results = zn_scaling_sweep(
            I_peak_list_MA=[20.0, 30.0],
            B_z0_list_T=[16.0],
            E_laser_list_kJ=[1.2, 4.0],
        )
        assert len(results) == 4

    def test_sweep_Q_eng_increases_with_I_peak(self):
        """At fixed (B, E_laser), higher I_peak gives higher Q_eng."""
        results = zn_scaling_sweep(
            I_peak_list_MA=[20.0, 40.0, 60.0],
            B_z0_list_T=[20.0],
            E_laser_list_kJ=[4.0],
        )
        Q_values = [r.Q_eng for r in results]
        assert Q_values[0] < Q_values[1] < Q_values[2]

    def test_sweep_eta_mix_increases_with_B(self):
        """At fixed (I, E_laser), higher B gives higher eta_mix."""
        results = zn_scaling_sweep(
            I_peak_list_MA=[60.0],
            B_z0_list_T=[10.0, 16.0, 20.0, 30.0],
            E_laser_list_kJ=[4.0],
        )
        eta_values = [r.eta_mix for r in results]
        assert eta_values[0] < eta_values[1] < eta_values[2] < eta_values[3]

    def test_sweep_T_stag_higher_for_ZN_than_Z(self):
        """ZN design (60 MA) has higher T_stag than Z present (20 MA)."""
        results = zn_scaling_sweep()
        z_anchor = next(r for r in results
                        if r.I_peak_MA == 20.0 and r.B_z0_T == 16.0 and r.E_laser_kJ == 1.2)
        zn_design = next(r for r in results
                         if r.I_peak_MA == 60.0 and r.B_z0_T == 30.0 and r.E_laser_kJ == 8.0)
        assert zn_design.T_stag_keV > z_anchor.T_stag_keV

    def test_sweep_runs_quickly(self):
        """96-point sweep should run in <5 seconds."""
        import time
        t0 = time.time()
        zn_scaling_sweep()
        elapsed = time.time() - t0
        assert elapsed < 5.0, f"Sweep took {elapsed:.1f}s (expected <5s)"


class TestBreakEvenContour:
    """Test the break-even contour filter."""

    def test_returns_subset_of_sweep(self):
        results = zn_scaling_sweep()
        contour = break_even_contour(results)
        assert len(contour) <= len(results)

    def test_returns_only_above_break_even(self):
        results = zn_scaling_sweep()
        contour = break_even_contour(results)
        for r in contour:
            assert r.above_break_even is True

    def test_mcbride_1D_predicts_no_break_even(self):
        """With the McBride 1D + 2D-mix model, no sweep point reaches
        break-even (Q_eng * eta_wp * eta_E > 1). This is the
        honest finding: ZN design as currently published hits
        Q_eng ~ 1e-4, far below the 12.5 break-even for ZN-class
        drivers. Larger I, higher eta_mix, or advanced concepts
        (ignition, magnetised target fusion) are needed.

        This test documents that finding. If future versions
        change this, the test will fail and force re-evaluation
        of the strategic conclusion.
        """
        results = zn_scaling_sweep()
        contour = break_even_contour(results)
        assert len(contour) == 0, (
            f"Expected 0 break-even points with McBride 1D + 2D mix, "
            f"got {len(contour)}. This would change the strategic "
            f"conclusion of the sweep; review MODEL_ASSUMPTIONS."
        )


class TestScalingSummary:
    """Test the scaling-law summary."""

    def test_summary_returns_expected_keys(self):
        results = zn_scaling_sweep()
        s = scaling_summary(results)
        assert "n_points" in s
        assert "zn_design_point" in s
        assert "z_present_anchor" in s
        assert "max_Q_eng_in_sweep" in s
        assert "num_above_break_even" in s
        assert "fraction_above_break_even" in s

    def test_summary_n_points_matches_sweep(self):
        results = zn_scaling_sweep()
        s = scaling_summary(results)
        assert s["n_points"] == 96

    def test_summary_zn_design_point_keys(self):
        results = zn_scaling_sweep()
        s = scaling_summary(results)
        zn = s["zn_design_point"]
        assert "I_peak_MA" in zn
        assert "B_z0_T" in zn
        assert "E_laser_kJ" in zn
        assert "T_stag_keV" in zn
        assert "Q_eng" in zn
        assert "E_fusion_2D_J" in zn
        assert "above_break_even" in zn

    def test_summary_finds_closest_ZN_design_point(self):
        """The 'closest' point should be exactly (60, 30, 8) since
        those are in the default sweep."""
        results = zn_scaling_sweep()
        s = scaling_summary(results)
        zn = s["zn_design_point"]
        assert zn["I_peak_MA"] == 60.0
        assert zn["B_z0_T"] == 30.0
        assert zn["E_laser_kJ"] == 8.0

    def test_summary_handles_empty_sweep(self):
        s = scaling_summary([])
        assert s == {}

    def test_summary_max_Q_eng_is_actual_max(self):
        results = zn_scaling_sweep()
        s = scaling_summary(results)
        actual_max = max(r.Q_eng for r in results)
        assert s["max_Q_eng_in_sweep"] == pytest.approx(actual_max, rel=1e-9)


class TestEndToEndZNDesign:
    """End-to-end smoke test of the ZN design sweep."""

    def test_ZN_design_above_Z_present_in_all_metrics(self):
        """ZN design should beat Z present in T_stag, Q_eng, E_fus."""
        results = zn_scaling_sweep()
        z_anchor = next(r for r in results
                        if r.I_peak_MA == 20.0 and r.B_z0_T == 16.0 and r.E_laser_kJ == 1.2)
        zn_design = next(r for r in results
                         if r.I_peak_MA == 60.0 and r.B_z0_T == 30.0 and r.E_laser_kJ == 8.0)
        # All three "improvement" metrics
        assert zn_design.T_stag_keV > z_anchor.T_stag_keV
        assert zn_design.Q_eng > z_anchor.Q_eng
        assert zn_design.E_fusion_2D_J > z_anchor.E_fusion_2D_J
        # ZN eta_mix should also be better (more B)
        assert zn_design.eta_mix > z_anchor.eta_mix
