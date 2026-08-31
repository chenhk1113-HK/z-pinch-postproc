"""
Plasma-facing component (PFC) lifetime estimation.

Two damage mechanisms that limit the lifetime of fusion plant
first-wall components:

1. **Neutron displacement damage (DPA)** — 14 MeV D-T neutrons
   displace atoms from the lattice. Structural materials
   (RAFM steel, tungsten) accumulate ~10-20 DPA per full-power
   year (FPY). Components must be replaced when they reach
   ~100-200 DPA (depending on material).

2. **MHD-driven erosion (liquid-metal blankets)** — Liquid
   breeders (LiPb, FLiBe) experience MHD pressure losses and
   wall shear stress in strong B-fields. Erosion rate depends
   on flow velocity, B-field, channel geometry, and material
   compatibility.

This module provides:
- DPA_rate_per_FPY() from neutron flux and energy.
- cumulative_DPA_per_FPY() for a given neutron wall load.
- MHD_wall_shear_stress() from Hartmann number.
- MHD_erosion_rate_mm_per_year() for liquid-metal blanket.
- first_wall_lifetime_years() — min of DPA-limited and
  erosion-limited lifetime.
- replacement_interval_years() — recommended swap interval.
- PFC_lifetime_result — combined summary for plant economics.

References:
- Zinkle & Ghoniem (2000) Fusion Eng. Des. 49-50 709.
- Malang et al. (2009) "Limitations of liquid breeders for
  fusion applications", Fusion Eng. Des. 84 2142.
- Smolentsev et al. (2008) "MHD considerations for liquid-metal
  blankets", Fusion Eng. Des. 83 771.
- Stieglitz et al. (2011) "MHD turbulence in liquid metal flows",
  KIT Scientific Reports 7577.
- Subbotin et al. (2002) "Integrated approach to liquid-metal
  blanket design", Fusion Eng. Des. 63-64 329.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional


# Physical constants
E_NEUTRON_DT_MeV = 14.1
M_NEUTRON_AMU = 1.008
M_Fe_AMU = 55.845
M_W_AMU = 183.84
EV_PER_ERG = 6.242e11
JOULES_PER_MeV = 1.602e-13
KB_EV_PER_K = 8.617e-5


# Default displacement threshold energies [eV].
# Energy below which an atom stays in its lattice site.
ED_THRESHOLD = {
    "W": 68.0,        # Tungsten (ASTM E521)
    "SS316": 40.0,    # Steel (NRT model)
    "RAFM": 40.0,     # Reduced-activation ferritic-martensitic
    "Be": 31.0,       # Beryllium
    "Cu": 30.0,       # Copper
    "Mo": 60.0,       # Molybdenum
}

# DPA limit (cumulative) before structural failure.
# Material-specific. Sources: Zinkle & Ghoniem 2000; Tanigawa 2011.
DPA_LIMIT = {
    "W": 50.0,        # Tungsten is brittle at low T, but high T limit
    "SS316": 100.0,   # Conventional steel
    "RAFM": 150.0,    # Reduced-activation steel (EUROFER, F82H)
    "Be": 30.0,       # Beryllium (swelling, embrittlement)
    "Cu": 50.0,       # Copper
    "Mo": 50.0,       # Molybdenum
}

# NRT model (Norgett, Robinson, Torrens) conversion factor:
# DPA per (neutron fluence * displacement cross-section).
# NRT-DPA = 0.8 * T_dam / (2 * E_d)
# where T_dam = damage energy = fraction of PKA energy going
# into atomic displacements.
NRT_COEFFICIENT = 0.8


@dataclass
class PFCDamageInputs:
    """Inputs to PFC lifetime calculation."""
    # Neutron wall load
    neutron_wall_load_MW_per_m2: float = 1.0   # ZN design: ~1 MW/m²
    material: str = "RAFM"
    # Operation
    plant_availability: float = 0.25           # Same as capacity factor
    # MHD erosion (only for liquid-metal blankets)
    blanket_fluid: str = "LiPb"                # "LiPb", "FLiBe", "Li", "none"
    flow_velocity_m_per_s: float = 0.1         # Typical for liquid-metal blanket
    B_field_T: float = 5.0                     # Background B at first wall
    channel_half_height_m: float = 0.01        # 1 cm half-height channel
    # Erosion limit
    erosion_limit_mm: float = 2.0              # Allowable wall loss before breach


@dataclass
class PFCDamageResult:
    """Outputs from PFC lifetime calculation."""
    # Neutron damage
    neutron_wall_load_MW_per_m2: float
    dpa_per_FPY: float
    dpa_limit: float
    DPA_lifetime_FPY: float
    # MHD erosion
    blanket_fluid: str
    Hartmann_number: float
    wall_shear_stress_Pa: float
    erosion_rate_mm_per_year: float
    erosion_lifetime_years: float
    # Combined
    first_wall_lifetime_years: float
    replacement_interval_years: float
    annual_replacement_rate: float
    # Notes
    material: str
    plant_availability: float
    notes: str


def DPA_rate_per_FPY(
    neutron_wall_load_MW_per_m2: float,
    material: str = "RAFM",
) -> float:
    """Compute DPA per full-power year for a given neutron wall load.

    Uses NRT (Norgett-Robinson-Torrens) model:
    - Neutron flux = (wall_load * 1e6) / (E_n * 1.602e-13) [n/m²/s]
    - DPA rate = 0.8 * T_dam * flux / (2 * E_d * N_atom)
    - T_dam ~ 0.5 * E_n for 14 MeV neutrons in heavy metals
    - N_atom ~ 8e28 atoms/m³ for steel

    For ZN design (1 MW/m² wall load):
    - DPA ~ 10-15 per FPY for RAFM steel
    - DPA ~ 8-12 per FPY for tungsten (higher Ed but lower N_atom)

    Args:
        neutron_wall_load_MW_per_m2: Neutron wall load [MW/m²].
        material: PFC material name.

    Returns:
        DPA per full-power year [dpa/FPY].
    """
    if material not in ED_THRESHOLD:
        raise ValueError(f"Unknown material: {material}. Known: {list(ED_THRESHOLD.keys())}")
    Ed_eV = ED_THRESHOLD[material]
    E_n_eV = E_NEUTRON_DT_MeV * 1e6
    # Convert wall load to neutron flux [n/m²/s].
    # wall_load in MW/m² -> W/m² -> J/s/m² -> / E_n [J] -> flux [n/m²/s]
    wall_load_W_per_m2 = neutron_wall_load_MW_per_m2 * 1e6
    E_n_J = E_NEUTRON_DT_MeV * JOULES_PER_MeV  # 14.1 MeV in joules
    flux = wall_load_W_per_m2 / E_n_J
    # Atomic density: approximate from material
    # Steel ~ 8e28, W ~ 6.3e28, Be ~ 1.2e29
    N_atom_per_m3 = {
        "W": 6.3e28,
        "SS316": 8.5e28,
        "RAFM": 8.5e28,
        "Be": 1.2e29,
        "Cu": 8.5e28,
        "Mo": 6.4e28,
    }.get(material, 8.0e28)
    # Damage energy fraction (T_dam / E_n)
    # For 14 MeV neutrons on heavy atoms, ~0.5 of E_n goes to PKA.
    T_dam_over_En = 0.5
    # DPA per second
    dpa_per_sec = (NRT_COEFFICIENT * T_dam_over_En * E_n_eV * flux) / (2 * Ed_eV * N_atom_per_m3)
    # DPA per year (1 year = 3.156e7 s)
    dpa_per_year = dpa_per_sec * 3.156e7
    return dpa_per_year


def MHD_Hartmann_number(B_field_T: float, channel_half_height_m: float,
                          fluid_electrical_conductivity_S_per_m: float,
                          fluid_viscosity_Pa_s: float) -> float:
    """Compute Hartmann number Ha = B * L * sqrt(sigma / eta).

    Args:
        B_field_T: Magnetic field at first wall [T].
        channel_half_height_m: Half-height of flow channel [m].
        fluid_electrical_conductivity_S_per_m: Liquid metal electrical
            conductivity [S/m].
        fluid_viscosity_Pa_s: Dynamic viscosity [Pa·s].

    Returns:
        Hartmann number (dimensionless).
    """
    import numpy as np
    Ha = B_field_T * channel_half_height_m * np.sqrt(
        fluid_electrical_conductivity_S_per_m / fluid_viscosity_Pa_s
    )
    return Ha


def MHD_wall_shear_stress(
    Hartmann_number: float,
    flow_velocity_m_per_s: float,
    fluid_viscosity_Pa_s: float,
    channel_half_height_m: float,
) -> float:
    """MHD wall shear stress for Hartmann flow.

    For high Ha (Ha >> 1), the wall shear stress is:
        tau_w ~ (eta * v / L) * sqrt(Ha)
    (Smolentsev 2008, eq. 11)
    """
    import numpy as np
    tau_w = (fluid_viscosity_Pa_s * flow_velocity_m_per_s / channel_half_height_m) * np.sqrt(
        Hartmann_number
    )
    return tau_w


def MHD_erosion_rate_mm_per_year(
    Hartmann_number: float,
    wall_shear_stress_Pa: float,
    fluid_density_kg_per_m3: float,
    material: str = "RAFM",
    fluid: str = "LiPb",
) -> float:
    """Estimate erosion rate of PFC by flowing liquid metal.

    Empirical correlation:
        erosion_rate [mm/yr] = (tau_w / tau_crit)^n * C
    where:
        tau_crit ~ 10 Pa for steel/LiPb (Smolentsev 2008)
        n ~ 2.5 (power-law)
        C ~ 0.01 mm/yr (constant for steel/LiPb)

    For low Ha (< 1), erosion is minimal (laminar).
    For high Ha (> 1000), erosion can be substantial.

    Args:
        Hartmann_number: Ha [-].
        wall_shear_stress_Pa: tau_w [Pa].
        fluid_density_kg_per_m3: Liquid density [kg/m³].
        material: PFC material.
        fluid: Liquid-metal fluid.

    Returns:
        Erosion rate [mm/yr].
    """
    if Hartmann_number < 1.0:
        return 0.0  # Laminar, no significant erosion
    # Critical shear stress for the material/fluid combination.
    # Steel-LiPb: 10 Pa. RAFM-LiPb: 8 Pa. W-LiPb: 15 Pa (harder).
    tau_crit = {
        ("W", "LiPb"): 15.0,
        ("RAFM", "LiPb"): 8.0,
        ("SS316", "LiPb"): 10.0,
        ("W", "FLiBe"): 25.0,
        ("RAFM", "FLiBe"): 20.0,
    }.get((material, fluid), 10.0)
    if wall_shear_stress_Pa < tau_crit:
        return 0.0
    # Power-law erosion correlation.
    n = 2.5
    C = 0.01  # mm/yr constant
    erosion_rate = C * ((wall_shear_stress_Pa / tau_crit) ** n)
    return erosion_rate


# Default liquid-metal properties.
LIQUID_METAL_PROPERTIES = {
    "LiPb": {
        "electrical_conductivity_S_per_m": 7.5e5,  # at 500°C
        "viscosity_Pa_s": 2.5e-3,
        "density_kg_per_m3": 9800.0,
    },
    "FLiBe": {
        "electrical_conductivity_S_per_m": 2.5e3,
        "viscosity_Pa_s": 5.0e-3,
        "density_kg_per_m3": 1900.0,
    },
    "Li": {
        "electrical_conductivity_S_per_m": 3.0e6,
        "viscosity_Pa_s": 4.0e-4,
        "density_kg_per_m3": 500.0,
    },
}


def first_wall_lifetime(
    inputs: PFCDamageInputs,
) -> PFCDamageResult:
    """Compute PFC lifetime (DPA-limited ∩ MHD-erosion-limited)."""
    # 1. DPA per FPY
    dpa_per_FPY = DPA_rate_per_FPY(
        inputs.neutron_wall_load_MW_per_m2,
        inputs.material,
    )
    dpa_lim = DPA_LIMIT.get(inputs.material, 100.0)
    DPA_lifetime_FPY = dpa_lim / dpa_per_FPY if dpa_per_FPY > 0 else float("inf")
    # 2. MHD erosion (only if liquid metal)
    if inputs.blanket_fluid == "none":
        Hartmann = 0.0
        tau_w = 0.0
        erosion_rate = 0.0
        erosion_lifetime = float("inf")
    else:
        props = LIQUID_METAL_PROPERTIES.get(inputs.blanket_fluid, LIQUID_METAL_PROPERTIES["LiPb"])
        Hartmann = MHD_Hartmann_number(
            inputs.B_field_T,
            inputs.channel_half_height_m,
            props["electrical_conductivity_S_per_m"],
            props["viscosity_Pa_s"],
        )
        tau_w = MHD_wall_shear_stress(
            Hartmann,
            inputs.flow_velocity_m_per_s,
            props["viscosity_Pa_s"],
            inputs.channel_half_height_m,
        )
        erosion_rate = MHD_erosion_rate_mm_per_year(
            Hartmann, tau_w,
            props["density_kg_per_m3"],
            inputs.material, inputs.blanket_fluid,
        )
        erosion_lifetime = (
            inputs.erosion_limit_mm / erosion_rate if erosion_rate > 0 else float("inf")
        )
    # 3. Combined lifetime
    fw_lifetime_years = min(DPA_lifetime_FPY, erosion_lifetime)
    # 4. Replacement interval (with safety factor)
    # Plant normally replaces at 80% of lifetime to avoid failure.
    replacement_interval = fw_lifetime_years * 0.80
    annual_replacement_rate = 1.0 / replacement_interval if replacement_interval > 0 else float("inf")
    # 5. Adjust for plant availability (calendar years vs FPY)
    calendar_lifetime_years = fw_lifetime_years / inputs.plant_availability if inputs.plant_availability > 0 else float("inf")
    calendar_replacement_interval = replacement_interval / inputs.plant_availability if inputs.plant_availability > 0 else float("inf")
    annual_calendar_replacement_rate = 1.0 / calendar_replacement_interval if calendar_replacement_interval > 0 else float("inf")
    notes = (
        f"material={inputs.material}, blanket={inputs.blanket_fluid}, "
        f"wall_load={inputs.neutron_wall_load_MW_per_m2:.2f} MW/m². "
        f"DPA={dpa_per_FPY:.2f}/FPY, lifetime={DPA_lifetime_FPY:.1f} FPY. "
        f"Ha={Hartmann:.0f}, τ_w={tau_w:.2f} Pa, erosion={erosion_rate:.3f} mm/yr. "
        f"FW lifetime={fw_lifetime_years:.1f} FPY ({calendar_lifetime_years:.1f} calendar years). "
        f"Replacement interval={calendar_replacement_interval:.1f} years."
    )
    return PFCDamageResult(
        neutron_wall_load_MW_per_m2=inputs.neutron_wall_load_MW_per_m2,
        dpa_per_FPY=dpa_per_FPY,
        dpa_limit=dpa_lim,
        DPA_lifetime_FPY=DPA_lifetime_FPY,
        blanket_fluid=inputs.blanket_fluid,
        Hartmann_number=Hartmann,
        wall_shear_stress_Pa=tau_w,
        erosion_rate_mm_per_year=erosion_rate,
        erosion_lifetime_years=erosion_lifetime,
        first_wall_lifetime_years=fw_lifetime_years,
        replacement_interval_years=calendar_replacement_interval,
        annual_replacement_rate=annual_calendar_replacement_rate,
        material=inputs.material,
        plant_availability=inputs.plant_availability,
        notes=notes,
    )


def PFC_lifetime_summary(
    inputs_list: list,
) -> list:
    """Compute PFC lifetimes for a list of design points."""
    return [first_wall_lifetime(inp) for inp in inputs_list]
