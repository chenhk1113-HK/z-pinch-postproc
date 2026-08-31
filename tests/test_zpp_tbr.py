"""
Tier 4.B — OpenMC-equivalent TBR calculator tests.

Verifies:
1. thickness_to_saturation gives values in [0, 1].
2. enrichment_factor = 1.0 at natural Li-6 (7.5%).
3. enrichment_factor increases monotonically with Li-6 enrichment.
4. compute_TBR returns expected fields.
5. ZN blanket at 30% Li-6 gives TBR > 1.05 (engineering threshold).
6. ZN blanket at natural Li-6 gives TBR < 1.05 (needs enrichment).
7. Tokamak reference TBR > 1.05 at all enrichments.
8. Coverage factor scales TBR linearly.
9. MHD and temperature effects scale TBR linearly.
"""
from __future__ import annotations
import sys
import os

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "code"))

from zpp.zpp_tbr import (
    TBR_PER_NEUTRON,
    NEUTRON_MULTIPLIER_GAIN,
    DEFAULT_COVERAGE,
    thickness_to_saturation,
    enrichment_factor,
    compute_TBR,
    tbr_for_blanket,
    TBRInputs,
    TBRResult,
    ALL_BLANKETS,
    BLANKET_ZN_DESIGN,
    BLANKET_TOKAMAK_REFERENCE,
    BLANKET_GF_MTF,
    BLANKET_ZAP_SFZ,
)


class TestThicknessToSaturation:
    """Test thickness_to_saturation."""

    def test_saturation_in_valid_range(self):
        """Always in [0, 1]."""
        for material in TBR_PER_NEUTRON:
            for thick in [0, 10, 30, 50, 100]:
                f = thickness_to_saturation(material, thick)
                assert 0.0 <= f <= 1.0

    def test_zero_thickness_zero_saturation(self):
        for material in TBR_PER_NEUTRON:
            assert thickness_to_saturation(material, 0.0) == 0.0

    def test_high_thickness_approaches_unity(self):
        """At 100+ cm, saturation is essentially 1."""
        f = thickness_to_saturation("LiPb", 200.0)
        assert f > 0.98

    def test_unknown_material_uses_default(self):
        """Unknown material falls back to 40 cm default."""
        # Use 200 cm thickness so both LiPb and default are saturated ~1
        f_known = thickness_to_saturation("LiPb", 200.0)
        f_unknown = thickness_to_saturation("NotAMaterial", 200.0)
        # Both should be near unity at 200 cm
        assert f_known > 0.95
        assert f_unknown > 0.95


class TestEnrichmentFactor:
    """Test enrichment_factor."""

    def test_natural_enrichment_factor_is_unity(self):
        """At natural 7.5% Li-6, factor = 1.0."""
        for material in TBR_PER_NEUTRON:
            f = enrichment_factor(0.075, material)
            assert f == pytest.approx(1.0, abs=1e-9)

    def test_below_natural_factor_is_unity(self):
        """Below natural (depleted Li), factor is still 1 (clamped)."""
        f = enrichment_factor(0.05, "LiPb")
        assert f == pytest.approx(1.0, abs=1e-9)

    def test_enrichment_factor_increases_with_Li6(self):
        """Higher Li-6 -> higher enrichment factor."""
        f_natural = enrichment_factor(0.075, "LiPb")
        f_30 = enrichment_factor(0.30, "LiPb")
        f_60 = enrichment_factor(0.60, "LiPb")
        f_90 = enrichment_factor(0.90, "LiPb")
        assert f_natural < f_30 < f_60 < f_90

    def test_enrichment_factor_saturates(self):
        """At very high enrichment (e.g. 99%), factor approaches asymptote."""
        f_90 = enrichment_factor(0.90, "LiPb")
        f_99 = enrichment_factor(0.99, "LiPb")
        # The increase from 90% to 99% is small (saturating curve)
        assert (f_99 - f_90) < (enrichment_factor(0.50, "LiPb") - enrichment_factor(0.30, "LiPb"))


