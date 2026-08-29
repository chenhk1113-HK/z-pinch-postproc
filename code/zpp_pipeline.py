"""
Core post-processor pipeline for Z-pinch fusion shots.

Reads a 1D rad-MHD profile (time-series of ion temperature, fuel density,
areal density, and optional radius) plus a few driver parameters, and
produces the engineering metrics relevant to a Z-pinch fusion power plant.

Output: a single dict that zpp_io.py will serialise to JSON.
"""
from __future__ import annotations
import json
import numpy as np

from zpp_bosch_hale import reactivity_DT_cm3s, E_DT_J, E_DT_MeV
from zpp_lawson import burn_weighted_lawson, lawson_criterion_classic_DT


# Physical constants
N_AVOGADRO = 6.02214076e23
MOLAR_MASS_DT = 2.5  # equimolar D-T average mass, g/mol

# NumPy 2.0+ renamed np.trapz -> np.trapezoid. Compat shim.
_trapz = getattr(np, "trapezoid", None) or getattr(np, "trapz", None)

# Defaults — overridable in zpp_run.py CLI
DEFAULT_ETA_HELPER = 0.40  # thermal-to-electric, Brayton cycle typical


def number_density_atoms_per_cc(rho_gcc: np.ndarray) -> np.ndarray:
    """Number density n [atoms/cm^3] for equimolar D-T (A_avg = 2.5)."""
    return rho_gcc * N_AVOGADRO / MOLAR_MASS_DT


def fusion_power_density(
    rho_gcc: np.ndarray, T_keV: np.ndarray
) -> np.ndarray:
    """Fusion power density P_fus [W/m^3] for D-T.

    P_fus = n_D * n_T * <sigma*v> * E_fus
    For equimolar D-T, n_D = n_T = n/2, so n_D * n_T = n^2 / 4.

    Returns in SI (W/m^3) for direct integration.
    """
    n_per_cc = number_density_atoms_per_cc(rho_gcc)  # atoms/cm^3
    n_per_m3 = n_per_cc * 1e6  # atoms/m^3 (1 cm^3 = 1e-6 m^3, so n/cm^3 -> n*1e6 /m^3)
    sigma_v = reactivity_DT_cm3s(T_keV)  # cm^3/s
    sigma_v_m3 = sigma_v * 1e-6  # m^3/s (1 cm^3 = 1e-6 m^3)
    n_D_m3 = n_per_m3 / 2.0
    n_T_m3 = n_per_m3 / 2.0
    # P [W/m^3] = n_D * n_T * <sigma*v> [m^3/s] * E_fus [J]
    p_fus = n_D_m3 * n_T_m3 * sigma_v_m3 * E_DT_J
    return p_fus


def areal_density(rho_gcc: np.ndarray, radius_cm: np.ndarray | None) -> np.ndarray:
    """Areal density rho*R [g/cm^2] from radial profile if radius is given,
    else from column density (1D simulation) which is already a column.

    For a 1D slab with the column density array passed directly (rho_R_gccm),
    the caller should skip this and pass areal_density directly via input.
    For a cylindrical Z-pinch with radius, the in-line column is
    integral(rho dl) = 2 * integral_0^R rho(r) dr ~ 2 * rho_mean * R.
    Here we approximate as 2 * rho * R (a thin-shell-like estimate).
    """
    if radius_cm is None:
        return np.array([])
    return 2.0 * rho_gcc * radius_cm


