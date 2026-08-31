"""
Tier 5.A — Integrated plant simulation tests.

Verifies:
1. PlantDesign dataclass.
2. PlantSimulationResult dataclass.
3. simulate_plant wires BOP × TBR × geometry × LCOE.
4. tritium_self_sufficient reflects TBR >= 1.05.
5. meets_commercial_power reflects P_net >= 50 MW.
6. sweep_plant_designs runs multiple designs.
7. End-to-end smoke test on ZN.
"""
from __future__ import annotations
import sys
import os

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "code"))

from zpp.zpp_plant_simulation import (
    PlantDesign, PlantSimulation, PlantSimulationResult,
    simulate_plant, sweep_plant_designs,
    TRITIUM_BREEDING_THRESHOLD, COMMERCIAL_LCOE_TARGET_USD_PER_MWH,
    COMMERCIAL_NET_POWER_MW,
)
from zpp.zpp_comparison import ZN_DESIGN, Z_PRESENT, ZAP_SFZ, GF_MTF, PACIFIC_FUSION


class TestPlantDesign:
    """Test the PlantDesign dataclass."""

    def test_default_values(self):
        pd = PlantDesign()
        assert pd.cycle == "Brayton"
        assert pd.T_hot_K == 1200.0
        assert pd.geometry_name == "ZN"
        assert pd.blanket_material == "LiPb"
        assert pd.Li6_enrichment_frac == 0.30

    def test_custom_values(self):
        pd = PlantDesign(
            name="ITER_design",
            cycle="Rankine",
            geometry_name="Tokamak",
            Li6_enrichment_frac=0.60,
        )
        assert pd.name == "ITER_design"
        assert pd.cycle == "Rankine"
        assert pd.geometry_name == "Tokamak"
        assert pd.Li6_enrichment_frac == 0.60


class TestPlantSimulationResult:
    """Test the result dataclass."""

    def test_result_has_all_fields(self):
        zn_plant = PlantDesign(name="test")
        result = simulate_plant(ZN_DESIGN, zn_plant, nameplate_MW=100)
        expected = {
            "plant_design_name", "concept_name", "bop",
            "eta_E_plant", "f_recirc", "eta_recirc_round_trip",
            "geometry_name", "geometry_total_radius_cm",
            "geometry_plasma_volume_L", "geometry_blanket_volume_m3",
            "coverage_fraction", "tbr", "TBR", "tritium_self_sufficient",
            "LCOE_USD_per_MWh", "LCOE_above_break_even",
            "P_net_electric_MW", "required_rep_rate_Hz",
            "achievable_at_design_rep_rate", "design_rep_rate_Hz",
            "nameplate_MW", "capacity_factor", "Q_eng",
            "meets_TBR_threshold", "meets_LCOE_target",
            "meets_commercial_power", "notes",
        }
        assert expected.issubset(set(result.__dict__.keys()))


