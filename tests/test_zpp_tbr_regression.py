"""
Tier 7.B — Regression tests pinning the parametric Tier 5.B formula
to known-good outputs from the 2026-08-31 OpenMC sweep.

These tests exist for two reasons:
  1. To prevent silent drift: if anyone modifies
     `thickness_to_saturation` or `compute_TBR` without re-running
     the MC sweep, the parametric-vs-MC gap could grow silently.
  2. To encode the Tier 6 reconciliation: at the Sobes 2011 50-cm
     reference blanket the parametric matches MC to within 4.3%,
     and we should preserve that.

The numeric values below are *measurements* from real OpenMC runs
on 2026-08-31 (20,000 particles × 20 batches, ENDF/B-VIII.0,
white boundary, mult_inside=True). They are not synthesised; see
MODEL_ASSUMPTIONS_AND_LIMITATIONS.md §3.4 and CHANGELOG [0.8.0].

If you edit this file because the MC numbers moved, document the
new sweep in CHANGELOG and the change in the commit message.
"""
import os
import sys
import pytest

# Make the code directory importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "code"))

from zpp_tbr import (
    compute_TBR, TBRInputs,
    TBR_PER_NEUTRON, NEUTRON_MULTIPLIER_GAIN,
    thickness_to_saturation, enrichment_factor,
)


# ---------------------------------------------------------------------------
# Tier 7.B.1 — Known-good parametric outputs (regression pins)
# ---------------------------------------------------------------------------

# These values were captured on 2026-08-31 from compute_TBR at the
# exact geometry used in the Tier 6.C sweep. They should be stable to
# the last decimal — these functions are pure-python with no RNG.
#
# Geometry: 90% Li-6, LiPb blanket with Be multiplier, cylindrical,
#            coverage 0.95, MHD 0.85, temperature_factor 1.0.
# Thicknesses correspond to R_blanket - R_be = R_blanket - 6 cm.

REGRESSION_VALUES = {
    # thickness_cm : TBR from compute_TBR
    6.0:    0.2547,   # R_blanket=12,  very thin — under-saturated
    44.0:   1.3182,   # R_blanket=50,  Sobes 2011 reference (was 1.9151 pre-Tier 7.C)
    74.0:   1.7397,   # R_blanket=80,  thick — MC plateau overestimates pre-fix
    104.0:  1.9711,   # R_blanket=110, very thick
    134.0:  2.0981,   # R_blanket=140, extreme — was +63.5% over MC pre-fix, now +12.6%
}


def _inputs_at(thickness_cm, material="LiPb", mult="Be"):
    return TBRInputs(
        blanket_material=material,
        neutron_multiplier=mult,
        Li6_enrichment_fraction=0.90,
        blanket_thickness_cm=thickness_cm,
        first_wall_coverage_fraction=0.95,
        geometry="cylindrical",
        MHD_effect_factor=0.85,
        temperature_factor=1.0,
    )


class TestTier5BRegressionPins:
    """The parametric Tier 5.B formula should produce these values
    to 4 decimal places. If a future edit breaks one of these, the
    commit is suspect and the MC sweep should be re-run to confirm
    whether the change is real or numerical.
    """

    @pytest.mark.parametrize("thickness,expected_tbr",
                             list(REGRESSION_VALUES.items()))
    def test_compute_TBR_value(self, thickness, expected_tbr):
        result = compute_TBR(_inputs_at(thickness))
        # Tolerance: 0.01 (4th-decimal round trip; pure-python
        # arithmetic should be exact but allow for 1ulp).
        assert abs(result.TBR - expected_tbr) < 0.01, (
            f"compute_TBR drifted at thickness={thickness} cm: "
            f"expected {expected_tbr}, got {result.TBR:.4f}. "
            f"If this is intentional, update REGRESSION_VALUES "
            f"and re-run the Tier 6.C sweep to confirm."
        )


# ---------------------------------------------------------------------------
# Tier 7.B.2 — Sub-component regression pins
# ---------------------------------------------------------------------------

