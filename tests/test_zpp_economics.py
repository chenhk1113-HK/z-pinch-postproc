"""
Tier 2.B — Rep-rate + LCOE model tests.

LCOE (levelized cost of electricity) for a Z-pinch fusion plant
depends on Q_eng, rep-rate, eta_wallplug, eta_E_plant, capacity
factor, CAPEX, OPEX, and discount rate. These tests verify:

1. PlantEconomics dataclass computes P_gross, P_recirc, P_net,
   annual cost, and LCOE correctly.
2. break_even_Q_eng matches the physics formula 1/(eta_wp * eta_E).
3. required_rep_rate_Hz returns inf when Q_eng < break-even.
4. lcoe_pareto_frontier produces a monotonic-decreasing LCOE in
   capacity_factor (and increasing required_rep_rate in Q_eng).
5. The model is design-driven (CAPEX fixed by nameplate, not by
   rep-rate), so the LCOE-vs-Q_eng frontier is bounded below by
   the CAPEX-amortization floor (which doesn't depend on Q_eng
   above break-even).
6. Energy and cost dimensions are consistent (MWh, USD).
"""
from __future__ import annotations
import math
import sys
import os

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "code"))

from zpp_economics import (
    PlantEconomics,
    break_even_Q_eng,
    lcoe_pareto_frontier,
    lcoe_vs_capacity_factor,
    min_rep_rate_for_target_LCOE,
)


class TestPlantEconomicsDataclass:
    """Test the PlantEconomics dataclass."""

    def test_default_plant_above_break_even(self):
        """Default plant (Q=1, eta_wp=0.04) is sub-break-even."""
        plant = PlantEconomics()
        assert plant.required_rep_rate_Hz() == float("inf")

    def test_E_fusion_per_shot(self):
        plant = PlantEconomics(Q_eng=10.0, E_grid_per_shot_MJ=22.0)
        assert plant.E_fusion_per_shot_MJ() == pytest.approx(220.0, abs=1e-9)

    def test_required_rep_rate_above_break_even(self):
        """ZN design: Q=20, eta_wp=0.20, eta_E=0.40 -> required rr for 100 MW."""
        plant = PlantEconomics(
            Q_eng=20.0,
            eta_wallplug_to_liner=0.20,
            eta_E_plant=0.40,
            E_grid_per_shot_MJ=22.0,
            nameplate_MW=100.0,
        )
        # net_per_Hz = 22 * (20*0.4 - 1/0.20) = 22 * (8 - 5) = 66 MW/Hz
        # required = 100 / 66 = 1.515 Hz
        assert plant.required_rep_rate_Hz() == pytest.approx(1.515, rel=1e-3)

    def test_required_rep_rate_returns_inf_below_break_even(self):
        """Sub-break-even Q_eng returns inf (plant cannot produce net power)."""
        plant = PlantEconomics(
            Q_eng=10.0,  # below 12.5 break-even for ZN
            eta_wallplug_to_liner=0.20,
            eta_E_plant=0.40,
        )
        assert plant.required_rep_rate_Hz() == float("inf")

    def test_P_gross_electric_MW(self):
        plant = PlantEconomics(
            Q_eng=20.0,
            eta_E_plant=0.40,
            E_grid_per_shot_MJ=22.0,
            rep_rate_Hz=1.0,
        )
        # P_gross = Q * E_grid * rr * eta_E = 20 * 22 * 1 * 0.4 = 176 MW
        assert plant.P_gross_electric_MW() == pytest.approx(176.0, rel=1e-3)

    def test_P_recirc_MW(self):
        """Recirc = P_gross * 1 / (Q_eng * eta_wp)."""
        plant = PlantEconomics(
            Q_eng=20.0,
            eta_wallplug_to_liner=0.20,
            eta_E_plant=0.40,
            E_grid_per_shot_MJ=22.0,
            rep_rate_Hz=1.0,
        )
        # f_recirc = 1/(20*0.20) = 0.25
        # P_recirc = 176 * 0.25 = 44 MW
        assert plant.P_recirc_MW() == pytest.approx(44.0, rel=1e-3)

    def test_P_net_electric_MW(self):
        """P_net = P_gross - P_recirc."""
        plant = PlantEconomics(
            Q_eng=20.0,
            eta_wallplug_to_liner=0.20,
            eta_E_plant=0.40,
            E_grid_per_shot_MJ=22.0,
            rep_rate_Hz=1.0,
        )
        # P_net = 176 - 44 = 132 MW
        assert plant.P_net_electric_MW() == pytest.approx(132.0, rel=1e-3)

    def test_P_net_zero_below_break_even(self):
        """P_net clamped to 0 when sub-break-even."""
        plant = PlantEconomics(
            Q_eng=5.0, eta_wallplug_to_liner=0.20, eta_E_plant=0.40,
            rep_rate_Hz=1.0, E_grid_per_shot_MJ=22.0,
        )
        assert plant.P_net_electric_MW() == 0.0

    def test_annual_net_energy_MWh(self):
        """annual_net_energy = nameplate * 8760 * CF."""
        plant = PlantEconomics(
            Q_eng=20.0, eta_wallplug_to_liner=0.20, eta_E_plant=0.40,
            nameplate_MW=100.0, capacity_factor=0.25,
        )
        # 100 * 8760 * 0.25 = 219,000 MWh
        assert plant.annual_net_energy_MWh() == pytest.approx(219000.0, abs=1.0)

    def test_capex_total_USD(self):
        plant = PlantEconomics(nameplate_MW=100.0, capex_per_GWe_USD=10e9)
        # 10B * (100/1000) = 1B
        assert plant.capex_total_USD() == pytest.approx(1e9, abs=1.0)

    def test_capex_amortized_USD_uses_CRF(self):
        """CAPEX amortized with capital recovery factor at 7%, 30y."""
        plant = PlantEconomics(
            nameplate_MW=100.0, capex_per_GWe_USD=10e9,
            discount_rate=0.07, plant_lifetime_years=30,
        )
        # CRF = 0.07 * 1.07^30 / (1.07^30 - 1) ~= 0.0806
        # annual = 1B * 0.0806 = 80.6 M$/year
        crf = 0.07 * (1.07 ** 30) / ((1.07 ** 30) - 1)
        expected = 1e9 * crf
        assert plant.capex_amortized_USD_per_year() == pytest.approx(expected, rel=1e-3)

    def test_lcoe_infinite_when_no_energy(self):
        plant = PlantEconomics(nameplate_MW=0.0)
        assert plant.lcoe_USD_per_MWh() == float("inf")


