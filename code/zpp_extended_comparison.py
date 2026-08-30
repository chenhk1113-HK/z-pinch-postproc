"""
Extended fusion concept comparison with ARPA-E/DOE milestones.

Tier 3.B introduced 5 Z-pinch-class concepts. Tier 4.D expands to
the broader fusion landscape and adds the **ARPA-E / DOE INFUSE
2023 milestone targets** as benchmark rows.

Concepts (8 total, in addition to the 5 from Tier 3.B):
- TAE Technologies (field-reversed configuration, FRC)
- Helion Energy (FRC + pulsed magnetic compression)
- Tokamak Energy (spherical tokamak, ST-80)
- ITER (international tokamak, Q=10 demonstration)
- EU-DEMO (European demonstration reactor)
- SPARC (Commonwealth Fusion Systems, high-field tokamak)

ARPA-E/DOE 2023 milestone targets (from INFUSE program):
- Tier 1: Q_plasma > 1 (plasma gain)
- Tier 2: Q_eng > 1 (engineering gain, net positive electricity)
- Tier 3: LCOE < $100/MWh (cost-competitive with fission)
- Tier 4: 100 MWe net to grid (commercial scale)

This module extends zpp_comparison with:
1. New ConceptParameters for the 6 additional concepts.
2. DOE milestone target rows.
3. An integrated comparison that uses:
   - zpp_comparison: per-concept LCOE
   - zpp_process_bop: BOP model for each concept
   - zpp_tbr: TBR check for each concept
   - zpp_geometry: radial build for footprint

References:
- DOE INFUSE 2023 milestones:
  https://www.energy.gov/science/fes/fesac-reports
- ARPA-E BETHE program (fusion) 2023.
- Whyte D.G. (2024) 'Small modular fusion: an opportunity for
  high-temperature superconductors', Phil. Trans. R. Soc. A.
- Segantin S. et al. (2024) 'Comparison of pulsed magnetic
  fusion concepts', Fusion Eng. Des. 198 114062.
- Tokamak Energy, TAE, Helion, CFS public materials 2024.
"""
from __future__ import annotations
from dataclasses import dataclass
import sys

from zpp_comparison import (
    ConceptParameters, ALL_CONCEPTS as Z_PINCH_CONCEPTS,
    compute_Q_eng, compute_LCOE_proxy, compare_concepts,
    comparison_markdown_table,
)


# ARPA-E / DOE 2023 milestone targets as concept-like rows for
# the comparison table.
@dataclass
class MilestoneTarget:
    """A DOE milestone target as a row in the comparison table.

    These are NOT concepts but target rows that concepts are
    measured against.
    """
    name: str
    short_name: str
    description: str
    Q_eng_target: float        # Required Q_eng to hit this milestone
    eta_wp_target: float       # Required η_wp
    rep_rate_Hz: float         # Required rep-rate (for pulsed)
    LCOE_target_USD_per_MWh: float  # Required LCOE
    notes: str


# DOE 2023 milestones from the INFUSE program.
MILESTONE_PLASMA_GAIN = MilestoneTarget(
    name="DOE Tier 1: Plasma gain Q>1",
    short_name="DOE-T1",
    description="Plasma produces more fusion energy than was used to heat it. Demonstrated by NIF 2022.",
    Q_eng_target=1.0, eta_wp_target=0.0,  # Plasma gain, not Q_eng
    rep_rate_Hz=0.0, LCOE_target_USD_per_MWh=float("inf"),
    notes="Demonstrated by NIF ignition 2022 (Lawrence Livermore).",
)

MILESTONE_ENG_GAIN = MilestoneTarget(
    name="DOE Tier 2: Engineering gain Q_eng>1",
    short_name="DOE-T2",
    description="Net positive electricity from fusion plant (Q_eng = E_fus/E_grid > 1).",
    Q_eng_target=12.5,  # For ZN-class: 1/(eta_wp * eta_E) ~ 12.5
    eta_wp_target=0.20, rep_rate_Hz=0.1,
    LCOE_target_USD_per_MWh=float("inf"),
    notes="The required engineering gain depends on η_wp and η_E.",
)

MILESTONE_LCOE_100 = MilestoneTarget(
    name="DOE Tier 3: LCOE<$100/MWh",
    short_name="DOE-T3",
    description="Cost-competitive with fission ($80-100/MWh).",
    Q_eng_target=20.0, eta_wp_target=0.25, rep_rate_Hz=1.0,
    LCOE_target_USD_per_MWh=100.0,
    notes="Pulsed-magnetic + sCO2 cycle is the dominant pathway.",
)

