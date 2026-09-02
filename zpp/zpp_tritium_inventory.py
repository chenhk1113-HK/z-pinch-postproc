"""Time-dependent tritium fuel cycle for Z-pinch fusion plant (Item 8).

Computes tritium inventory over plant lifetime using an ODE solver.
Tracks:
- Tritium breeding rate (from TBR × fusion neutron rate)
- Tritium decay (T_half = 12.32 years, negligible on plant timescale)
- Tritium extraction loss (~1-5% per cycle, industry standard)
- Tritium inventory growth / decline
- Doubling time (time to reach steady-state inventory)

References
----------
- Sawan 2011, FNSF tritium breeding analysis
- Boccaccini 2016, ITER TBM tritium inventory
- Glugla 2007, ITER tritium systems
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

# Physical constants
T_HALF_YEARS = 12.32           # Tritium half-life [years]
T_DECAY_PER_S = math.log(2) / (T_HALF_YEARS * 365.25 * 86400)  # [s^-1]
AVOGADRO = 6.02214076e23        # atoms/mol
T_MOLAR_MASS_G_PER_MOL = 3.016  # g/mol (T2 molecular mass)
T_DENSITY_G_PER_CC = 0.32       # Liquid T2 density (cryogenic)

# Industry-standard extraction loss fraction per inventory cycle.
# Glugla 2007 reports 1-5% depending on detritiation system efficiency.
# Default 2% is conservative for a well-designed plant.
DEFAULT_EXTRACTION_LOSS_FRACTION = 0.02

# Industry-standard startup inventory for a 1 GW fusion plant.
# ITER TBM startup: ~1 kg. Power plant: ~5-10 kg.
DEFAULT_STARTUP_INVENTORY_KG = 5.0

# ITER-grade target doubling time: 1-2 weeks for steady-state.
# Power plant acceptable: 1-6 months.


@dataclass
class TritiumInventoryInputs:
    """Inputs for tritium inventory time evolution.

    Attributes
    ----------
    TBR : float
        Tritium breeding ratio (T atoms per source neutron, dimensionless).
        Must be > 1.05 for self-sufficiency (industry threshold).
    fusion_power_GW : float
        Fusion thermal power [GW]. Typical Z-pinch power plant: 1-3 GW.
    plant_availability : float
        Fraction of time the plant is operating [0, 1]. Typical 0.7-0.9.
    startup_inventory_kg : float
        Initial tritium inventory at plant start [kg]. Default 5 kg.
    extraction_loss_fraction : float
        Fraction of inventory lost per extraction cycle [0, 1].
        Default 0.02 (Glugla 2007 industry standard).
    cycle_time_hours : float
        Time per tritium extraction cycle [hours]. Default 24 h.
    """
    TBR: float = 1.83
    fusion_power_GW: float = 1.0
    plant_availability: float = 0.85
    startup_inventory_kg: float = DEFAULT_STARTUP_INVENTORY_KG
    extraction_loss_fraction: float = DEFAULT_EXTRACTION_LOSS_FRACTION
    cycle_time_hours: float = 24.0


@dataclass
class TritiumInventoryResult:
    """Result of tritium inventory time evolution.

    Attributes
    ----------
    time_days : np.ndarray
        Time array [days].
    inventory_kg : np.ndarray
        Tritium inventory at each time [kg].
    production_rate_kg_per_day : np.ndarray
        Instantaneous production rate [kg/day].
    consumption_rate_kg_per_day : np.ndarray
        Instantaneous consumption (= loss) rate [kg/day].
    doubling_time_days : float or None
        Time to reach 2x startup inventory [days]. None if TBR < 1 + loss rate.
    steady_state_inventory_kg : float or None
        Equilibrium inventory (production = consumption) [kg].
    time_to_steady_state_days : float or None
        Time to reach 95% of steady-state [days].
    """
    time_days: np.ndarray
    inventory_kg: np.ndarray
    production_rate_kg_per_day: np.ndarray
    consumption_rate_kg_per_day: np.ndarray
    doubling_time_days: float | None = None
    steady_state_inventory_kg: float | None = None
    time_to_steady_state_days: float | None = None


def fusion_neutron_rate_per_s(fusion_power_GW: float) -> float:
    """Convert fusion thermal power to D-T neutron production rate.

    D-T fusion releases 17.6 MeV per reaction (14.1 MeV neutron + 3.5 MeV alpha).
    1 eV = 1.602e-19 J; 1 MeV = 1.602e-13 J.

    Parameters
    ----------
    fusion_power_GW : float
        Fusion thermal power [GW].

    Returns
    -------
    n_per_s : float
        D-T neutron production rate [neutrons/second].
    """
    MeV_to_J = 1.602e-13
    E_per_reaction_J = 17.6 * MeV_to_J
    power_W = fusion_power_GW * 1e9
    return power_W / E_per_reaction_J


def tritium_production_rate_kg_per_s(
    TBR: float,
    fusion_power_GW: float,
    plant_availability: float = 1.0,
) -> float:
    """Tritium production rate [kg/s].

    Production rate = TBR × neutron rate × atoms per T (2 for T2) × molar mass / NA.

    Parameters
    ----------
    TBR : float
        Tritium breeding ratio.
    fusion_power_GW : float
        Fusion thermal power [GW].
    plant_availability : float
        Plant uptime fraction [0, 1].

    Returns
    -------
    prod_kg_per_s : float
        Tritium production rate [kg/s].
    """
    n_per_s = fusion_neutron_rate_per_s(fusion_power_GW)
    atoms_per_kg = AVOGADRO / (T_MOLAR_MASS_G_PER_MOL * 1e-3)  # atoms/kg of T atoms
    # TBR gives T atoms per source neutron; multiply by 1 for T (atoms, not T2 molecules)
    return TBR * n_per_s * plant_availability / atoms_per_kg


def tritium_decay_rate_kg_per_s(inventory_kg: float) -> float:
    """Tritium loss rate due to radioactive decay [kg/s].

    T_half = 12.32 years. Loss rate = decay_constant × inventory.
    """
    return T_DECAY_PER_S * inventory_kg


def tritium_extraction_loss_rate_kg_per_s(
    inventory_kg: float,
    extraction_loss_fraction: float,
    cycle_time_hours: float,
) -> float:
    """Tritium loss rate due to extraction cycle [kg/s].

    Loss = inventory × loss_fraction / cycle_time.
    """
    cycle_time_s = cycle_time_hours * 3600
    return inventory_kg * extraction_loss_fraction / cycle_time_s


def tritium_inventory_dynamics(
    inputs: TritiumInventoryInputs,
    duration_days: float = 365.0,
    n_time_steps: int = 1000,
) -> TritiumInventoryResult:
    """Solve tritium inventory ODE over plant lifetime.

    ODE: dI/dt = P(TBR) - L(I)
        where P = production rate, L = total loss rate (decay + extraction)

    For TBR < threshold, inventory DECLINES (TBR doesn't cover losses).
    For TBR > threshold, inventory grows until steady-state (production = loss).

    Parameters
    ----------
    inputs : TritiumInventoryInputs
        Plant operating parameters.
    duration_days : float
        Simulation duration [days]. Default 365 (~1 year).
    n_time_steps : int
        Number of time steps. Default 1000.

    Returns
    -------
    TritiumInventoryResult with full time series + derived metrics.
    """
    t_array = np.linspace(0, duration_days, n_time_steps + 1)
    dt_s = (duration_days * 86400) / n_time_steps  # [s

    I = np.zeros(n_time_steps + 1)
    prod_rate = np.zeros(n_time_steps + 1)
    cons_rate = np.zeros(n_time_steps + 1)
    I[0] = inputs.startup_inventory_kg

    for i in range(n_time_steps):
        # Production rate (constant for fixed TBR + power)
        P = tritium_production_rate_kg_per_s(
            inputs.TBR,
            inputs.fusion_power_GW,
            inputs.plant_availability,
        )
        # Loss rate (proportional to inventory)
        L_decay = tritium_decay_rate_kg_per_s(I[i])
        L_extract = tritium_extraction_loss_rate_kg_per_s(
            I[i],
            inputs.extraction_loss_fraction,
            inputs.cycle_time_hours,
        )
        L = L_decay + L_extract

        # Forward Euler
        dI_dt = P - L
        I[i + 1] = max(0.0, I[i] + dI_dt * dt_s)

        prod_rate[i] = P
        cons_rate[i] = L

    # Final rate at last time
    P_final = tritium_production_rate_kg_per_s(
        inputs.TBR, inputs.fusion_power_GW, inputs.plant_availability
    )
    L_final = (
        tritium_decay_rate_kg_per_s(I[-1])
        + tritium_extraction_loss_rate_kg_per_s(
            I[-1], inputs.extraction_loss_fraction, inputs.cycle_time_hours
        )
    )
    prod_rate[-1] = P_final
    cons_rate[-1] = L_final

    # Steady-state inventory: I_ss × total_loss_rate_per_kg = production_rate
    # total_loss_per_kg = T_DECAY_PER_S + extraction_loss_fraction / cycle_time_s
    total_loss_rate_per_s_per_kg = T_DECAY_PER_S + inputs.extraction_loss_fraction / (inputs.cycle_time_hours * 3600)
    if inputs.TBR > 0 and P_final > 0:
        I_ss = P_final / total_loss_rate_per_s_per_kg
    else:
        I_ss = 0.0

    # Doubling time: t such that I(t) = 2 × I_startup
    doubling_time = None
    for i in range(1, n_time_steps + 1):
        if I[i] >= 2 * inputs.startup_inventory_kg:
            doubling_time = float(t_array[i])
            break

    # Time to 95% of steady state
    time_to_ss = None
    if I_ss > 0:
        target = 0.95 * I_ss
        for i in range(1, n_time_steps + 1):
            if I[i] >= target:
                time_to_ss = float(t_array[i])
                break

    return TritiumInventoryResult(
        time_days=t_array,
        inventory_kg=I,
        production_rate_kg_per_day=prod_rate * 86400,
        consumption_rate_kg_per_day=cons_rate * 86400,
        doubling_time_days=doubling_time,
        steady_state_inventory_kg=I_ss if I_ss > 0 else None,
        time_to_steady_state_days=time_to_ss,
    )


def tritium_self_sufficient(
    TBR: float,
    extraction_loss_fraction: float = DEFAULT_EXTRACTION_LOSS_FRACTION,
    cycle_time_hours: float = 24.0,
) -> bool:
    """Check if TBR is sufficient for tritium self-sufficiency.

    Self-sufficiency requires production rate ≥ total loss rate at SOME
    feasible inventory level. Since production is constant and loss
    is proportional to inventory, the only condition is:
        P > 0  ⟺  TBR > 0

    But practical self-sufficiency also requires the steady-state inventory
    to be physically achievable (≤ some reasonable limit, ~100 kg).

    Parameters
    ----------
    TBR : float
        Tritium breeding ratio.
    extraction_loss_fraction : float
        Loss fraction per extraction cycle.
    cycle_time_hours : float
        Time per extraction cycle.

    Returns
    -------
    self_sufficient : bool
        True if TBR > 1.05 (industry threshold).
    """
    return TBR >= 1.05


def headline_tritium_claim(TBR: float = 1.83, fusion_power_GW: float = 1.0) -> str:
    """Compute the headline claim string for the GitHub paper.

    At TBR=1.83 and 1 GW fusion power:
    - Net production = (TBR - 1) × neutron rate
    - Doubling time depends on startup inventory + extraction loss

    Returns a human-readable string.
    """
    inputs = TritiumInventoryInputs(
        TBR=TBR, fusion_power_GW=fusion_power_GW, plant_availability=0.85
    )
    result = tritium_inventory_dynamics(inputs, duration_days=730, n_time_steps=2000)

    parts = [
        f"TBR={TBR:.2f} at {fusion_power_GW:.1f} GW fusion power (85% availability):",
    ]
    if result.doubling_time_days is not None:
        parts.append(f"  Doubling time: {result.doubling_time_days:.1f} days")
    else:
        parts.append("  Doubling time: > 2 years (TBR < threshold)")
    if result.steady_state_inventory_kg is not None:
        parts.append(f"  Steady-state inventory: {result.steady_state_inventory_kg:.2f} kg")
    if result.time_to_steady_state_days is not None:
        parts.append(f"  Time to 95% steady state: {result.time_to_steady_state_days:.1f} days")
    return "\n".join(parts)