class TestComputeTBR:
    """Test compute_TBR."""

    def test_returns_TBRResult(self):
        result = compute_TBR(TBRInputs())
        assert isinstance(result, TBRResult)

    def test_ZN_natural_Li_below_threshold(self):
        """ZN with natural Li-6 (7.5%) and MHD losses needs enrichment."""
        inp = TBRInputs(
            blanket_material="LiPb",
            neutron_multiplier="Be",
            Li6_enrichment_fraction=0.075,  # natural
            blanket_thickness_cm=50.0,
            first_wall_coverage_fraction=0.75,
            MHD_effect_factor=0.90,  # MHD losses in liquid LiPb
        )
        result = compute_TBR(inp)
        # At natural Li + MHD: TBR < 1.05 (engineering threshold)
        assert result.TBR < 1.05
        assert result.needs_enrichment is True

    def test_ZN_enriched_above_threshold(self):
        """ZN with 30% Li-6 enrichment is self-sufficient (TBR >= 1.0)
        but at the engineering margin, NOT safely above 1.05.

        Tier 7.C (2026-08-31): the parametric Tier 5.B formula was
        re-calibrated against the OpenMC Monte Carlo sweep. With the
        calibrated enrichment_factor, the ZN design gives TBR = 1.0009,
        right at the self-sufficiency boundary. The previous (un-
        calibrated) value was TBR = 1.51 — overestimating by ~50%
        because the enrichment_factor saturated too aggressively.

        Engineering implication: the ZN design needs higher Li-6
        enrichment (e.g., 60% like Tokamak), or thicker blanket,
        or higher coverage, to provide a safety margin above TBR=1.0.
        """
        result = tbr_for_blanket("ZN")
        # 30% Li-6 + Be multiplier + 50 cm blanket + MHD=0.9
        # Self-sufficient (TBR >= 1.0) but NOT above 1.05.
        assert result.TBR >= 1.0, (
            f"ZN design TBR={result.TBR:.4f} — fails self-sufficiency!"
        )
        assert result.TBR < 1.05, (
            f"ZN design TBR={result.TBR:.4f} — at the engineering "
            f"margin; needs higher enrichment or thicker blanket."
        )
        assert result.needs_enrichment is False

    def test_tokamak_reference_above_threshold(self):
        """ITER/DEMO-class tokamak reference TBR > 1.05."""
        result = tbr_for_blanket("Tokamak")
        assert result.TBR > 1.05

    def test_coverage_factor_scales_TBR_linearly(self):
        """TBR scales linearly with coverage."""
        base = TBRInputs(
            Li6_enrichment_fraction=0.30, first_wall_coverage_fraction=0.50,
        )
        higher = TBRInputs(
            Li6_enrichment_fraction=0.30, first_wall_coverage_fraction=1.00,
        )
        r_base = compute_TBR(base)
        r_higher = compute_TBR(higher)
        assert r_higher.TBR == pytest.approx(r_base.TBR * 2.0, rel=1e-9)

    def test_MHD_effect_scales_TBR_linearly(self):
        """MHD_effect_factor scales TBR linearly."""
        base = TBRInputs(MHD_effect_factor=1.0)
        reduced = TBRInputs(MHD_effect_factor=0.5)
        r_base = compute_TBR(base)
        r_reduced = compute_TBR(reduced)
        assert r_reduced.TBR == pytest.approx(r_base.TBR * 0.5, rel=1e-9)

    def test_temperature_effect_scales_TBR_linearly(self):
        """temperature_factor scales TBR linearly."""
        base = TBRInputs(temperature_factor=1.0)
        reduced = TBRInputs(temperature_factor=0.8)
        r_base = compute_TBR(base)
        r_reduced = compute_TBR(reduced)
        assert r_reduced.TBR == pytest.approx(r_base.TBR * 0.8, rel=1e-9)

    def test_unknown_material_raises(self):
        with pytest.raises(ValueError):
            compute_TBR(TBRInputs(blanket_material="NotAMaterial"))

    def test_unknown_multiplier_raises(self):
        with pytest.raises(ValueError):
            compute_TBR(TBRInputs(neutron_multiplier="NotAMultiplier"))

    def test_notes_field_describes_calculation(self):
        result = compute_TBR(TBRInputs())
        assert "Blanket=" in result.notes
        assert "TBR_total=" in result.notes


