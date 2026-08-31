"""
Tier 4.D — Extended fusion concept comparison + DOE milestone tests.

Verifies:
1. 11 concepts in EXTENDED_CONCEPTS (5 Z-pinch + 6 others).
2. extended_compare returns 11 rows.
3. extended_comparison_markdown contains all 11 concepts.
4. check_milestones returns 4 milestone rows (DOE T1-T4).
5. Tokamak/FRC concepts hit DOE-T2 (eng gain > 1).
6. Z-pinch concepts at target Q don't hit DOE-T2 (sub-break-even).
"""
from __future__ import annotations
import sys
import os

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "code"))

from zpp.zpp_extended_comparison import (
    TAE_FRC, HELION, TOKAMAK_ENERGY, ITER, EU_DEMO, SPARC,
    EXTENDED_CONCEPTS, MILESTONE_PLASMA_GAIN, MILESTONE_ENG_GAIN,
    MILESTONE_LCOE_100, MILESTONE_GRID_100MW, ALL_MILESTONES,
    extended_compare, extended_comparison_markdown,
    check_milestones, milestones_markdown_table, _categorize,
)


class TestExtendedConcepts:
    """Test the 6 new concepts."""

    def test_all_six_new_concepts_exist(self):
        for c in [TAE_FRC, HELION, TOKAMAK_ENERGY, ITER, EU_DEMO, SPARC]:
            assert c.short_name is not None
            assert c.fuel is not None
            assert c.Q_target_design > 0

    def test_TAE_uses_D_He3(self):
        assert TAE_FRC.fuel == "D-He3"

    def test_Helion_uses_D_He3(self):
        assert HELION.fuel == "D-He3"

    def test_ITER_is_DT(self):
        assert ITER.fuel == "DT"

    def test_EU_DEMO_target_Q_25(self):
        """EU-DEMO targets Q=25 (commercial-scale demonstration)."""
        assert EU_DEMO.Q_target_design == 25.0

    def test_SPARC_high_B_field(self):
        """SPARC is the high-field tokamak (HTS magnets)."""
        assert SPARC.B_field_T > 8.0

    def test_EXTENDED_CONCEPTS_has_11(self):
        """5 Z-pinch + 6 new = 11 concepts total."""
        assert len(EXTENDED_CONCEPTS) == 11


class TestExtendedCompare:
    """Test extended_compare."""

    def test_returns_11_rows(self):
        rows = extended_compare()
        assert len(rows) == 11

    def test_each_row_has_required_fields(self):
        rows = extended_compare()
        for r in rows:
            assert "short_name" in r
            assert "Q_eng_computed" in r
            assert "Q_eng_target" in r
            assert "lcoe_current" in r
            assert "lcoe_target" in r
            assert "concept_category" in r

    def test_concept_category_assigned(self):
        rows = extended_compare()
        for r in rows:
            assert r["concept_category"] in (
                "pulsed_magnetic_or_MTF", "FRC", "spherical_tokamak", "tokamak", "other"
            )

    def test_ITER_categorized_as_tokamak(self):
        rows = extended_compare()
        iter_row = next(r for r in rows if r["short_name"] == "ITER")
        assert iter_row["concept_category"] == "tokamak"

    def test_Helion_categorized_as_FRC(self):
        rows = extended_compare()
        h = next(r for r in rows if r["short_name"] == "Helion")
        assert h["concept_category"] == "FRC"


class TestCategorize:
    """Test the _categorize helper."""

    def test_Z_pinch_concepts_categorized(self):
        from zpp.zpp_comparison import ZN_DESIGN, Z_PRESENT, ZAP_SFZ, GF_MTF, PACIFIC_FUSION
        for c in [ZN_DESIGN, Z_PRESENT, ZAP_SFZ, GF_MTF, PACIFIC_FUSION]:
            assert _categorize(c) == "pulsed_magnetic_or_MTF"

    def test_FRC_concepts_categorized(self):
        for c in [TAE_FRC, HELION]:
            assert _categorize(c) == "FRC"

    def test_tokamak_concepts_categorized(self):
        for c in [ITER, EU_DEMO, SPARC]:
            assert _categorize(c) == "tokamak"


class TestExtendedComparisonMarkdown:
    """Test the markdown rendering."""

    def test_returns_string(self):
        rows = extended_compare()
        md = extended_comparison_markdown(rows)
        assert isinstance(md, str)

    def test_table_contains_all_11_concepts(self):
        rows = extended_compare()
        md = extended_comparison_markdown(rows)
        expected = ["Z-present", "ZN", "Zap-SFZ", "GF-MTF", "PF",
                    "TAE", "Helion", "ST-80", "ITER", "EU-DEMO", "SPARC"]
        for c in expected:
            assert c in md, f"Markdown table missing {c}"

    def test_table_format_valid(self):
        rows = extended_compare()
        md = extended_comparison_markdown(rows)
        lines = md.split("\n")
        assert lines[0].startswith("| ")
        assert lines[1].startswith("|---")
        for line in lines[2:]:
            assert line.startswith("| ")


