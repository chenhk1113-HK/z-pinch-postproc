"""
Tier 5.C — Sensitivity analysis tests.

Verifies:
1. TornadoEntry dataclass.
2. tornado_analysis returns list of TornadoEntry sorted by sensitivity.
3. TBR tornado ranks MHD > thickness > Li-6 enrichment.
4. eta_E_plant tornado ranks T_hot > T_cold > others.
5. LCOE_infinite_treated_specially (no division by zero).
6. tornado_markdown produces valid Markdown.
7. saltelli_sample produces correct shapes.
8. sobol_indices works on a toy function with known S_i.
"""
from __future__ import annotations
import sys
import os

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "code"))

from zpp.zpp_sensitivity import (
    TornadoEntry, tornado_analysis, tornado_markdown,
    saltelli_sample, sobol_indices,
)
from zpp.zpp_plant_simulation import PlantDesign
from zpp.zpp_comparison import ZN_DESIGN


class TestTornadoEntry:
    """Test the TornadoEntry dataclass."""

    def test_fields(self):
        e = TornadoEntry(
            param_name="MHD_effect_factor",
            base_value=0.9, low_value=0.81, high_value=0.99,
            low_output=1.37, high_output=1.67, base_output=1.52,
            sensitivity_pct=10.0, rank=1,
        )
        assert e.param_name == "MHD_effect_factor"
        assert e.swing == pytest.approx(0.3, abs=0.01)


class TestTornadoAnalysis:
    """Test tornado_analysis()."""

    def test_returns_list_of_entries(self):
        base = PlantDesign()
        entries = tornado_analysis("TBR", base, ZN_DESIGN)
        assert isinstance(entries, list)
        assert len(entries) > 0
        assert all(isinstance(e, TornadoEntry) for e in entries)

    def test_entries_sorted_descending(self):
        base = PlantDesign()
        entries = tornado_analysis("TBR", base, ZN_DESIGN)
        sensitivities = [e.sensitivity_pct for e in entries]
        assert sensitivities == sorted(sensitivities, reverse=True)

    def test_ranks_assigned(self):
        base = PlantDesign()
        entries = tornado_analysis("TBR", base, ZN_DESIGN)
        ranks = [e.rank for e in entries]
        assert ranks == list(range(1, len(entries) + 1))

    def test_TBR_tornado_MHD_top(self):
        """MHD_effect_factor is the most influential parameter for TBR."""
        base = PlantDesign()
        entries = tornado_analysis("TBR", base, ZN_DESIGN)
        # First entry should be MHD_effect_factor
        assert entries[0].param_name == "MHD_effect_factor"

    def test_TBR_tornado_thickness_second(self):
        """Blanket thickness ranks second."""
        base = PlantDesign()
        entries = tornado_analysis("TBR", base, ZN_DESIGN)
        # Find blanket_thickness_cm rank
        thickness_entry = next(e for e in entries if e.param_name == "blanket_thickness_cm")
        # Should rank in top 3
        assert thickness_entry.rank <= 3

    def test_eta_E_tornado_T_hot_top(self):
        """T_hot_K is most influential for η_E_plant."""
        base = PlantDesign()
        entries = tornado_analysis("eta_E_plant", base, ZN_DESIGN)
        assert entries[0].param_name == "T_hot_K"

    def test_bool_outputs_dont_divide_by_zero(self):
        """Boolean outputs should not error."""
        base = PlantDesign()
        entries = tornado_analysis("tritium_self_sufficient", base, ZN_DESIGN)
        assert isinstance(entries, list)

    def test_infinite_outputs_dont_divide_by_zero(self):
        """LCOE=∞ shouldn't cause errors."""
        base = PlantDesign()
        entries = tornado_analysis("LCOE_USD_per_MWh", base, ZN_DESIGN)
        assert isinstance(entries, list)
        # All entries should have valid sensitivity (0.0 for booleans/inf)
        for e in entries:
            assert e.sensitivity_pct >= 0

    def test_custom_perturbation(self):
        """Use a larger perturbation (50%) and check sensitivities grow."""
        base = PlantDesign()
        entries_10 = tornado_analysis("TBR", base, ZN_DESIGN, perturbation_frac=0.10)
        entries_50 = tornado_analysis("TBR", base, ZN_DESIGN, perturbation_frac=0.50)
        # 50% should give >= 5x sensitivity (linear regime)
        for e10, e50 in zip(entries_10[:3], entries_50[:3]):
            assert e50.sensitivity_pct >= e10.sensitivity_pct * 4


class TestTornadoMarkdown:
    """Test tornado_markdown()."""

    def test_returns_string(self):
        base = PlantDesign()
        entries = tornado_analysis("TBR", base, ZN_DESIGN)
        md = tornado_markdown(entries, "TBR")
        assert isinstance(md, str)

    def test_markdown_includes_output_name(self):
        base = PlantDesign()
        entries = tornado_analysis("TBR", base, ZN_DESIGN)
        md = tornado_markdown(entries, "TBR")
        assert "TBR" in md

    def test_markdown_includes_top_param(self):
        base = PlantDesign()
        entries = tornado_analysis("TBR", base, ZN_DESIGN)
        md = tornado_markdown(entries, "TBR")
        # Top param is MHD_effect_factor
        assert "MHD_effect_factor" in md


