"""
Coupled plant simulator: LCOE adjusted for PFC replacement cost.

Tier 5.C identifies which inputs have the most impact on TBR /
eta_E_plant / LCOE.
Tier 5.D identifies PFC replacement interval (DPA + MHD erosion).
Tier 6.B couples them: PFC replacement CAPEX enters the LCOE
denominator, lowering it (and the LCOE itself goes up if
replacement is needed).

Coupling model:
    LCOE_total = (CAPEX_plant + CAPEX_replacement * N_replacements)
                / annual_net_energy_MWh * lifetime_years
where:
    N_replacements = floor(plant_lifetime / replacement_interval)
    CAPEX_replacement = blanket_module_cost + labor + downtime

The cost model is parametric, calibrated from published fusion
studies (Entler et al. 2018, Segantin et al. 2021). It can be
replaced by real cost codes (SYSCON, PROCESS cost module) via
the v0.5-E adapter interface.
"""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np

from zpp.zpp_plant_simulation import (
    PlantDesign, simulate_plant, PlantSimulationResult,
)
from zpp.zpp_comparison import (
    ZN_DESIGN, ConceptParameters,
)
from zpp.zpp_pfc_lifetime import (
    first_wall_lifetime, PFCDamageInputs, PFCDamageResult,
)


# Default cost parameters from fusion literature.
# Reference: Entler et al. 2018 (DEMO cost study), Segantin 2021.
DEFAULT_BLANKET_MODULE_COST_USD = 5e6  # per module, ~10 m² area
DEFAULT_MODULE_AREA_M2 = 10.0
DEFAULT_LABOR_COST_PER_REPLACEMENT_USD = 50e6
DEFAULT_DOWNTIME_DAYS_PER_REPLACEMENT = 90.0
DEFAULT_FOREGONE_REVENUE_PER_DAY_USD = 1e6  # ~100 MW @ $100/MWh


@dataclass
class ReplacementCostInputs:
    """Cost parameters for PFC replacement."""
    blanket_module_cost_USD: float = DEFAULT_BLANKET_MODULE_COST_USD
    module_area_m2: float = DEFAULT_MODULE_AREA_M2
    labor_cost_per_replacement_USD: float = DEFAULT_LABOR_COST_PER_REPLACEMENT_USD
    downtime_days_per_replacement: float = DEFAULT_DOWNTIME_DAYS_PER_REPLACEMENT
    foregone_revenue_per_day_USD: float = DEFAULT_FOREGONE_REVENUE_PER_DAY_USD


@dataclass
class CoupledPlantResult:
    """Output of coupled plant simulation with PFC replacement cost."""
    # Base plant simulation
    plant_result: PlantSimulationResult
    # PFC lifetime
    pfc_result: PFCDamageResult
    # Replacement cost
    n_replacements: int
    CAPEX_replacement_total_USD: float
    downtime_total_days: float
    foregone_revenue_total_USD: float
    # Adjusted LCOE
    LCOE_base_USD_per_MWh: float
    LCOE_adjusted_USD_per_MWh: float
    LCOE_increase_pct: float
    notes: str


