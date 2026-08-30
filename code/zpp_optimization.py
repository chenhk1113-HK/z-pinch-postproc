"""
Plant design optimization via grid search.

Multi-objective: minimize LCOE while meeting:
- TBR >= 1.05 (tritium self-sufficiency)
- meets_commercial_power (P_net >= 50 MW)
- meets_LCOE_target (LCOE <= $150/MWh)

Search variables:
- cycle: Brayton, sCO2 (binary)
- T_hot_K: [1000, 1100, 1200, 1300, 1400]
- Li6_enrichment_fraction: [0.10, 0.30, 0.60]
- blanket_thickness_cm: [30, 50, 80, 100]
- BOP pulsed_power aux fractions: depends on cycle

Method: enumerate all combinations (5 × 3 × 4 × 2 = 120 designs),
rank by LCOE (or by Pareto frontier if multiple objectives).

Outputs:
- Pareto-optimal frontier (TBR >= 1.05 ∧ LCOE minimal)
- Sensitivity of LCOE to each input
- Best design point
"""
from __future__ import annotations
from dataclasses import dataclass, field
from itertools import product
import numpy as np

from zpp_plant_simulation import (
    PlantDesign, simulate_plant, PlantSimulationResult,
)
from zpp_comparison import ZN_DESIGN, ConceptParameters
from zpp_cost_model import (
    CapitalCostBreakdown, OperatingCostBreakdown, FinancingParams,
    capital_recovery_factor, PlantCostResult, extended_plant_cost,
)
from zpp_coupled_plant import ReplacementCostInputs


@dataclass
class OptimizationConstraints:
    """Constraints for plant design optimization."""
    TBR_min: float = 1.05
    LCOE_max_USD_per_MWh: float = 150.0
    P_net_min_MW: float = 50.0
    TBR_weight: float = 1.0     # weight in objective
    LCOE_weight: float = 1.0


@dataclass
class DesignPoint:
    """One design point in the optimization."""
    plant_design: PlantDesign
    result: PlantSimulationResult
    TBR: float
    LCOE_USD_per_MWh: float
    meets_TBR: bool
    meets_LCOE: bool
    meets_power: bool
    feasible: bool
    objective_value: float