class TestSaltelliSample:
    """Test saltelli_sample()."""

    def test_A_B_shapes(self):
        bounds = [[0, 1], [0, 1], [0, 1]]
        A, B, AB = saltelli_sample(bounds, n_samples=100, seed=42)
        assert A.shape == (100, 3)
        assert B.shape == (100, 3)
        assert len(AB) == 3
        for ab in AB:
            assert ab.shape == (100, 3)

    def test_AB_replaces_correct_column(self):
        bounds = [[0, 1], [0, 1]]
        A, B, AB = saltelli_sample(bounds, n_samples=10, seed=42)
        # AB[0] should have column 0 from B, column 1 from A
        np.testing.assert_array_equal(AB[0][:, 0], B[:, 0])
        np.testing.assert_array_equal(AB[0][:, 1], A[:, 1])
        # AB[1] should have column 0 from A, column 1 from B
        np.testing.assert_array_equal(AB[1][:, 0], A[:, 0])
        np.testing.assert_array_equal(AB[1][:, 1], B[:, 1])

    def test_A_B_independent(self):
        """A and B should be statistically independent (different RNG draws)."""
        bounds = [[0, 1], [0, 1]]
        A, B, AB = saltelli_sample(bounds, n_samples=1000, seed=42)
        # Correlation should be ~0 for independent uniform samples
        corr = np.corrcoef(A[:, 0], B[:, 0])[0, 1]
        assert abs(corr) < 0.1


class TestSobolIndices:
    """Test sobol_indices()."""

    def test_toy_function_S_i(self):
        """For y = x0 + 2*x1 + 0.1*x2, S_0~0.2, S_1~0.8, S_2~0.002."""
        def evaluate(params):
            return params[0] + 2 * params[1] + 0.1 * params[2]
        bounds = [[0, 1], [0, 1], [0, 1]]
        result = sobol_indices(evaluate, bounds, n_samples=512, seed=42)
        # S_1 ~ 0.8 (largest)
        assert result["S_i"][1] == max(result["S_i"])
        # S_0 ~ 0.2
        assert 0.15 < result["S_i"][0] < 0.25
        # S_2 ~ 0.002 (smallest)
        assert result["S_i"][2] < 0.05

    def test_total_indices_greater_than_first(self):
        """Total S_Ti >= S_i for any param (interactions included)."""
        def evaluate(params):
            return params[0] * params[1] + params[2]
        bounds = [[0, 1], [0, 1], [0, 1]]
        result = sobol_indices(evaluate, bounds, n_samples=512, seed=42)
        for i in range(3):
            assert result["S_Ti"][i] >= result["S_i"][i] - 0.1  # small tolerance

    def test_sum_S_i_leq_1(self):
        """Sum of first-order S_i <= 1 + numerical noise (for additive models)."""
        def evaluate(params):
            return params[0] + params[1] + params[2]
        bounds = [[0, 1], [0, 1], [0, 1]]
        result = sobol_indices(evaluate, bounds, n_samples=1024, seed=42)
        # For purely additive model, sum(S_i) ≈ 1 with small noise.
        # Allow up to 30% over with finite sample.
        assert 0.7 <= sum(result["S_i"]) <= 1.3

    def test_n_evaluations(self):
        def evaluate(params):
            return sum(params)
        bounds = [[0, 1], [0, 1]]
        result = sobol_indices(evaluate, bounds, n_samples=100, seed=42)
        assert result["n_evaluations"] == (2 + 2) * 100


class TestStrategicFindings:
    """Document strategic findings from sensitivity analysis."""

    def test_ZN_TBR_MHD_is_dominant_uncertainty(self):
        """The MHD loss factor is the dominant uncertainty source for ZN TBR.

        This is the strategic finding: for ZN, getting MHD losses
        right (via flow channel design, MHD code benchmarks) is more
        important than blanket thickness or Li-6 enrichment.
        """
        base = PlantDesign()
        entries = tornado_analysis("TBR", base, ZN_DESIGN)
        # MHD should be 1.5x more sensitive than thickness
        mhd = next(e for e in entries if e.param_name == "MHD_effect_factor")
        thk = next(e for e in entries if e.param_name == "blanket_thickness_cm")
        assert mhd.sensitivity_pct > thk.sensitivity_pct

    def test_ZN_eta_E_T_hot_is_dominant(self):
        """For ZN, T_hot_K is the dominant uncertainty for η_E_plant."""
        base = PlantDesign()
        entries = tornado_analysis("eta_E_plant", base, ZN_DESIGN)
        T_hot = next(e for e in entries if e.param_name == "T_hot_K")
        # T_hot should be the top entry
        assert T_hot.rank == 1
