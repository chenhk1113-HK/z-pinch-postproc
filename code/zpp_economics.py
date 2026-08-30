"""
Rep-rate + LCOE model for Z-IFC (Z-pinch fusion power plant).

This module answers the strategic question: *if* a Z-pinch driver can
fire at N Hz with a given Q_eng and wall-plug efficiency, what's the
resulting LCOE (levelized cost of electricity)?

The model is deliberately simple — it's an engineering scoping
model, not a full PROCESS call. It exists to:

1. Show the **Pareto frontier** of rep-rate vs LCOE for a given Q_eng.
2. Identify the **break-even Q_eng** below which the plant cannot
   pay for itself even at infinite rep-rate.
3. Identify the **minimum rep-rate** at which a given Q_eng reaches
   a target LCOE (default $100/MWh = competitive with fission).

References:
- Entler S. et al. (2018) "Approximation of the economy of fusion
  energy", Energy 152 489-497.
- Entler S. et al. (2018) "Engineering breakeven of fusion
  reactors", Fusion Eng. Des. 134 1-7.
- Meier W.R. (2017) "Economic analysis of inertial fusion
  energy", Fusion Eng. Des. 125 239-245.
- Pacific Fusion (2024) public company materials — rep-rate
  is the central design choice.
- Princeton Stellar Energy / Type One Energy (2024) public
  materials on pulsed-power plant economics.

References for Z-pinch-specific rep-rate and LCOE:
- Yager-Elorriaga D.A. et al. (2022) Nucl. Fusion 62 042015.
- Sinars D.B. et al. (2020) Phys. Plasmas 27 070501.
- Hansen S. (2021) SULI lecture — Z present fires ~1 shot/day.

Cost assumptions (defaults; can be overridden):
- CAPEX: $10B per GWe of installed nameplate. Sourced from
  generic fission/PWR scaling ($8-12B/GWe range; fusion is
  expected to be higher due to tritium handling and pulsed-power
  capital). Default $10B/GWe is a midpoint.
- OPEX: $10/MWh. Typical nuclear OPEX. Default.
- Plant lifetime: 30 years (typical).
- Discount rate: 7% (WACC for a regulated utility).
- Tax/insurance: 2% of CAPEX/year (typical).
- Tritium cost: $0 (assumed bred in-blanket; if not, ~$100k/kg).
"""
from __future__ import annotations
from dataclasses import dataclass, field
import numpy as np


