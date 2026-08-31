"""
Extended ZN parameter sweeps for design-envelope analysis.

This module extends Tier 2.D's `zn_scaling_sweep` with:
1. **ZN-65 sweep**: sweep at the actual ZN design point (I=65 MA),
   the planned peak current per Yager-Elorriaga 2022.
2. **Fine-grained sweep around ZN design**: 4D sweep (I_peak, B_z0,
   E_laser, rho_0) at higher resolution around the ZN design point.
3. **Mix-aware Pareto frontier**: filter to the points where the
   2D mix-corrected Q_eng is highest. This is the "best achievable"
   design point given the McBride 1D + 2D-mix model.
4. **Output scaling laws**: linear regression of Q_eng vs each
   driver parameter at fixed others.

References:
- Yager-Elorriaga et al. (2022) Nucl. Fusion 62 042015 — ZN design.
- Slutz (2021) Phys. Plasmas 28 082101 — ice-burner scaling.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Iterable
import numpy as np

from zpp.zpp_scaling import (
    SweepResult,
    sweep_one_point,
    zn_scaling_sweep,
    scaling_summary,
)
from zpp.zpp_wallplug import (
    wallplug_chain_zn_design,
    wallplug_chain_z_present,
    wallplug_chain_pf_design,
    WallPlugChain,
)


# ZN design point at 65 MA (Yager-Elorriaga 2022 actual peak).
# The Tier 2.D default was 60 MA; this is the published "best estimate".
ZN_65_DEFAULTS = {
    "I_peak_MA": 65.0,
    "B_z0_T": 30.0,
    "E_laser_kJ": 8.0,
    "rho_0_mgcc": 1.5,
    "R_0_cm": 0.5,
    "T_preheat_eV": 300.0,
    "fuel": "DT",
}


def zn_65_sweep(
    E_stored_J: float | None = None,
    wallplug: WallPlugChain | None = None,
    apply_2d_mix: bool = True,
) -> list[SweepResult]:
    """Sweep around the ZN design point at I=65 MA.

    Axes:
    - I_peak: [55, 60, 65, 70, 75] MA (centered on 65)
    - B_z0: [20, 25, 30, 35, 40] T
    - E_laser: [4, 6, 8, 10, 12] kJ

    Total: 5 * 5 * 5 = 125 points. Runs in <2 seconds.
    """
    if wallplug is None:
        wallplug = wallplug_chain_zn_design()

    results = []
    for I in [55.0, 60.0, 65.0, 70.0, 75.0]:
        for B in [20.0, 25.0, 30.0, 35.0, 40.0]:
            for E in [4.0, 6.0, 8.0, 10.0, 12.0]:
                results.append(sweep_one_point(
                    I_peak_MA=I, B_z0_T=B, E_laser_kJ=E,
                    E_stored_J=E_stored_J, E_kinetic_J=None,
                    wallplug=wallplug, apply_2d_mix=apply_2d_mix,
                ))
    return results


def fine_grained_sweep(
    I_peak_MA_center: float = 65.0,
    B_z0_center: float = 30.0,
    E_laser_center: float = 8.0,
    I_peak_range: tuple[float, float] = (55.0, 75.0),
    B_z0_range: tuple[float, float] = (20.0, 40.0),
    E_laser_range: tuple[float, float] = (4.0, 12.0),
    n_per_axis: int = 5,
    wallplug: WallPlugChain | None = None,
    apply_2d_mix: bool = True,
) -> list[SweepResult]:
    """Fine-grained 3D sweep around a custom center point.

    Default center is the ZN design point (65 MA, 30 T, 8 kJ).
    """
    if wallplug is None:
        wallplug = wallplug_chain_zn_design()

    I_list = np.linspace(I_peak_range[0], I_peak_range[1], n_per_axis)
    B_list = np.linspace(B_z0_range[0], B_z0_range[1], n_per_axis)
    E_list = np.linspace(E_laser_range[0], E_laser_range[1], n_per_axis)

    results = []
    for I in I_list:
        for B in B_list:
            for E in E_list:
                results.append(sweep_one_point(
                    I_peak_MA=float(I), B_z0_T=float(B), E_laser_kJ=float(E),
                    E_stored_J=None, E_kinetic_J=None,
                    wallplug=wallplug, apply_2d_mix=apply_2d_mix,
                ))
    return results


def mix_aware_pareto(
    sweep_results: list[SweepResult],
    top_n: int = 10,
) -> list[SweepResult]:
    """Return the top-N sweep points by mix-corrected Q_eng.

    This is the "best achievable" design envelope given the
    McBride 1D + 2D-mix model. The Q_eng values are typically
    1e-4 to 1e-3 (sub-break-even), but the top of the distribution
    tells you which design choices give the highest yield per shot.
    """
    return sorted(sweep_results, key=lambda r: -r.Q_eng)[:top_n]


def scaling_law_regression(
    sweep_results: list[SweepResult],
    parameter: str = "I_peak_MA",
) -> dict:
    """Linear regression of Q_eng vs a sweep parameter at fixed others.

    Q_eng = a * parameter + b

    Returns dict with slope, intercept, R^2, and the fixed-other
    values used (median of all other params).
    """
    if parameter not in ("I_peak_MA", "B_z0_T", "E_laser_kJ"):
        raise ValueError(f"Unsupported parameter: {parameter}")

    other_params = [p for p in ("I_peak_MA", "B_z0_T", "E_laser_kJ") if p != parameter]
    # Compute medians of the other parameters
    fixed_values = {
        p: float(np.median([getattr(r, p) for r in sweep_results]))
        for p in other_params
    }
    # Filter to points near the medians (within 10%)
    filtered = []
    for r in sweep_results:
        if all(
            abs(getattr(r, p) - fixed_values[p]) < 0.1 * abs(fixed_values[p]) + 0.1
            for p in other_params
        ):
            filtered.append(r)
    if len(filtered) < 2:
        return {"slope": 0.0, "intercept": 0.0, "R_squared": 0.0,
                "n_points": len(filtered), "fixed_values": fixed_values,
                "parameter": parameter}

    x = np.array([getattr(r, parameter) for r in filtered])
    y = np.array([r.Q_eng for r in filtered])
    slope, intercept = np.polyfit(x, y, 1)
    # R^2
    y_pred = slope * x + intercept
    ss_res = np.sum((y - y_pred) ** 2)
    ss_tot = np.sum((y - np.mean(y)) ** 2)
    R_squared = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
    return {
        "slope": float(slope),
        "intercept": float(intercept),
        "R_squared": float(R_squared),
        "n_points": int(len(filtered)),
        "fixed_values": fixed_values,
        "parameter": parameter,
    }


def zn_65_summary(
    sweep_results: list[SweepResult] | None = None,
    wallplug: WallPlugChain | None = None,
    apply_2d_mix: bool = True,
) -> dict:
    """Summary of the ZN-65 sweep, including regression scaling laws."""
    if sweep_results is None:
        sweep_results = zn_65_sweep(
            wallplug=wallplug, apply_2d_mix=apply_2d_mix,
        )
    # Scaling laws at fixed (median) values
    scaling_I = scaling_law_regression(sweep_results, "I_peak_MA")
    scaling_B = scaling_law_regression(sweep_results, "B_z0_T")
    scaling_E = scaling_law_regression(sweep_results, "E_laser_kJ")

    # Best mix-corrected point
    best = mix_aware_pareto(sweep_results, top_n=1)[0]
    # Closest-to-design point
    def _key(r: SweepResult) -> float:
        return (
            (r.I_peak_MA - 65.0) ** 2
            + (r.B_z0_T - 30.0) ** 2
            + (r.E_laser_kJ - 8.0) ** 2
        )
    design = min(sweep_results, key=_key)

    return {
        "n_points": len(sweep_results),
        "best_mix_aware_point": {
            "I_peak_MA": best.I_peak_MA,
            "B_z0_T": best.B_z0_T,
            "E_laser_kJ": best.E_laser_kJ,
            "T_stag_keV": best.T_stag_keV,
            "Q_eng": best.Q_eng,
            "eta_mix": best.eta_mix,
            "E_fusion_2D_J": best.E_fusion_2D_J,
        },
        "design_point_65_30_8": {
            "I_peak_MA": design.I_peak_MA,
            "B_z0_T": design.B_z0_T,
            "E_laser_kJ": design.E_laser_kJ,
            "T_stag_keV": design.T_stag_keV,
            "Q_eng": design.Q_eng,
            "eta_mix": design.eta_mix,
            "E_fusion_2D_J": design.E_fusion_2D_J,
        },
        "scaling_laws": {
            "Q_eng_vs_I_peak_MA": scaling_I,
            "Q_eng_vs_B_z0_T": scaling_B,
            "Q_eng_vs_E_laser_kJ": scaling_E,
        },
        "max_Q_eng_in_sweep": max(r.Q_eng for r in sweep_results),
    }
