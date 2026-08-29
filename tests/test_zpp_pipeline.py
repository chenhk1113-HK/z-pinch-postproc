"""
Smoke tests for zpp_pipeline.

Loads the synthetic-shot fixture and runs the full pipeline through
both default (Sandia Z present-day) and alternative (ZN design,
Pacific Fusion design) wall-plug chains. Verifies:
1. All key engineering metrics are finite
2. E_fusion is positive (synthetic profile has burn window)
3. Q_eng > 1.0 (synthetic is a *design* scenario, Q_eng~4 in v0.1;
   real Z-shot 2960 had Q_eng < 0.001)
4. The wall-plug chain summary is in the report
5. Different wall-plug chains give different G_required
6. eta_helper (= eta_E_plant) only affects G_required, not eta_wallplug
"""
import json
import sys
from pathlib import Path

import numpy as np
import pytest

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent / "code"))
sys.path.insert(0, str(_HERE))

from zpp_pipeline import run_pipeline
from zpp_wallplug import (
    WallPlugChain,
    wallplug_chain_z_present,
    wallplug_chain_zn_design,
    wallplug_chain_pf_design,
)
from zpp_io import read_profile


FIXTURE = _HERE.parent / "data" / "fixtures" / "z2960_synthetic.csv"


def _build_inputs():
    prof = read_profile(FIXTURE)
    E_stored_J = 11.5e6    # 11.5 MJ Marx bank
    E_kinetic_J = 0.45e6   # 0.45 MJ liner KE
    R_initial_cm = 0.50
    return prof, E_stored_J, E_kinetic_J, R_initial_cm


def test_pipeline_runs_default_chain():
    prof, E_stored, E_kin, R_init = _build_inputs()
    rep = run_pipeline(
        time_ns=prof["time_ns"],
        T_keV=prof["T_keV"],
        rho_gcc=prof["rho_gcc"],
        E_stored_J=E_stored,
        E_kinetic_J=E_kin,
        radius_cm=prof.get("radius_cm"),
        R_initial_cm=R_init,
        eta_helper=0.40,
        input_provenance={"shot_id": "z2960_synthetic", "simulator": "synthetic"},
    )
    r = rep["results"]
    # All metrics finite and non-trivial
    assert np.isfinite(r["E_fusion_J"]), "E_fusion_J must be finite"
    assert r["E_fusion_J"] > 0, "E_fusion_J must be positive"
    assert np.isfinite(r["Q_target"]), "Q_target must be finite"
    assert np.isfinite(r["Q_eng"]), "Q_eng must be finite"
    assert r["Q_eng"] > 1.0, (
        "synthetic profile is a near-ignition design scenario; current MagLIF "
        "shots have Q_eng < 0.001. The synthetic is intentionally optimistic "
        "to exercise the full metric pipeline."
    )
    # Wall-plug chain present in report
    assert "wallplug_chain" in rep, "wallplug_chain summary must be in report"
    assert "G_required" in r, "G_required must be in results"
    # G_required is in the realistic 50-1000 range for the Z present chain
    assert 50 < r["G_required"] < 1000, (
        f"G_required {r['G_required']:.1f} is outside the realistic range "
        f"50-1000 for present-day Z. Check the wall-plug chain."
    )
    # CR: R_initial=0.50, profile min(R)=0.16 -> CR ~ 3.1
    assert 3.0 < r["convergence_ratio"] < 3.2, (
        f"CR should be ~3.1, got {r['convergence_ratio']}"
    )
    # Default wallplug is Z present (4% wall-plug target)
    assert abs(rep["wallplug_chain"]["eta_liner_coupling"] - 0.10) < 1e-6, (
        "default wallplug should be Z present (eta_liner=0.10)"
    )


def test_results_contain_all_metrics():
    prof, E_stored, E_kin, R_init = _build_inputs()
    rep = run_pipeline(
        time_ns=prof["time_ns"],
        T_keV=prof["T_keV"],
        rho_gcc=prof["rho_gcc"],
        E_stored_J=E_stored,
        E_kinetic_J=E_kin,
        radius_cm=prof.get("radius_cm"),
        R_initial_cm=R_init,
        eta_helper=0.40,
    )
    required = {
        "E_fusion_MJ", "E_fusion_J",
        "Q_target", "Q_eng", "Q_eng_stored",
        "E_grid_MJ",
        "eta_wallplug", "eta_wallplug_to_liner",
        "G_required",
        "tau_burn_ns",
        "lawson_nTtau_keVs_per_m3", "lawson_nTtau_atoms_cm3_keV_s",
        "lawson_class",
        "P_stag_GPa",
        "convergence_ratio",
    }
    assert required.issubset(rep["results"].keys()), (
        f"missing keys: {required - set(rep['results'].keys())}"
    )