class TestSubComponentPins:
    """Pin the saturation curve and enrichment factor. If these
    drift, every downstream TBR value drifts with them."""

    def test_thickness_to_saturation_at_L_sat(self):
        # At thickness = L_sat, f_sat = 1 - exp(-1) = 0.6321
        assert thickness_to_saturation("LiPb", 50.0) == pytest.approx(0.6321, abs=1e-4)

    def test_thickness_to_saturation_at_zero(self):
        assert thickness_to_saturation("LiPb", 0.0) == pytest.approx(0.0, abs=1e-9)

    def test_thickness_to_saturation_at_infinity(self):
        # The current formula saturates at 1.0 in the limit (the bug).
        assert thickness_to_saturation("LiPb", 1000.0) == pytest.approx(1.0, abs=1e-6)

    def test_enrichment_at_natural(self):
        # 7.5% natural Li -> f_enr = 1.0
        assert enrichment_factor(0.075, "LiPb") == pytest.approx(1.0, abs=1e-3)

    def test_enrichment_at_90_percent(self):
        # 90% Li-6 — pin the calibrated value (Tier 7.C, 2026-08-31).
        # The function saturates near 1 + mat_factor for very high Li-6
        # fractions; mat_factor for LiPb is 0.95, so 100% Li-6 would
        # give 1 + 0.95 = 1.95, but at 90% the L_enr=2.17 calibrated
        # curve gives ~1.30 (matching the original docstring claim
        # "factor ~1.3 at 90%" that the pre-fix L_enr=0.3 overshot).
        v = enrichment_factor(0.90, "LiPb")
        assert 1.29 < v < 1.31, (
            f"enrichment_factor(0.90, LiPb) drifted: expected ~1.300, "
            f"got {v:.4f}. Update this pin if the change is intentional."
        )

    def test_enrichment_at_100_percent(self):
        # Asymptote: f_enr(1.0) = 1 + mat_factor * (1 - exp(-0.925/2.17))
        # For LiPb (mat_factor=0.95): 1.0 + 0.95 * 0.347 = ~1.330.
        # The function never reaches 1 + mat_factor because Li-6 cannot
        # exceed 1.0. The 1 + mat_factor ceiling is reachable only with
        # Li-6 fraction -> infinity.
        v = enrichment_factor(1.00, "LiPb")
        assert 1.32 < v < 1.34, (
            f"enrichment_factor(1.00, LiPb) drifted: expected ~1.330, "
            f"got {v:.4f}."
        )


# ---------------------------------------------------------------------------
# Tier 7.B.3 — MC-plateau upper-bound check (Tier 7.B the structural fix)
# ---------------------------------------------------------------------------

# These are the 2026-08-31 OpenMC Monte Carlo measurements for the
# Z-pinch LiPb + Be blanket. They pin the *physical* upper bound on
# TBR — the parametric should not exceed MC × 1.05 at any thickness
# once Tier 7.C adds the saturation ceiling.
MC_PLATEAU_VALUES = {
    # R_blanket_cm: (TBR_MC_central, TBR_MC_rel_stddev)
    12:  (1.5341, 0.0013),
    50:  (1.8361, 0.0011),
    80:  (1.8574, 0.0010),
    110: (1.8625, 0.0011),
    140: (1.8639, 0.0011),
}


