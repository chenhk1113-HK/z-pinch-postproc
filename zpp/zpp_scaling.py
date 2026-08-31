"""
ZN (Z Next, 60-65 MA class) parameter sweep module.

This module runs the post-processor over a 3D parameter space of
Z-pinch driver inputs and reports the scaling laws. The motivation
is the strategic question: *what operating point does ZN need to
hit to reach break-even?* — and the derivative question: *how does
Q_eng scale with each driver parameter?*

Sweep axes (default ranges):
- I_peak:    20-65 MA (Z present to ZN design)
- B_z0:      10-30 T (Z-Beamlet standard to ZN design)
- E_laser:   0-8 kJ (bare Z-pinch to ZN design laser)

Outputs:
- A 3D table of (I_peak, B_z0, E_laser) -> (E_fus_2D, Q_eng, T_stag, ...)
- A scaling-law summary: Q_eng vs each parameter at fixed others
- The break-even contour: (I_peak, B_z0, E_laser) triples where
  Q_eng * eta_wallplug * eta_E_plant = 1.

This is a "scoping" tool — it tells you where the design envelope
needs to be to reach the break-even target, not the exact physics
of any specific shot.

References:
- Yager-Elorriaga et al. (2022) Nucl. Fusion 62 042015 — ZN design
- McBride & Slutz (2015) Phys. Plasmas 22 052708 — MagLIF scaling
- Gomez et al. (2020) PRL 125 155002 — Z 2960 anchor
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Iterable
import numpy as np

from zpp.zpp_mcbride import MagLIFInputs, stagnation_profile
from zpp.zpp_pipeline import run_pipeline
from zpp.zpp_wallplug import wallplug_chain_zn_design, WallPlugChain
from zpp.zpp_economics import break_even_Q_eng


@dataclass
class SweepResult:
    """A single sweep point: inputs + derived engineering metrics."""
    I_peak_MA: float
    B_z0_T: float
    E_laser_kJ: float
    T_stag_keV: float
    CR_fuel: float
    tau_burn_ns: float
    rho_stag_gcc: float
    E_fusion_1D_J: float
    E_fusion_2D_J: float
    eta_mix: float
    Q_eng_stored: float
    Q_eng: float
    eta_wallplug: float
    above_break_even: bool


def _make_inputs(I_peak_MA: float, B_z0_T: float, E_laser_kJ: float) -> MagLIFInputs:
    """Construct a MagLIFInputs with ZN-ish defaults.

    Other parameters (rho_0, R_0, T_preheat, liner height) are scaled
    from the Yager-Elorriaga 2022 ZN design at I_peak=60 MA, B=30 T.
    """
    # Scaling: at higher I_peak, use slightly larger R_0 (more liner mass).
    # At higher B_z0, increase T_preheat (adiabatic heating during implosion).
    R_0_cm = 0.3 + 0.005 * (I_peak_MA - 20.0)  # 0.3 at 20 MA -> 0.45 at 70 MA
    R_0_cm = max(0.3, min(0.6, R_0_cm))
    rho_0_mgcc = 1.0 + 0.01 * (I_peak_MA - 20.0)  # 1.0 -> 1.5 mg/cc
    rho_0_mgcc = max(0.5, min(2.0, rho_0_mgcc))
    T_preheat_eV = 200.0  # baseline (laser boosts this in McBride)
    liner_height_cm = 1.0
    return MagLIFInputs(
        I_peak_MA=I_peak_MA,
        E_laser_kJ=E_laser_kJ,
        T_preheat_eV=T_preheat_eV,
        rho_0_mgcc=rho_0_mgcc,
        R_0_cm=R_0_cm,
        B_z0_T=B_z0_T,
        liner_height_cm=liner_height_cm,
        fuel="DT",
    )


def sweep_one_point(
    I_peak_MA: float,
    B_z0_T: float,
    E_laser_kJ: float,
    E_stored_J: float | None = None,  # auto-scale if None
    E_kinetic_J: float | None = None,
    wallplug: WallPlugChain | None = None,
    apply_2d_mix: bool = True,
) -> SweepResult:
    """Run the pipeline on a single (I_peak, B_z0, E_laser) point.

    E_stored_J defaults to scaling with I_peak^2 from the Z baseline:
        E_stored(I) = 22 MJ * (I / 20 MA)^2
    so 60 MA ZN -> ~200 MJ (matching Yager-Elorriaga 2022 estimates).
    Pass an explicit E_stored_J for a fixed-energy comparison.

    E_kinetic_J defaults to 5% of E_stored (typical magnetic-direct-
    drive efficiency for Z present, slightly higher for ZN).
    """
    if E_stored_J is None:
        E_stored_J = 22e6 * (I_peak_MA / 20.0) ** 2
    if E_kinetic_J is None:
        E_kinetic_J = E_stored_J * 0.05

    if wallplug is None:
        wallplug = wallplug_chain_zn_design()  # ZN-design wall-plug by default

    inputs = _make_inputs(I_peak_MA, B_z0_T, E_laser_kJ)
    p = stagnation_profile(inputs)
    rep = run_pipeline(
        time_ns=p["time_ns"],
        T_keV=p["T_keV"],
        rho_gcc=p["rho_gcc"],
        E_stored_J=E_stored_J,
        E_kinetic_J=E_kinetic_J,
        radius_cm=p["radius_cm"],
        R_initial_cm=inputs.R_0_cm,
        wallplug=wallplug,
        eta_helper=0.40,
        apply_2d_mix=apply_2d_mix,
        input_provenance={
            "I_peak_MA": I_peak_MA,
            "B_z0_T": B_z0_T,
            "E_laser_kJ": E_laser_kJ,
            "maglif": {"B_z0_T": B_z0_T},
        },
    )
    mix = rep["mix_correction_2d"]
    res = rep["results"]

    Q_eng = res["Q_eng"]
    eta_wp = res["eta_wallplug"]
    # Above break-even if Q_eng * eta_wp * eta_E > 1
    # (eta_E = 0.40 for Brayton; passed to gain_chain as eta_helper)
    above_be = (Q_eng * eta_wp * 0.40) >= 1.0

    return SweepResult(
        I_peak_MA=I_peak_MA,
        B_z0_T=B_z0_T,
        E_laser_kJ=E_laser_kJ,
        T_stag_keV=p["T_stag_keV"],
        CR_fuel=p["CR"],
        tau_burn_ns=p["tau_burn_ns"],
        rho_stag_gcc=p["rho_stag_gcc"],
        E_fusion_1D_J=mix["E_fusion_1D_J"],
        E_fusion_2D_J=mix["E_fusion_2D_J"],
        eta_mix=mix["eta_mix"],
        Q_eng_stored=res["Q_eng_stored"],
        Q_eng=Q_eng,
        eta_wallplug=eta_wp,
        above_break_even=bool(above_be),
    )


def zn_scaling_sweep(
    I_peak_list_MA: Iterable[float] | None = None,
    B_z0_list_T: Iterable[float] | None = None,
    E_laser_list_kJ: Iterable[float] | None = None,
    E_stored_J: float | None = None,
    wallplug: WallPlugChain | None = None,
    apply_2d_mix: bool = True,
) -> list[SweepResult]:
    """Full 3D parameter sweep over (I_peak, B_z0, E_laser).

    Default ranges:
    - I_peak: [20, 30, 40, 50, 60, 65] MA (Z present to ZN design)
    - B_z0: [10, 16, 20, 30] T
    - E_laser: [0, 1.2, 4, 8] kJ

    Total points: 6 * 4 * 4 = 96. With the full pipeline each takes
    ~5ms, so the sweep runs in <1 second.

    E_stored_J defaults to None (auto-scales with I_peak^2 from 22 MJ
    at 20 MA, so ZN at 60 MA gets 22 * 9 = 198 MJ). Pass a constant
    value to compare at fixed stored energy.

    Returns a list of SweepResult sorted by (I_peak, B_z0, E_laser).
    """
    if I_peak_list_MA is None:
        I_peak_list_MA = [20.0, 30.0, 40.0, 50.0, 60.0, 65.0]
    if B_z0_list_T is None:
        B_z0_list_T = [10.0, 16.0, 20.0, 30.0]
    if E_laser_list_kJ is None:
        E_laser_list_kJ = [0.0, 1.2, 4.0, 8.0]

    if wallplug is None:
        wallplug = wallplug_chain_zn_design()

    results = []
    for I in I_peak_list_MA:
        for B in B_z0_list_T:
            for E in E_laser_list_kJ:
                results.append(sweep_one_point(
                    I_peak_MA=I, B_z0_T=B, E_laser_kJ=E,
                    E_stored_J=E_stored_J,  # may be None (auto-scale)
                    E_kinetic_J=None,  # auto-scale inside sweep_one_point
                    wallplug=wallplug, apply_2d_mix=apply_2d_mix,
                ))
    return results


def break_even_contour(
    sweep_results: list[SweepResult],
    eta_E_plant: float = 0.40,
) -> list[SweepResult]:
    """Filter a sweep to the points where Q_eng * eta_wp * eta_E >= 1.

    The returned points are the design envelope where the plant
    reaches break-even. These are the points ZN must hit to be
    commercially viable (modulo LCOE considerations in zpp_economics).
    """
    return [r for r in sweep_results
            if (r.Q_eng * r.eta_wallplug * eta_E_plant) >= 1.0]


def scaling_summary(
    sweep_results: list[SweepResult],
) -> dict:
    """Compute the scaling-law summary at the ZN design point.

    Returns:
        dict with:
        - min_Q_eng_at_ZN_design: Q_eng at (I=60, B=30, E=8) (ZN design)
        - max_Q_eng_in_sweep: max Q_eng across the sweep
        - num_above_break_even: count of points above break-even
        - fraction_above_break_even: same as fraction
        - z_present_anchor: result closest to Gomez 2020 (I=20, B=16, E=1.2)
    """
    def _key(r: SweepResult) -> float:
        # Distance from ZN design point (60 MA, 30 T, 8 kJ)
        d_I = (r.I_peak_MA - 60.0) ** 2
        d_B = (r.B_z0_T - 30.0) ** 2
        d_E = (r.E_laser_kJ - 8.0) ** 2
        return d_I + d_B + d_E

    def _key_z(r: SweepResult) -> float:
        # Distance from Z present anchor (20 MA, 16 T, 1.2 kJ)
        d_I = (r.I_peak_MA - 20.0) ** 2
        d_B = (r.B_z0_T - 16.0) ** 2
        d_E = (r.E_laser_kJ - 1.2) ** 2
        return d_I + d_B + d_E

    if not sweep_results:
        return {}

    zn_design = min(sweep_results, key=_key)
    z_anchor = min(sweep_results, key=_key_z)
    max_Q = max(r.Q_eng for r in sweep_results)
    above_be = [r for r in sweep_results if r.above_break_even]

    return {
        "n_points": len(sweep_results),
        "zn_design_point": {
            "I_peak_MA": zn_design.I_peak_MA,
            "B_z0_T": zn_design.B_z0_T,
            "E_laser_kJ": zn_design.E_laser_kJ,
            "T_stag_keV": zn_design.T_stag_keV,
            "Q_eng": zn_design.Q_eng,
            "E_fusion_2D_J": zn_design.E_fusion_2D_J,
            "above_break_even": zn_design.above_break_even,
        },
        "z_present_anchor": {
            "I_peak_MA": z_anchor.I_peak_MA,
            "B_z0_T": z_anchor.B_z0_T,
            "E_laser_kJ": z_anchor.E_laser_kJ,
            "T_stag_keV": z_anchor.T_stag_keV,
            "Q_eng": z_anchor.Q_eng,
            "E_fusion_2D_J": z_anchor.E_fusion_2D_J,
            "above_break_even": z_anchor.above_break_even,
        },
        "max_Q_eng_in_sweep": max_Q,
        "num_above_break_even": len(above_be),
        "fraction_above_break_even": len(above_be) / len(sweep_results),
    }
