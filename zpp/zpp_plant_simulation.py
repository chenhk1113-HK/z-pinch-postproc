"""
Integrated plant simulation: BOP × TBR × geometry × LCOE.

v0.4 shipped four independent models (zpp_process_bop, zpp_tbr,
zpp_geometry, zpp_comparison). This module wires them into a
single `PlantSimulation` so that a design point can be evaluated
end-to-end.

Flow:
    concept (Q_eng, eta_wp, rep_rate, E_grid, ...)
        +
    plant_design (cycle, T_hot, blanket, geometry)
        |
        v
    PlantSimulation.simulate(concept, plant_design)
        |
        +--> BOP model -> eta_E_plant, f_recirc
        +--> Geometry  -> blanket_volume, coverage_fraction
        +--> TBR model -> TBR using coverage × blanket material
        +--> LCOE model -> LCOE using BOP-derived eta_E_plant
        |
        v
    PlantSimulationResult { bop, tbr, geometry, lcoe, tritium_sufficiency, ... }

This is what an end-to-end design study needs. The independent
modules are still available for users who want one piece.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from zpp.zpp_process_bop import (
    PlantBOPInputs, compute_process_bop, bop_for_scenario,
    bop_result_to_wallplug_kwargs, ProcessBOPResult,
)
from zpp.zpp_tbr import (
    TBRInputs, compute_TBR, tbr_for_blanket, TBRResult,
)
from zpp.zpp_geometry import (
    ZIFERadialBuild, get_build, ALL_BUILDS,
)
from zpp.zpp_economics import (
    PlantEconomics,
)
from zpp.zpp_comparison import (
    ConceptParameters, compute_Q_eng, compute_LCOE_proxy,
)
from zpp.zpp_tritium_inventory import (
    TritiumInventoryInputs, tritium_inventory_dynamics,
)


# Default engineering thresholds (used for pass/fail checks).
TRITIUM_BREEDING_THRESHOLD = 1.05  # TBR for tritium self-sufficiency
COMMERCIAL_LCOE_TARGET_USD_PER_MWH = 150.0
COMMERCIAL_NET_POWER_MW = 100.0


@dataclass
class PlantDesign:
    """Inputs describing a fusion plant's design choices.

    Combines the BOP parameters (cycle, T_hot, plant_aux fractions)
    with the geometry parameters (radial build name, blanket
    material, multiplier) and blanket design (enrichment,
    thickness).
    """
    name: str = "ZN_design"
    # BOP parameters
    cycle: str = "Brayton"          # Brayton, Rankine, sCO2
    T_hot_K: float = 1200.0
    T_cold_K: float = 300.0
    P_fusion_MW: float = 2000.0
    is_pulsed: bool = True
    include_laser_aux: bool = True
    include_magnet_aux: bool = True
    include_cryogenic_aux: bool = True
    # Geometry parameters
    geometry_name: str = "ZN"       # ZN, Tokamak, GF-MTF, Zap-SFZ
    # TBR parameters
    blanket_material: str = "LiPb"
    neutron_multiplier: str = "Be"
    blanket_thickness_cm: float = 50.0
    Li6_enrichment_frac: float = 0.30  # 7.5% natural, 30% enriched
    MHD_effect_factor: float = 0.90  # 0.85-1.0 typical for liquid LiPb


@dataclass
class PlantSimulationResult:
    """End-to-end plant simulation output.

    Bundles BOPResult, TBRResult, geometry summary, LCOE proxy,
    and tritium self-sufficiency check.
    """
    # Inputs (echoed back)
    plant_design_name: str
    concept_name: str
    # BOP
    bop: ProcessBOPResult
    eta_E_plant: float
    f_recirc: float
    eta_recirc_round_trip: float
    # Geometry
    geometry_name: str
    geometry_total_radius_cm: float
    geometry_plasma_volume_L: float
    geometry_blanket_volume_m3: float
    coverage_fraction: float
    # TBR
    tbr: TBRResult
    TBR: float
    tritium_self_sufficient: bool
    # LCOE (BOP-derived)
    LCOE_USD_per_MWh: float
    LCOE_above_break_even: bool
    P_net_electric_MW: float
    required_rep_rate_Hz: float
    achievable_at_design_rep_rate: bool
    design_rep_rate_Hz: float
    nameplate_MW: float
    capacity_factor: float
    # Plant Q_eng
    Q_eng: float
    # Pass/fail
    meets_TBR_threshold: bool
    meets_LCOE_target: bool
    meets_commercial_power: bool
    notes: str
    # Tritium inventory dynamics (Item 8 / v2.2.0)
    tritium_doubling_time_days: Optional[float] = None
    tritium_steady_state_inventory_kg: Optional[float] = None
    tritium_time_to_steady_state_days: Optional[float] = None
    tritium_net_production_kg_per_year: Optional[float] = None


@dataclass
class PlantSimulation:
    """A plant simulation that ties BOP × TBR × geometry × LCOE.

    Usage:
        plant = PlantSimulation(
            concept=ZN_DESIGN,
            plant_design=PlantDesign(name="ZN_DESIGN_Brayton"),
        )
        result = plant.simulate(nameplate_MW=100, capacity_factor=0.25)
    """
    concept: ConceptParameters
    plant_design: PlantDesign = field(default_factory=PlantDesign)
    # Optional CAPEX override
    capex_per_GWe_USD: float = 10e9

    def _bop_inputs(self) -> PlantBOPInputs:
        pd = self.plant_design
        return PlantBOPInputs(
            cycle=pd.cycle,
            T_hot_K=pd.T_hot_K,
            T_cold_K=pd.T_cold_K,
            P_fusion_MW=pd.P_fusion_MW,
            is_pulsed=pd.is_pulsed,
            has_laser=pd.include_laser_aux,
            has_superconducting_magnets=pd.include_magnet_aux,
        )

    def _tbr_inputs(self, coverage: float) -> TBRInputs:
        pd = self.plant_design
        return TBRInputs(
            blanket_material=pd.blanket_material,
            neutron_multiplier=pd.neutron_multiplier,
            blanket_thickness_cm=pd.blanket_thickness_cm,
            Li6_enrichment_fraction=pd.Li6_enrichment_frac,
            MHD_effect_factor=pd.MHD_effect_factor,
            first_wall_coverage_fraction=coverage,
        )

    def simulate(
        self,
        nameplate_MW: float = 100.0,
        capacity_factor: float = 0.25,
        startup_inventory_kg: float = 5.0,
        tritium_duration_days: float = 730.0,
    ) -> PlantSimulationResult:
        """Run the full plant simulation.

        Args:
            nameplate_MW: Plant nameplate electric capacity [MW].
            capacity_factor: Fraction of time plant is operational.
            startup_inventory_kg: Initial tritium inventory at plant startup [kg].
                Default 5 kg (ITER TBM-equivalent).
            tritium_duration_days: How long to simulate tritium inventory [days].
                Default 730 (2 years — covers doubling time + initial approach to SS).

        Returns:
            PlantSimulationResult with all sub-model outputs.
        """
        # 1. BOP
        bop = compute_process_bop(self._bop_inputs())
        # 2. Geometry
        geometry = get_build(self.plant_design.geometry_name)
        coverage = geometry.coverage_fraction("Z-pinch" if "Z" in self.plant_design.geometry_name or self.plant_design.geometry_name == "GF-MTF" or self.plant_design.geometry_name == "Zap-SFZ" else "tokamak")
        geo_summary = geometry.summary()
        # 3. TBR using geometry-derived coverage
        tbr = compute_TBR(self._tbr_inputs(coverage))
        # 4. LCOE using BOP-derived eta_E_plant
        lcoe_kwargs = bop_result_to_wallplug_kwargs(bop)
        # Override eta_E_plant from BOP, keep user's f_recirc override.
        lcoe_proxy = compute_LCOE_proxy(
            self.concept,
            nameplate_MW=nameplate_MW,
            capacity_factor=capacity_factor,
            capex_per_GWe_USD=self.capex_per_GWe_USD,
            eta_E_plant=lcoe_kwargs["eta_E_plant"],
        )
        # 5. Compute Q_eng
        Q_eng = compute_Q_eng(self.concept)
        # 6. Pass/fail
        meets_TBR = tbr.TBR >= TRITIUM_BREEDING_THRESHOLD
        LCOE = lcoe_proxy["LCOE_USD_per_MWh"]
        LCOE_finite = LCOE != float("inf")
        meets_LCOE = LCOE_finite and LCOE <= COMMERCIAL_LCOE_TARGET_USD_PER_MWH
        meets_power = lcoe_proxy["P_net_electric_MW"] >= 0.5 * COMMERCIAL_NET_POWER_MW

        # 7. Tritium inventory dynamics (Item 8 / v2.2.0)
        # Plant fusion thermal power is self.plant_design.P_fusion_MW (MW)
        # → 1e-3 GW for tritium module.
        fusion_power_GW = self.plant_design.P_fusion_MW * 1e-3
        tritium_inputs = TritiumInventoryInputs(
            TBR=tbr.TBR,
            fusion_power_GW=fusion_power_GW,
            plant_availability=capacity_factor,  # use plant CF as availability
            startup_inventory_kg=startup_inventory_kg,
        )
        tritium_result = tritium_inventory_dynamics(
            tritium_inputs, duration_days=tritium_duration_days, n_time_steps=2000
        )

        base_notes = (
            f"Plant={self.plant_design.name}, Concept={self.concept.short_name}. "
            f"BOP: {self.plant_design.cycle} @ {self.plant_design.T_hot_K:.0f} K, "
            f"η_E={bop.eta_E_plant:.3f}, f_recirc={bop.f_recirc:.3f}. "
            f"Geometry: {self.plant_design.geometry_name}, R_total={geo_summary['total_radius_cm']:.0f} cm, "
            f"coverage={coverage:.3f}. "
            f"TBR: blanket={self.plant_design.blanket_material}+{self.plant_design.neutron_multiplier}, "
            f"TBR_total={tbr.TBR:.3f}. "
            f"LCOE: nameplate={nameplate_MW:.0f} MW, CF={capacity_factor:.2f}, "
            f"LCOE={'$%.0f/MWh' % LCOE if LCOE_finite else 'inf'}. "
            f"Pass: TBR>={TRITIUM_BREEDING_THRESHOLD}? {meets_TBR}; "
            f"LCOE<=$150? {meets_LCOE}; "
            f"power>={0.5*COMMERCIAL_NET_POWER_MW} MW? {meets_power}."
        )
        if tritium_result.doubling_time_days is not None and tritium_result.steady_state_inventory_kg is not None:
            notes = base_notes + (
                f" Tritium: TBR={tbr.TBR:.2f}, "
                f"doubling_time={tritium_result.doubling_time_days:.0f}d, "
                f"I_ss={tritium_result.steady_state_inventory_kg:.2f}kg."
            )
        else:
            notes = base_notes + (
                f" Tritium: TBR={tbr.TBR:.2f} (below self-sufficiency threshold)."
            )

        return PlantSimulationResult(
            plant_design_name=self.plant_design.name,
            concept_name=self.concept.short_name,
            bop=bop,
            eta_E_plant=bop.eta_E_plant,
            f_recirc=bop.f_recirc,
            eta_recirc_round_trip=bop.eta_recirc_round_trip,
            geometry_name=self.plant_design.geometry_name,
            geometry_total_radius_cm=geo_summary["total_radius_cm"],
            geometry_plasma_volume_L=geo_summary["plasma_volume_L"],
            geometry_blanket_volume_m3=geo_summary["blanket_volume_m3"],
            coverage_fraction=coverage,
            tbr=tbr,
            TBR=tbr.TBR,
            tritium_self_sufficient=meets_TBR,
            LCOE_USD_per_MWh=LCOE,
            LCOE_above_break_even=lcoe_proxy["above_break_even"],
            P_net_electric_MW=lcoe_proxy["P_net_electric_MW"],
            required_rep_rate_Hz=lcoe_proxy["required_rep_rate_Hz"],
            achievable_at_design_rep_rate=lcoe_proxy.get("achievable_at_design_rep_rate", False),
            design_rep_rate_Hz=lcoe_proxy.get("design_rep_rate_Hz", 0.0),
            nameplate_MW=nameplate_MW,
            capacity_factor=capacity_factor,
            Q_eng=Q_eng,
            meets_TBR_threshold=meets_TBR,
            meets_LCOE_target=meets_LCOE,
            meets_commercial_power=meets_power,
            notes=notes,
            # Tritium inventory (Item 8 / v2.2.0)
            tritium_doubling_time_days=tritium_result.doubling_time_days,
            tritium_steady_state_inventory_kg=tritium_result.steady_state_inventory_kg,
            tritium_time_to_steady_state_days=tritium_result.time_to_steady_state_days,
            tritium_net_production_kg_per_year=(
                tritium_result.production_rate_kg_per_day.mean() * 365.25
                if tritium_result.production_rate_kg_per_day.size > 0
                else None
            ),
        )


def simulate_plant(
    concept: ConceptParameters,
    plant_design: Optional[PlantDesign] = None,
    nameplate_MW: float = 100.0,
    capacity_factor: float = 0.25,
    capex_per_GWe_USD: float = 10e9,
) -> PlantSimulationResult:
    """One-shot plant simulation.

    Args:
        concept: ConceptParameters for the fusion concept.
        plant_design: Optional PlantDesign (uses defaults if None).
        nameplate_MW: Plant nameplate [MW].
        capacity_factor: Operational capacity factor.
        capex_per_GWe_USD: Plant CAPEX per GW electric.

    Returns:
        PlantSimulationResult.
    """
    if plant_design is None:
        plant_design = PlantDesign()
    sim = PlantSimulation(
        concept=concept,
        plant_design=plant_design,
        capex_per_GWe_USD=capex_per_GWe_USD,
    )
    return sim.simulate(nameplate_MW=nameplate_MW, capacity_factor=capacity_factor)


def sweep_plant_designs(
    concept: ConceptParameters,
    plant_designs: list[PlantDesign],
    nameplate_MW: float = 100.0,
    capacity_factor: float = 0.25,
) -> list[PlantSimulationResult]:
    """Run multiple plant designs for the same concept.

    Args:
        concept: The fusion concept.
        plant_designs: List of PlantDesign configurations to compare.
        nameplate_MW, capacity_factor: Plant sizing.

    Returns:
        List of PlantSimulationResult, one per plant_design.
    """
    results = []
    for pd in plant_designs:
        results.append(
            simulate_plant(concept, pd, nameplate_MW, capacity_factor)
        )
    return results