class TestBreakEvenQEng:
    """Test the break-even Q_eng formula."""

    def test_Z_present_break_even(self):
        """Z present (eta_wp=0.04, eta_E=0.40) -> Q_break_even = 62.5."""
        assert break_even_Q_eng(0.04, 0.40) == pytest.approx(62.5, abs=1e-9)

    def test_ZN_design_break_even(self):
        """ZN design (eta_wp=0.20, eta_E=0.40) -> Q_break_even = 12.5."""
        assert break_even_Q_eng(0.20, 0.40) == pytest.approx(12.5, abs=1e-9)

    def test_break_even_inversely_proportional_to_eta_wp(self):
        """Doubling eta_wp halves break-even Q_eng."""
        be_low = break_even_Q_eng(0.10, 0.40)
        be_high = break_even_Q_eng(0.20, 0.40)
        assert be_low == pytest.approx(2 * be_high, rel=1e-9)

    def test_break_even_inversely_proportional_to_eta_E(self):
        """Doubling eta_E halves break-even Q_eng."""
        be_low = break_even_Q_eng(0.20, 0.30)
        be_high = break_even_Q_eng(0.20, 0.60)
        assert be_low == pytest.approx(2 * be_high, rel=1e-9)


class TestLCOEParetoFrontier:
    """Test the lcoe_pareto_frontier function."""

    def test_pareto_returns_list_of_dicts(self):
        frontier = lcoe_pareto_frontier(
            Q_eng_list=[10, 20, 50],
            eta_wallplug_to_liner=0.20,
        )
        assert isinstance(frontier, list)
        assert len(frontier) == 3
        for p in frontier:
            assert "Q_eng" in p
            assert "required_rep_rate_Hz" in p
            assert "lcoe_USD_per_MWh" in p

    def test_pareto_sub_break_even_returns_inf_rep_rate(self):
        frontier = lcoe_pareto_frontier(
            Q_eng_list=[1.0, 5.0, 10.0],
            eta_wallplug_to_liner=0.20,
        )
        for p in frontier:
            assert p["required_rep_rate_Hz"] == float("inf")
            assert p["lcoe_USD_per_MWh"] == float("inf")

    def test_pareto_above_break_even_has_finite_LCOE(self):
        frontier = lcoe_pareto_frontier(
            Q_eng_list=[20, 50, 100, 200],
            eta_wallplug_to_liner=0.20,
        )
        for p in frontier:
            assert p["required_rep_rate_Hz"] != float("inf")
            assert p["lcoe_USD_per_MWh"] < float("inf")
            assert p["lcoe_USD_per_MWh"] > 0

    def test_pareto_rep_rate_decreases_with_Q_eng(self):
        """Above break-even, higher Q_eng -> lower required rep-rate."""
        frontier = lcoe_pareto_frontier(
            Q_eng_list=[20, 50, 100, 200],
            eta_wallplug_to_liner=0.20,
        )
        rr_list = [p["required_rep_rate_Hz"] for p in frontier]
        for i in range(1, len(rr_list)):
            assert rr_list[i] < rr_list[i - 1]

    def test_default_Q_eng_list_is_reasonable(self):
        frontier = lcoe_pareto_frontier(
            Q_eng_list=None,  # use default
            eta_wallplug_to_liner=0.20,
        )
        assert len(frontier) >= 5
        Q_values = [p["Q_eng"] for p in frontier]
        assert Q_values == sorted(Q_values)  # monotonic


