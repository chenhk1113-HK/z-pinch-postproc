"""
Extended plant cost model with detailed capital + operating cost breakdown.

The Tier 6.B cost model is a 3-term breakdown (modules + labor + downtime).
This module adds more cost categories so that the LCOE estimate is closer
to what real fusion plant cost studies produce:

- **Capital costs**: buildings, tokamak/IFC structure, magnet system,
  heating/CD systems, blanket, tritium plant, BOP, grid connection,
  contingency.
- **Operating costs**: staffing, fuel (T, D), consumables, spares,
  decommissioning.
- **Financing**: discount rate + construction period.

References:
- Entler et al. 2018 "DEMO cost model", Fusion Eng. Des. 138 199.
- Segantin et al. 2021 "BOP for pulsed magnetic fusion", Fusion Eng. Des.
- Whyte et al. 2016 "Small modular fusion: SMF", Phil. Trans. R. Soc. A.
- IAEA 2020 "Fusion Plant Cost-Sharing Methodology".
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
import numpy as np

from zpp_plant_simulation import PlantDesign, simulate_plant
from zpp_pfc_lifetime import first_wall_lifetime, PFCDamageInputs
from zpp_coupled_plant import (
    ReplacementCostInputs, n_replacements_during_plant_life,
)


@dataclass
class CapitalCostBreakdown:
    """Capital cost breakdown by category.

    All values in USD. Categories from Entler 2018 + Segantin 2021.
    """
    # Buildings and site
    land_USD: float = 50e6
    buildings_USD: float = 200e6
    site_improvements_USD: float = 50e6
    # Reactor structure
    reactor_structure_USD: float = 300e6
    vacuum_vessel_USD: float = 200e6
    cryostat_USD: float = 100e6
    # Magnets
    magnet_system_USD: float = 500e6
    # Heating & current drive
    heating_CD_USD: float = 200e6
    # Blanket (initial)
    blanket_initial_USD: float = 250e6
    # Divertor / first wall
    divertor_first_wall_USD: float = 100e6
    # Shielding
    shielding_USD: float = 100e6
    # Tritium
    tritium_plant_USD: float = 100e6
    # BOP
    cooling_system_USD: float = 150e6
    electrical_system_USD: float = 100e6
    instrumentation_control_USD: float = 50e6
    # Pulsed-power (for Z-IFE)
    pulsed_power_USD: float = 0.0
    laser_system_USD: float = 0.0
    # Grid
    grid_connection_USD: float = 50e6
    # Indirect costs (engineering, procurement, construction)
    engineering_USD: float = 200e6
    contingency_pct: float = 0.15

    def total(self, include_pulsed: bool = True) -> float:
        """Total capital cost including contingency."""
        total = (
            self.land_USD + self.buildings_USD + self.site_improvements_USD
            + self.reactor_structure_USD + self.vacuum_vessel_USD + self.cryostat_USD
            + self.magnet_system_USD + self.heating_CD_USD
            + self.blanket_initial_USD + self.divertor_first_wall_USD
            + self.shielding_USD + self.tritium_plant_USD
            + self.cooling_system_USD + self.electrical_system_USD
            + self.instrumentation_control_USD
            + self.grid_connection_USD + self.engineering_USD
        )
        if include_pulsed:
            total += self.pulsed_power_USD + self.laser_system_USD
        return total * (1 + self.contingency_pct)


@dataclass
class OperatingCostBreakdown:
    """Annual operating cost (OPEX).

    All values USD/year. Categories from Entler 2018.
    """
    staffing_USD_per_year: float = 30e6      # ~200 staff @ $150k
    fuel_DT_USD_per_year: float = 5e6       # D + T (T is the expensive one)
    tritium_recovery_USD_per_year: float = 5e6
    consumables_USD_per_year: float = 10e6
    spares_USD_per_year: float = 10e6
    maintenance_USD_per_year: float = 30e6  # ~3% of CAPEX/year
    insurance_USD_per_year: float = 5e6
    overhead_USD_per_year: float = 5e6
    decommissioning_fund_USD_per_year: float = 20e6  # ~10% CAPEX / lifetime

    def total_annual(self) -> float:
        return (
            self.staffing_USD_per_year + self.fuel_DT_USD_per_year
            + self.tritium_recovery_USD_per_year + self.consumables_USD_per_year
            + self.spares_USD_per_year + self.maintenance_USD_per_year
            + self.insurance_USD_per_year + self.overhead_USD_per_year
            + self.decommissioning_fund_USD_per_year
        )


@dataclass
class FinancingParams:
    """Financing parameters for LCOE calculation."""
    discount_rate: float = 0.07          # WACC for nuclear plants
    construction_years: float = 6.0      # Construction period
    capacity_factor: float = 0.25


def capital_recovery_factor(
    discount_rate: float,
    lifetime_years: float,
    construction_years: float = 6.0,
) -> float:
    """Compute capital recovery factor (annualizes CAPEX over lifetime).

    CRF = r(1+r)^n / ((1+r)^n - 1)
    where n is the economic lifetime (operating + construction).

    Args:
        discount_rate: Real discount rate [fraction].
        lifetime_years: Operating lifetime [years].
        construction_years: Construction period [years].

    Returns:
        Capital recovery factor [1/year].
    """
    if discount_rate == 0:
        return 1.0 / lifetime_years
    n = lifetime_years + construction_years
    return discount_rate * (1 + discount_rate) ** n / ((1 + discount_rate) ** n - 1)


@dataclass
class PlantCostResult:
    """Extended plant cost analysis output."""
    # Capital
    capital: CapitalCostBreakdown
    CAPEX_total_USD: float
    # Operating
    operating: OperatingCostBreakdown
    OPEX_annual_USD: float
    # Financing
    financing: FinancingParams
    capital_recovery_factor: float
    # LCOE
    annual_net_energy_MWh: float
    LCOE_capital_USD_per_MWh: float
    LCOE_operating_USD_per_MWh: float
    LCOE_total_USD_per_MWh: float
    # Replacement (from coupled model)
    n_replacements: int
    LCOE_with_replacements_USD_per_MWh: float
    notes: str


def extended_plant_cost(
    plant_design: PlantDesign = None,
    pfc_inputs: PFCDamageInputs = None,
    capital: CapitalCostBreakdown = None,
    operating: OperatingCostBreakdown = None,
    financing: FinancingParams = None,
    plant_lifetime_years: float = 30.0,
    replacement_cost: ReplacementCostInputs = None,
) -> PlantCostResult:
    """Compute extended plant LCOE with full cost breakdown.

    Args:
        plant_design: Plant design (default PlantDesign()).
        pfc_inputs: PFC damage inputs (default RAFM, 1 MW/m², 25% CF).
        capital: Capital cost breakdown (default literature).
        operating: Operating cost breakdown (default literature).
        financing: Financing params (default 7% WACC, 6 yr construction).
        plant_lifetime_years: Plant operating lifetime [years].
        replacement_cost: PFC replacement cost params.

    Returns:
        PlantCostResult with full breakdown.
    """
    if plant_design is None:
        plant_design = PlantDesign()
    if pfc_inputs is None:
        pfc_inputs = PFCDamageInputs(material="RAFM", plant_availability=0.25)
    if capital is None:
        capital = CapitalCostBreakdown()
    if operating is None:
        operating = OperatingCostBreakdown()
    if financing is None:
        financing = FinancingParams()
    if replacement_cost is None:
        replacement_cost = ReplacementCostInputs()
    # CAPEX
    capex = capital.total(include_pulsed=True)
    # OPEX
    opex = operating.total_annual()
    # CRF
    crf = capital_recovery_factor(
        financing.discount_rate,
        plant_lifetime_years,
        financing.construction_years,
    )
    # Plant annual energy
    # First, plant simulation for rep-rate and P_net
    from zpp_comparison import ZN_DESIGN
    plant_result = simulate_plant(
        ZN_DESIGN, plant_design,
        nameplate_MW=100, capacity_factor=financing.capacity_factor,
    )
    annual_net_energy = (
        plant_result.P_net_electric_MW * 8760.0 * financing.capacity_factor
    )
    # PFC replacement
    pfc_result = first_wall_lifetime(pfc_inputs)
    n_repl = n_replacements_during_plant_life(
        plant_lifetime_years, pfc_result.replacement_interval_years,
    )
    # Per-event cost
    from zpp_coupled_plant import replacement_capex_USD
    capex_per_replacement = replacement_capex_USD(
        plant_design, pfc_inputs, replacement_cost,
    )
    replacement_capital_total = n_repl * capex_per_replacement
    # LCOE components
    # LCOE_capital = CRF * CAPEX / annual_energy
    LCOE_capital = (crf * capex) / annual_net_energy if annual_net_energy > 0 else float("inf")
    # LCOE_operating = OPEX / annual_energy
    LCOE_operating = opex / annual_net_energy if annual_net_energy > 0 else float("inf")
    LCOE_total = LCOE_capital + LCOE_operating
    # LCOE with replacements
    capex_with_repl = capex + replacement_capital_total
    LCOE_with_repl = (crf * capex_with_repl) / annual_net_energy + LCOE_operating if annual_net_energy > 0 else float("inf")
    notes = (
        f"Plant lifetime={plant_lifetime_years:.1f} yr. "
        f"CAPEX=${capex:.2e}, OPEX=${opex:.2e}/yr. "
        f"CRF={crf:.4f} (r={financing.discount_rate:.2%}, "
        f"n={plant_lifetime_years+financing.construction_years:.1f}). "
        f"Annual energy={annual_net_energy:.0f} MWh. "
        f"LCOE: capital=${LCOE_capital:.0f}/MWh, "
        f"operating=${LCOE_operating:.0f}/MWh, "
        f"total=${LCOE_total:.0f}/MWh. "
        f"With {n_repl} PFC replacements: ${LCOE_with_repl:.0f}/MWh."
    )
    return PlantCostResult(
        capital=capital,
        CAPEX_total_USD=capex,
        operating=operating,
        OPEX_annual_USD=opex,
        financing=financing,
        capital_recovery_factor=crf,
        annual_net_energy_MWh=annual_net_energy,
        LCOE_capital_USD_per_MWh=LCOE_capital,
        LCOE_operating_USD_per_MWh=LCOE_operating,
        LCOE_total_USD_per_MWh=LCOE_total,
        n_replacements=n_repl,
        LCOE_with_replacements_USD_per_MWh=LCOE_with_repl,
        notes=notes,
    )


def cost_breakdown_markdown(result: PlantCostResult) -> str:
    """Format the cost breakdown as Markdown."""
    lines = [
        "# Extended Plant Cost Analysis\n",
        f"**Plant lifetime**: {result.financing.capacity_factor * 100:.0f}% CF, "
        f"discount rate {result.financing.discount_rate:.0%}.\n",
        "## Capital cost breakdown\n",
    ]
    cap = result.capital
    items = [
        ("Land", cap.land_USD),
        ("Buildings", cap.buildings_USD),
        ("Site improvements", cap.site_improvements_USD),
        ("Reactor structure", cap.reactor_structure_USD),
        ("Vacuum vessel", cap.vacuum_vessel_USD),
        ("Cryostat", cap.cryostat_USD),
        ("Magnet system", cap.magnet_system_USD),
        ("Heating & CD", cap.heating_CD_USD),
        ("Blanket (initial)", cap.blanket_initial_USD),
        ("Divertor/first wall", cap.divertor_first_wall_USD),
        ("Shielding", cap.shielding_USD),
        ("Tritium plant", cap.tritium_plant_USD),
        ("Cooling system", cap.cooling_system_USD),
        ("Electrical system", cap.electrical_system_USD),
        ("I&C", cap.instrumentation_control_USD),
        ("Pulsed power", cap.pulsed_power_USD),
        ("Laser system", cap.laser_system_USD),
        ("Grid connection", cap.grid_connection_USD),
        ("Engineering", cap.engineering_USD),
    ]
    for name, val in items:
        if val > 0:
            lines.append(f"- {name}: ${val/1e6:.0f}M")
    lines.append(f"- **Contingency ({cap.contingency_pct:.0%})**: ${cap.total(include_pulsed=False) * cap.contingency_pct / 1e6:.0f}M")
    lines.append(f"- **Total CAPEX**: ${result.CAPEX_total_USD/1e9:.2f}B")
    lines.append("\n## Operating cost (annual)\n")
    op = result.operating
    op_items = [
        ("Staffing", op.staffing_USD_per_year),
        ("Fuel (D+T)", op.fuel_DT_USD_per_year),
        ("Tritium recovery", op.tritium_recovery_USD_per_year),
        ("Consumables", op.consumables_USD_per_year),
        ("Spares", op.spares_USD_per_year),
        ("Maintenance", op.maintenance_USD_per_year),
        ("Insurance", op.insurance_USD_per_year),
        ("Overhead", op.overhead_USD_per_year),
        ("Decommissioning fund", op.decommissioning_fund_USD_per_year),
    ]
    for name, val in op_items:
        lines.append(f"- {name}: ${val/1e6:.1f}M/yr")
    lines.append(f"- **Total OPEX**: ${result.OPEX_annual_USD/1e6:.1f}M/yr")
    lines.append("\n## LCOE\n")
    lines.append(f"- Annual energy: {result.annual_net_energy_MWh:.0f} MWh")
    lines.append(f"- Capital recovery factor: {result.capital_recovery_factor:.4f}")
    lines.append(f"- LCOE (capital): ${result.LCOE_capital_USD_per_MWh:.0f}/MWh")
    lines.append(f"- LCOE (operating): ${result.LCOE_operating_USD_per_MWh:.0f}/MWh")
    lines.append(f"- **LCOE (total)**: ${result.LCOE_total_USD_per_MWh:.0f}/MWh")
    lines.append(f"- LCOE with {result.n_replacements} PFC replacements: "
                  f"${result.LCOE_with_replacements_USD_per_MWh:.0f}/MWh")
    return "\n".join(lines)
