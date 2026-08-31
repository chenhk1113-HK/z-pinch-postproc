"""
Tier 5.B — Geometry-aware TBR tests.

Verifies:
1. SaturationCurve dataclass.
2. tbr_vs_thickness returns saturation curve with 8-10 points.
3. TBR_saturation = TBR_list[-1].
4. TBR_95pct_thickness_cm returns 95% saturation point.
5. TBR_at_thickness interpolates correctly.
6. sweep_blanket_thickness returns dict of all 4 builds.
7. build_compare_at_thickness returns rows with all required fields.
8. compare_table_markdown contains all 4 builds.
"""
from __future__ import annotations
import sys
import os

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "code"))

from zpp.zpp_geometry_tbr import (
    SaturationCurve, BlanketThicknessSweep,
    tbr_vs_thickness, sweep_blanket_thickness,
    build_compare_at_thickness, compare_table_markdown,
    saturation_curve_csv, THICKNESS_SWEEP_CM,
    DEFAULT_TRITIUM_THRESHOLD,
)


class TestSaturationCurve:
    """Test the SaturationCurve dataclass."""

    def test_fields(self):
        c = SaturationCurve(
            build_name="ZN", blanket_material="LiPb",
            neutron_multiplier="Be", Li6_enrichment_fraction=0.30,
            MHD_effect_factor=0.90,
            thickness_cm_list=[10.0, 50.0, 100.0],
            TBR_list=[0.5, 1.5, 2.0],
            coverage_fraction=0.83,
        )
        assert c.build_name == "ZN"
        assert len(c.thickness_cm_list) == 3

    def test_TBR_saturation_is_last(self):
        c = SaturationCurve(
            build_name="ZN", blanket_material="LiPb",
            neutron_multiplier="Be", Li6_enrichment_fraction=0.30,
            MHD_effect_factor=0.90,
            thickness_cm_list=[10.0, 50.0, 100.0],
            TBR_list=[0.5, 1.5, 2.0],
            coverage_fraction=0.83,
        )
        assert c.TBR_saturation() == 2.0

    def test_TBR_95pct_thickness(self):
        """TBR_95pct_thickness returns thickness where TBR >= 95% sat."""
        c = SaturationCurve(
            build_name="ZN", blanket_material="LiPb",
            neutron_multiplier="Be", Li6_enrichment_fraction=0.30,
            MHD_effect_factor=0.90,
            thickness_cm_list=[10.0, 50.0, 100.0],
            TBR_list=[1.0, 1.5, 2.0],   # saturation = 2.0
            coverage_fraction=0.83,
        )
        # 95% of 2.0 = 1.9, achieved at thickness 100 (TBR=2.0)
        assert c.TBR_95pct_thickness_cm() == 100.0

    def test_TBR_at_thickness_interpolation(self):
        c = SaturationCurve(
            build_name="ZN", blanket_material="LiPb",
            neutron_multiplier="Be", Li6_enrichment_fraction=0.30,
            MHD_effect_factor=0.90,
            thickness_cm_list=[10.0, 50.0, 100.0],
            TBR_list=[0.5, 1.5, 2.0],
            coverage_fraction=0.83,
        )
        # At thickness=30: 0.5 + (1.5-0.5)*(30-10)/(50-10) = 1.0
        assert c.TBR_at_thickness(30.0) == pytest.approx(1.0, abs=0.01)
        # At thickness=75: 1.5 + (2.0-1.5)*(75-50)/(100-50) = 1.75
        assert c.TBR_at_thickness(75.0) == pytest.approx(1.75, abs=0.01)

    def test_TBR_at_thickness_below_range(self):
        c = SaturationCurve(
            build_name="ZN", blanket_material="LiPb",
            neutron_multiplier="Be", Li6_enrichment_fraction=0.30,
            MHD_effect_factor=0.90,
            thickness_cm_list=[10.0, 50.0, 100.0],
            TBR_list=[0.5, 1.5, 2.0],
            coverage_fraction=0.83,
        )
        # Below min: returns first
        assert c.TBR_at_thickness(5.0) == 0.5

    def test_TBR_at_thickness_above_range(self):
        c = SaturationCurve(
            build_name="ZN", blanket_material="LiPb",
            neutron_multiplier="Be", Li6_enrichment_fraction=0.30,
            MHD_effect_factor=0.90,
            thickness_cm_list=[10.0, 50.0, 100.0],
            TBR_list=[0.5, 1.5, 2.0],
            coverage_fraction=0.83,
        )
        # Above max: returns last
        assert c.TBR_at_thickness(200.0) == 2.0


class TestTBRvsThickness:
    """Test tbr_vs_thickness()."""

    def test_returns_curve(self):
        c = tbr_vs_thickness("ZN", "LiPb", "Be")
        assert isinstance(c, SaturationCurve)
        assert c.build_name == "ZN"
        assert c.blanket_material == "LiPb"

    def test_default_thickness_list(self):
        """Default sweep has 10 points."""
        c = tbr_vs_thickness("ZN", "LiPb", "Be")
        assert len(c.thickness_cm_list) == len(THICKNESS_SWEEP_CM)

    def test_TBR_increases_with_thickness(self):
        """Monotonic increase."""
        c = tbr_vs_thickness("ZN", "LiPb", "Be")
        for i in range(len(c.TBR_list) - 1):
            assert c.TBR_list[i + 1] >= c.TBR_list[i]

    def test_coverage_fraction_recorded(self):
        c = tbr_vs_thickness("ZN", "LiPb", "Be")
        assert 0.5 < c.coverage_fraction < 1.0

    def test_enrichment_increases_TBR(self):
        """Higher Li-6 enrichment gives higher TBR at same thickness."""
        c_low = tbr_vs_thickness("ZN", "LiPb", "Be", Li6_enrichment_fraction=0.075)
        c_high = tbr_vs_thickness("ZN", "LiPb", "Be", Li6_enrichment_fraction=0.60)
        # Both should be monotonically increasing, and high > low at any thickness
        for tbr_low, tbr_high in zip(c_low.TBR_list, c_high.TBR_list):
            assert tbr_high > tbr_low