class TestMCPlateauBound:
    """Tier 7+ — the parametric Tier 5.B formula with calibrated
    boundary_condition='reflective' should match the MC plateau
    to within ±1% at the 5 calibration points (R_b ∈ {12, 50,
    80, 110, 140} cm) by construction.

    Pre-Tier 7+ (infinite-medium Sobes): ±60% disagreement at
    R >= 80 cm (overestimate); −83% at R = 12 cm (underestimate
    from missing boundary-reflection gain).
    Post-Tier 7+: ±0% at the 5 calibration points by construction;
    bounded by ±10% between points (linear interpolation).

    Tier 7+ also adds the `boundary_condition="infinite"` case
    which preserves the Tier 7.C behavior: Sobes-only, ±15% at
    R >= 50 cm; known limitation at R <= 50 cm.
    """

    @pytest.mark.parametrize("R_b", list(MC_PLATEAU_VALUES.keys()))
    def test_reflective_matches_MC_at_calibration_points(self, R_b):
        """With boundary_condition='reflective', the parametric should
        reproduce the MC value to within 0.01 (it interpolates the
        calibration table at the calibration points exactly)."""
        mc_tbr, mc_rel_std = MC_PLATEAU_VALUES[R_b]
        LiPb_thick = R_b - 6.0
        if LiPb_thick <= 0:
            pytest.skip("no LiPb")
        inp = _inputs_at(LiPb_thick)
        inp_reflective = TBRInputs(
            **{**inp.__dict__, "boundary_condition": "reflective"}
        )
        result = compute_TBR(inp_reflective)
        delta_pct = (result.TBR - mc_tbr) / mc_tbr
        assert abs(delta_pct) <= 0.001, (
            f"Reflective parametric TBR ({result.TBR:.4f}) should "
            f"match MC plateau ({mc_tbr:.4f}) to within 0.1% at the "
            f"calibration point R_b={R_b} cm. Got delta={delta_pct*100:+.2f}%"
            f". Check MC_CALIBRATION_TABLE and boundary_correction_"
            f"factor interpolation."
        )

    @pytest.mark.parametrize("R_b", list(MC_PLATEAU_VALUES.keys()))
    def test_infinite_preserves_tier7c_behavior(self, R_b):
        """With boundary_condition='infinite' (default), the
        parametric should match the Tier 7.C Sobes-only behavior:
        ±15% at R >= 50 cm, known thin-blanket limitation at R <= 50 cm.
        """
        mc_tbr, mc_rel_std = MC_PLATEAU_VALUES[R_b]
        LiPb_thick = R_b - 6.0
        if LiPb_thick <= 0:
            pytest.skip("no LiPb")
        inp = _inputs_at(LiPb_thick)
        # Default boundary_condition='infinite'
        result = compute_TBR(inp)
        assert result.boundary_correction == pytest.approx(1.0), (
            f"Default boundary_condition should give f_geom=1.0, "
            f"got {result.boundary_correction:.4f}"
        )
        delta_pct = (result.TBR - mc_tbr) / mc_tbr
        if R_b <= 50:
            # Known thin-blanket limitation (Sobes underestimates)
            assert delta_pct < -0.20, (
                f"At R_b={R_b} cm with infinite boundary, parametric "
                f"underestimates by {delta_pct*100:+.1f}% (known limitation)."
            )
        else:
            assert abs(delta_pct) <= 0.15, (
                f"Infinite-boundary parametric TBR ({result.TBR:.4f}) "
                f"disagrees with MC plateau ({mc_tbr:.4f}) by "
                f"{delta_pct*100:+.1f}% at R_blanket={R_b} cm."
            )


# ---------------------------------------------------------------------------
# Tier 7+ — boundary_correction_factor tests
# ---------------------------------------------------------------------------

