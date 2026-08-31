"""
D-T reactivity <sigma*v> parametrisation.

Implementation: Bosch & Hale (1992) "Improved formulas for fusion
cross-sections and thermal reactivities", Nuclear Fusion 32 611.
R-matrix fit to the cross-section data valid 0.2-100 keV for T(d,n)4He
(D-T).

The source code in Appendix II of UWFDM-1268 (Heltemes, Moses,
Santarius 2005, University of Wisconsin) is the canonical Python/C
reference for the coefficients and the theta/X formulae:

  BG = 34.3827                    (D-T gamow constant)
  C1 = 1.17302e-9                 (cm^3/s normalisation)
  C2 = 1.51361e-2, C3 = 7.51886e-2, C4 = 4.60643e-3,
  C5 = 1.35000e-2, C6 = -1.06750e-4, C7 = 1.36600e-5
                                  (theta continued-fraction coefs)
  mrc2 = 1.124656e6                (reduced-mass * c^2, keV)

  theta = T / (1 - T*(C2 + T*(C4 + T*C6)) /
                    (1 + T*(C3 + T*(C5 + T*C7))))
  X     = (BG^2 / (4*theta))^(1/3)
  <sigma*v> = C1 * theta * sqrt(X / (mrc2 * T^3)) * exp(-3*X)

E_DT = 17.6 MeV per reaction (D + T -> He-4 + n + 17.6 MeV).
This module also exposes reactivity_DD_cm3s for D(d,n)3He
(primary reaction in D-only MagLIF shots, valid 0.2-1000 keV).
"""
from __future__ import annotations
import warnings
import numpy as np

# Constants
E_DT_MeV = 17.6  # D + T -> He-4 + n fusion energy, MeV
E_DT_J = E_DT_MeV * 1.602176634e-13  # Joules
E_DD_n_MeV = 2.45  # D + D -> T + p secondary, then T + D -> He-4 + n (total 2.45 + 17.6 = ~20 MeV)
#   For D(d,n)3He primary: E_DDn = 3.27 MeV
E_DDn_MeV = 3.27


def _bosch_hale(T_keV: np.ndarray, BG: float, C1: float,
                C2: float, C3: float, C4: float,
                C5: float, C6: float, C7: float,
                mrc2: float) -> np.ndarray:
    """Bosch-Hale 1992 R-matrix fit for one reaction channel.

    Implements equations 2-5 of Bosch & Hale 1992 NF 32 611 exactly as
    given in the C++ reference code in Appendix II of UWFDM-1268.
    """
    T = np.atleast_1d(T_keV).astype(float)
    # theta = T / (1 - T*(C2 + T*(C4 + T*C6)) / (1 + T*(C3 + T*(C5 + T*C7))))
    denom_inner = 1.0 + T * (C3 + T * (C5 + T * C7))
    denom_outer = 1.0 - T * (C2 + T * (C4 + T * C6)) / denom_inner
    theta = T / denom_outer
    # X = (BG^2 / (4 theta))^(1/3)
    X = np.power((BG * BG) / (4.0 * theta), 1.0 / 3.0)
    # <sigma*v> = C1 * theta * sqrt(X / (mrc2 * T^3)) * exp(-3 X)
    return C1 * theta * np.sqrt(X / (mrc2 * np.power(T, 3.0))) * np.exp(-3.0 * X)


# Bosch-Hale 1992 D-T coefficients (valid 0.2-100 keV).
# Source: UWFDM-1268 Appendix II, lines 10-11 of the C++ reference.
_BH_DT = {
    "BG":   34.3827,
    "mrc2": 1.124656e6,    # keV
    "C1":   1.17302e-9,    # cm^3/s normalisation
    "C2":   1.51361e-2,
    "C3":   7.51886e-2,
    "C4":   4.60643e-3,
    "C5":   1.35000e-2,
    "C6":  -1.06750e-4,
    "C7":   1.36600e-5,
}

# Bosch-Hale 1992 D(d,n)3He coefficients (valid 0.2-1000 keV, asymptote near 1 MeV).
# Source: UWFDM-1268 Appendix II C++ code, reaction index 3 (DD->n).
_BH_DDn = {
    "BG":   31.3970,
    "mrc2": 9.37814e5,     # keV
    "C1":   5.43360e-12,
    "C2":   5.85778e-3,
    "C3":   7.68222e-3,
    "C4":   0.0,
    "C5":  -2.96400e-6,
    "C6":   0.0,
    "C7":   0.0,
}


def _dt_valid(T: np.ndarray) -> None:
    """Emit a RuntimeWarning if T is outside the Bosch-Hale 1992 D-T range."""
    if np.any(T < 0.2):
        warnings.warn(
            f"reactivity_DT_cm3s: T_min = {T.min():.3f} keV < 0.2 keV "
            f"(below Bosch-Hale 1992 D-T valid range 0.2-100 keV).",
            RuntimeWarning, stacklevel=3,
        )
    if np.any(T > 100.0):
        warnings.warn(
            f"reactivity_DT_cm3s: T_max = {T.max():.3f} keV > 100 keV "
            f"(above Bosch-Hale 1992 D-T valid range 0.2-100 keV).",
            RuntimeWarning, stacklevel=3,
        )


def reactivity_DT_cm3s(T_keV) -> np.ndarray:
    """D-T reactivity <sigma*v> in cm^3/s.

    Parameters
    ----------
    T_keV : float or array
        Ion temperature in keV. Valid range 0.2-100 keV; outside this
        range, the parametrisation may still return a value but
        a RuntimeWarning is emitted.

    Returns
    -------
    np.ndarray
        Reactivity in cm^3/s, same shape as T_keV.
    """
    T = np.atleast_1d(T_keV).astype(float)
    _dt_valid(T)
    return _bosch_hale(T, **_BH_DT)


def reactivity_DDn_cm3s(T_keV) -> np.ndarray:
    """D(d,n)3He reactivity in cm^3/s. Valid 0.2-1000 keV (asymptote near 1 MeV)."""
    T = np.atleast_1d(T_keV).astype(float)
    if np.any(T < 0.2):
        warnings.warn(
            f"reactivity_DDn_cm3s: T_min = {T.min():.3f} keV < 0.2 keV "
            f"(below Bosch-Hale 1992 D-D valid range 0.2-1000 keV).",
            RuntimeWarning, stacklevel=2,
        )
    return _bosch_hale(T, **_BH_DDn)


# Bosch-Hale 1992 D-T reference values (UWFDM-1268 Table 6, T(d,n)4He column).
# These are the gold-standard values that the parametrisation must reproduce
# to <1% (it does in the valid range).
_BH_DT_REF = {
    1.0:   6.86e-21,
    2.0:   2.98e-19,
    5.0:   1.37e-17,    # 5 keV: typical MagLIF stagnation
    10.0:  1.14e-16,    # 10 keV: NIF ignition design
    20.0:  4.33e-16,
    50.0:  8.65e-16,
    100.0: 8.45e-16,    # 100 keV: boundary of parametrisation
}
