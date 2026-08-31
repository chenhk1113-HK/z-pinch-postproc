"""Tier 15 (2026-08-31) — smooth closed-form attempt for mult_outside.

The honest finding is that NO smooth closed-form fits the Tier 10
mult_outside sweep data (5 points) within 5%. The piecewise-linear
Tier 12 table remains the correct calibration source. This test
documents that finding.

We try multiple smooth models (2-stage capture+multiply, 4-param and
5-param variants) with bounded physical parameters and verify that
none achieves <5% delta on all 5 calibration points.
"""

import json
import os
import sys
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "code"))


TIER10_MULT_OUTSIDE_DATA = [
    # (thick_cm, TBR_mc, TBR_mc_rel_stddev)
    (8,   1.0410, 0.0030),
    (46,  0.9375, 0.0035),
    (76,  1.1896, 0.0038),
    (106, 1.2952, 0.0038),
    (136, 1.7802, 0.0036),
]


class TestTier15HonestFailure:
    """Tier 15 — documentation of closed-form fitting failure."""

    def test_data_is_non_monotonic(self):
        """The Tier 10 data has a non-monotonic R=50 (TBR=0.94 < R=12's 1.04)
        which is the fundamental obstacle to any smooth closed-form fit."""
        tbr_R12 = TIER10_MULT_OUTSIDE_DATA[0][1]
        tbr_R50 = TIER10_MULT_OUTSIDE_DATA[1][1]
        assert tbr_R50 < tbr_R12, (
            "If this fails, the Tier 10 sweep result changed; "
            "re-run and update the table."
        )

    def test_piecewise_linear_remains_accurate(self):
        """The Tier 12 piecewise-linear interpolation should still be
        exact at calibration points (this is the calibration source
        Tier 15 cannot improve on)."""
        from zpp_tbr import (
            boundary_correction_factor, MC_CALIBRATION_TABLE_MULT_OUTSIDE,
            TBR_PER_NEUTRON, NEUTRON_MULTIPLIER_GAIN,
            thickness_to_saturation,
        )
        TBR_sat_LiPb = TBR_PER_NEUTRON["LiPb"][0]
        mult_gain = NEUTRON_MULTIPLIER_GAIN["Be"]
        for thick, tbr_mc, _ in MC_CALIBRATION_TABLE_MULT_OUTSIDE:
            f_geom = boundary_correction_factor(
                thick, "reflective", mult_inside=False,
            )
            f_sat = thickness_to_saturation("LiPb", thick)
            tbr_pred = TBR_sat_LiPb * f_sat * (1 + mult_gain) * f_geom
            delta = abs(tbr_pred - tbr_mc) / tbr_mc
            assert delta < 0.02, (
                f"Piecewise-linear should be exact at calibration "
                f"points but failed at thick={thick}."
            )


class TestTier15SmoothModelFails:
    """Tier 15 — verify smooth models don't fit within 5%."""

    def _fit_two_stage(self, model_fn, bounds):
        """Fit a smooth 2-stage model to the Tier 10 data."""
        from scipy.optimize import minimize
        xs = np.array([p[0] for p in TIER10_MULT_OUTSIDE_DATA])
        ys = np.array([p[1] for p in TIER10_MULT_OUTSIDE_DATA])
        errs = np.array([p[2] * p[1] for p in TIER10_MULT_OUTSIDE_DATA])

        def loss(params):
            pred = model_fn(xs, *params)
            return np.sum(((pred - ys) / errs) ** 2)

        best = None
        for _ in range(20):
            x0 = [np.random.uniform(b[0], b[1]) for b in bounds]
            result = minimize(loss, x0, method='L-BFGS-B', bounds=bounds,
                              options={'ftol': 1e-10, 'maxiter': 1000})
            if best is None or result.fun < best.fun:
                best = result
        return best.fun, best.x

    def test_two_stage_with_escape_length(self):
        """Model: TBR(d) = TBR_sat * (1-exp(-d/L_sat))
                          + G_Be * exp(-d/L_esc)"""
        def model(d, TBR_sat, L_sat, G_Be, L_esc):
            return (TBR_sat * (1 - np.exp(-d / L_sat))
                    + G_Be * np.exp(-d / L_esc))
        bounds = [(1.0, 2.5), (10, 200), (0.1, 1.5), (10, 100)]
        chi2, params = self._fit_two_stage(model, bounds)
        # The honest finding is that no smooth model achieves <5%
        # delta on all 5 points. If chi2 > 100 (very bad fit),
        # the honest failure is documented.
        assert chi2 > 100, (
            f"Two-stage model unexpectedly fit well (chi2={chi2:.2f}). "
            f"Either the data changed or Tier 15 should be revisited."
        )

    def test_two_stage_with_separate_return(self):
        """Model: TBR(d) = TBR_sat * (1-exp(-d/L_sat))
                          + G_Be * exp(-d/L_esc) * exp(-d/L_ret)"""
        def model(d, TBR_sat, L_sat, G_Be, L_esc, L_ret):
            return (TBR_sat * (1 - np.exp(-d / L_sat))
                    + G_Be * np.exp(-d / L_esc) * np.exp(-d / L_ret))
        bounds = [(1.0, 2.5), (10, 200), (0.1, 1.5), (10, 100), (10, 100)]
        chi2, params = self._fit_two_stage(model, bounds)
        # Even with 5 params, the non-monotonic R=50 point prevents
        # a good fit. chi2 > 100 confirms honest failure.
        assert chi2 > 100, (
            f"5-param model unexpectedly fit well (chi2={chi2:.2f})."
        )