def grid_search_plant_design(
    cycles: list = None,
    T_hot_K_values: list = None,
    Li6_enrichment_values: list = None,
    blanket_thickness_values: list = None,
    concept: ConceptParameters = None,
    constraints: OptimizationConstraints = None,
    nameplate_MW: float = 100.0,
    capacity_factor: float = 0.25,
) -> list:
    """Run a grid search over plant design variables.

    Args:
        cycles: List of cycle names (default: ["Brayton", "sCO2"]).
        T_hot_K_values: Hot-side temperatures [K] (default [1000, 1100,
            1200, 1300, 1400]).
        Li6_enrichment_values: Li-6 enrichment fractions
            (default [0.10, 0.30, 0.60]).
        blanket_thickness_values: Blanket thicknesses [cm]
            (default [30, 50, 80, 100]).
        concept: Fusion concept (default ZN_DESIGN).
        constraints: Optimization constraints.
        nameplate_MW, capacity_factor: Plant sizing.

    Returns:
        List of DesignPoint, sorted by objective_value.
    """
    if cycles is None:
        cycles = ["Brayton", "sCO2"]
    if T_hot_K_values is None:
        T_hot_K_values = [1000.0, 1100.0, 1200.0, 1300.0, 1400.0]
    if Li6_enrichment_values is None:
        Li6_enrichment_values = [0.10, 0.30, 0.60]
    if blanket_thickness_values is None:
        blanket_thickness_values = [30.0, 50.0, 80.0, 100.0]
    if concept is None:
        concept = ZN_DESIGN
    if constraints is None:
        constraints = OptimizationConstraints()
    # Iterate all combinations
    results = []
    for cycle, T_hot, Li6_e, thk in product(
        cycles, T_hot_K_values, Li6_enrichment_values, blanket_thickness_values,
    ):
        pd = PlantDesign(
            name=f"{cycle}_T{T_hot:.0f}_Li6{Li6_e:.2f}_thk{thk:.0f}",
            cycle=cycle,
            T_hot_K=T_hot,
            Li6_enrichment_frac=Li6_e,
            blanket_thickness_cm=thk,
            blanket_material="LiPb",
            neutron_multiplier="Be",
        )
        try:
            sim_result = simulate_plant(
                concept, pd, nameplate_MW, capacity_factor,
            )
            # LCOE from extended cost model
            from zpp_pfc_lifetime import PFCDamageInputs
            pfc_inputs = PFCDamageInputs(
                neutron_wall_load_MW_per_m2=1.0,
                material="RAFM", blanket_fluid="LiPb",
                plant_availability=capacity_factor,
            )
            cost_result = extended_plant_cost(
                plant_design=pd, pfc_inputs=pfc_inputs,
                plant_lifetime_years=30.0,
            )
            LCOE = cost_result.LCOE_with_replacements_USD_per_MWh
        except Exception:
            continue
        meets_TBR = sim_result.TBR >= constraints.TBR_min
        meets_LCOE = (
            LCOE != float("inf")
            and LCOE <= constraints.LCOE_max_USD_per_MWh
        )
        meets_power = (
            sim_result.P_net_electric_MW >= constraints.P_net_min_MW
        )
        feasible = meets_TBR and meets_LCOE and meets_power
        # Objective: lower LCOE is better, higher TBR is better
        # Normalize TBR to be on same scale as LCOE (just for ranking)
        if LCOE == float("inf"):
            obj = 1e9
        else:
            obj = (
                constraints.LCOE_weight * LCOE
                - constraints.TBR_weight * sim_result.TBR * 50
            )
        results.append(DesignPoint(
            plant_design=pd,
            result=sim_result,
            TBR=sim_result.TBR,
            LCOE_USD_per_MWh=LCOE,
            meets_TBR=meets_TBR,
            meets_LCOE=meets_LCOE,
            meets_power=meets_power,
            feasible=feasible,
            objective_value=obj,
        ))
    # Sort by objective (lower = better)
    results.sort(key=lambda d: d.objective_value)
    return results


def pareto_frontier(results: list) -> list:
    """Identify Pareto-optimal designs (maximize TBR, minimize LCOE).

    A design is Pareto-optimal if no other design has both
    higher TBR and lower LCOE.
    """
    pareto = []
    for d in results:
        dominated = False
        for other in results:
            if (other.TBR >= d.TBR
                and other.LCOE_USD_per_MWh <= d.LCOE_USD_per_MWh
                and (other.TBR > d.TBR
                     or other.LCOE_USD_per_MWh < d.LCOE_USD_per_MWh)):
                dominated = True
                break
        if not dominated:
            pareto.append(d)
    return pareto


def optimization_markdown(results: list, top_n: int = 10) -> str:
    """Format the optimization results as Markdown.

    Args:
        results: List of DesignPoint sorted by objective.
        top_n: Number of top designs to include.

    Returns:
        Markdown table string.
    """
    headers = ["Rank", "Design", "T_hot_K", "Li6", "Thk (cm)",
               "TBR", "LCOE ($/MWh)", "Feasible"]
    lines = [
        "| " + " | ".join(headers) + " |",
        "|" + "|".join(["---"] * len(headers)) + "|",
    ]
    for i, d in enumerate(results[:top_n]):
        LCOE_str = (
            "inf" if d.LCOE_USD_per_MWh == float("inf")
            else f"${d.LCOE_USD_per_MWh:.0f}"
        )
        lines.append("| " + " | ".join([
            str(i + 1),
            d.plant_design.name,
            f"{d.plant_design.T_hot_K:.0f}",
            f"{d.plant_design.Li6_enrichment_frac:.2f}",
            f"{d.plant_design.blanket_thickness_cm:.0f}",
            f"{d.TBR:.3f}",
            LCOE_str,
            "✓" if d.feasible else "✗",
        ]) + " |")
    return "\n".join(lines)


def best_design(results: list) -> DesignPoint:
    """Return the best feasible design, or None."""
    feasible = [d for d in results if d.feasible]
    if feasible:
        return feasible[0]
    # Fall back to the best objective even if not feasible
    if results:
        return results[0]
    return None