class TestLCOEvsCapacityFactor:
    """Test the lcoe_vs_capacity_factor function."""

    def test_lcoe_decreases_with_capacity_factor(self):
        """Higher CF -> more annual energy -> lower LCOE."""
        frontier = lcoe_vs_capacity_factor(
            Q_eng=20.0,
            eta_wallplug_to_liner=0.20,
        )
        lcoe_list = [p["lcoe_USD_per_MWh"] for p in frontier]
        for i in range(1, len(lcoe_list)):
            assert lcoe_list[i] < lcoe_list[i - 1]

    def test_annual_energy_proportional_to_CF(self):
        """annual_net_energy = nameplate * 8760 * CF (linear in CF)."""
        frontier = lcoe_vs_capacity_factor(
            Q_eng=20.0,
            nameplate_MW=100.0,
            eta_wallplug_to_liner=0.20,
        )
        # 100 MW * 8760 h * 0.10 = 87,600 MWh; 0.50 -> 438,000 MWh
        e_low = frontier[0]["annual_net_energy_MWh"]
        e_high = next(
            p for p in frontier if p["capacity_factor"] == 0.50
        )["annual_net_energy_MWh"]
        assert e_high / e_low == pytest.approx(5.0, rel=1e-3)


class TestMinRepRateForTargetLCOE:
    """Test min_rep_rate_for_target_LCOE."""

    def test_returns_inf_below_break_even(self):
        """Below break-even, no rep-rate achieves positive LCOE."""
        rr = min_rep_rate_for_target_LCOE(
            Q_eng=5.0,
            target_lcoe_USD_per_MWh=100.0,
            eta_wallplug_to_liner=0.20,
        )
        assert rr == float("inf")

    def test_returns_required_rep_rate_above_break_even(self):
        """Above break-even, returns the rep-rate needed for nameplate."""
        rr = min_rep_rate_for_target_LCOE(
            Q_eng=20.0,
            target_lcoe_USD_per_MWh=100.0,  # doesn't matter, design-driven model
            eta_wallplug_to_liner=0.20,
        )
        # 1.515 Hz from earlier test
        assert rr == pytest.approx(1.515, rel=1e-3)


class TestSummaryReport:
    """Test the summary() method."""

    def test_summary_contains_all_keys(self):
        plant = PlantEconomics(Q_eng=20.0, eta_wallplug_to_liner=0.20)
        s = plant.summary()
        expected_keys = {
            "Q_eng", "rep_rate_Hz", "required_rep_rate_Hz",
            "eta_wallplug_to_liner", "eta_E_plant", "capacity_factor",
            "E_grid_per_shot_MJ", "E_fusion_per_shot_MJ",
            "P_thermal_GW", "P_gross_electric_MW", "P_recirc_MW",
            "P_net_electric_MW", "P_net_at_required_Hz_MW",
            "nameplate_MW", "annual_net_energy_MWh",
            "capex_amortized_USD_per_year", "annual_opex_USD",
            "annual_tax_insurance_USD", "total_annual_cost_USD",
            "lcoe_USD_per_MWh",
        }
        assert expected_keys.issubset(set(s.keys()))


class TestEndToEndIntegration:
    """End-to-end smoke test of the LCOE model."""

    def test_ZN_design_plant_at_100_MW(self):
        """ZN design at Q=20, 100 MW nameplate, 25% CF -> LCOE ~$470/MWh."""
        plant = PlantEconomics(
            Q_eng=20.0,
            eta_wallplug_to_liner=0.20,
            eta_E_plant=0.40,
            nameplate_MW=100.0,
            capacity_factor=0.25,
            capex_per_GWe_USD=10e9,
        )
        s = plant.summary()
        # Required rep-rate
        assert s["required_rep_rate_Hz"] == pytest.approx(1.515, rel=1e-3)
        # P_net at required rep-rate = nameplate_MW by construction
        assert s["P_net_at_required_Hz_MW"] == pytest.approx(100.0, rel=1e-3)
        # Annual energy = 219 GWh
        assert s["annual_net_energy_MWh"] == pytest.approx(219000.0, abs=1.0)
        # LCOE ~$470/MWh (CAPEX-dominated)
        assert 400 < s["lcoe_USD_per_MWh"] < 550
