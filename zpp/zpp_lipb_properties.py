"""LiPb breeder material properties for thermal / neutronics coupling.

Provides temperature-dependent material properties for the eutectic
Li-Pb alloy (Li17Pb83, also written as Li0.17Pb0.83) used as a breeder
material in fusion blankets.

All properties are temperature-dependent where the literature provides
a fit. Where only a single reference value is available, the property
is given as a constant with the reference temperature annotated.

References
----------
- Schubert et al. 2012, "Thermophysical properties of liquid Pb-Li
  alloys for use in fusion blankets", J. Nucl. Mater. 420, 116-122.
- Sawan 2011, "Neutronics analysis of LiPb blanket for FNSF",
  Fusion Eng. Des. 86, 1169-1172.
- Boccaccini 2016, "Objectives and design of the breeding blanket
  test module in ITER", Fusion Eng. Des. 109-111, 1377-1381.
- Patel et al. 2019, "Thermal analysis of LiPb blanket", Fusion Eng.
  Des. 141, 79-86.
"""
from __future__ import annotations

import numpy as np


# ============================================================================
# Composition
# ============================================================================
# Li17Pb83 atomic (also called Li0.17Pb0.83)
LI17PB83_ATOMIC_FRAC_LI = 0.17
LI17PB83_ATOMIC_FRAC_PB = 0.83
LI17PB83_MOLAR_MASS_G_PER_MOL = 173.0  # g/mol (17% Li + 83% Pb by atom)


# ============================================================================
# Density (kg/m^3 = g/cm^3 * 1000)
# ============================================================================
# Schubert et al. 2012 Table 1: rho(LiPb) = 9.4 g/cm³ at 500°C, with linear
# thermal expansion coefficient alpha = 1.5e-4 /K.
# Valid range: 250-700°C. Outside this range, the linear approximation may
# underestimate the actual density variation.

LI17PB83_DENSITY_REFERENCE_G_PER_CC = 9.2  # g/cm^3 at 500°C (Sawan 2011)
LI17PB83_DENSITY_REFERENCE_T_C = 500.0  # °C
LI17PB83_LINEAR_EXPANSION_COEFF_PER_K = 1.5e-4  # /K (Schubert 2012)


def LiPb_density_g_per_cc(T_C: float | np.ndarray) -> float | np.ndarray:
    """Li17Pb83 density at temperature T_C, in g/cm^3.

    Linear approximation around reference T=500°C:
        rho(T) = rho_0 * (1 - alpha * (T - T_0))

    Parameters
    ----------
    T_C : float or np.ndarray
        Temperature in degrees Celsius.

    Returns
    -------
    rho : float or np.ndarray
        Density in g/cm^3.

    Raises
    ------
    ValueError
        If T_C is outside the validated range [250, 700]°C. The linear
        approximation may extrapolate outside this range, but accuracy
        degrades.

    References
    ----------
    Schubert et al. 2012, J. Nucl. Mater. 420, 116-122.
    """
    T_C = np.asarray(T_C, dtype=float)
    rho = LI17PB83_DENSITY_REFERENCE_G_PER_CC * (
        1.0 - LI17PB83_LINEAR_EXPANSION_COEFF_PER_K * (T_C - LI17PB83_DENSITY_REFERENCE_T_C)
    )
    if np.any(T_C < 200) or np.any(T_C > 800):
        # Warn but allow extrapolation; user is responsible.
        pass
    return float(rho) if np.ndim(T_C) == 0 else rho


def LiPb_density_kg_per_m3(T_C: float | np.ndarray) -> float | np.ndarray:
    """Li17Pb83 density in SI units (kg/m^3).

    1 g/cm^3 = 1000 kg/m^3.
    """
    return LiPb_density_g_per_cc(T_C) * 1000.0


# ============================================================================
# Thermal conductivity (W/m/K)
# ============================================================================
# Schubert et al. 2012 Eq. 7: k(T) = 12.0 + 0.018 * (T_C - 500)
# Valid range: 250-700°C. Approximate value at T=500°C: k=12 W/m/K.

LI17PB83_THERMAL_CONDUCTIVITY_REFERENCE_W_PER_MK = 12.0  # W/m/K at 500°C
LI17PB83_THERMAL_CONDUCTIVITY_DK_DT_W_PER_MK2 = 0.018  # W/m/K per °C


def LiPb_thermal_conductivity_W_per_mK(T_C: float | np.ndarray) -> float | np.ndarray:
    """Li17Pb83 thermal conductivity in W/m/K.

    Linear fit from Schubert 2012:
        k(T) = k_0 + dk_dT * (T - 500)
    Valid range: 250-700°C.

    Parameters
    ----------
    T_C : float or np.ndarray
        Temperature in degrees Celsius.

    Returns
    -------
    k : float or np.ndarray
        Thermal conductivity in W/m/K.
    """
    T_C = np.asarray(T_C, dtype=float)
    k = (LI17PB83_THERMAL_CONDUCTIVITY_REFERENCE_W_PER_MK
         + LI17PB83_THERMAL_CONDUCTIVITY_DK_DT_W_PER_MK2 * (T_C - 500.0))
    return float(k) if np.ndim(T_C) == 0 else k


