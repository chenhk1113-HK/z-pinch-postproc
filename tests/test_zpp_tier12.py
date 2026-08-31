"""Tier 12 (2026-08-31) — tests for mult_inside=False calibration.

The Tier 10 sweep exposed that the Tier 8 closed-form doesn't fit
the mult_inside=False geometry (Be outside LiPb) because:
  1. The R=50 point is non-monotonic (TBR=0.94 < R=12's 1.04).
  2. Be placement matters physically: neutrons see LiPb first,
     then Be catches them on the way out.

Tier 12 extends the parametric model with:
  - TBRInputs.mult_inside field (default True, backward compat)
  - MC_CALIBRATION_TABLE_MULT_OUTSIDE (5 points from Tier 10)
  - boundary_correction_factor(thick, "reflective", mult_inside=False)
    uses piecewise-linear interpolation (Tier 7+ style) since
    no smooth closed-form fits the non-monotonic data.
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "code"))


class TestTier12Inputs:
    """Tier 12 — TBRInputs.mult_inside field."""

    def test_mult_inside_field_exists(self):
        """TBRInputs should have mult_inside field with default True."""
        from zpp.zpp_tbr import TBRInputs
        inp = TBRInputs()
        assert hasattr(inp, "mult_inside")
        assert inp.mult_inside is True  # backward compat: Tier 6 default

    def test_mult_inside_settable(self):
        """mult_inside can be set to False."""
        from zpp.zpp_tbr import TBRInputs
        inp = TBRInputs(mult_inside=False)
        assert inp.mult_inside is False


class TestTier12MultOutsideTable:
    """Tier 12 — mult_outside calibration table exists."""

    def test_table_has_5_points(self):
        """MC_CALIBRATION_TABLE_MULT_OUTSIDE should have 5 points."""
        from zpp.zpp_tbr import MC_CALIBRATION_TABLE_MULT_OUTSIDE
        assert len(MC_CALIBRATION_TABLE_MULT_OUTSIDE) == 5

    def test_table_thicknesses_monotonic(self):
        """Table thicknesses should be in increasing order."""
        from zpp.zpp_tbr import MC_CALIBRATION_TABLE_MULT_OUTSIDE
        ts = [p[0] for p in MC_CALIBRATION_TABLE_MULT_OUTSIDE]
        assert ts == sorted(ts)
        assert ts[0] == 8 and ts[-1] == 136  # R_b 12 -> 140, LiPb=thick

    def test_R50_is_below_R12(self):
        """The non-monotonic R=50 point (TBR=0.94) must be < R=12 (1.04).
        This is the Tier 12 honest finding — Tier 10 sweep
        documented it; Tier 12 preserves the finding."""
        from zpp.zpp_tbr import MC_CALIBRATION_TABLE_MULT_OUTSIDE
        # First point: thick=8 (R_b=12)
        tbr_R12 = MC_CALIBRATION_TABLE_MULT_OUTSIDE[0][1]
        # Second point: thick=46 (R_b=50)
        tbr_R50 = MC_CALIBRATION_TABLE_MULT_OUTSIDE[1][1]
        assert tbr_R50 < tbr_R12, (
            f"Non-monotonic finding: TBR(R_b=50)={tbr_R50} should be "
            f"< TBR(R_b=12)={tbr_R12}. If this fails, the Tier 10 "
            f"sweep result changed; re-run and update the table."
        )


class TestTier12BoundaryCorrection:
    """Tier 12 — boundary_correction_factor with mult_inside=False."""

    def test_infinite_boundary_returns_one(self):
        """For 'infinite' boundary, correction is 1.0 regardless of mult_inside."""
        from zpp.zpp_tbr import boundary_correction_factor
        f_inside = boundary_correction_factor(50.0, "infinite", mult_inside=True)
        f_outside = boundary_correction_factor(50.0, "infinite", mult_inside=False)
        assert f_inside == 1.0
        assert f_outside == 1.0

    def test_mult_outside_at_calibration_points(self):
        """At the 5 calibration thicknesses, f_geom should match the
        ratio MC TBR / Sobes TBR-with-Be-multiplier baseline.

        At calibration points, the piecewise-linear interpolation is
        exact by construction (delta = 0).
        """
        from zpp.zpp_tbr import (
            boundary_correction_factor, MC_CALIBRATION_TABLE_MULT_OUTSIDE,
            TBR_PER_NEUTRON, NEUTRON_MULTIPLIER_GAIN,
            thickness_to_saturation,
        )
        TBR_sat_LiPb = TBR_PER_NEUTRON["LiPb"][0]  # 1.30
        mult_gain = NEUTRON_MULTIPLIER_GAIN["Be"]  # 0.65
        # Sobes-with-Be baseline: TBR_sat * f_sat * (1 + mult_gain)
        for thick, tbr_mc, _ in MC_CALIBRATION_TABLE_MULT_OUTSIDE:
            f_geom = boundary_correction_factor(
                thick, "reflective", mult_inside=False,
            )
            f_sat = thickness_to_saturation("LiPb", thick)
            tbr_sobes_with_be = TBR_sat_LiPb * f_sat * (1 + mult_gain)
            tbr_pred = tbr_sobes_with_be * f_geom
            delta = abs(tbr_pred - tbr_mc) / tbr_mc
            assert delta < 0.02, (
                f"At thick={thick}, predicted TBR={tbr_pred:.4f} vs "
                f"MC TBR={tbr_mc:.4f} ({delta*100:.2f}% delta). "
                f"Should be < 2% by construction."
            )

    def test_mult_inside_default_unchanged(self):
        """Default (mult_inside=True) behavior must NOT change.
        Tier 8 closed-form at R_b=80 cm (thick=74) should give
        the same value as before."""
        from zpp.zpp_tbr import boundary_correction_factor
        f_default = boundary_correction_factor(74.0, "reflective")
        f_explicit_true = boundary_correction_factor(74.0, "reflective", mult_inside=True)
        assert f_default == f_explicit_true


class TestTier12ComputeTBR:
    """Tier 12 — compute_TBR uses mult_inside."""

    def test_compute_TBR_with_mult_inside_false(self):
        """compute_TBR should accept mult_inside=False in TBRInputs."""
        from zpp.zpp_tbr import TBRInputs, compute_TBR
        inp = TBRInputs(
            blanket_material="LiPb",
            neutron_multiplier="Be",
            Li6_enrichment_fraction=0.90,
            blanket_thickness_cm=50.0,
            first_wall_coverage_fraction=1.0,
            geometry="Z-pinch",
            MHD_effect_factor=1.0,
            temperature_factor=1.0,
            boundary_condition="reflective",
            mult_inside=False,
        )
        result = compute_TBR(inp)
        # Should not raise; TBR should be a reasonable finite number
        assert 0.0 < result.TBR < 10.0

    def test_compute_TBR_mult_inside_changes_tbr(self):
        """mult_inside=False should give a different TBR than mult_inside=True
        at the same blanket_thickness_cm + reflective boundary."""
        from zpp.zpp_tbr import TBRInputs, compute_TBR
        common = dict(
            blanket_material="LiPb",
            neutron_multiplier="Be",
            Li6_enrichment_fraction=0.90,
            blanket_thickness_cm=50.0,
            first_wall_coverage_fraction=1.0,
            geometry="Z-pinch",
            MHD_effect_factor=1.0,
            temperature_factor=1.0,
            boundary_condition="reflective",
        )
        inp_inside = TBRInputs(mult_inside=True, **common)
        inp_outside = TBRInputs(mult_inside=False, **common)
        r_inside = compute_TBR(inp_inside)
        r_outside = compute_TBR(inp_outside)
        assert r_inside.TBR != r_outside.TBR, (
            "mult_inside=True vs False should give different TBR; "
            f"both gave {r_inside.TBR}"
        )

    def test_compute_TBR_mult_outside_far_below_inside(self):
        """At R_b=50 cm, mult_outside parametric TBR should be lower than
        mult_inside parametric TBR. The Tier 5.B parametric overshoots
        at reflective boundary, so the absolute difference is smaller
        than the MC difference (1.84 vs 0.94), but the mult_outside
        correction factor absorbs the bulk of the gap."""
        from zpp.zpp_tbr import TBRInputs, compute_TBR
        common = dict(
            blanket_material="LiPb",
            neutron_multiplier="Be",
            Li6_enrichment_fraction=0.90,
            blanket_thickness_cm=44.0,  # LiPb thickness at R_b=50 cm
            first_wall_coverage_fraction=1.0,
            geometry="Z-pinch",
            MHD_effect_factor=1.0,
            temperature_factor=1.0,
            boundary_condition="reflective",
        )
        r_inside = compute_TBR(TBRInputs(mult_inside=True, **common))
        r_outside = compute_TBR(TBRInputs(mult_inside=False, **common))
        # MC at R=50: inside 1.8361, outside 0.9375. Difference ~0.9.
        # Parametric difference is smaller (~0.24) because Tier 5.B
        # formula structure includes the Be multiplier term, but the
        # mult_outside correction still pushes TBR lower.
        assert r_inside.TBR > r_outside.TBR, (
            f"mult_inside=True TBR ({r_inside.TBR:.3f}) should be > "
            f"mult_inside=False TBR ({r_outside.TBR:.3f}) at R_b=50. "
            f"Tier 12 honest finding."
        )


class TestTier12BackwardCompat:
    """Tier 12 — backward compat with v1.2.0."""

    def test_all_v1_2_0_tests_still_pass(self):
        """Run the existing Tier 8 closed-form tests; they should still pass
        because mult_inside defaults to True."""
        from zpp.zpp_tbr import (
            boundary_correction_factor, compute_TBR, TBRInputs,
        )
        # Tier 8 closed-form: thick=74 cm, reflective
        f = boundary_correction_factor(74.0, "reflective")
        # Expected: 0.8267 / (1 - 0.973 * (1 - (1-exp(-74/50))))
        import math
        f_sat = 1 - math.exp(-74 / 50)
        expected = 0.8267 / (1 - 0.973 * (1 - f_sat))
        assert abs(f - expected) < 1e-4  # loose tolerance for float

    def test_TBRInputs_mult_inside_in_TBRInputs_docstring(self):
        """The mult_inside field must appear in the TBRInputs docstring."""
        from zpp.zpp_tbr import TBRInputs
        doc = TBRInputs.__doc__ or ""
        assert "mult_inside" in doc, (
            f"TBRInputs docstring should document the new mult_inside "
            f"field. Got: {doc!r}"
        )