def n_replacements_during_plant_life(
    plant_lifetime_years: float,
    replacement_interval_years: float,
) -> int:
    """Count the number of replacements during plant life.

    The first replacement happens at `replacement_interval_years`
    after plant startup. So n_replacements = floor(plant_lifetime / interval).

    Args:
        plant_lifetime_years: Plant operating lifetime [yr].
        replacement_interval_years: PFC replacement interval [yr].

    Returns:
        Number of replacements during plant life.
    """
    if replacement_interval_years <= 0:
        return 0
    return int(plant_lifetime_years // replacement_interval_years)


def replacement_capex_USD(
    plant_design: PlantDesign,
    pfc_inputs: PFCDamageInputs,
    cost_inputs: ReplacementCostInputs,
    blanket_area_m2: float = None,
) -> float:
    """Total CAPEX for one PFC replacement event.

    Includes blanket modules (number × cost) + labor + downtime
    foregone revenue.
    """
    if blanket_area_m2 is None:
        # Approximate blanket area from first-wall area of geometry
        from zpp.zpp_geometry import get_build
        geometry = get_build(plant_design.geometry_name)
        fw_area_m2 = geometry.first_wall_area_cm2() / 1e4
        blanket_area_m2 = fw_area_m2
    n_modules = int(np.ceil(blanket_area_m2 / cost_inputs.module_area_m2))
    capex_modules = n_modules * cost_inputs.blanket_module_cost_USD
    capex_labor = cost_inputs.labor_cost_per_replacement_USD
    capex_downtime = (
        cost_inputs.downtime_days_per_replacement
        * cost_inputs.foregone_revenue_per_day_USD
    )
    return capex_modules + capex_labor + capex_downtime


def coupled_plant_simulation(
    concept: ConceptParameters = None,
    plant_design: PlantDesign = None,
    pfc_inputs: PFCDamageInputs = None,
    cost_inputs: ReplacementCostInputs = None,
    plant_lifetime_years: float = 30.0,
    nameplate_MW: float = 100.0,
    capacity_factor: float = 0.25,
) -> CoupledPlantResult:
    """Run coupled plant simulation: base + PFC + replacement cost.

    Args:
        concept: Fusion concept (default ZN_DESIGN).
        plant_design: Plant design (default PlantDesign()).
        pfc_inputs: PFC damage inputs (default derived from plant).
        cost_inputs: Replacement cost params (default from literature).
        plant_lifetime_years: Plant operating lifetime [yr].
        nameplate_MW: Plant nameplate [MW].
        capacity_factor: Operational CF.

    Returns:
        CoupledPlantResult with LCOE base and adjusted for PFC cost.
    """
    if concept is None:
        concept = ZN_DESIGN
    if plant_design is None:
        plant_design = PlantDesign()
    if cost_inputs is None:
        cost_inputs = ReplacementCostInputs()
    if pfc_inputs is None:
        # Default PFC inputs from plant design
        pfc_inputs = PFCDamageInputs(
            neutron_wall_load_MW_per_m2=1.0,  # ZN typical
            material="RAFM",
            blanket_fluid="LiPb",
            plant_availability=capacity_factor,
        )
    # 1. Base plant simulation
    plant_result = simulate_plant(
        concept, plant_design, nameplate_MW, capacity_factor,
    )
    # 2. PFC lifetime
    pfc_result = first_wall_lifetime(pfc_inputs)
    # 3. Number of replacements during plant life
    n_repl = n_replacements_during_plant_life(
        plant_lifetime_years, pfc_result.replacement_interval_years,
    )
    # 4. CAPEX per replacement
    capex_per_repl = replacement_capex_USD(
        plant_design, pfc_inputs, cost_inputs,
    )
    capex_replacement_total = n_repl * capex_per_repl
    downtime_total = n_repl * cost_inputs.downtime_days_per_replacement
    foregone_revenue = n_repl * (
        cost_inputs.downtime_days_per_replacement
        * cost_inputs.foregone_revenue_per_day_USD
    )
    # 5. LCOE adjusted
    # Plant CAPEX = capex_per_GWe * nameplate_GWe
    plant_capex_USD = plant_result.bop.eta_E_plant  # placeholder, compute properly
    plant_capex_USD = 10e9 * (nameplate_MW / 1000.0)  # $10B per GWe
    # LCOE base = (plant_capex + opex * lifetime) / annual_net_energy_MWh * lifetime_years
    annual_net_energy = plant_result.annual_net_energy_MWh() if hasattr(plant_result, "annual_net_energy_MWh") else 0
    if annual_net_energy == 0:
        # Fall back to design-point annual energy
        annual_net_energy = nameplate_MW * 8760.0 * capacity_factor
    LCOE_base = plant_capex_USD / (annual_net_energy * plant_lifetime_years) if annual_net_energy > 0 else float("inf")
    LCOE_adjusted = (
        (plant_capex_USD + capex_replacement_total) /
        (annual_net_energy * plant_lifetime_years)
        if annual_net_energy > 0 else float("inf")
    )
    if LCOE_base == 0 or LCOE_base == float("inf"):
        LCOE_increase_pct = 0.0
    else:
        LCOE_increase_pct = (LCOE_adjusted - LCOE_base) / LCOE_base * 100
    notes = (
        f"Plant lifetime={plant_lifetime_years:.1f} yr, "
        f"PFC replacement interval={pfc_result.replacement_interval_years:.1f} yr. "
        f"N replacements={n_repl}. "
        f"CAPEX/replacement=${capex_per_repl:.2e}. "
        f"Total replacement CAPEX=${capex_replacement_total:.2e}. "
        f"LCOE_base=${LCOE_base:.0f}/MWh, LCOE_adjusted=${LCOE_adjusted:.0f}/MWh "
        f"({LCOE_increase_pct:+.1f}%)."
    )
    return CoupledPlantResult(
        plant_result=plant_result,
        pfc_result=pfc_result,
        n_replacements=n_repl,
        CAPEX_replacement_total_USD=capex_replacement_total,
        downtime_total_days=downtime_total,
        foregone_revenue_total_USD=foregone_revenue,
        LCOE_base_USD_per_MWh=LCOE_base,
        LCOE_adjusted_USD_per_MWh=LCOE_adjusted,
        LCOE_increase_pct=LCOE_increase_pct,
        notes=notes,
    )


def couple_sweep_materials(
    plant_design: PlantDesign = None,
    concept: ConceptParameters = None,
    materials: list = None,
    plant_lifetime_years: float = 30.0,
) -> list:
    """Compare coupled LCOE across PFC materials."""
    if plant_design is None:
        plant_design = PlantDesign()
    if concept is None:
        concept = ZN_DESIGN
    if materials is None:
        materials = ["RAFM", "W", "Be", "Cu"]
    results = []
    for mat in materials:
        pfc_inputs = PFCDamageInputs(
            neutron_wall_load_MW_per_m2=1.0,
            material=mat,
            blanket_fluid="LiPb",
            plant_availability=0.25,
        )
        result = coupled_plant_simulation(
            concept, plant_design, pfc_inputs,
            plant_lifetime_years=plant_lifetime_years,
        )
        results.append({
            "material": mat,
            "replacement_interval_years": result.pfc_result.replacement_interval_years,
            "n_replacements": result.n_replacements,
            "LCOE_base": result.LCOE_base_USD_per_MWh,
            "LCOE_adjusted": result.LCOE_adjusted_USD_per_MWh,
            "LCOE_increase_pct": result.LCOE_increase_pct,
        })
    return results


def coupled_sweep_markdown(results: list) -> str:
    """Format coupled sweep as Markdown."""
    headers = ["Material", "Replacement (yr)", "N_repl",
               "LCOE_base ($/MWh)", "LCOE_adj ($/MWh)", "Increase (%)"]
    lines = [
        "| " + " | ".join(headers) + " |",
        "|" + "|".join(["---"] * len(headers)) + "|",
    ]
    for r in results:
        lines.append("| " + " | ".join([
            r["material"],
            f"{r['replacement_interval_years']:.1f}",
            str(r["n_replacements"]),
            f"${r['LCOE_base']:.0f}",
            f"${r['LCOE_adjusted']:.0f}",
            f"{r['LCOE_increase_pct']:+.1f}",
        ]) + " |")
    return "\n".join(lines)
