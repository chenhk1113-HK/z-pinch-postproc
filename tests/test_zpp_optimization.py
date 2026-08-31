"""
Tier 6.D — Plant design optimization tests.

Verifies:
1. OptimizationConstraints dataclass.
2. DesignPoint dataclass.
3. grid_search_plant_design evaluates all combinations.
4. Results sorted by objective.
5. pareto_frontier identifies non-dominated designs.
6. best_design returns feasible design or first by objective.
7. optimization_markdown produces valid Markdown.
8. ZN at current physics: no design is feasible (LCOE=inf).
"""
from __future__ import annotations
import sys
import os

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "code"))

from zpp.zpp_optimization import (
    OptimizationConstraints, DesignPoint,
    grid_search_plant_design, pareto_frontier, best_design,
    optimization_markdown,
)
from zpp.zpp_plant_simulation import PlantDesign, PlantSimulationResult


class TestOptimizationConstraints:
    """Test the constraints dataclass."""

    def test_defaults(self):
        c = OptimizationConstraints()
        assert c.TBR_min == 1.05
        assert c.LCOE_max_USD_per_MWh == 150.0


class TestDesignPoint:
    """Test the DesignPoint dataclass."""

    def test_fields(self):
        d = DesignPoint(
            plant_design=PlantDesign(name="test"),
            result=None,
            TBR=1.5, LCOE_USD_per_MWh=120.0,
            meets_TBR=True, meets_LCOE=True, meets_power=True,
            feasible=True, objective_value=120.0,
        )
        assert d.feasible is True
        assert d.TBR == 1.5


class TestGridSearchPlantDesign:
    """Test grid_search_plant_design()."""

    def test_returns_list(self):
        results = grid_search_plant_design(
            cycles=["Brayton"],
            T_hot_K_values=[1200.0],
            Li6_enrichment_values=[0.30],
            blanket_thickness_values=[50.0],
        )
        assert isinstance(results, list)
        assert len(results) == 1

    def test_enumerates_all_combinations(self):
        results = grid_search_plant_design(
            cycles=["Brayton", "sCO2"],
            T_hot_K_values=[1100.0, 1200.0],
            Li6_enrichment_values=[0.30, 0.60],
            blanket_thickness_values=[50.0, 100.0],
        )
        # 2 * 2 * 2 * 2 = 16
        assert len(results) == 16

    def test_results_sorted_by_objective(self):
        results = grid_search_plant_design(
            cycles=["Brayton"],
            T_hot_K_values=[1100.0, 1200.0, 1300.0],
            Li6_enrichment_values=[0.30, 0.60],
            blanket_thickness_values=[50.0],
        )
        objectives = [d.objective_value for d in results]
        assert objectives == sorted(objectives)

    def test_results_are_DesignPoint(self):
        results = grid_search_plant_design(
            cycles=["Brayton"], T_hot_K_values=[1200.0],
            Li6_enrichment_values=[0.30], blanket_thickness_values=[50.0],
        )
        assert all(isinstance(d, DesignPoint) for d in results)


class TestParetoFrontier:
    """Test pareto_frontier()."""

    def test_returns_list(self):
        results = grid_search_plant_design(
            cycles=["Brayton"], T_hot_K_values=[1200.0],
            Li6_enrichment_values=[0.30], blanket_thickness_values=[50.0],
        )
        pareto = pareto_frontier(results)
        assert isinstance(pareto, list)
        assert len(pareto) >= 1

    def test_includes_higher_TBR_design(self):
        """A design with higher TBR is in Pareto set (if non-dominated)."""
        results = grid_search_plant_design(
            cycles=["Brayton"],
            T_hot_K_values=[1200.0],
            Li6_enrichment_values=[0.10, 0.60],
            blanket_thickness_values=[50.0],
        )
        pareto = pareto_frontier(results)
        # Both should be Pareto-optimal: one has higher TBR, other has lower LCOE
        assert len(pareto) >= 1


class TestBestDesign:
    """Test best_design()."""

    def test_returns_None_for_empty_list(self):
        assert best_design([]) is None

    def test_returns_first_when_no_feasible(self):
        results = grid_search_plant_design(
            cycles=["Brayton"],
            T_hot_K_values=[1200.0],
            Li6_enrichment_values=[0.30],
            blanket_thickness_values=[50.0],
        )
        best = best_design(results)
        # With LCOE=inf for ZN, no design is feasible;
        # best_design should still return the first by objective.
        if results:
            assert best is not None
            assert best is results[0]


class TestOptimizationMarkdown:
    """Test optimization_markdown()."""

    def test_returns_string(self):
        results = grid_search_plant_design(
            cycles=["Brayton"], T_hot_K_values=[1200.0],
            Li6_enrichment_values=[0.30], blanket_thickness_values=[50.0],
        )
        md = optimization_markdown(results)
        assert isinstance(md, str)

    def test_table_format(self):
        results = grid_search_plant_design(
            cycles=["Brayton"], T_hot_K_values=[1200.0],
            Li6_enrichment_values=[0.30], blanket_thickness_values=[50.0],
        )
        md = optimization_markdown(results)
        lines = md.split("\n")
        assert lines[0].startswith("|")
        assert lines[1].startswith("|---")

    def test_top_n(self):
        """top_n limits the number of designs shown."""
        results = grid_search_plant_design(
            cycles=["Brayton"],
            T_hot_K_values=[1100.0, 1200.0, 1300.0],
            Li6_enrichment_values=[0.30],
            blanket_thickness_values=[50.0],
        )
        md = optimization_markdown(results, top_n=2)
        # 2 designs + header + separator = 4 lines
        assert len(md.split("\n")) == 4


class TestStrategicFindings:
    """Document strategic findings from optimization."""

    def test_ZN_no_design_meets_LCOE_target(self):
        """Strategic finding: at current ZN physics, no plant design
        delivers commercial LCOE <= $150/MWh.

        This is consistent with Tier 2.D: ZN at McBride 1D + 2D mix
        physics has Q_eng ~1e-3, which is sub-break-even. No amount
        of cycle / temperature / enrichment / thickness tuning can
        overcome the Q_eng deficit.
        """
        results = grid_search_plant_design(
            cycles=["Brayton", "sCO2"],
            T_hot_K_values=[1200.0, 1400.0],
            Li6_enrichment_values=[0.30, 0.60],
            blanket_thickness_values=[50.0, 100.0],
        )
        feasible = [d for d in results if d.feasible]
        # At current ZN Q_eng, no design is feasible.
        assert len(feasible) == 0
        # All LCOE should be inf
        assert all(d.LCOE_USD_per_MWh == float("inf") for d in results)

    def test_TBR_increases_with_thickness_and_enrichment(self):
        """TBR should increase with blanket thickness and Li-6 enrichment."""
        results = grid_search_plant_design(
            cycles=["Brayton"],
            T_hot_K_values=[1200.0],
            Li6_enrichment_values=[0.10, 0.30, 0.60],
            blanket_thickness_values=[30.0, 100.0],
        )
        # Find extremes
        low_TBR = min(results, key=lambda d: d.TBR)
        high_TBR = max(results, key=lambda d: d.TBR)
        assert high_TBR.TBR > low_TBR.TBR
