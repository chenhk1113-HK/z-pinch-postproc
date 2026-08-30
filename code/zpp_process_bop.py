"""
PROCESS-equivalent BOP (balance-of-plant) wall-plug chain.

PROCESS (https://github.com/ukaea/PROCESS) is the UK's fusion systems
code for BOP modeling. It computes the full thermal-to-electric
chain from fusion power to grid, including cryogenic plant, magnet
power, laser power, balance-of-plant auxiliaries, and the
appropriate thermodynamic cycle (Brayton, Rankine, sCO2).

This module is a **parametric PROCESS replacement** that:
1. Computes η_E_plant from the chosen thermodynamic cycle with
   realistic efficiency losses (not the magic 0.40 scalar).
2. Computes f_recirc from the plant auxiliary loads (cryogenics,
   magnets, lasers, tritium handling).
3. Computes η_plant_aux from the auxiliary equipment.
4. Returns a `ProcessBOPResult` with all fields, ready to drop
   into the WallPlugChain or stand alone for LCOE analysis.

This is NOT a full PROCESS call (which would require the
PROCESS binary, MFiles database, and 100+ input parameters).
It captures the *leading-order* BOP physics at the right level
of fidelity for Z-IFE scoping studies.

References:
- Kovari M. et al. (2014) "PROCESS: A systems code for fusion
  power plants — reference manual", CCFE.
- Entler S. et al. (2018) Energy 152 489-497 — fusion LCOE methodology.
- Segantin S. et al. (2021) Fusion Eng. Des. 168 112418 — BOP for
  pulsed-magnetic fusion plants.
- Whyte D.G. et al. (2016) Nucl. Fusion 56 086022 — small fusion
  plant BOP.
- Pacific Fusion company materials 2024 — rep-rate architecture
  BOP.
"""
from __future__ import annotations
from dataclasses import dataclass, field
import numpy as np


# Physical constants for cycle efficiency calculations
T_HOT_K_DEFAULT = 1200.0  # Hot-side temperature for Brayton [K] (helium, ~1200K)
T_COLD_K_DEFAULT = 300.0  # Cold-side temperature (sink) [K]
# Realistic cycle efficiencies (vs Carnot):
# Brayton helium: ~0.55-0.60 of Carnot
# Rankine steam: ~0.40-0.45 of Carnot
# Supercritical CO2: ~0.60-0.65 of Carnot
BRAYTON_EFFICIENCY_FRACTION = 0.57
RANKINE_EFFICIENCY_FRACTION = 0.42
SCO2_EFFICIENCY_FRACTION = 0.62


# Auxiliary power fractions for pulsed-magnetic fusion BOP.
# These are *typical* values from BOP studies; specific to Z-IFE.
# Reference: Segantin 2021 (BOP for pulsed-magnetic plants).
DEFAULT_AUX_FRACTIONS = {
    "cryogenic": 0.02,       # Cryoplant (liners, lasers, magnets)
    "magnets": 0.01,         # Magnet power (superconducting if used)
    "laser": 0.05,           # Laser wall-plug (for MagLIF only)
    "pulsed_power_charging": 0.08,  # Capacitor recharging (pulsed-mag)
    "tritium_handling": 0.01, # Tritium processing plant
    "balance_of_plant": 0.03,  # General BOP (cooling, vacuum, etc.)
    "buildings_services": 0.01,
}


@dataclass
class PlantBOPInputs:
    """Inputs to the parametric BOP model.

    These map roughly to PROCESS inputs but are at higher level
    for our scoping purposes.
    """
    # Thermal cycle
    cycle: str = "Brayton"  # "Brayton", "Rankine", "sCO2"
    T_hot_K: float = T_HOT_K_DEFAULT
    T_cold_K: float = T_COLD_K_DEFAULT
    # Plant design
    P_fusion_MW: float = 500.0       # Total fusion power [MW thermal]
    is_pulsed: bool = True            # Pulsed (True) or steady (False)
    has_laser: bool = True            # MagLIF-class laser in plant
    has_superconducting_magnets: bool = False  # Most Z-pinch plants use normal conducting
    # Cost (for LCOE downstream)
    plant_lifetime_years: int = 30
    capacity_factor: float = 0.25