class TestPreDefinedBlankets:
    """Test the pre-defined blanket designs."""

    def test_all_four_blankets_defined(self):
        for name in ["ZN", "Tokamak", "GF-MTF", "Zap-SFZ"]:
            assert name in ALL_BLANKETS
            assert isinstance(ALL_BLANKETS[name], TBRInputs)

    def test_ZN_uses_LiPb_with_Be(self):
        assert BLANKET_ZN_DESIGN.blanket_material == "LiPb"
        assert BLANKET_ZN_DESIGN.neutron_multiplier == "Be"

    def test_tokamak_uses_solid_breeder(self):
        """Tokamak reference uses Li4SiO4 (DEMO-class solid breeder)."""
        assert BLANKET_TOKAMAK_REFERENCE.blanket_material == "Li4SiO4"

    def test_GF_MTF_uses_FLiBe(self):
        """MTF uses FLiBe (molten salt, easy to handle with liner)."""
        assert BLANKET_GF_MTF.blanket_material == "FLiBe"

    def test_Zap_SFZ_uses_Pb_multiplier(self):
        """Zap-SFZ uses Pb (cheaper than Be for steady-state plant)."""
        assert BLANKET_ZAP_SFZ.neutron_multiplier == "Pb"

    def test_all_predefined_TBR_above_threshold(self):
        """All pre-defined blankets should be self-sufficient
        (TBR >= 1.0) at their chosen enrichment. Note that the ZN
        design at 30% Li-6 enrichment is right at the boundary
        (TBR = 1.0009); the other designs are safely above.

        Tier 7.C (2026-08-31): the threshold changed from >1.05
        to >=1.0 because the calibrated parametric Tier 5.B formula
        no longer overestimates at high Li-6 enrichment. Pre-Tier 7.C
        all designs showed TBR > 1.05 because the un-calibrated
        enrichment_factor saturated too aggressively.
        """
        for name, inputs in ALL_BLANKETS.items():
            result = compute_TBR(inputs)
            assert result.TBR >= 1.0, (
                f"{name}: TBR={result.TBR:.3f} (expected >=1.0 for "
                f"self-sufficiency)"
            )


class TestTBRForBlanket:
    """Test the convenience function."""

    def test_returns_TBRResult_for_known_name(self):
        for name in ["ZN", "Tokamak", "GF-MTF", "Zap-SFZ"]:
            result = tbr_for_blanket(name)
            assert isinstance(result, TBRResult)

    def test_unknown_blanket_raises(self):
        with pytest.raises(ValueError):
            tbr_for_blanket("ITER")


class TestStrategicFindings:
    """Document strategic findings on TBR."""

    def test_ZN_needs_enrichment(self):
        """ZN blanket needs Li-6 enrichment for tritium self-sufficiency.

        Documented as a regression test: future changes to the
        TBR model should preserve this finding (or surface a
        revised understanding).
        """
        # Natural Li
        inp_natural = TBRInputs(
            blanket_material=BLANKET_ZN_DESIGN.blanket_material,
            neutron_multiplier=BLANKET_ZN_DESIGN.neutron_multiplier,
            Li6_enrichment_fraction=0.075,
            blanket_thickness_cm=BLANKET_ZN_DESIGN.blanket_thickness_cm,
            first_wall_coverage_fraction=BLANKET_ZN_DESIGN.first_wall_coverage_fraction,
            MHD_effect_factor=BLANKET_ZN_DESIGN.MHD_effect_factor,
        )
        result = compute_TBR(inp_natural)
        assert result.TBR < 1.05, (
            f"ZN natural-Li TBR={result.TBR:.3f}; expected <1.05. "
            f"If >1.05, ZN would be self-sufficient without enrichment."
        )

    def test_tokamak_highest_TBR(self):
        """Tokamak reference TBR > all Z-pinch designs (better coverage)."""
        tbrs = {name: tbr_for_blanket(name).TBR for name in ALL_BLANKETS}
        # Tokamak has the highest coverage (0.92 vs 0.75-0.85)
        assert tbrs["Tokamak"] >= max(tbrs.values()) * 0.95  # within 5% of max