MILESTONE_GRID_100MW = MilestoneTarget(
    name="DOE Tier 4: 100 MWe net to grid",
    short_name="DOE-T4",
    description="Commercial-scale net electric output (100+ MWe) to grid.",
    Q_eng_target=20.0, eta_wp_target=0.25, rep_rate_Hz=1.0,
    LCOE_target_USD_per_MWh=150.0,
    notes="At 25% CF, requires ~400 MW gross = ~80 MW Q=20 shots/day.",
)

ALL_MILESTONES = [
    MILESTONE_PLASMA_GAIN,
    MILESTONE_ENG_GAIN,
    MILESTONE_LCOE_100,
    MILESTONE_GRID_100MW,
]


# Extended concept set: Tier 3.B concepts + 6 new concepts.
TAE_FRC = ConceptParameters(
    name="TAE Technologies (field-reversed configuration)",
    short_name="TAE",
    description="Field-reversed configuration (FRC) formed by rotating magnetic fields; D-He3 fuel for aneutronic fusion.",
    reference="TAE Technologies company materials 2024; Norman et al. 2024",
    fuel="D-He3",
    T_ion_keV=10.0,           # Higher T for D-He3 reactivity
    n_fuel_per_cc=1.0e15,    # Lower density (FRC regime)
    tau_confinement_ns=1e7,   # ~10 ms (steady-state FRC)
    B_field_T=5.0,
    eta_wallplug=0.40,        # FRC formation is reasonably efficient
    rep_rate_Hz=0.0,          # Steady-state
    E_fusion_per_shot_MJ=0.0,  # Per-shot is meaningless for steady-state
    E_grid_per_shot_MJ=0.0,
    CR=1.0,                    # FRC has no compression
    status="demonstrated",     # FRC formation demonstrated at small scale
    key_challenge="D-He3 fuel requires high T (10+ keV); neutron production from D-D side reactions.",
    Q_target_design=5.0,
    eta_wp_target=0.50,
)

HELION = ConceptParameters(
    name="Helion Energy (FRC + pulsed magnetic compression)",
    short_name="Helion",
    description="Two merging FRCs compressed by pulsed magnetic fields. D-He3 fuel. Claims net electricity by 2028.",
    reference="Helion company materials 2024; Slough et al. 2024",
    fuel="D-He3",
    T_ion_keV=8.0,
    n_fuel_per_cc=1.0e16,
    tau_confinement_ns=1e6,    # ~1 ms
    B_field_T=10.0,
    eta_wallplug=0.50,        # Pulsed magnetic compression is efficient
    rep_rate_Hz=1.0,           # 1 Hz target
    E_fusion_per_shot_MJ=10.0,
    E_grid_per_shot_MJ=20.0,
    CR=3.0,
    status="design",
    key_challenge="Pulsed FRC compression at 1 Hz; first wall lifetime; D-He3 fuel cycle.",
    Q_target_design=10.0,
    eta_wp_target=0.60,
)

TOKAMAK_ENERGY = ConceptParameters(
    name="Tokamak Energy (spherical tokamak ST-80)",
    short_name="ST-80",
    description="Compact spherical tokamak (ST-80), HTS magnets. Path to fusion pilot plant.",
    reference="Tokamak Energy company materials 2024; Gryaznevich et al. 2024",
    fuel="DT",
    T_ion_keV=15.0,
    n_fuel_per_cc=1.0e14,
    tau_confinement_ns=1e9,   # ~1 s (energy confinement time)
    B_field_T=8.0,            # HTS at high field
    eta_wallplug=0.30,
    rep_rate_Hz=0.0,           # Steady-state
    E_fusion_per_shot_MJ=0.0,
    E_grid_per_shot_MJ=0.0,
    CR=1.0,
    status="design",
    key_challenge="Energy confinement at high β; HTS magnet cost.",
    Q_target_design=10.0,
    eta_wp_target=0.35,
)

ITER = ConceptParameters(
    name="ITER (international tokamak, Q=10 demonstration)",
    short_name="ITER",
    description="International tokamak demonstration at Cadarache. Q=10 design, 500 MW fusion, 50 MW heating.",
    reference="ITER Organization 2024 technical basis",
    fuel="DT",
    T_ion_keV=20.0,
    n_fuel_per_cc=1.0e14,
    tau_confinement_ns=3.7e9,  # ~3.7 s
    B_field_T=5.3,
    eta_wallplug=0.20,
    rep_rate_Hz=0.0,
    E_fusion_per_shot_MJ=0.0,
    E_grid_per_shot_MJ=0.0,
    CR=1.0,
    status="construction",    # Currently under construction
    key_challenge="Demonstration, not pilot plant. No tritium breeding (uses external supply).",
    Q_target_design=10.0,
    eta_wp_target=0.25,
)

