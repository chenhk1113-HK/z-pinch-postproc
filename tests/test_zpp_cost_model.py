"""
Tier 6.C — Extended plant cost model tests.

Verifies:
1. CapitalCostBreakdown dataclass with all categories.
2. OperatingCostBreakdown dataclass.
3. capital_recovery_factor formula.
4. extended_plant_cost returns PlantCostResult.
5. LCOE components sum correctly.
6. CRF > 0 for non-zero discount rate.
7. Be PFC replacement adds to LCOE.
"""
from __future__ import annotations
import sys
import os

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "code"))

from zpp_cost_model import (
    CapitalCostBreakdown, OperatingCostBreakdown,
    FinancingParams, capital_recovery_factor,
    extended_plant_cost, PlantCostResult, cost_breakdown_markdown,
)


class TestCapitalCostBreakdown:
    """Test the capital cost breakdown dataclass."""

    def test_default_values(self):
        c = CapitalCostBreakdown()
        # Default CAPEX ~ $3B before contingency
        total = c.total()
        assert 2e9 < total < 5e9

    def test_contingency_applied(self):
        c = CapitalCostBreakdown()
        # Sub-total without contingency (sum all line items)
        subtotal = (
            c.land_USD + c.buildings_USD + c.site_improvements_USD
            + c.reactor_structure_USD + c.vacuum_vessel_USD + c.cryostat_USD
            + c.magnet_system_USD + c.heating_CD_USD
            + c.blanket_initial_USD + c.divertor_first_wall_USD
            + c.shielding_USD + c.tritium_plant_USD
            + c.cooling_system_USD + c.electrical_system_USD
            + c.instrumentation_control_USD + c.grid_connection_USD
            + c.engineering_USD
        )
        # Total includes 15% contingency
        assert c.total(include_pulsed=False) == pytest.approx(subtotal * 1.15, rel=0.05)

    def test_pulsed_power_zero_by_default(self):
        """For Z-pinch: pulsed_power_USD and laser_system_USD zero by default."""
        c = CapitalCostBreakdown()
        assert c.pulsed_power_USD == 0.0
        assert c.laser_system_USD == 0.0

    def test_pulsed_power_adds_to_total(self):
        """Adding pulsed power increases CAPEX."""
        c1 = CapitalCostBreakdown()
        c2 = CapitalCostBreakdown(pulsed_power_USD=500e6, laser_system_USD=300e6)
        assert c2.total() > c1.total()


class TestOperatingCostBreakdown:
    """Test the operating cost breakdown dataclass."""

    def test_default_annual(self):
        op = OperatingCostBreakdown()
        annual = op.total_annual()
        # Default OPEX ~ $100M/yr
        assert 50e6 < annual < 200e6

    def test_components_sum(self):
        """Total annual = sum of components."""
        op = OperatingCostBreakdown()
        components = (
            op.staffing_USD_per_year + op.fuel_DT_USD_per_year
            + op.tritium_recovery_USD_per_year + op.consumables_USD_per_year
            + op.spares_USD_per_year + op.maintenance_USD_per_year
            + op.insurance_USD_per_year + op.overhead_USD_per_year
            + op.decommissioning_fund_USD_per_year
        )
        assert op.total_annual() == pytest.approx(components, rel=0.01)


class TestCapitalRecoveryFactor:
    """Test the CRF formula."""

    def test_CRF_at_zero_rate(self):
        """At r=0, CRF = 1/lifetime."""
        crf = capital_recovery_factor(
            discount_rate=0.0, lifetime_years=30, construction_years=6,
        )
        # CRF(0, 30) = 1/30
        assert crf == pytest.approx(1.0 / 30, rel=0.01)

    def test_CRF_at_7pct(self):
        """At r=7%, CRF ~0.077."""
        crf = capital_recovery_factor(
            discount_rate=0.07, lifetime_years=30, construction_years=6,
        )
        assert 0.06 < crf < 0.10

    def test_CRF_increases_with_rate(self):
        """CRF increases with discount rate."""
        crf_5 = capital_recovery_factor(0.05, 30, 6)
        crf_10 = capital_recovery_factor(0.10, 30, 6)
        assert crf_10 > crf_5

    def test_CRF_decreases_with_lifetime(self):
        """CRF decreases with longer lifetime."""
        crf_30 = capital_recovery_factor(0.07, 30, 6)
        crf_60 = capital_recovery_factor(0.07, 60, 6)
        assert crf_30 > crf_60


class TestExtendedPlantCost:
    """Test extended_plant_cost()."""

    def test_returns_PlantCostResult(self):
        result = extended_plant_cost()
        assert isinstance(result, PlantCostResult)

    def test_CAPEX_total_positive(self):
        result = extended_plant_cost()
        assert result.CAPEX_total_USD > 0

    def test_OPEX_annual_positive(self):
        result = extended_plant_cost()
        assert result.OPEX_annual_USD > 0

    def test_LCOE_capital_plus_operating_equals_total(self):
        """LCOE_total = LCOE_capital + LCOE_operating."""
        result = extended_plant_cost()
        # When LCOE is finite
        if result.LCOE_total_USD_per_MWh != float("inf"):
            assert result.LCOE_total_USD_per_MWh == pytest.approx(
                result.LCOE_capital_USD_per_MWh + result.LCOE_operating_USD_per_MWh,
                rel=0.01,
            )

    def test_RAFM_zero_replacements_keeps_LCOE_same(self):
        """For RAFM (outlives plant), LCOE_with_repl == LCOE_total."""
        result = extended_plant_cost()
        if result.n_replacements == 0:
            assert result.LCOE_with_replacements_USD_per_MWh == pytest.approx(
                result.LCOE_total_USD_per_MWh, rel=0.01,
            )

    def test_Be_replacements_increase_LCOE(self):
        """For Be (3 replacements), LCOE_with_repl > LCOE_total."""
        from zpp_pfc_lifetime import PFCDamageInputs
        result = extended_plant_cost(
            pfc_inputs=PFCDamageInputs(material="Be", plant_availability=0.25),
        )
        # If annual energy is finite, the increase is visible
        if result.annual_net_energy_MWh > 0:
            assert result.LCOE_with_replacements_USD_per_MWh > result.LCOE_total_USD_per_MWh


class TestCostBreakdownMarkdown:
    """Test cost_breakdown_markdown()."""

    def test_returns_string(self):
        result = extended_plant_cost()
        md = cost_breakdown_markdown(result)
        assert isinstance(md, str)

    def test_contains_capex_total(self):
        result = extended_plant_cost()
        md = cost_breakdown_markdown(result)
        assert "CAPEX" in md
        assert "OPEX" in md
        assert "LCOE" in md


class TestStrategicFindings:
    """Document strategic findings from extended cost model."""

    def test_ZN_CAPEX_realistic(self):
        """ZN plant CAPEX ~$3B is consistent with published estimates.

        Real fusion plant CAPEX estimates:
        - ITER: $20-30B (international project overhead)
        - DEMO: $5-10B (EU estimate)
        - Compact fusion (CFS, Tokamak Energy): $2-5B
        - Z-IFE: $1-5B (smaller, pulsed-magnetic)
        """
        result = extended_plant_cost()
        assert 1e9 < result.CAPEX_total_USD < 1e10

    def test_ZN_OPEX_realistic(self):
        """ZN plant OPEX ~$120M/yr is consistent with published estimates."""
        result = extended_plant_cost()
        assert 50e6 < result.OPEX_annual_USD < 300e6