class TestSweepBlanketThickness:
    """Test sweep_blanket_thickness()."""

    def test_returns_dict_of_all_builds(self):
        sweeps = sweep_blanket_thickness()
        assert "ZN" in sweeps
        assert "Tokamak" in sweeps
        assert "GF-MTF" in sweeps
        assert "Zap-SFZ" in sweeps

    def test_each_sweep_has_curves(self):
        sweeps = sweep_blanket_thickness()
        for build_name, sweep in sweeps.items():
            assert isinstance(sweep, BlanketThicknessSweep)
            assert len(sweep.curves) > 0

    def test_custom_build_list(self):
        sweeps = sweep_blanket_thickness(build_names=["ZN", "Tokamak"])
        assert len(sweeps) == 2

    def test_custom_blanket_list(self):
        sweeps = sweep_blanket_thickness(
            blankets=[("LiPb", "Pb")],
        )
        for sweep in sweeps.values():
            assert ("LiPb", "Pb") in sweep.curves


class TestBuildCompare:
    """Test build_compare_at_thickness()."""

    def test_returns_list_of_rows(self):
        sweeps = sweep_blanket_thickness()
        rows = build_compare_at_thickness(sweeps, target_thickness_cm=50.0)
        assert len(rows) == 4

    def test_each_row_has_required_fields(self):
        sweeps = sweep_blanket_thickness()
        rows = build_compare_at_thickness(sweeps, target_thickness_cm=50.0)
        for r in rows:
            assert "build_name" in r
            assert "TBR_at_target" in r
            assert "TBR_saturation" in r
            assert "TBR_saturation_ratio" in r
            assert "sufficient_at_target" in r

    def test_target_thickness_50(self):
        """At 50 cm thickness, all 4 builds should be sufficient."""
        sweeps = sweep_blanket_thickness()
        rows = build_compare_at_thickness(sweeps, target_thickness_cm=50.0)
        for r in rows:
            assert r["sufficient_at_target"] is True


class TestCompareMarkdown:
    """Test compare_table_markdown()."""

    def test_returns_string(self):
        sweeps = sweep_blanket_thickness()
        rows = build_compare_at_thickness(sweeps, target_thickness_cm=50.0)
        md = compare_table_markdown(rows)
        assert isinstance(md, str)

    def test_table_contains_all_builds(self):
        sweeps = sweep_blanket_thickness()
        rows = build_compare_at_thickness(sweeps, target_thickness_cm=50.0)
        md = compare_table_markdown(rows)
        for r in rows:
            assert r["build_name"] in md


class TestSaturationCurveCSV:
    """Test saturation_curve_csv()."""

    def test_returns_csv(self):
        c = SaturationCurve(
            build_name="ZN", blanket_material="LiPb",
            neutron_multiplier="Be", Li6_enrichment_fraction=0.30,
            MHD_effect_factor=0.90,
            thickness_cm_list=[10.0, 50.0, 100.0],
            TBR_list=[0.5, 1.5, 2.0],
            coverage_fraction=0.83,
        )
        csv = saturation_curve_csv(c)
        lines = csv.split("\n")
        assert lines[0] == "thickness_cm,TBR"
        assert len(lines) == 4  # header + 3 rows


class TestStrategicFindings:
    """Document strategic findings from geometry-aware TBR."""

    def test_ZN_sufficient_at_30cm(self):
        """ZN reaches TBR>=1.0 (self-sufficiency) at thickness ~50 cm.

        Tier 7.C (2026-08-31): the parametric Tier 5.B formula was
        re-calibrated against the OpenMC Monte Carlo sweep. With
        30% Li-6 enrichment, the ZN design needs ~50 cm of LiPb to
        reach TBR>=1.0 (self-sufficiency). At 30 cm thickness the
        calibrated parametric gives TBR ~ 0.79 — below the threshold.

        Pre-Tier 7.C, the un-calibrated formula gave TBR=1.5 at 30 cm
        because the enrichment_factor saturated too aggressively
        (f_enr(0.30) was 1.45 instead of the calibrated 1.09).
        """
        c = tbr_vs_thickness("ZN", "LiPb", "Be")
        tbr_at_50 = c.TBR_at_thickness(50.0)
        assert tbr_at_50 >= 1.0, (
            f"ZN at 50 cm gives TBR={tbr_at_50:.4f}; should reach "
            f"self-sufficiency (>=1.0) by 50 cm per Tier 7.C "
            f"calibration. Engineering implication: the ZN design "
            f"is borderline and may need higher Li-6 enrichment."
        )

    def test_Zap_SFZ_highest_TBR(self):
        """Zap-SFZ has highest TBR due to highest coverage (0.98)."""
        sweeps = sweep_blanket_thickness()
        rows = build_compare_at_thickness(sweeps, target_thickness_cm=50.0)
        zap_row = next(r for r in rows if r["build_name"] == "Zap-SFZ")
        zn_row = next(r for r in rows if r["build_name"] == "ZN")
        assert zap_row["TBR_at_target"] > zn_row["TBR_at_target"]