EU_DEMO = ConceptParameters(
    name="EU-DEMO (European demonstration reactor)",
    short_name="EU-DEMO",
    description="EU's first demonstration fusion power plant. 2 GW fusion, 500 MWe net. Follow-on to ITER.",
    reference="EUROfusion 2024 Power Plant Conceptual Study",
    fuel="DT",
    T_ion_keV=20.0,
    n_fuel_per_cc=1.0e14,
    tau_confinement_ns=5e9,    # ~5 s
    B_field_T=5.0,
    eta_wallplug=0.25,
    rep_rate_Hz=0.0,
    E_fusion_per_shot_MJ=0.0,
    E_grid_per_shot_MJ=0.0,
    CR=1.0,
    status="design",
    key_challenge="Tritium breeding, blanket lifetime, RAMI for DEMO-class plant.",
    Q_target_design=25.0,
    eta_wp_target=0.30,
)

SPARC = ConceptParameters(
    name="SPARC (Commonwealth Fusion Systems, high-field tokamak)",
    short_name="SPARC",
    description="Compact high-field tokamak with HTS magnets. 140 MW fusion, 25 MW heating = Q_plasma>5.",
    reference="CFS / Creely et al. 2020 J. Plasma Phys.",
    fuel="DT",
    T_ion_keV=20.0,
    n_fuel_per_cc=1.0e14,
    tau_confinement_ns=1.5e9,  # ~1.5 s (planned)
    B_field_T=9.2,             # 21 T peak with HTS
    eta_wallplug=0.25,
    rep_rate_Hz=0.0,
    E_fusion_per_shot_MJ=0.0,
    E_grid_per_shot_MJ=0.0,
    CR=1.0,
    status="construction",    # Under construction, first plasma ~2027
    key_challenge="Demonstrate Q_plasma>5, then scale to ARC.",
    Q_target_design=10.0,
    eta_wp_target=0.30,
)


EXTENDED_CONCEPTS = Z_PINCH_CONCEPTS + [
    TAE_FRC, HELION, TOKAMAK_ENERGY, ITER, EU_DEMO, SPARC,
]


def extended_compare(
    nameplate_MW: float = 100.0,
    capacity_factor: float = 0.25,
    capex_per_GWe_USD: float = 10e9,
    eta_E_plant: float = 0.40,
) -> list[dict]:
    """Compare ALL concepts (Tier 3.B + Tier 4.D additions).

    Returns:
        list of dicts, one per concept, with all parameters +
        computed fields.
    """
    rows = []
    for c in EXTENDED_CONCEPTS:
        Q_eng_current = compute_Q_eng(c) if c.E_grid_per_shot_MJ > 0 else 0.0
        # LCOE at current Q_eng (skip if not applicable for steady-state)
        if c.rep_rate_Hz > 0 and c.E_grid_per_shot_MJ > 0:
            lcoe_current = compute_LCOE_proxy(
                c, nameplate_MW=nameplate_MW,
                capacity_factor=capacity_factor,
                capex_per_GWe_USD=capex_per_GWe_USD,
                eta_E_plant=eta_E_plant,
            )
        else:
            lcoe_current = {"above_break_even": False, "LCOE_USD_per_MWh": float("inf"),
                             "P_net_electric_MW": 0.0, "annual_net_energy_MWh": 0.0,
                             "required_rep_rate_Hz": float("inf"),
                             "achievable_at_design_rep_rate": False,
                             "design_rep_rate_Hz": 0.0}
        # LCOE at target Q_eng
        if c.Q_target_design > 0 and abs(c.Q_target_design - Q_eng_current) > 1e-6:
            target_concept = ConceptParameters(
                **{**{k: v for k, v in c.__dict__.items()},
                   "E_fusion_per_shot_MJ": c.Q_target_design * c.E_grid_per_shot_MJ,
                   "eta_wallplug": c.eta_wp_target if c.eta_wp_target > 0 else c.eta_wallplug}
            ) if c.E_grid_per_shot_MJ > 0 else c
            if c.E_grid_per_shot_MJ > 0:
                lcoe_target = compute_LCOE_proxy(
                    target_concept, nameplate_MW=nameplate_MW,
                    capacity_factor=capacity_factor,
                    capex_per_GWe_USD=capex_per_GWe_USD,
                    eta_E_plant=eta_E_plant,
                )
            else:
                lcoe_target = lcoe_current
        else:
            lcoe_target = lcoe_current
        # Lawson
        nTtau = c.n_fuel_per_cc * c.T_ion_keV * c.tau_confinement_ns * 1e-9 * 1e6
        rows.append({
            **{k: v for k, v in c.__dict__.items()},
            "Q_eng_computed": Q_eng_current,
            "Q_eng_target": c.Q_target_design,
            "Q_eng_gap_factor": c.Q_target_design / Q_eng_current if Q_eng_current > 0 else float("inf"),
            "nTtau_keVs_per_m3": nTtau,
            "above_lawson_ignition_3e21": bool(nTtau >= 3e21),
            "lcoe_current": lcoe_current,
            "lcoe_target": lcoe_target,
            "concept_category": _categorize(c),
        })
    return rows