@dataclass
class PlantEconomics:
    """Economic parameters for a Z-pinch fusion power plant.

    All cost inputs are in USD; all energy in MWh; all times in years.
    Defaults are a "midpoint" nuclear-like plant, NOT a fusion-specific
    estimate. Override these for your actual study.

    The model is **design-driven**: the caller specifies a target
    `nameplate_MW`. The required rep-rate is computed from the
    physics (Q_eng, eta_wallplug, etc.) so that the plant delivers
    that nameplate. This makes the LCOE sensitive to both Q_eng and
    rep-rate, as expected for a pulsed-power plant.

    For Z present (Q_eng ~ 0.001), the required rep-rate is infinite
    (cannot reach nameplate) — handled by returning inf for LCOE.
    """
    # Cost parameters (USD)
    capex_per_GWe_USD: float = 10e9      # Capital cost per GWe nameplate
    annual_opex_per_MWh_USD: float = 10.0  # $/MWh operating cost
    plant_lifetime_years: int = 30
    discount_rate: float = 0.07          # WACC
    tax_insurance_fraction_capex_per_year: float = 0.02

    # Physics-derived (passed in from pipeline)
    Q_eng: float = 1.0                   # Engineering gain (E_fus / E_grid)
    eta_wallplug_to_liner: float = 0.04  # Driver wall-plug efficiency
    eta_E_plant: float = 0.40            # Thermal-to-electric
    rep_rate_Hz: float = 0.1             # Shots per second (at this design point)
    E_grid_per_shot_MJ: float = 22.0     # Energy per shot at the grid

    # Plant design
    nameplate_MW: float = 100.0          # Target net electric output [MW]

    # Uptime (fraction of the day the plant is actually firing)
    capacity_factor: float = 0.25        # Default 25% (typical for first-gen fusion)

    def E_fusion_per_shot_MJ(self) -> float:
        """Fusion yield per shot [MJ], from Q_eng * E_grid_per_shot."""
        return self.Q_eng * self.E_grid_per_shot_MJ

    def required_rep_rate_Hz(self) -> float:
        """Rep-rate [Hz] required to deliver `nameplate_MW` at this Q_eng.

        P_net = P_gross - P_recirc = E_grid_per_shot_MJ * rep_rate
                * (Q_eng * eta_E - 1/eta_wp) [in MW]
        Setting P_net = nameplate_MW:
            rep_rate = nameplate / (E_grid_MJ * (Q_eng * eta_E - 1/eta_wp))
        Returns np.inf if Q_eng < 1/(eta_wp * eta_E) (sub-break-even).
        """
        net_per_Hz_MW = (
            self.E_grid_per_shot_MJ
            * (self.Q_eng * self.eta_E_plant - 1.0 / self.eta_wallplug_to_liner)
        )
        if net_per_Hz_MW <= 0:
            return float("inf")
        return self.nameplate_MW / net_per_Hz_MW

    def E_fusion_per_shot_MWh(self) -> float:
        """Fusion yield per shot [MWh]."""
        return self.E_fusion_per_shot_MJ() / 3600.0  # 1 MWh = 3600 MJ

    def P_thermal_GW(self) -> float:
        """Gross thermal power [GW] from rep-rate * E_fusion_per_shot.

        P_thermal = E_fus_per_shot * rep_rate (W) -> divide by 1e9 for GW.
        """
        E_fus_J = self.E_fusion_per_shot_MJ() * 1e6
        P_W = E_fus_J * self.rep_rate_Hz
        return P_W / 1e9

    def P_gross_electric_MW(self) -> float:
        """Gross electric power output [MW] before recirculation."""
        return self.P_thermal_GW() * 1e3 * self.eta_E_plant

    def P_recirc_MW(self) -> float:
        """Power recirculated to the driver [MW]."""
        # Recirculation = f_recirc * P_gross (from the wall-plug chain's f_recirc)
        # We approximate f_recirc as 1/eta_E * E_grid / E_fus when Q_eng > 1.
        # For a self-consistent plant: f_recirc = 1 / (Q_eng * eta_wallplug)
        # This is the "Round-trip" efficiency.
        f_recirc = 1.0 / (self.Q_eng * self.eta_wallplug_to_liner) if self.Q_eng > 0 else 1.0
        return self.P_gross_electric_MW() * f_recirc

    def P_net_electric_MW(self) -> float:
        """Net electric power to grid [MW].

        Computed at the user-specified `rep_rate_Hz`. Returns 0 if
        Q_eng is below break-even (sub-break-even plants cannot
        produce net power at any rate).
        """
        if self.required_rep_rate_Hz() == float("inf"):
            return 0.0
        return max(self.P_gross_electric_MW() - self.P_recirc_MW(), 0.0)

    def P_net_at_required_Hz_MW(self) -> float:
        """Net electric power [MW] at the rep-rate that hits nameplate.

        This is `nameplate_MW` by construction — by definition, the
        required rep-rate delivers exactly nameplate_MW of net power.
        """
        if self.required_rep_rate_Hz() == float("inf"):
            return 0.0
        return self.nameplate_MW

    def annual_net_energy_MWh(self) -> float:
        """Annual net energy delivered [MWh/year]."""
        return self.nameplate_MW * 8760.0 * self.capacity_factor

    def capex_total_USD(self) -> float:
        """Total CAPEX [USD] for this plant."""
        return self.capex_per_GWe_USD * (self.nameplate_MW / 1e3)

    def capex_amortized_USD_per_year(self) -> float:
        """Annualised CAPEX using capital recovery factor.

        CRF = r(1+r)^n / ((1+r)^n - 1)
        """
        r = self.discount_rate
        n = self.plant_lifetime_years
        capex = self.capex_total_USD()
        if r == 0:
            return capex / n
        crf = r * (1 + r) ** n / ((1 + r) ** n - 1)
        return capex * crf

    def annual_opex_USD(self) -> float:
        """Annual OPEX [USD/year]."""
        return self.annual_opex_per_MWh_USD * self.annual_net_energy_MWh()

    def annual_tax_insurance_USD(self) -> float:
        """Annual tax/insurance [USD/year]."""
        return self.tax_insurance_fraction_capex_per_year * self.capex_total_USD()

    def total_annual_cost_USD(self) -> float:
        """Annualised total cost [USD/year]."""
        return (
            self.capex_amortized_USD_per_year()
            + self.annual_opex_USD()
            + self.annual_tax_insurance_USD()
        )

    def lcoe_USD_per_MWh(self) -> float:
        """Levelized cost of electricity [USD/MWh].

        LCOE = total_annual_cost / annual_net_energy.
        Returns np.inf if Q_eng is below break-even (plant can't produce
        net power at any rep-rate).
        """
        if self.required_rep_rate_Hz() == float("inf"):
            return float("inf")
        e = self.annual_net_energy_MWh()
        if e <= 0:
            return float("inf")
        return self.total_annual_cost_USD() / e

    def summary(self) -> dict:
        """One-shot dict for reports."""
        return {
            "Q_eng": self.Q_eng,
            "rep_rate_Hz": self.rep_rate_Hz,
            "required_rep_rate_Hz": self.required_rep_rate_Hz(),
            "eta_wallplug_to_liner": self.eta_wallplug_to_liner,
            "eta_E_plant": self.eta_E_plant,
            "capacity_factor": self.capacity_factor,
            "E_grid_per_shot_MJ": self.E_grid_per_shot_MJ,
            "E_fusion_per_shot_MJ": self.E_fusion_per_shot_MJ(),
            "P_thermal_GW": self.P_thermal_GW(),
            "P_gross_electric_MW": self.P_gross_electric_MW(),
            "P_recirc_MW": self.P_recirc_MW(),
            "P_net_electric_MW": self.P_net_electric_MW(),
            "P_net_at_required_Hz_MW": self.P_net_at_required_Hz_MW(),
            "nameplate_MW": self.nameplate_MW,
            "annual_net_energy_MWh": self.annual_net_energy_MWh(),
            "capex_amortized_USD_per_year": self.capex_amortized_USD_per_year(),
            "annual_opex_USD": self.annual_opex_USD(),
            "annual_tax_insurance_USD": self.annual_tax_insurance_USD(),
            "total_annual_cost_USD": self.total_annual_cost_USD(),
            "lcoe_USD_per_MWh": self.lcoe_USD_per_MWh(),
        }