def burn_yield(
    T_keV: np.ndarray,
    rho_gcc: np.ndarray,
    time_ns: np.ndarray,
    radius_cm: np.ndarray | None = None,
    T_burn_thresh_keV: float = 1.0,
    rho_burn_thresh_gcc: float = 0.1,
) -> dict:
    """Compute total fusion yield [J] and supporting burn statistics.

    Integration is over the burn window: T > T_burn_thresh AND rho > rho_burn_thresh.
    """
    T = np.asarray(T_keV, dtype=float)
    rho = np.asarray(rho_gcc, dtype=float)
    t = np.asarray(time_ns, dtype=float)
    R = np.asarray(radius_cm, dtype=float) if radius_cm is not None else None

    if not (len(T) == len(rho) == len(t)):
        raise ValueError(
            f"lengths must match: len(T)={len(T)}, len(rho)={len(rho)}, len(t)={len(t)}"
        )

    p_fus = fusion_power_density(rho, T)  # W/m^3

    # Volume: cylindrical Z-pinch with radius R -> V = pi R^2 L, but we don't
    # have L (axial length). For ICF post-processing, we report the total yield
    # per unit length [J/m]. The caller scales by the actual liner height.
    # For a 1D profile with no radius, we report per-unit-volume [J/m^3]
    # and the caller multiplies by the imploded fuel volume.
    if R is not None and len(R) == len(T):
        # The imploded fuel volume is set by the MINIMUM (stagnation) radius,
        # not the time-varying R. Use min(R) as the constant imploded cross-section.
        R_stag_cm = float(np.min(R))
        # Volume per unit length at stagnation: pi R_stag^2  [m^2]
        vol_per_length_m2 = np.pi * (R_stag_cm * 1e-2) ** 2  # convert cm to m
        # Power per unit length at stagnation [W/m]
        p_fus_per_length = p_fus * vol_per_length_m2
        # Total yield per unit length [J/m]
        E_fus_per_length_J_per_m = float(_trapz(p_fus_per_length, t) * 1e-9)  # ns->s
        # Default Z-pinch liner height ~ 1 cm = 1e-2 m
        default_liner_height_m = 1e-2
        E_fus_J = E_fus_per_length_J_per_m * default_liner_height_m
        E_fus_MJ = E_fus_J / 1e6
        # Areal density from the radial profile: rho*R = int rho(r) dr
        # Approximate as trapz(rho, R) over the time-implosion history
        # (uses the rho values at each timestep, which is a rough proxy)
        rho_R_gccm = float(_trapz(rho, R)) if len(rho) and len(R) > 1 else float(rho[0] * R_stag_cm)
    else:
        # No radius: return yield per unit volume, per unit time
        # Integrate P_fus * dt -> J/m^3
        E_fus_per_volume_J_per_m3 = float(_trapz(p_fus, t) * 1e-9)
        E_fus_J = E_fus_per_volume_J_per_m3  # placeholder; caller multiplies by fuel volume
        E_fus_MJ = E_fus_J / 1e6
        rho_R_gccm = 0.0

    # Burn-window detection
    in_burn = (T > T_burn_thresh_keV) & (rho > rho_burn_thresh_gcc)
    tau_burn_ns = (
        float(t[in_burn][-1] - t[in_burn][0]) if in_burn.sum() >= 2 else 0.0
    )

    return {
        "E_fusion_J": E_fus_J,
        "E_fusion_MJ": E_fus_MJ,
        "tau_burn_ns": tau_burn_ns,
        "rho_R_gccm": rho_R_gccm,
        "T_peak_keV": float(T.max()) if len(T) else 0.0,
        "rho_peak_gcc": float(rho.max()) if len(rho) else 0.0,
        "in_burn_n_samples": int(in_burn.sum()),
    }


def gain_chain(
    E_fus_J: float,
    E_stored_J: float,
    E_kinetic_J: float,
    eta_helper: float = DEFAULT_ETA_HELPER,
) -> dict:
    """Compute Q_target, Q_eng, and eta_wallplug.

    Q_target = E_fus / E_kinetic  (driver efficiency stripped out)
    Q_eng    = E_fus / E_stored  (raw engineering gain)
    eta_wp   = E_fus / E_grid    (wall-plug efficiency)
    """
    E_fus = max(E_fus_J, 0.0)
    E_kin = max(E_kinetic_J, 1e-30)  # avoid div-by-zero
    E_st = max(E_stored_J, 1e-30)
    eta = max(min(eta_helper, 1.0), 0.0)
    Q_target = E_fus / E_kin
    Q_eng = E_fus / E_st
    eta_wp = Q_eng * eta
    return {
        "Q_target": Q_target,
        "Q_eng": Q_eng,
        "eta_wallplug": eta_wp,
        "eta_helper_used": eta,
    }


def stagnation_pressure_GPa(
    rho_gcc: np.ndarray, T_keV: np.ndarray
) -> float:
    """Stagnation pressure estimate.

    P = 2 nT  (Boltzmann x2 for adiabatic compression; nT in keV/cm^3).
    Convert to GPa: 1 keV * 1e6 atoms/cm^3 = 1.602e-13 J/cm^3 = 1.602e-7 J/m^3 * 1e9
    = 0.1602 Pa ... actually, the standard conversion for nT [keV * cm^-3] to
    pressure is P [Pa] = nT * 1.602e-16, since 1 eV = 1.602e-19 J.
    So 1 keV * 1 atom/cm^3 = 1.602e-16 Pa. Multiply by 1e6 for 1e6 atoms/cm^3
    * 1 keV = 1.602e-10 Pa. To get GPa, multiply by 1e-9 -> 1.602e-19. Wait
    let me redo this more carefully.

    Energy per particle = T [keV] * 1.602e-16 J/keV = T * 1.602e-16 J.
    Number density n [atoms/cm^3] = N.
    P = 2/3 * energy_density = 2/3 * N * T * 1.602e-16 J/cm^3
      = (2/3) * N * T * 1.602e-16 J/cm^3
    Convert J/cm^3 to Pa: 1 J/cm^3 = 1e6 Pa (since 1 J = 1 Pa*m^3 and 1 cm^3 = 1e-6 m^3)
    So P [Pa] = (2/3) * N * T * 1.602e-16 * 1e6 = (2/3) * N * T * 1.602e-10
    For 1D P estimate (P = nT), we drop the 2/3 and use P = N * T * 1.602e-10 Pa.
    P [GPa] = N * T * 1.602e-10 / 1e9 = N * T * 1.602e-19.
    Equivalently: P [GPa] = (n_per_cc * 1e6) * T_keV * 1.602e-19 / 1e9
                = n_per_cc * T_keV * 1.602e-19
    where n_per_cc is in atoms/cm^3.

    Returns
    -------
    float
        Stagnation pressure in GPa at the sample with peak nT.
    """
    rho = np.asarray(rho_gcc, dtype=float)
    T = np.asarray(T_keV, dtype=float)
    n_per_cc = rho * N_AVOGADRO / MOLAR_MASS_DT  # atoms/cm^3
    nT = n_per_cc * T  # keV * atoms/cm^3
    # Use the sample with peak nT
    idx = int(np.argmax(nT))
    P_GPa = float(nT[idx] * 1.602e-19)  # 1 keV*atom/cm^3 = 1.602e-19 GPa
    return P_GPa