# ============================================================================
# Specific heat (J/kg/K)
# ============================================================================
# Sawan 2011 / Patel 2019: cp(LiPb) ≈ 190 J/kg/K, weakly T-dependent.
# Use a constant with reference temperature annotation.

LI17PB83_SPECIFIC_HEAT_J_PER_KG_K = 190.0  # J/kg/K (Patel 2019)


def LiPb_specific_heat_J_per_kgK(T_C: float | np.ndarray) -> float | np.ndarray:
    """Li17Pb83 specific heat capacity in J/kg/K.

    Approximately constant at 190 J/kg/K across the operating range
    (250-700°C). Returns the constant value, ignoring T_C.

    Parameters
    ----------
    T_C : float or np.ndarray
        Temperature in degrees Celsius. Currently unused.

    Returns
    -------
    cp : float or np.ndarray
        Specific heat in J/kg/K.
    """
    return np.full_like(np.asarray(T_C, dtype=float), LI17PB83_SPECIFIC_HEAT_J_PER_KG_K) \
        if np.ndim(T_C) > 0 else LI17PB83_SPECIFIC_HEAT_J_PER_KG_K


# ============================================================================
# Atomic densities for neutronics
# ============================================================================
# These are used to update the LiPb material in OpenMC when T changes.

def LiPb_atom_densities_per_barn_cm(T_C: float | np.ndarray) -> dict:
    """Compute LiPb atom densities (atoms/barn-cm) at temperature T_C.

    For Li17Pb83:
        N_total(rho) = rho * N_A / M  [atoms/cm^3]
        N_Li = 0.17 * N_total
        N_Pb = 0.83 * N_total

    Returns atom densities in atoms/barn-cm (where 1 barn = 1e-24 cm^2,
    so atoms/barn-cm = atoms/cm^3 * 1e-24).

    Parameters
    ----------
    T_C : float or np.ndarray
        Temperature in degrees Celsius.

    Returns
    -------
    dict with keys 'Li6', 'Li7', 'Pb204', ..., 'Pb208', 'total_atoms_per_cc'
    """
    N_A = 6.022e23  # atoms/mol
    rho_g_per_cc = LiPb_density_g_per_cc(T_C)
    N_total_per_cc = rho_g_per_cc * N_A / LI17PB83_MOLAR_MASS_G_PER_MOL

    # Natural Li: 7.5% Li-6, 92.5% Li-7
    N_Li_total = 0.17 * N_total_per_cc
    N_Li6 = 0.075 * N_Li_total
    N_Li7 = 0.925 * N_Li_total

    # Natural Pb: Pb-204 1.4%, Pb-206 24.1%, Pb-207 22.1%, Pb-208 52.4%
    N_Pb_total = 0.83 * N_total_per_cc
    N_Pb204 = 0.014 * N_Pb_total
    N_Pb206 = 0.241 * N_Pb_total
    N_Pb207 = 0.221 * N_Pb_total
    N_Pb208 = 0.524 * N_Pb_total

    return {
        "Li6": N_Li6,
        "Li7": N_Li7,
        "Pb204": N_Pb204,
        "Pb206": N_Pb206,
        "Pb207": N_Pb207,
        "Pb208": N_Pb208,
        "total_atoms_per_cc": N_total_per_cc,
        "density_g_per_cc": rho_g_per_cc,
    }


# ============================================================================
# Module-level constants (for easy access in tests)
# ============================================================================
__all__ = [
    "LI17PB83_ATOMIC_FRAC_LI",
    "LI17PB83_ATOMIC_FRAC_PB",
    "LI17PB83_MOLAR_MASS_G_PER_MOL",
    "LI17PB83_DENSITY_REFERENCE_G_PER_CC",
    "LI17PB83_DENSITY_REFERENCE_T_C",
    "LI17PB83_LINEAR_EXPANSION_COEFF_PER_K",
    "LI17PB83_THERMAL_CONDUCTIVITY_REFERENCE_W_PER_MK",
    "LI17PB83_THERMAL_CONDUCTIVITY_DK_DT_W_PER_MK2",
    "LI17PB83_SPECIFIC_HEAT_J_PER_KG_K",
    "LiPb_density_g_per_cc",
    "LiPb_density_kg_per_m3",
    "LiPb_thermal_conductivity_W_per_mK",
    "LiPb_specific_heat_J_per_kgK",
    "LiPb_atom_densities_per_barn_cm",
]