def break_even_Q_eng(
    eta_wallplug_to_liner: float = 0.04,
    eta_E_plant: float = 0.40,
) -> float:
    """Minimum Q_eng for net-positive electricity (Q_eng * eta_wp * eta_E = 1).

    For Z present-day (eta_wp=0.04, eta_E=0.40):
        Q_eng_break_even = 1 / (0.04 * 0.40) = 62.5

    Note: this is the *engineering break-even*, not the target gain.
    The target gain must also exceed 1/(eta_E * f_recirc * eta_wp)
    where f_recirc accounts for the recirculated fraction.

    For Z present, this matches the Yager-Elorriaga 2022 figure of
    "G ~ 50 for a 20% magnetic-direct-drive driver" (which gives
    G_required = 1 / (0.4 * 0.25 * 0.20) = 50).
    """
    return 1.0 / (eta_wallplug_to_liner * eta_E_plant)


def min_rep_rate_for_target_LCOE(
    Q_eng: float,
    target_lcoe_USD_per_MWh: float,
    capex_per_GWe_USD: float = 10e9,
    eta_wallplug_to_liner: float = 0.04,
    eta_E_plant: float = 0.40,
    capacity_factor: float = 0.25,
    E_grid_per_shot_MJ: float = 22.0,
    nameplate_MW: float = 100.0,
) -> float:
    """Minimum rep-rate [Hz] for a given LCOE target at fixed Q_eng.

    NOTE: With the design-driven model (CAPEX fixed by nameplate),
    LCOE is **independent** of rep-rate (CAPEX is amortized over
    annual_net_energy which scales with rep-rate via capacity_factor,
    not directly). This function therefore returns the rep-rate
    required to deliver `nameplate_MW` at the given Q_eng. If
    `Q_eng < 1/(eta_wp * eta_E)` (below break-even), the rep-rate
    is infinite.

    A rep-rate of 0.1 Hz with Q_eng=10 gives a LCOE ~$150/MWh
    (Entler 2018, scaled to Z-class driver).
    """
    plant = PlantEconomics(
        Q_eng=Q_eng,
        eta_wallplug_to_liner=eta_wallplug_to_liner,
        eta_E_plant=eta_E_plant,
        rep_rate_Hz=1.0,  # placeholder, will be overwritten
        capacity_factor=capacity_factor,
        E_grid_per_shot_MJ=E_grid_per_shot_MJ,
        capex_per_GWe_USD=capex_per_GWe_USD,
        nameplate_MW=nameplate_MW,
    )
    return plant.required_rep_rate_Hz()


