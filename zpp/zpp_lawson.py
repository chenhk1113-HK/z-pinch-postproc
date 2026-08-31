"""
Burn-weighted Lawson triple product <nT tau> for D-T.

The Lawson criterion (J.D. Lawson 1957, rediscovered many times) states
that net energy production requires the product of fuel density, ion
temperature, and confinement time to exceed a critical value. For D-T,
the canonical value is roughly 3e21 keV s/m^3 for ignition at T ~ 14 keV.

Inertial-confinement fusion doesn't strictly "confinement time" in the
magnetic-confinement sense — instead the relevant timescale is the
disassembly time of the compressed fuel, which we take from the burn
window where T > 1 keV and rho > 0.1 g/cc.

The "burn-weighted" form integrates nT over the burn window:
    <nT tau>_DT = integral(n(t) * T(t) * dt, t in burn_window)
"""
from __future__ import annotations
import numpy as np

# NumPy 2.0+ renamed np.trapz -> np.trapezoid. Compat shim.
_trapz = getattr(np, "trapezoid", None) or getattr(np, "trapz", None)

# Default burn-window thresholds (CLI-overridable in zpp_run.py)
DEFAULT_T_BURN_THRESH_KEV = 1.0
DEFAULT_RHO_BURN_THRESH_GCC = 0.1


def burn_weighted_lawson(
    T_keV: np.ndarray,
    rho_gcc: np.ndarray,
    time_ns: np.ndarray,
    T_thresh_keV: float = DEFAULT_T_BURN_THRESH_KEV,
    rho_thresh_gcc: float = DEFAULT_RHO_BURN_THRESH_GCC,
) -> dict:
    """Compute the burn-weighted Lawson triple product <nT tau>_DT.

    Parameters
    ----------
    T_keV : array
        Ion temperature in keV, same length as time_ns.
    rho_gcc : array
        Fuel mass density in g/cm^3, same length as time_ns.
    time_ns : array
        Time in ns, monotonically increasing, same length as T_keV.
    T_thresh_keV, rho_thresh_gcc : float
        Burn-window thresholds: a sample is "in burn" if both T > T_thresh
        AND rho > rho_thresh.

    Returns
    -------
    dict with keys:
        'lawson_nTtau_keVs_per_m3' : float
            The triple product in canonical Lawson units.
        'lawson_nTtau_atoms_cm3_keV_s' : float
            Same thing in ICF-conventional units (atoms/cm^3 * keV * s).
        'tau_burn_ns' : float
            Duration of the burn window in ns.
        'n_samples_in_burn' : int
        'T_peak_keV' : float
        'rho_peak_gcc' : float
    """
    T = np.asarray(T_keV, dtype=float)
    rho = np.asarray(rho_gcc, dtype=float)
    t = np.asarray(time_ns, dtype=float)

    if not (len(T) == len(rho) == len(t)):
        raise ValueError(
            f"lengths must match: len(T)={len(T)}, len(rho)={len(rho)}, len(t)={len(t)}"
        )
    if len(t) < 2:
        raise ValueError("need at least 2 samples to integrate over time")

    # Number density: n = rho * N_A / (A_avg) where A_avg = 2.5 for equimolar D-T
    # n [atoms/cm^3] = rho [g/cm^3] * 6.022e23 / 2.5 = rho * 2.409e23
    n_atoms_per_cc = rho * 6.02214076e23 / 2.5

    in_burn = (T > T_thresh_keV) & (rho > rho_thresh_gcc)

    # Trapezoid integration over the burn window only
    if in_burn.sum() < 2:
        return {
            "lawson_nTtau_keVs_per_m3": 0.0,
            "lawson_nTtau_atoms_cm3_keV_s": 0.0,
            "tau_burn_ns": 0.0,
            "n_samples_in_burn": int(in_burn.sum()),
            "T_peak_keV": float(T.max()) if len(T) else 0.0,
            "rho_peak_gcc": float(rho.max()) if len(rho) else 0.0,
        }

    t_b = t[in_burn]
    nT_b = n_atoms_per_cc[in_burn] * T[in_burn]  # [atoms/cm^3 * keV]
    # Integrate: int(nT dt) over the burn window in time units of ns.
    # To convert to keV*s, multiply ns by 1e-9.
    nT_tau_atoms_cm3_keV_s = float(_trapz(nT_b, t_b) * 1e-9)
    # Convert to SI: nT tau in m^-3 keV s.
    # 1 atom/cm^3 = 1e6 atoms/m^3, so atoms/cm^3 * keV * s * 1e6 = m^-3 keV s
    nT_tau_SI_keVs_per_m3 = nT_tau_atoms_cm3_keV_s * 1e6

    return {
        "lawson_nTtau_keVs_per_m3": nT_tau_SI_keVs_per_m3,
        "lawson_nTtau_atoms_cm3_keV_s": nT_tau_atoms_cm3_keV_s,
        "tau_burn_ns": float(t_b[-1] - t_b[0]),
        "n_samples_in_burn": int(in_burn.sum()),
        "T_peak_keV": float(T.max()),
        "rho_peak_gcc": float(rho.max()),
    }


def lawson_criterion_classic_DT(lawson_value: float) -> str:
    """Classify the triple product against the canonical D-T Lawson criterion.

    Classic D-T ignition at T_opt ~ 14 keV requires n*T*tau ~ 3e21 keV s/m^3.
    'Ignition-class' is taken here as >= 0.5 * canonical.
    'Break-even' is >= 0.05 * canonical (gain > 1 in idealized ICF).
    'Below break-even' otherwise.
    """
    canonical = 3.0e21
    if lawson_value >= 0.5 * canonical:
        return "ignition-class"
    if lawson_value >= 0.05 * canonical:
        return "break-even"
    return "below-break-even"
