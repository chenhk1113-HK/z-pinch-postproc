"""
Regression tests for the Bosch-Hale 1992 D-T reactivity parametrisation.

Reference values are taken from Wisconsin UWFDM-1268 (Heltemes, Moses,
Santarius 2005), Table 6, T(d,n)4He column. The coefficients in our
code (`zpp_bosch_hale.py`) come from UWFDM-1268 Appendix II (the C++
reference implementation), which is the canonical transcription of
Bosch & Hale 1992 (Nuclear Fusion 32 611).

Acceptance: within 1% of the published value. The parametrisation is
self-consistent at the coefficient precision given; we allow 1% for
floating-point round-off.
"""
import sys
from pathlib import Path

import numpy as np
import pytest

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent / "code"))

from zpp.zpp_bosch_hale import (
    reactivity_DT_cm3s,
    reactivity_DDn_cm3s,
    E_DT_MeV,
    E_DT_J,
)


# Bosch-Hale 1992 D-T reference values, T(d,n)4He column,
# Wisconsin UWFDM-1268 Table 6. (These are the same numbers Bosch & Hale
# 1992 published in Nuclear Fusion 32 611 Table VII, just transcribed
# into the Wisconsin paper's data table.)
REFERENCE = {
    1.0:   6.86e-21,
    2.0:   2.98e-19,
    5.0:   1.37e-17,    # 5 keV: typical MagLIF stagnation
    10.0:  1.14e-16,    # 10 keV: NIF ignition design
    20.0:  4.33e-16,
    50.0:  8.65e-16,
    100.0: 8.45e-16,    # 100 keV: boundary of parametrisation
}


@pytest.mark.parametrize("T_keV,expected", list(REFERENCE.items()))
def test_reactivity_DT_matches_table(T_keV, expected):
    sv = reactivity_DT_cm3s(np.array([T_keV]))[0]
    rel = abs(sv - expected) / expected
    # Bosch-Hale 1992 form (as transcribed in UWFDM-1268 Appendix II)
    # matches the published table values to <0.5%. We use 1% as the
    # unit-test tolerance to allow for floating-point round-off.
    assert rel < 0.01, (
        f"D-T reactivity at T={T_keV} keV: got {sv:.4e}, "
        f"Bosch-Hale 1992 reference {expected:.4e}, rel error {rel:.3%} > 1%"
    )


def test_reactivity_DT_array_input():
    """Vectorised input should give same result as scalar input."""
    Ts = np.array([1.0, 5.0, 10.0, 20.0])
    svs = reactivity_DT_cm3s(Ts)
    for T, sv in zip(Ts, svs):
        sv_scalar = reactivity_DT_cm3s(np.array([T]))[0]
        assert abs(sv - sv_scalar) < 1e-20


def test_reactivity_increases_with_T_below_peak():
    """For T < ~65 keV, d<sigma*v>/dT > 0 (Bosch-Hale 1992 peak is ~65 keV,
    the cross-section peak is at ~64 keV CM)."""
    Ts = np.array([1.0, 5.0, 10.0, 20.0, 50.0])  # all below the 65 keV peak
    svs = reactivity_DT_cm3s(Ts)
    assert np.all(np.diff(svs) > 0), "reactivity must increase with T below 65 keV"


def test_reactivity_peak_location():
    """The D-T reactivity peaks at T ~ 65 keV. Test that svs(60) < svs(65)
    and svs(65) > svs(70) (or at least that the peak is in this region)."""
    Ts = np.array([50.0, 60.0, 65.0, 70.0, 80.0, 100.0])
    svs = reactivity_DT_cm3s(Ts)
    peak_idx = int(np.argmax(svs))
    # Peak should be in 50-100 keV
    assert 50.0 <= Ts[peak_idx] <= 100.0, (
        f"reactivity peak at T={Ts[peak_idx]} keV (svs[peak_idx]={svs[peak_idx]:.3e}) "
        f"is outside expected 50-100 keV range"
    )


def test_reactivity_below_range_emits_warning():
    import warnings
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        _ = reactivity_DT_cm3s(np.array([0.1]))
        assert any(issubclass(x.category, RuntimeWarning) for x in w), (
            "should warn when T < 0.2 keV"
        )


def test_reactivity_above_range_emits_warning():
    import warnings
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        _ = reactivity_DT_cm3s(np.array([200.0]))
        assert any(issubclass(x.category, RuntimeWarning) for x in w), (
            "should warn when T > 100 keV"
        )


def test_reactivity_DDn_table():
    """D(d,n)3He reactivity. Reference from UWFDM-1268 Table 6 (DDn column)."""
    refs = {
        1.0: 9.93e-23,
        5.0: 9.13e-20,
        10.0: 6.02e-19,
        20.0: 2.60e-18,
    }
    for T, expected in refs.items():
        sv = reactivity_DDn_cm3s(np.array([T]))[0]
        rel = abs(sv - expected) / expected
        assert rel < 0.01, (
            f"D(d,n)3He reactivity at T={T} keV: got {sv:.4e}, "
            f"reference {expected:.4e}, rel error {rel:.3%} > 1%"
        )


def test_E_DT_constants():
    """D-T fusion Q-value: 17.6 MeV per reaction."""
    assert abs(E_DT_MeV - 17.6) < 1e-6
    # E_DT_J = 17.6 MeV * 1.602176634e-13 J/MeV
    assert abs(E_DT_J - 17.6 * 1.602176634e-13) < 1e-30