@dataclass
class ProcessBOPResult:
    """Output of the parametric BOP model.

    The fields are PROCESS-comparable. Drop this into WallPlugChain
    by setting `eta_E_plant = result.eta_E_plant` and
    `f_recirc = result.f_recirc`.
    """
    cycle: str
    eta_E_plant: float        # Thermal-to-electric efficiency
    f_recirc: float           # Fraction of gross electric recirculated to driver
    eta_plant_aux: float      # Auxiliary plant efficiency (1 - sum of aux fractions)
    eta_recirc_round_trip: float  # = eta_E_plant * (1 - f_recirc)
    aux_breakdown: dict        # Per-auxiliary breakdown
    notes: str


def carnot_efficiency(T_hot_K: float, T_cold_K: float) -> float:
    """Carnot efficiency η = 1 - T_cold/T_hot."""
    if T_hot_K <= T_cold_K:
        return 0.0
    return 1.0 - T_cold_K / T_hot_K


def cycle_efficiency(
    cycle: str,
    T_hot_K: float = T_HOT_K_DEFAULT,
    T_cold_K: float = T_COLD_K_DEFAULT,
) -> float:
    """Realistic cycle efficiency (vs Carnot-limited).

    Args:
        cycle: "Brayton", "Rankine", or "sCO2".
        T_hot_K: Hot-side temperature [K].
        T_cold_K: Cold-side temperature [K].

    Returns:
        Realistic η_E_plant.
    """
    eta_carnot = carnot_efficiency(T_hot_K, T_cold_K)
    if cycle == "Brayton":
        return BRAYTON_EFFICIENCY_FRACTION * eta_carnot
    elif cycle == "Rankine":
        return RANKINE_EFFICIENCY_FRACTION * eta_carnot
    elif cycle == "sCO2":
        return SCO2_EFFICIENCY_FRACTION * eta_carnot
    else:
        raise ValueError(f"Unknown cycle: {cycle!r}")


def compute_aux_breakdown(
    is_pulsed: bool = True,
    has_laser: bool = True,
    has_superconducting_magnets: bool = False,
    P_fusion_MW: float = 500.0,
) -> dict:
    """Compute the auxiliary power fraction breakdown.

    Returns:
        dict mapping auxiliary name to fraction of gross electric.
        The sum is f_recirc (recirculated fraction).
    """
    aux = dict(DEFAULT_AUX_FRACTIONS)
    # Adjust based on plant features
    if not has_laser:
        aux["laser"] = 0.0
    if not is_pulsed:
        # No pulsed-power recharging in steady-state plants
        aux["pulsed_power_charging"] = 0.0
    if has_superconducting_magnets:
        # SC magnets need cryogenic cooling at higher fraction
        aux["cryogenic"] = 0.05
        aux["magnets"] = 0.02
    # Large plants (>1 GW fusion) benefit from economy of scale on aux
    if P_fusion_MW > 1000:
        scale_factor = 0.8
        aux = {k: v * scale_factor for k, v in aux.items()}
    elif P_fusion_MW < 100:
        # Small plants pay a fixed-cost penalty on aux
        scale_factor = 1.2
        aux = {k: v * scale_factor for k, v in aux.items()}
    return aux


def compute_f_recirc(
    aux_breakdown: dict,
) -> float:
    """Total recirculated fraction = sum of auxiliary fractions.

    Args:
        aux_breakdown: From compute_aux_breakdown.

    Returns:
        f_recirc in [0, 1). Should be ~0.10-0.25 for pulsed-mag fusion.
    """
    return float(sum(aux_breakdown.values()))