class TestSimulatePlant:
    """Test simulate_plant()."""

    def test_ZN_default_plant_simulates(self):
        """ZN with default plant design runs end-to-end."""
        zn_plant = PlantDesign(name="ZN_default")
        result = simulate_plant(ZN_DESIGN, zn_plant, nameplate_MW=100)
        assert result.concept_name == "ZN"
        assert result.eta_E_plant > 0
        assert result.f_recirc > 0

    def test_ZN_TBR_above_threshold(self):
        """ZN with 30% Li-6 enrichment and Be multiplier should be TBR-sufficient."""
        zn_plant = PlantDesign(
            Li6_enrichment_frac=0.30,
            MHD_effect_factor=0.90,
        )
        result = simulate_plant(ZN_DESIGN, zn_plant, nameplate_MW=100)
        assert result.TBR >= TRITIUM_BREEDING_THRESHOLD
        assert result.tritium_self_sufficient is True
        assert result.meets_TBR_threshold is True

    def test_ZN_LCOE_infinite_sub_break_even(self):
        """ZN at current Q_eng × η_wp × η_E is sub-break-even, LCOE=∞."""
        zn_plant = PlantDesign()
        result = simulate_plant(ZN_DESIGN, zn_plant, nameplate_MW=100)
        assert result.LCOE_above_break_even is False
        assert result.LCOE_USD_per_MWh == float("inf")
        assert result.meets_LCOE_target is False

    def test_ZN_geometry_used(self):
        """ZN geometry has plasma V ~785 L."""
        zn_plant = PlantDesign(geometry_name="ZN")
        result = simulate_plant(ZN_DESIGN, zn_plant, nameplate_MW=100)
        assert 700 < result.geometry_plasma_volume_L < 900

    def test_Tokamak_geometry_larger(self):
        """Tokamak geometry has 38 m³ plasma volume, much larger than ZN."""
        tk_plant = PlantDesign(geometry_name="Tokamak")
        zn_plant = PlantDesign(geometry_name="ZN")
        r_tk = simulate_plant(ZN_DESIGN, tk_plant, nameplate_MW=100)
        r_zn = simulate_plant(ZN_DESIGN, zn_plant, nameplate_MW=100)
        assert r_tk.geometry_plasma_volume_L > 30000
        assert r_zn.geometry_plasma_volume_L < 1000

    def test_BOP_changes_with_cycle(self):
        """sCO2 cycle has different η_E than Rankine."""
        b_plant = PlantDesign(cycle="Brayton")
        r_plant = PlantDesign(cycle="Rankine")
        s_plant = PlantDesign(cycle="sCO2")
        r_b = simulate_plant(ZN_DESIGN, b_plant, nameplate_MW=100)
        r_r = simulate_plant(ZN_DESIGN, r_plant, nameplate_MW=100)
        r_s = simulate_plant(ZN_DESIGN, s_plant, nameplate_MW=100)
        # sCO2 should have higher eta_E than Rankine
        assert r_s.eta_E_plant > r_r.eta_E_plant
        # Brayton at 1200K should beat Rankine at 800K (default for Rankine)
        assert r_b.eta_E_plant > r_r.eta_E_plant

    def test_enrichment_affects_TBR(self):
        """Higher Li-6 enrichment increases TBR."""
        low_e = simulate_plant(ZN_DESIGN, PlantDesign(Li6_enrichment_frac=0.075), nameplate_MW=100)
        high_e = simulate_plant(ZN_DESIGN, PlantDesign(Li6_enrichment_frac=0.60), nameplate_MW=100)
        assert high_e.TBR > low_e.TBR

    def test_capacity_factor_does_not_change_result_in_current(self):
        """For sub-break-even concepts, CF doesn't matter (LCOE = inf)."""
        result_25 = simulate_plant(ZN_DESIGN, PlantDesign(), nameplate_MW=100, capacity_factor=0.25)
        result_50 = simulate_plant(ZN_DESIGN, PlantDesign(), nameplate_MW=100, capacity_factor=0.50)
        assert result_25.LCOE_USD_per_MWh == float("inf")
        assert result_50.LCOE_USD_per_MWh == float("inf")


class TestSweepPlantDesigns:
    """Test sweep_plant_designs()."""

    def test_returns_list_of_results(self):
        designs = [
            PlantDesign(cycle="Brayton"),
            PlantDesign(cycle="Rankine"),
            PlantDesign(cycle="sCO2"),
        ]
        results = sweep_plant_designs(ZN_DESIGN, designs, nameplate_MW=100)
        assert len(results) == 3

    def test_results_have_different_BOP(self):
        """Three cycles give three different η_E."""
        designs = [
            PlantDesign(cycle="Brayton"),
            PlantDesign(cycle="Rankine"),
            PlantDesign(cycle="sCO2"),
        ]
        results = sweep_plant_designs(ZN_DESIGN, designs, nameplate_MW=100)
        eta_E_values = [r.eta_E_plant for r in results]
        assert len(set(eta_E_values)) == 3  # all distinct


class TestEndToEndZN:
    """End-to-end: ZN plant simulation with all defaults."""

    def test_ZN_full_sim_summary(self):
        zn_plant = PlantDesign()
        result = simulate_plant(ZN_DESIGN, zn_plant, nameplate_MW=100)
        # TBR passes (ZN design has enriched blanket)
        assert result.meets_TBR_threshold is True
        # LCOE fails (ZN sub-break-even)
        assert result.meets_LCOE_target is False
        # Power fails (ZN can't deliver 50 MW at sub-break-even)
        assert result.meets_commercial_power is False
        # The strategic finding: TBR yes, but economics no.

    def test_ZN_notes_contains_summary(self):
        zn_plant = PlantDesign()
        result = simulate_plant(ZN_DESIGN, zn_plant, nameplate_MW=100)
        assert "Plant=ZN_design" in result.notes
        assert "Concept=ZN" in result.notes
        assert "TBR" in result.notes
        assert "LCOE" in result.notes