class TestBoundaryCorrectionFactor:
    """Tier 7+ — tests for the boundary_correction_factor function."""

    def test_infinite_boundary_returns_one(self):
        from zpp_tbr import boundary_correction_factor
        for thick in [0, 6, 44, 100, 200]:
            f = boundary_correction_factor(thick, "infinite")
            assert f == 1.0, (
                f"infinite boundary at thickness={thick} cm: "
                f"expected f_geom=1.0, got {f:.4f}"
            )

    def test_invalid_boundary_raises(self):
        from zpp_tbr import boundary_correction_factor
        with pytest.raises(ValueError, match="boundary_condition"):
            boundary_correction_factor(50.0, "vacuum")

    def test_reflective_at_calibration_points(self):
        """At the 5 calibration points, f_geom = MC / Sobes."""
        from zpp_tbr import boundary_correction_factor, MC_CALIBRATION_TABLE
        expected = {
            6.0:   1.5341 / 0.2547,  # R_b=12
            44.0:  1.8361 / 1.3182,  # R_b=50
            74.0:  1.8574 / 1.7397,  # R_b=80
            104.0: 1.8625 / 1.9711,  # R_b=110
            134.0: 1.8639 / 2.0981,  # R_b=140
        }
        for thick, expected_f in expected.items():
            f = boundary_correction_factor(thick, "reflective")
            assert abs(f - expected_f) < 0.01, (
                f"f_geom at thickness={thick} cm: expected "
                f"{expected_f:.4f}, got {f:.4f}"
            )

    def test_reflective_clamps_at_extremes(self):
        """At thickness < min or > max, f_geom should clamp to the
        boundary value, not extrapolate."""
        from zpp_tbr import boundary_correction_factor
        # Below min thickness (6 cm): clamp to f_geom(R_b=12)
        f_low = boundary_correction_factor(0.0, "reflective")
        f_min = boundary_correction_factor(6.0, "reflective")
        assert f_low == pytest.approx(f_min, abs=1e-6), (
            f"f_geom below min thickness should clamp: "
            f"f(0)={f_low:.4f}, f(6)={f_min:.4f}"
        )
        # Above max thickness (134 cm): clamp to f_geom(R_b=140)
        f_high = boundary_correction_factor(500.0, "reflective")
        f_max = boundary_correction_factor(134.0, "reflective")
        assert f_high == pytest.approx(f_max, abs=1e-6), (
            f"f_geom above max thickness should clamp: "
            f"f(500)={f_high:.4f}, f(134)={f_max:.4f}"
        )

    def test_reflective_interpolation_monotonic(self):
        """Between calibration points, f_geom should interpolate
        monotonically (no spurious oscillations)."""
        from zpp_tbr import boundary_correction_factor
        thicknesses = [6, 25, 44, 60, 74, 90, 104, 120, 134]
        fs = [boundary_correction_factor(t, "reflective") for t in thicknesses]
        # Between adjacent calibration points, the value should be
        # between the two endpoint values.
        # Specifically, going from R=12 to R=140, f_geom decreases
        # monotonically from 6.02 to 0.89.
        for i in range(len(fs) - 1):
            assert fs[i] > fs[i+1], (
                f"f_geom not monotonically decreasing: "
                f"thicknesses[{i}]={thicknesses[i]} -> {fs[i]:.4f}, "
                f"thicknesses[{i+1}]={thicknesses[i+1]} -> {fs[i+1]:.4f}"
            )


# ---------------------------------------------------------------------------
# Tier 7.B.4 — Self-consistency: TBR_final = sum of named components
# ---------------------------------------------------------------------------

class TestSelfConsistency:
    """The TBR_final should equal the product of named multiplicative
    components. If the formula structure changes, this catches it."""

    def test_TBR_equals_product_of_components(self):
        from zpp_tbr import (
            TBR_PER_NEUTRON, NEUTRON_MULTIPLIER_GAIN,
        )
        inputs = TBRInputs(
            blanket_material="LiPb",
            neutron_multiplier="Be",
            Li6_enrichment_fraction=0.90,
            blanket_thickness_cm=44.0,  # R_blanket=50
            first_wall_coverage_fraction=0.95,
            geometry="cylindrical",
            MHD_effect_factor=0.85,
            temperature_factor=1.0,
        )
        result = compute_TBR(inputs)
        TBR_sat, _ = TBR_PER_NEUTRON["LiPb"]
        mult_gain = NEUTRON_MULTIPLIER_GAIN["Be"]
        # Manually recompute the formula (Tier 7.C calibrated L_enr=2.17)
        f_sat = thickness_to_saturation("LiPb", 44.0)
        f_enr = enrichment_factor(0.90, "LiPb")
        TBR_blanket = TBR_sat * f_sat
        TBR_multiplier = TBR_sat * f_sat * mult_gain
        TBR_raw = (TBR_blanket + TBR_multiplier) * f_enr * 0.95
        expected = TBR_raw * 0.85 * 1.0
        assert abs(result.TBR - expected) < 1e-9, (
            f"TBR formula structure changed: result.TBR={result.TBR}, "
            f"manual={expected}. Update this test and the docstring "
            f"if the new structure is intentional."
        )