def compute_process_bop(
    inputs: PlantBOPInputs,
    custom_aux: dict | None = None,
) -> ProcessBOPResult:
    """Run the parametric PROCESS-equivalent BOP model.

    Args:
        inputs: PlantBOPInputs dataclass.
        custom_aux: Optional override of auxiliary fractions.

    Returns:
        ProcessBOPResult with η_E_plant, f_recirc, η_plant_aux,
        and the auxiliary breakdown.
    """
    # Cycle efficiency
    eta_E = cycle_efficiency(inputs.cycle, inputs.T_hot_K, inputs.T_cold_K)
    # Auxiliary breakdown
    aux = custom_aux if custom_aux is not None else compute_aux_breakdown(
        is_pulsed=inputs.is_pulsed,
        has_laser=inputs.has_laser,
        has_superconducting_magnets=inputs.has_superconducting_magnets,
        P_fusion_MW=inputs.P_fusion_MW,
    )
    f_recirc = compute_f_recirc(aux)
    # Cap f_recirc at 0.5 — beyond this the plant becomes infeasible
    if f_recirc > 0.5:
        raise ValueError(
            f"f_recirc={f_recirc:.2f} > 0.5 (plant infeasible). "
            f"Check auxiliary breakdown: {aux}"
        )
    eta_plant_aux = 1.0 - f_recirc  # auxiliary plant efficiency
    eta_recirc_round_trip = eta_E * (1.0 - f_recirc)
    notes = (
        f"Cycle: {inputs.cycle}, η_carnot={carnot_efficiency(inputs.T_hot_K, inputs.T_cold_K):.3f}, "
        f"η_E={eta_E:.3f}, f_recirc={f_recirc:.3f}, η_aux={eta_plant_aux:.3f}. "
        f"Pulsed plant={inputs.is_pulsed}, laser={inputs.has_laser}."
    )
    return ProcessBOPResult(
        cycle=inputs.cycle,
        eta_E_plant=float(eta_E),
        f_recirc=float(f_recirc),
        eta_plant_aux=float(eta_plant_aux),
        eta_recirc_round_trip=float(eta_recirc_round_trip),
        aux_breakdown=aux,
        notes=notes,
    )


def bop_result_to_wallplug_kwargs(result: ProcessBOPResult) -> dict:
    """Convert a ProcessBOPResult to WallPlugChain kwargs.

    The WallPlugChain dataclass has `eta_E_plant` and `f_recirc`
    fields; this function returns them as a dict ready to spread.
    """
    return {
        "eta_E_plant": result.eta_E_plant,
        "f_recirc": result.f_recirc,
    }


# Pre-defined BOP scenarios for common fusion plant types.
# These are sensible defaults — the user can override.
SCENARIO_ZN_DESIGN = PlantBOPInputs(
    cycle="Brayton",
    T_hot_K=1200.0,
    T_cold_K=300.0,
    P_fusion_MW=2000.0,  # ZN design: 200 MJ at 0.1 Hz = 20 MW fusion, * 100x for plant size
    is_pulsed=True,
    has_laser=True,
    has_superconducting_magnets=False,
)

SCENARIO_PACIFIC_FUSION = PlantBOPInputs(
    cycle="sCO2",  # PF claims sCO2 for compactness
    T_hot_K=700.0,    # sCO2 has lower T_hot limit
    T_cold_K=300.0,
    P_fusion_MW=2000.0,
    is_pulsed=True,
    has_laser=True,
    has_superconducting_magnets=False,
)

SCENARIO_GENERAL_FUSION = PlantBOPInputs(
    cycle="Brayton",
    T_hot_K=1200.0,
    T_cold_K=300.0,
    P_fusion_MW=2000.0,
    is_pulsed=True,
    has_laser=False,  # MTF doesn't use laser
    has_superconducting_magnets=True,  # Spheromak uses SC magnets
)

SCENARIO_ZAP_SFZ = PlantBOPInputs(
    cycle="Brayton",
    T_hot_K=1200.0,
    T_cold_K=300.0,
    P_fusion_MW=500.0,  # Smaller per plant
    is_pulsed=False,  # Steady-state Z-pinch
    has_laser=False,
    has_superconducting_magnets=False,
)


ALL_SCENARIOS = {
    "ZN": SCENARIO_ZN_DESIGN,
    "PF": SCENARIO_PACIFIC_FUSION,
    "GF-MTF": SCENARIO_GENERAL_FUSION,
    "Zap-SFZ": SCENARIO_ZAP_SFZ,
}


def bop_for_scenario(scenario_name: str) -> ProcessBOPResult:
    """Run the BOP model for a pre-defined scenario.

    Args:
        scenario_name: One of "ZN", "PF", "GF-MTF", "Zap-SFZ".

    Returns:
        ProcessBOPResult.
    """
    if scenario_name not in ALL_SCENARIOS:
        raise ValueError(
            f"Unknown scenario: {scenario_name!r}. "
            f"Available: {list(ALL_SCENARIOS.keys())}"
        )
    return compute_process_bop(ALL_SCENARIOS[scenario_name])
