"""
Comparative analysis: Z-pinch / MagLIF vs Zap sheared-flow vs General Fusion MTF.

This module answers the strategic-context question: *how do the
three pulsed-magnetic-fusion approaches stack up against each other?*

Concepts:
1. **Sandia Z / MagLIF**: pulsed-power-driven Z-pinch with optional
   laser preheat. The focus of this project. References:
   - Slutz et al. (2010) Phys. Plasmas 17 056303 — MagLIF concept.
   - Yager-Elorriaga et al. (2022) Nucl. Fusion 62 042015 — ZN design.
   - Gomez et al. (2020) PRL 125 155002 — Z 2960 anchor.

2. **Zap Energy sheared-flow Z-pinch (SFZ)**: a steady-state Z-pinch
   where sheared axial flow (v_axial ~ 100 km/s) suppresses MRT
   instability. References:
   - Shumlak et al. (2017) Nucl. Fusion 57 056005 — sheared-flow
     stabilisation.
   - Zap Energy company materials (2024).

3. **General Fusion magnetized target fusion (MTF)**: a spheromak
   plasma compressed by a mechanically-driven liner. References:
   - Laberge (2008) J. Fusion Energy 27 65 — MTF concept.
   - General Fusion company materials (2024).

This is a **scoping** comparison: it surfaces the strategic trade-offs
at each concept's design point without re-implementing the underlying
physics. Each concept has a different physics regime; this module
just lays them side-by-side.

References:
- Entler et al. (2018) Energy 152 489-497 — fusion LCOE methodology.
- Wurzel & Hsu (2022) Phys. Plasmas 29 062103 — progress in
  alternate fusion concepts.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Optional


@dataclass
class ConceptParameters:
    """Reference design parameters for a fusion concept.

    All values are at the *design point* (i.e. what the concept
    aims to achieve, not what has been demonstrated).
    """
    name: str
    short_name: str
    description: str
    reference: str
    fuel: str
    T_ion_keV: float          # Ion temperature [keV]
    n_fuel_per_cc: float      # Fuel density [atoms/cm³]
    tau_confinement_ns: float  # Confinement time [ns]
    B_field_T: float          # Magnetic field [T]
    eta_wallplug: float       # Wall-plug-to-fuel efficiency
    rep_rate_Hz: float        # Shots/cycles per second [Hz]
    E_fusion_per_shot_MJ: float  # Per-shot yield [MJ]
    E_grid_per_shot_MJ: float    # Per-shot grid energy [MJ]
    CR: float                  # Convergence ratio
    status: str               # "demonstrated", "design", "speculative"
    key_challenge: str         # Main engineering challenge
    Q_target_design: float = 0.0  # Long-term Q_eng target (if different from current)
    eta_wp_target: float = 0.0   # Long-term η_wp target (if different)


# Reference design points (compiled from public sources).
# These are *published* design points, not derived from our pipeline.
Z_PRESENT = ConceptParameters(
    name="Sandia Z (MagLIF, present-day)",
    short_name="Z-present",
    description="Pulsed-power Z-pinch with Z-Beamlet laser preheat (1.2 kJ, 16 T B-field).",
    reference="Gomez et al. 2020 PRL 125 155002",
    fuel="DT",
    T_ion_keV=3.0,
    n_fuel_per_cc=3.0e19,   # 0.05 g/cc / 2.5 * Avogadro, mid-stagnation
    tau_confinement_ns=5.0,
    B_field_T=16.0,
    eta_wallplug=0.04,
    rep_rate_Hz=1.16e-5,    # 1 shot / day (Z present reality)
    E_fusion_per_shot_MJ=2.0e-3,   # 2 kJ D-T equivalent
    E_grid_per_shot_MJ=22.0,
    CR=3.0,
    status="demonstrated",
    key_challenge="Q_eng 1000x below break-even; sub-ignition regime.",
    Q_target_design=10.0,    # Long-term target: ZN/PF-class
    eta_wp_target=0.20,      # 20% magnetic direct drive
)

ZN_DESIGN = ConceptParameters(
    name="Sandia ZN (MagLIF, next-gen)",
    short_name="ZN",
    description="60 MA pulsed-power driver with 8 kJ laser, 30 T B-field. Yager-Elorriaga 2022 design.",
    reference="Yager-Elorriaga et al. 2022 Nucl. Fusion 62 042015",
    fuel="DT",
    T_ion_keV=5.0,
    n_fuel_per_cc=3.0e19,
    tau_confinement_ns=10.0,
    B_field_T=30.0,
    eta_wallplug=0.09,        # eta_wp = 0.09 (ZN chain default)
    rep_rate_Hz=0.1,          # ~10 sec/shot design
    E_fusion_per_shot_MJ=20.0,  # design target
    E_grid_per_shot_MJ=200.0,
    CR=4.7,
    status="design",
    key_challenge="McBride 1D + 2D mix predicts Q_eng ~ 1e-3; below break-even.",
    Q_target_design=10.0,
    eta_wp_target=0.20,
)

ZAP_SFZ = ConceptParameters(
    name="Zap Energy sheared-flow Z-pinch",
    short_name="Zap-SFZ",
    description="Steady-state Z-pinch with sheared axial flow (~100 km/s) suppressing MRT. Repetitively-pulsed formation.",
    reference="Shumlak et al. 2017 Nucl. Fusion 57 056005; Zap Energy company materials 2024",
    fuel="DD",
    T_ion_keV=2.0,           # Lower T than MagLIF, but higher rep-rate compensates
    n_fuel_per_cc=1.0e17,    # 1e17 cm^-3 ~ 10^23 m^-3 (Zap regime)
    tau_confinement_ns=10000.0,  # ~10 us (much longer than MagLIF)
    B_field_T=10.0,
    eta_wallplug=0.20,        # claims 20%+ wall-plug (no driver Marx)
    rep_rate_Hz=10.0,         # 10 Hz design (kHz-class claimed)
    E_fusion_per_shot_MJ=0.5,
    E_grid_per_shot_MJ=2.5,
    CR=2.0,                   # Sheared flow prevents large CR
    status="demonstrated",     # Sheared-flow stabilisation demonstrated at small scale
    key_challenge="DD fuel has lower reactivity than DT; needs high rep-rate for Q.",
    Q_target_design=5.0,       # Zap's public target (no eta_wp given for rep-rate arch)
    eta_wp_target=0.50,        # claimed wall-plug for rep-rated Z-pinch
)

GF_MTF = ConceptParameters(
    name="General Fusion magnetized target fusion",
    short_name="GF-MTF",
    description="Spheromak plasma compressed by mechanically-driven piston liner. No pulsed-power driver.",
    reference="Laberge 2008 J. Fusion Energy 27 65; General Fusion company materials 2024",
    fuel="DT",
    T_ion_keV=10.0,          # Higher T at peak compression
    n_fuel_per_cc=1.0e21,    # Compressed to ~few mg/cc
    tau_confinement_ns=1000.0,  # ~1 us (compression + burn)
    B_field_T=5.0,
    eta_wallplug=0.30,        # Mechanical compression is reasonably efficient
    rep_rate_Hz=1.0,          # 1 Hz design target
    E_fusion_per_shot_MJ=50.0,
    E_grid_per_shot_MJ=200.0,
    CR=10.0,                  # Large compression via liner
    status="design",
    key_challenge="Mechanical liner lifetime at 1 Hz; plasma stability during compression.",
    Q_target_design=5.0,      # General Fusion's public target
    eta_wp_target=0.40,       # claimed plant electrical efficiency
)

PACIFIC_FUSION = ConceptParameters(
    name="Pacific Fusion (rep-rate pulsed magnetic)",
    short_name="PF",
    description="Rep-rated pulsed magnetic fusion (Pacific Fusion design, $900M Series A 2024). Targets 3x Z's stored energy at 1+ Hz.",
    reference="Pacific Fusion company materials 2024",
    fuel="DT",
    T_ion_keV=8.0,
    n_fuel_per_cc=2.0e20,
    tau_confinement_ns=10.0,
    B_field_T=25.0,
    eta_wallplug=0.13,        # from zpp_wallplug PF chain
    rep_rate_Hz=1.0,
    E_fusion_per_shot_MJ=100.0,
    E_grid_per_shot_MJ=770.0,  # 3x Z's stored = 66 MJ; close
    CR=5.0,
    status="design",
    key_challenge="First wall lifetime at 1 Hz; driver cost reduction.",
    Q_target_design=10.0,     # PF public target
    eta_wp_target=0.25,       # PF design eta_wp
)


ALL_CONCEPTS = [Z_PRESENT, ZN_DESIGN, ZAP_SFZ, GF_MTF, PACIFIC_FUSION]


def compute_Q_eng(concept: ConceptParameters) -> float:
    """Compute Q_eng = E_fus / E_grid for a concept.

    This is the published reference value, not derived from our
    McBride pipeline. Used as a sanity check.
    """
    return concept.E_fusion_per_shot_MJ / concept.E_grid_per_shot_MJ


def compute_LCOE_proxy(
    concept: ConceptParameters,
    nameplate_MW: float = 100.0,
    capacity_factor: float = 0.25,
    capex_per_GWe_USD: float = 10e9,
    eta_E_plant: float = 0.40,
) -> dict:
    """Compute a *proxy* LCOE for a concept using the design-driven model.

    Uses the same model as zpp_economics.PlantEconomics, but takes
    inputs from ConceptParameters instead of being user-supplied.

    Returns:
        dict with required_rep_rate_Hz, P_net_electric_MW,
        annual_net_energy_MWh, LCOE.
    """
    from zpp.zpp_economics import PlantEconomics

    Q_eng = compute_Q_eng(concept)
    if Q_eng * concept.eta_wallplug * eta_E_plant < 1:
        # Sub-break-even: cannot deliver net power
        return {
            "above_break_even": False,
            "required_rep_rate_Hz": float("inf"),
            "P_net_electric_MW": 0.0,
            "annual_net_energy_MWh": 0.0,
            "LCOE_USD_per_MWh": float("inf"),
        }
    plant = PlantEconomics(
        Q_eng=Q_eng,
        eta_wallplug_to_liner=concept.eta_wallplug,
        eta_E_plant=eta_E_plant,
        rep_rate_Hz=concept.rep_rate_Hz,
        E_grid_per_shot_MJ=concept.E_grid_per_shot_MJ,
        capacity_factor=capacity_factor,
        capex_per_GWe_USD=capex_per_GWe_USD,
        nameplate_MW=nameplate_MW,
    )
    required_rr = plant.required_rep_rate_Hz()
    actual_rr = concept.rep_rate_Hz
    # The "achievable" P_net is the min of design-rr and required-rr.
    if actual_rr >= required_rr:
        achievable = True
        P_net = nameplate_MW
    else:
        achievable = False
        # Limited by rep-rate
        P_net = (actual_rr / required_rr) * nameplate_MW if required_rr > 0 else 0
    annual = P_net * 8760.0 * capacity_factor
    lcoe = plant.lcoe_USD_per_MWh() if achievable else float("inf")
    return {
        "above_break_even": True,
        "achievable_at_design_rep_rate": bool(achievable),
        "required_rep_rate_Hz": float(required_rr),
        "design_rep_rate_Hz": float(actual_rr),
        "P_net_electric_MW": float(P_net),
        "annual_net_energy_MWh": float(annual),
        "LCOE_USD_per_MWh": float(lcoe),
    }


def compare_concepts(
    nameplate_MW: float = 100.0,
    capacity_factor: float = 0.25,
    capex_per_GWe_USD: float = 10e9,
    eta_E_plant: float = 0.40,
) -> list[dict]:
    """Compare all concepts side-by-side at a given plant design point.

    For each concept, computes:
    - Q_eng from per-shot E_fusion / E_grid (current best estimate)
    - Q_eng_target (long-term design target)
    - LCOE proxy at current Q_eng
    - LCOE proxy at target Q_eng

    Returns:
        list of dicts, one per concept, with all parameters + computed
        fields including both current and target Q_eng / LCOE.
    """
    rows = []
    for c in ALL_CONCEPTS:
        Q_eng_current = compute_Q_eng(c)
        # LCOE at current Q_eng
        lcoe_current = compute_LCOE_proxy(
            c, nameplate_MW=nameplate_MW,
            capacity_factor=capacity_factor,
            capex_per_GWe_USD=capex_per_GWe_USD,
            eta_E_plant=eta_E_plant,
        )
        # LCOE at target Q_eng with target eta_wp (if different from current)
        if c.Q_target_design > 0 and (
            abs(c.Q_target_design - Q_eng_current) > 1e-6
            or (c.eta_wp_target > 0 and abs(c.eta_wp_target - c.eta_wallplug) > 1e-6)
        ):
            target_concept = ConceptParameters(
                **{
                    **asdict(c),
                    "E_fusion_per_shot_MJ": c.Q_target_design * c.E_grid_per_shot_MJ,
                    "eta_wallplug": c.eta_wp_target if c.eta_wp_target > 0 else c.eta_wallplug,
                }
            )
            lcoe_target = compute_LCOE_proxy(
                target_concept, nameplate_MW=nameplate_MW,
                capacity_factor=capacity_factor,
                capex_per_GWe_USD=capex_per_GWe_USD,
                eta_E_plant=eta_E_plant,
            )
        else:
            lcoe_target = lcoe_current
        # Lawson-like triple product
        nTtau = c.n_fuel_per_cc * c.T_ion_keV * c.tau_confinement_ns * 1e-9 * 1e6  # keV·s/m³
        rows.append({
            **asdict(c),
            "Q_eng_computed": Q_eng_current,
            "Q_eng_target": c.Q_target_design,
            "Q_eng_gap_factor": c.Q_target_design / Q_eng_current if Q_eng_current > 0 else float("inf"),
            "nTtau_keVs_per_m3": nTtau,
            "above_lawson_ignition_3e21": bool(nTtau >= 3e21),
            "lcoe_current": lcoe_current,
            "lcoe_target": lcoe_target,
        })
    return rows


def comparison_markdown_table(rows: list[dict]) -> str:
    """Format a comparison table as Markdown.

    Args:
        rows: Output of compare_concepts().

    Returns:
        Markdown table string suitable for printing or saving.
    """
    headers = [
        "Concept", "Fuel", "T (keV)", "n (cm⁻³)", "τ (ns)",
        "η_wp", "rep (Hz)", "Q_eng", "Q_eng (target)",
        "LCOE curr", "LCOE target", "nTτ", "status",
    ]
    lines = [
        "| " + " | ".join(headers) + " |",
        "|" + "|".join(["---"] * len(headers)) + "|",
    ]
    for r in rows:
        LCOE_curr = "∞" if r["lcoe_current"]["LCOE_USD_per_MWh"] == float("inf") else f"${r['lcoe_current']['LCOE_USD_per_MWh']:.0f}"
        LCOE_target = "∞" if r["lcoe_target"]["LCOE_USD_per_MWh"] == float("inf") else f"${r['lcoe_target']['LCOE_USD_per_MWh']:.0f}"
        nTtau_str = f"{r['nTtau_keVs_per_m3']:.1e}"
        lines.append("| " + " | ".join([
            r["short_name"], r["fuel"],
            f"{r['T_ion_keV']:.1f}", f"{r['n_fuel_per_cc']:.1e}", f"{r['tau_confinement_ns']:.0f}",
            f"{r['eta_wallplug']:.2f}", f"{r['rep_rate_Hz']:.1e}",
            f"{r['Q_eng_computed']:.3f}", f"{r['Q_eng_target']:.1f}",
            LCOE_curr, LCOE_target, nTtau_str, r["status"],
        ]) + " |")
    return "\n".join(lines)