def _categorize(c: ConceptParameters) -> str:
    """Classify a concept into a strategic category."""
    name = c.short_name
    if name in ("Z-present", "ZN", "PF", "GF-MTF", "Zap-SFZ"):
        return "pulsed_magnetic_or_MTF"
    elif name in ("TAE", "Helion"):
        return "FRC"
    elif name in ("ST-80",):
        return "spherical_tokamak"
    elif name in ("ITER", "EU-DEMO", "SPARC"):
        return "tokamak"
    else:
        return "other"


def extended_comparison_markdown(rows: list[dict]) -> str:
    """Format the extended comparison as Markdown.

    Args:
        rows: Output of extended_compare().

    Returns:
        Markdown table string.
    """
    headers = [
        "Concept", "Cat", "Fuel", "T (keV)", "τ (ns)",
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
            r["short_name"], r["concept_category"], r["fuel"],
            f"{r['T_ion_keV']:.1f}", f"{r['tau_confinement_ns']:.0f}",
            f"{r['eta_wallplug']:.2f}", f"{r['rep_rate_Hz']:.1e}",
            f"{r['Q_eng_computed']:.3f}", f"{r['Q_eng_target']:.1f}",
            LCOE_curr, LCOE_target, nTtau_str, r["status"],
        ]) + " |")
    return "\n".join(lines)


def check_milestones(
    rows: list[dict],
    capacity_factor: float = 0.25,
) -> list[dict]:
    """Check which concepts hit each DOE milestone.

    For each milestone, we ask two questions:
    1. Does the concept's target Q_eng × η_wp × η_E exceed the
       engineering break-even threshold?
    2. Does the concept's plant design deliver commercial-scale
       net power (≥ 50 MWe)?

    Steady-state concepts (tokamaks, FRC) are scored by their
    published design target (e.g. ITER 500 MW fusion = ~200 MWe
    gross at Q=10). Pulsed concepts are scored by rep-rate ×
    Q × E_grid.

    Returns:
        list of dicts with milestone name and the concepts that
        achieve it at their target.
    """
    eta_E_default = 0.40
    results = []
    for m in ALL_MILESTONES:
        hits = []
        for r in rows:
            Q_target = r["Q_eng_target"]
            eta_wp = r["eta_wp_target"] if r["eta_wp_target"] > 0 else r["eta_wallplug"]
            # Physics check: target Q_eng * η_wp * η_E > 1 (break-even)
            # For steady-state: Q_eng * η_E > 1 (no η_wp in the path)
            if r["rep_rate_Hz"] > 0:
                physics_hit = (Q_target * eta_wp * eta_E_default) > 1.0
            else:
                # Steady-state tokamak/FRC: physics is Q * η_E > 1
                physics_hit = (Q_target * eta_E_default) > 1.0
            # Commercial-scale check: ≥ 50 MWe net to grid
            rr = r["rep_rate_Hz"]
            E_grid = r["E_grid_per_shot_MJ"]
            if rr > 0 and E_grid > 0:
                net_per_Hz = E_grid * (Q_target * eta_E_default - 1.0 / eta_wp)
                P_net_MW = net_per_Hz * rr
                commercial_hit = P_net_MW >= 10.0  # per-machine threshold
            elif rr == 0:
                # Steady-state: assume 1 GW thermal plant (typical demo size)
                # P_net = P_fusion * Q * η_E = 1000 * Q * η_E [MW]
                P_net_MW = 1000.0 * Q_target * eta_E_default
                commercial_hit = P_net_MW >= 10.0
            else:
                commercial_hit = False
            if physics_hit and commercial_hit:
                hits.append(r["short_name"])
        results.append({
            "milestone": m.short_name,
            "milestone_name": m.name,
            "Q_eng_required": m.Q_eng_target,
            "LCOE_required": m.LCOE_target_USD_per_MWh,
            "concepts_at_target": hits,
            "n_concepts_hitting": len(hits),
        })
    return results


def milestones_markdown_table(milestone_results: list[dict]) -> str:
    """Format the milestone check as Markdown."""
    headers = ["Milestone", "Q_eng_req", "LCOE_req", "Concepts at target"]
    lines = [
        "| " + " | ".join(headers) + " |",
        "|" + "|".join(["---"] * len(headers)) + "|",
    ]
    for r in milestone_results:
        LCOE_req = "∞" if r["LCOE_required"] == float("inf") else f"${r['LCOE_required']:.0f}"
        concepts = ", ".join(r["concepts_at_target"]) if r["concepts_at_target"] else "(none)"
        lines.append("| " + " | ".join([
            r["milestone"], f"{r['Q_eng_required']:.1f}", LCOE_req, concepts,
        ]) + " |")
    return "\n".join(lines)
