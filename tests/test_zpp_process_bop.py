"""
Tier 4.A — PROCESS-equivalent BOP model tests.

Verifies:
1. Carnot efficiency = 1 - T_cold/T_hot.
2. Cycle efficiency matches the realistic-fraction × Carnot formula.
3. Auxiliary breakdown sums to f_recirc in [0.05, 0.30].
4. BOP result fields are populated correctly.
5. Pre-defined scenarios have sensible η_E (0.30-0.50) and
   f_recirc (0.05-0.25) for fusion plant types.
6. bop_result_to_wallplug_kwargs gives WallPlugChain-compatible fields.
"""
from __future__ import annotations
import sys
import os

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "code"))

from zpp_process_bop import (
    carnot_efficiency,
    cycle_efficiency,
    BRAYTON_EFFICIENCY_FRACTION,
    RANKINE_EFFICIENCY_FRACTION,
    SCO2_EFFICIENCY_FRACTION,
    compute_aux_breakdown,
    compute_f_recirc,
    compute_process_bop,
    bop_result_to_wallplug_kwargs,
    PlantBOPInputs,
    ProcessBOPResult,
    bop_for_scenario,
    SCENARIO_ZN_DESIGN,
    SCENARIO_PACIFIC_FUSION,
    SCENARIO_GENERAL_FUSION,
    SCENARIO_ZAP_SFZ,
    ALL_SCENARIOS,
)


class TestCarnotEfficiency:
    """Test the Carnot efficiency calculation."""

    def test_carnot_300K_cold(self):
        """Carnot = 1 - 300/1200 = 0.75."""
        eta = carnot_efficiency(T_hot_K=1200.0, T_cold_K=300.0)
        assert eta == pytest.approx(0.75, abs=1e-9)

    def test_carnot_zero_when_T_hot_equals_T_cold(self):
        assert carnot_efficiency(300.0, 300.0) == 0.0

    def test_carnot_zero_when_T_hot_below_T_cold(self):
        assert carnot_efficiency(200.0, 300.0) == 0.0

    def test_carnot_increases_with_T_hot(self):
        """Higher T_hot -> higher Carnot."""
        eta_low = carnot_efficiency(900.0, 300.0)
        eta_high = carnot_efficiency(1200.0, 300.0)
        assert eta_high > eta_low


class TestCycleEfficiency:
    """Test the cycle efficiency calculation."""

    def test_brayton_realistic(self):
        """Brayton should be ~0.42-0.45 at 1200/300 K."""
        eta = cycle_efficiency("Brayton", T_hot_K=1200.0, T_cold_K=300.0)
        assert 0.40 < eta < 0.50

    def test_rankine_lower_than_brayton(self):
        """Rankine is less efficient than Brayton at the same T."""
        eta_b = cycle_efficiency("Brayton")
        eta_r = cycle_efficiency("Rankine")
        assert eta_r < eta_b

    def test_sco2_highest_efficiency(self):
        """sCO2 has the highest realistic efficiency fraction."""
        eta_b = cycle_efficiency("Brayton")
        eta_s = cycle_efficiency("sCO2")
        assert eta_s > eta_b

    def test_unknown_cycle_raises(self):
        with pytest.raises(ValueError):
            cycle_efficiency("Stellarator")


class TestAuxBreakdown:
    """Test the auxiliary power breakdown."""

    def test_default_breakdown_has_all_keys(self):
        aux = compute_aux_breakdown()
        expected = {"cryogenic", "magnets", "laser",
                    "pulsed_power_charging", "tritium_handling",
                    "balance_of_plant", "buildings_services"}
        assert expected.issubset(set(aux.keys()))

    def test_no_laser_zeroes_laser_aux(self):
        """has_laser=False sets laser aux to 0."""
        aux = compute_aux_breakdown(has_laser=False)
        assert aux["laser"] == 0.0

    def test_steady_state_zeroes_pulsed_power(self):
        """Steady-state plants don't pay pulsed-power charging."""
        aux = compute_aux_breakdown(is_pulsed=False)
        assert aux["pulsed_power_charging"] == 0.0

    def test_SC_magnets_higher_cryogenic(self):
        """SC magnets need more cryogenic cooling."""
        aux_normal = compute_aux_breakdown(has_superconducting_magnets=False)
        aux_sc = compute_aux_breakdown(has_superconducting_magnets=True)
        assert aux_sc["cryogenic"] > aux_normal["cryogenic"]

    def test_f_recirc_in_realistic_range(self):
        """f_recirc should be 0.05-0.30 for fusion plants."""
        for is_pulsed in [True, False]:
            for has_laser in [True, False]:
                aux = compute_aux_breakdown(
                    is_pulsed=is_pulsed, has_laser=has_laser,
                )
                f = compute_f_recirc(aux)
                assert 0.05 <= f <= 0.30, (
                    f"f_recirc={f} out of range for pulsed={is_pulsed}, laser={has_laser}"
                )