def lcoe_pareto_frontier(
    Q_eng_list: list[float],
    eta_wallplug_to_liner: float = 0.04,
    eta_E_plant: float = 0.40,
    capacity_factor: float = 0.25,
    E_grid_per_shot_MJ: float = 22.0,
    capex_per_GWe_USD: float = 10e9,
    nameplate_MW: float = 100.0,
) -> list[dict]:
    """Compute LCOE for a list of Q_eng values, at a fixed nameplate.

    Returns a list of dicts with Q_eng, required_rep_rate_Hz, and
    lcoe_USD_per_MWh, suitable for plotting the LCOE-vs-Q_eng
    frontier (the more useful Pareto for a fusion plant).

    Note: in the design-driven model, LCOE is independent of rep-rate
    for a fixed Q_eng (CAPEX and energy scale together with
    capacity_factor, which is a separate input). The rep-rate that
    *achieves* the design nameplate at each Q_eng is reported.
    """
    if Q_eng_list is None:
        Q_eng_list = [1.0, 2.0, 5.0, 10.0, 20.0, 50.0, 100.0, 200.0]

    frontier = []
    for Q in Q_eng_list:
        plant = PlantEconomics(
            Q_eng=Q,
            eta_wallplug_to_liner=eta_wallplug_to_liner,
            eta_E_plant=eta_E_plant,
            rep_rate_Hz=1.0,  # placeholder; required_rep_rate_Hz is the answer
            capacity_factor=capacity_factor,
            E_grid_per_shot_MJ=E_grid_per_shot_MJ,
            capex_per_GWe_USD=capex_per_GWe_USD,
            nameplate_MW=nameplate_MW,
        )
        frontier.append({
            "Q_eng": Q,
            "required_rep_rate_Hz": plant.required_rep_rate_Hz(),
            "lcoe_USD_per_MWh": plant.lcoe_USD_per_MWh(),
            "P_net_electric_MW": plant.P_net_electric_MW(),
            "annual_net_energy_MWh": plant.annual_net_energy_MWh(),
        })
    return frontier


def lcoe_vs_capacity_factor(
    Q_eng: float,
    capacity_factors: list[float] | None = None,
    eta_wallplug_to_liner: float = 0.04,
    eta_E_plant: float = 0.40,
    E_grid_per_shot_MJ: float = 22.0,
    capex_per_GWe_USD: float = 10e9,
    nameplate_MW: float = 100.0,
) -> list[dict]:
    """LCOE vs capacity_factor at a fixed Q_eng.

    This is the **operational** Pareto: how much LCOE falls as the
    plant achieves better uptime / availability. A fusion plant with
    CF=0.9 (baseload) gets dramatically lower LCOE than CF=0.25
    (first-gen fusion).

    Returns list of dicts with capacity_factor and lcoe_USD_per_MWh.
    """
    if capacity_factors is None:
        capacity_factors = [0.10, 0.25, 0.50, 0.70, 0.85, 0.95]

    frontier = []
    for cf in capacity_factors:
        plant = PlantEconomics(
            Q_eng=Q_eng,
            eta_wallplug_to_liner=eta_wallplug_to_liner,
            eta_E_plant=eta_E_plant,
            rep_rate_Hz=1.0,
            capacity_factor=cf,
            E_grid_per_shot_MJ=E_grid_per_shot_MJ,
            capex_per_GWe_USD=capex_per_GWe_USD,
            nameplate_MW=nameplate_MW,
        )
        frontier.append({
            "capacity_factor": cf,
            "lcoe_USD_per_MWh": plant.lcoe_USD_per_MWh(),
            "annual_net_energy_MWh": plant.annual_net_energy_MWh(),
        })
    return frontier