def convergence_ratio(R_initial_cm: float, R_stag_cm: float) -> float:
    """Convergence ratio CR = R_initial / R_stagnation.

    For MagLIF typical values: R_initial ~ 0.5 cm, R_stag ~ 0.02 cm
    gives CR ~ 25. SLACK HEDP target CR is 20-30.
    """
    if R_stag_cm <= 0:
        return 0.0
    return R_initial_cm / R_stag_cm


def run_pipeline(
    time_ns: np.ndarray,
    T_keV: np.ndarray,
    rho_gcc: np.ndarray,
    E_stored_J: float,
    E_kinetic_J: float,
    radius_cm: np.ndarray | None = None,
    R_initial_cm: float | None = None,
    eta_helper: float = DEFAULT_ETA_HELPER,
    input_provenance: dict | None = None,
) -> dict:
    """Top-level pipeline: ingest inputs, compute all engineering metrics, return report dict.

    Parameters
    ----------
    time_ns, T_keV, rho_gcc : array
        1D rad-MHD profile, same length, ns / keV / g/cm^3.
    E_stored_J, E_kinetic_J : float
        Driver parameters: stored electrical energy and liner kinetic energy.
    radius_cm : array, optional
        Optional radial profile (cm) for stagnation pressure and CR.
    R_initial_cm : float, optional
        Required if radius_cm is given (for CR calculation).
    eta_helper : float
        Thermal-to-electric efficiency (default 0.40 Brayton cycle).
    input_provenance : dict, optional
        Caller-supplied provenance info (e.g. shot_id, source_file).

    Returns
    -------
    dict
        Full engineering-metric report; serialise via zpp_io.write_report.
    """
    # 1. Yield + burn stats
    burn = burn_yield(T_keV, rho_gcc, time_ns, radius_cm=radius_cm)

    # 2. Gain chain
    gains = gain_chain(burn["E_fusion_J"], E_stored_J, E_kinetic_J, eta_helper=eta_helper)

    # 3. Lawson
    lawson = burn_weighted_lawson(T_keV, rho_gcc, time_ns)
    lawson_class = lawson_criterion_classic_DT(lawson["lawson_nTtau_keVs_per_m3"])

    # 4. Stagnation pressure
    P_stag_GPa = stagnation_pressure_GPa(rho_gcc, T_keV)

    # 5. Convergence ratio
    CR = (
        convergence_ratio(R_initial_cm, float(np.min(radius_cm)))
        if (radius_cm is not None and R_initial_cm is not None and len(radius_cm))
        else 0.0
    )

    return {
        "input_provenance": input_provenance or {},
        "results": {
            "E_fusion_MJ": burn["E_fusion_MJ"],
            "E_fusion_J": burn["E_fusion_J"],
            "Q_target": gains["Q_target"],
            "Q_eng": gains["Q_eng"],
            "eta_wallplug": gains["eta_wallplug"],
            "tau_burn_ns": burn["tau_burn_ns"],
            "lawson_nTtau_keVs_per_m3": lawson["lawson_nTtau_keVs_per_m3"],
            "lawson_nTtau_atoms_cm3_keV_s": lawson["lawson_nTtau_atoms_cm3_keV_s"],
            "lawson_class": lawson_class,
            "P_stag_GPa": P_stag_GPa,
            "convergence_ratio": CR,
        },
        "derived": {
            "T_peak_keV": burn["T_peak_keV"],
            "rho_peak_gcc": burn["rho_peak_gcc"],
            "rho_R_gccm": burn["rho_R_gccm"],
            "n_samples_in_burn": burn["in_burn_n_samples"],
        },
        "constants": {
            "eta_helper": gains["eta_helper_used"],
            "E_DT_MeV": E_DT_MeV,
            "A_avg_DT": MOLAR_MASS_DT,
        },
    }