class TestProcessBOP:
    """Test the parametric BOP model."""

    def test_returns_ProcessBOPResult(self):
        inputs = PlantBOPInputs()
        result = compute_process_bop(inputs)
        assert isinstance(result, ProcessBOPResult)

    def test_default_ZN_Brayton_result(self):
        inputs = PlantBOPInputs()  # default = Brayton 1200/300, pulsed, laser
        result = compute_process_bop(inputs)
        assert result.cycle == "Brayton"
        assert 0.30 < result.eta_E_plant < 0.50
        assert 0.10 < result.f_recirc < 0.25
        assert result.eta_plant_aux == pytest.approx(1.0 - result.f_recirc)

    def test_notes_field_describes_calculation(self):
        inputs = PlantBOPInputs()
        result = compute_process_bop(inputs)
        assert "Brayton" in result.notes
        assert "η_E=" in result.notes or "f_recirc=" in result.notes

    def test_f_recirc_over_50pct_raises(self):
        """Plant with f_recirc > 50% is infeasible."""
        inputs = PlantBOPInputs()
        # Custom aux summing to > 0.5
        custom_aux = {
            "cryogenic": 0.3, "magnets": 0.1, "laser": 0.2,
            "pulsed_power_charging": 0.1, "tritium_handling": 0.05,
            "balance_of_plant": 0.05, "buildings_services": 0.02,
        }
        with pytest.raises(ValueError):
            compute_process_bop(inputs, custom_aux=custom_aux)

    def test_round_trip_efficiency(self):
        """eta_recirc_round_trip = eta_E * (1 - f_recirc)."""
        result = compute_process_bop(PlantBOPInputs())
        expected = result.eta_E_plant * (1.0 - result.f_recirc)
        assert result.eta_recirc_round_trip == pytest.approx(expected, rel=1e-9)


class TestPreDefinedScenarios:
    """Test the pre-defined BOP scenarios for fusion concepts."""

    def test_all_four_scenarios_defined(self):
        for name in ["ZN", "PF", "GF-MTF", "Zap-SFZ"]:
            assert name in ALL_SCENARIOS
            assert isinstance(ALL_SCENARIOS[name], PlantBOPInputs)

    def test_ZN_scenario_pulsed_with_laser(self):
        assert SCENARIO_ZN_DESIGN.is_pulsed is True
        assert SCENARIO_ZN_DESIGN.has_laser is True
        assert SCENARIO_ZN_DESIGN.cycle == "Brayton"

    def test_GF_MTF_no_laser_with_SC_magnets(self):
        assert SCENARIO_GENERAL_FUSION.has_laser is False
        assert SCENARIO_GENERAL_FUSION.has_superconducting_magnets is True

    def test_Zap_SFZ_steady_state(self):
        assert SCENARIO_ZAP_SFZ.is_pulsed is False
        assert SCENARIO_ZAP_SFZ.has_laser is False

    def test_PF_uses_sCO2(self):
        assert SCENARIO_PACIFIC_FUSION.cycle == "sCO2"

    def test_all_scenarios_have_sensible_eta_E(self):
        """All scenarios should have η_E in 0.30-0.50 (realistic)."""
        for name, inputs in ALL_SCENARIOS.items():
            result = compute_process_bop(inputs)
            assert 0.30 < result.eta_E_plant < 0.50, (
                f"{name}: η_E={result.eta_E_plant:.3f} outside 0.30-0.50"
            )

    def test_all_scenarios_have_sensible_f_recirc(self):
        """All scenarios should have f_recirc in 0.05-0.30."""
        for name, inputs in ALL_SCENARIOS.items():
            result = compute_process_bop(inputs)
            assert 0.05 < result.f_recirc < 0.30, (
                f"{name}: f_recirc={result.f_recirc:.3f} outside 0.05-0.30"
            )

    def test_Zap_SFZ_lowest_f_recirc(self):
        """Steady-state Zap-SFZ should have the lowest f_recirc
        (no pulsed-power charging)."""
        all_f_recirc = {
            name: compute_process_bop(inputs).f_recirc
            for name, inputs in ALL_SCENARIOS.items()
        }
        assert all_f_recirc["Zap-SFZ"] == min(all_f_recirc.values())


class TestBOPForScenario:
    """Test the convenience function."""

    def test_bop_for_scenario_returns_result(self):
        for name in ["ZN", "PF", "GF-MTF", "Zap-SFZ"]:
            result = bop_for_scenario(name)
            assert isinstance(result, ProcessBOPResult)
            assert result.cycle == ALL_SCENARIOS[name].cycle

    def test_unknown_scenario_raises(self):
        with pytest.raises(ValueError):
            bop_for_scenario("ITER")


class TestBOPToWallPlugKwargs:
    """Test the BOP-to-WallPlugChain adapter."""

    def test_returns_eta_E_and_f_recirc(self):
        result = bop_for_scenario("ZN")
        kwargs = bop_result_to_wallplug_kwargs(result)
        assert "eta_E_plant" in kwargs
        assert "f_recirc" in kwargs
        assert kwargs["eta_E_plant"] == result.eta_E_plant
        assert kwargs["f_recirc"] == result.f_recirc

    def test_kwargs_apply_to_wallplug(self):
        """Verify the kwargs can construct a WallPlugChain."""
        from zpp_wallplug import WallPlugChain
        result = bop_for_scenario("ZN")
        kwargs = bop_result_to_wallplug_kwargs(result)
        wp = WallPlugChain(**kwargs)
        assert wp.eta_E_plant == result.eta_E_plant
        assert wp.f_recirc == result.f_recirc


class TestEndToEndZNScenario:
    """End-to-end: ZN scenario gives the expected BOP."""

    def test_ZN_round_trip_efficiency(self):
        """ZN at Brayton 1200/300 K, 16.8% f_recirc:
        round-trip = 0.43 * 0.83 = 0.36 (within 0.30-0.40)."""
        result = bop_for_scenario("ZN")
        assert 0.30 < result.eta_recirc_round_trip < 0.40