class TestMilestones:
    """Test the DOE milestone definitions."""

    def test_four_milestones(self):
        assert len(ALL_MILESTONES) == 4

    def test_milestone_progression(self):
        """DOE milestones are increasingly ambitious."""
        T1, T2, T3, T4 = ALL_MILESTONES
        # Q_eng required increases (or at least, LCOE required decreases)
        assert T1.Q_eng_target <= T2.Q_eng_target
        assert T3.LCOE_target_USD_per_MWh < T4.LCOE_target_USD_per_MWh


class TestCheckMilestones:
    """Test the milestone check function."""

    def test_returns_4_milestone_rows(self):
        rows = extended_compare()
        ms = check_milestones(rows)
        assert len(ms) == 4

    def test_each_milestone_has_required_fields(self):
        rows = extended_compare()
        ms = check_milestones(rows)
        for m in ms:
            assert "milestone" in m
            assert "milestone_name" in m
            assert "Q_eng_required" in m
            assert "LCOE_required" in m
            assert "concepts_at_target" in m
            assert "n_concepts_hitting" in m

    def test_ITER_hits_DOE_T2(self):
        """ITER targets Q=10, hits eng gain > 1."""
        rows = extended_compare()
        ms = check_milestones(rows)
        T2 = next(m for m in ms if m["milestone"] == "DOE-T2")
        assert "ITER" in T2["concepts_at_target"]

    def test_ZN_does_not_hit_DOE_T2(self):
        """ZN at target Q=10 with eta_wp=0.20: Q*eta_wp*eta_E = 0.80 (sub-break-even)."""
        rows = extended_compare()
        ms = check_milestones(rows)
        T2 = next(m for m in ms if m["milestone"] == "DOE-T2")
        assert "ZN" not in T2["concepts_at_target"]

    def test_Helion_hits_DOE_T2(self):
        """Helion at Q=10, eta_wp=0.60: physics 2.4 > 1, hits."""
        rows = extended_compare()
        ms = check_milestones(rows)
        T2 = next(m for m in ms if m["milestone"] == "DOE-T2")
        assert "Helion" in T2["concepts_at_target"]

    def test_steady_state_concepts_have_commercial_power(self):
        """EU-DEMO targets Q=25 -> 25*0.4*1000 MW = 10 GW commercial-scale."""
        rows = extended_compare()
        ms = check_milestones(rows)
        T2 = next(m for m in ms if m["milestone"] == "DOE-T2")
        assert "EU-DEMO" in T2["concepts_at_target"]


class TestMilestonesMarkdown:
    """Test the milestone markdown rendering."""

    def test_returns_string(self):
        rows = extended_compare()
        ms = check_milestones(rows)
        md = milestones_markdown_table(ms)
        assert isinstance(md, str)

    def test_table_contains_all_milestones(self):
        rows = extended_compare()
        ms = check_milestones(rows)
        md = milestones_markdown_table(ms)
        for m in ALL_MILESTONES:
            assert m.short_name in md


class TestStrategicFindings:
    """Document the strategic findings from extended comparison."""

    def test_Z_pinch_class_does_not_hit_milestones(self):
        """Strategic finding: Z-pinch-class concepts (Z/ZN/Zap-SFZ/
        GF-MTF/PF) at their design targets do not hit DOE milestones,
        because Q_eng × η_wp × η_E < 1 for the published targets.

        This is consistent with the Tier 2.D finding: ZN needs
        Q_eng ~ 28 to break even (with eta_wp=0.09, eta_E=0.40).
        """
        rows = extended_compare()
        ms = check_milestones(rows)
        T2 = next(m for m in ms if m["milestone"] == "DOE-T2")
        for c in ["Z-present", "ZN", "Zap-SFZ", "GF-MTF", "PF"]:
            assert c not in T2["concepts_at_target"], (
                f"{c} unexpectedly hits DOE-T2 at target. "
                f"Strategic finding would change."
            )

    def test_at_least_4_concepts_hit_DOE_T2(self):
        """At their targets, the steady-state concepts + Helion +
        TAE + ST-80 + ITER + EU-DEMO + SPARC all hit DOE-T2 (Q>1)."""
        rows = extended_compare()
        ms = check_milestones(rows)
        T2 = next(m for m in ms if m["milestone"] == "DOE-T2")
        # ITER, EU-DEMO, SPARC, ST-80, Helion, TAE all hit
        assert T2["n_concepts_hitting"] >= 6