def test_wallplug_chain_comparison():
    """Different wall-plug chains should give different G_required.

    - Z present (~4% wall-plug, eta_liner=0.10): G_required ~ 200-400
    - ZN design (~13% wall-plug, eta_liner=0.20): G_required ~ 50-100
    - Pacific Fusion design (~18% wall-plug, eta_liner=0.25): G_required < 50
    """
    prof, E_stored, E_kin, R_init = _build_inputs()

    rep_z = run_pipeline(
        time_ns=prof["time_ns"], T_keV=prof["T_keV"], rho_gcc=prof["rho_gcc"],
        E_stored_J=E_stored, E_kinetic_J=E_kin,
        radius_cm=prof.get("radius_cm"), R_initial_cm=R_init,
        wallplug=wallplug_chain_z_present(),
    )
    rep_zn = run_pipeline(
        time_ns=prof["time_ns"], T_keV=prof["T_keV"], rho_gcc=prof["rho_gcc"],
        E_stored_J=E_stored, E_kinetic_J=E_kin,
        radius_cm=prof.get("radius_cm"), R_initial_cm=R_init,
        wallplug=wallplug_chain_zn_design(),
    )
    rep_pf = run_pipeline(
        time_ns=prof["time_ns"], T_keV=prof["T_keV"], rho_gcc=prof["rho_gcc"],
        E_stored_J=E_stored, E_kinetic_J=E_kin,
        radius_cm=prof.get("radius_cm"), R_initial_cm=R_init,
        wallplug=wallplug_chain_pf_design(),
    )

    # E_fusion, Q_target, Q_eng_stored should be IDENTICAL across chains
    # (the chain only affects the E_grid/G_required part of the gain chain)
    assert rep_z["results"]["E_fusion_MJ"] == rep_zn["results"]["E_fusion_MJ"]
    assert rep_z["results"]["Q_target"] == rep_zn["results"]["Q_target"]

    # eta_wallplug should differ (Z present is lowest, PF is highest)
    eta_z = rep_z["wallplug_chain"]["eta_wallplug"]
    eta_zn = rep_zn["wallplug_chain"]["eta_wallplug"]
    eta_pf = rep_pf["wallplug_chain"]["eta_wallplug"]
    assert eta_z < eta_zn < eta_pf, (
        f"wallplug efficiencies should increase Z < ZN < PF, got "
        f"Z={eta_z:.4f}, ZN={eta_zn:.4f}, PF={eta_pf:.4f}"
    )

    # G_required should DECREASE as wallplug efficiency increases
    G_z = rep_z["results"]["G_required"]
    G_zn = rep_zn["results"]["G_required"]
    G_pf = rep_pf["results"]["G_required"]
    assert G_z > G_zn > G_pf, (
        f"G_required should decrease Z > ZN > PF, got "
        f"Z={G_z:.1f}, ZN={G_zn:.1f}, PF={G_pf:.1f}"
    )
    # Sanity: Z present G_required should be 200-500 range
    assert 200 < G_z < 500, f"Z present G_required {G_z:.1f} is outside 200-500"
    # ZN should be 50-200 range
    assert 50 < G_zn < 200, f"ZN design G_required {G_zn:.1f} is outside 50-200"


def test_eta_helper_affects_G_required_only():
    """eta_helper (= eta_E_plant) should ONLY affect G_required, not
    eta_wallplug or Q_eng_stored. The wall-plug chain stages are
    independent of plant thermal-to-electric efficiency.
    """
    prof, E_stored, E_kin, R_init = _build_inputs()
    r1 = run_pipeline(
        time_ns=prof["time_ns"], T_keV=prof["T_keV"], rho_gcc=prof["rho_gcc"],
        E_stored_J=E_stored, E_kinetic_J=E_kin,
        radius_cm=prof.get("radius_cm"), R_initial_cm=R_init,
        eta_helper=0.30,
    )
    r2 = run_pipeline(
        time_ns=prof["time_ns"], T_keV=prof["T_keV"], rho_gcc=prof["rho_gcc"],
        E_stored_J=E_stored, E_kinetic_J=E_kin,
        radius_cm=prof.get("radius_cm"), R_initial_cm=R_init,
        eta_helper=0.50,
    )
    # eta_wallplug and Q_eng_stored should be IDENTICAL (plant efficiency
    # doesn't affect the wall-plug chain or the stored-energy gain)
    assert r1["wallplug_chain"]["eta_wallplug"] == r2["wallplug_chain"]["eta_wallplug"]
    assert r1["results"]["Q_eng_stored"] == r2["results"]["Q_eng_stored"]
    # G_required should DECREASE with higher eta_helper (better plant)
    G1 = r1["results"]["G_required"]
    G2 = r2["results"]["G_required"]
    assert G2 < G1, f"G_required should decrease with higher eta_helper, got G1={G1:.1f}, G2={G2:.1f}"


def test_bosch_hale_in_pipeline():
    """Verify the synthetic profile produces MJ-class yield with Bosch-Hale 1992.

    With peak T=2.9 keV, peak rho=1.85 g/cc, R_stag=0.16 cm, 1 cm liner height,
    E_fusion should be in the 1-1000 MJ class. This is a smoke check that
    the orders of magnitude are right, not a precise yield prediction.
    """
    prof, E_stored, E_kin, R_init = _build_inputs()
    rep = run_pipeline(
        time_ns=prof["time_ns"], T_keV=prof["T_keV"], rho_gcc=prof["rho_gcc"],
        E_stored_J=E_stored, E_kinetic_J=E_kin,
        radius_cm=prof.get("radius_cm"), R_initial_cm=R_init, eta_helper=0.40,
    )
    assert 1e6 < rep["results"]["E_fusion_J"] < 1e12, (
        f"Synthetic E_fusion {rep['results']['E_fusion_J']:.2e} J is outside "
        f"expected 1e6 - 1e12 J range."
    )


def test_backward_compat_no_chain():
    """A caller that doesn't pass `wallplug` (v0.0.1 API) should still
    get a valid result with default Z present chain."""
    prof, E_stored, E_kin, R_init = _build_inputs()
    rep = run_pipeline(
        time_ns=prof["time_ns"], T_keV=prof["T_keV"], rho_gcc=prof["rho_gcc"],
        E_stored_J=E_stored, E_kinetic_J=E_kin,
        radius_cm=prof.get("radius_cm"), R_initial_cm=R_init, eta_helper=0.40,
        # Note: no wallplug= argument
    )
    assert rep["results"]["Q_eng_stored"] > 0
    assert "wallplug_chain" in rep
