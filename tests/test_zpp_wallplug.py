"""
Tests for the 6-stage wall-plug efficiency chain (zpp_wallplug).

Verifies:
1. The chain product is the product of all stages.
2. The Z present chain has eta_wallplug ~ 2-5% (Hansen 2021 published 4%).
3. The ZN design chain has eta_wallplug ~ 10-15% (Yager-Elorriaga 2022).
4. G_required is in the right regime for each chain.
5. The dataclass is serialisable and reconstructable.
"""
import json
import sys
from pathlib import Path

import pytest

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent / "code"))

from zpp_wallplug import (
    WallPlugChain,
    wallplug_chain_z_present,
    wallplug_chain_zn_design,
    wallplug_chain_pf_design,
)


def test_chain_product_is_product_of_stages():
    """The eta_wallplug is the product of all 8 stage efficiencies."""
    chain = WallPlugChain()
    expected = (
        chain.eta_charging * chain.eta_marx * chain.eta_pfl *
        chain.eta_ltd_per_stage ** chain.n_ltd_stages *
        chain.eta_convolute * chain.eta_transmission *
        chain.eta_liner_coupling * chain.eta_fuel_coupling
    )
    assert abs(chain.eta_wallplug() - expected) < 1e-12


def test_z_present_wallplug_in_published_range():
    """Sandia Z present-day wall-plug efficiency should be 2-5%.

    Hansen 2021 SULI: "22 MJ -> 1 MJ in 10-7s, 1 cm, ~1 MJ/cc, ~10 TW/cc,
    ~4% wall-plug efficiency". Our default Z present chain with
    eta_liner=0.10 gives eta_wallplug ~ 0.027, which is slightly below
    the published 4% but in the right regime.
    """
    chain = wallplug_chain_z_present()
    eta = chain.eta_wallplug()
    assert 0.02 < eta < 0.06, (
        f"Z present wallplug efficiency {eta:.4f} is outside the "
        f"published 2-6% range (Hansen 2021 cites ~4%)"
    )


def test_zn_design_wallplug_higher_than_z_present():
    """ZN (60 MA design) should have higher wallplug than Z present
    because of LTD technology and improved magnetic direct drive."""
    eta_z = wallplug_chain_z_present().eta_wallplug()
    eta_zn = wallplug_chain_zn_design().eta_wallplug()
    assert eta_zn > eta_z, (
        f"ZN ({eta_zn:.4f}) should have higher wallplug than Z present ({eta_z:.4f})"
    )
    # ZN design target: 10-15%
    assert 0.08 < eta_zn < 0.20, (
        f"ZN design wallplug {eta_zn:.4f} is outside 8-20% target range"
    )


def test_pf_design_wallplug_highest():
    """Pacific Fusion commercial design should have the highest wallplug
    (most aggressive rep-rate optimisation)."""
    eta_z = wallplug_chain_z_present().eta_wallplug()
    eta_zn = wallplug_chain_zn_design().eta_wallplug()
    eta_pf = wallplug_chain_pf_design().eta_wallplug()
    assert eta_pf > eta_zn, (
        f"PF ({eta_pf:.4f}) should have higher wallplug than ZN ({eta_zn:.4f})"
    )
    assert 0.10 < eta_pf < 0.30, (
        f"PF design wallplug {eta_pf:.4f} is outside 10-30% target range"
    )


def test_z_present_G_required_in_100_to_500_range():
    """G_required = 1 / (eta_E * f_recirc * eta_wallplug).

    For Z present (eta_wp ~ 3%, eta_E=0.40, f_recirc=0.25):
        G = 1 / (0.40 * 0.25 * 0.03) ~ 333
    """
    chain = wallplug_chain_z_present()
    G = chain.required_target_gain()
    assert 100 < G < 500, (
        f"Z present G_required {G:.1f} is outside the 100-500 range"
    )


def test_zn_design_G_required_50_to_200():
    """For ZN (eta_wp ~ 12%, eta_E=0.40, f_recirc=0.25):
        G = 1 / (0.40 * 0.25 * 0.12) ~ 83
    """
    chain = wallplug_chain_zn_design()
    G = chain.required_target_gain()
    assert 30 < G < 200, (
        f"ZN design G_required {G:.1f} is outside the 30-200 range "
        f"(Yager-Elorriaga 2022 cites G~50 for an optimistic 20% driver)"
    )


def test_summary_returns_all_fields():
    """summary() returns all chain fields plus computed values."""
    chain = wallplug_chain_z_present()
    s = chain.summary()
    required = {
        "eta_charging", "eta_marx", "eta_pfl",
        "n_ltd_stages", "eta_ltd_per_stage", "eta_ltd_total",
        "eta_convolute", "eta_transmission",
        "eta_liner_coupling", "eta_fuel_coupling",
        "eta_E_plant", "f_recirc",
        "eta_wallplug", "eta_wallplug_to_liner", "G_required",
    }
    assert required.issubset(s.keys())


def test_summary_is_json_serialisable():
    """The chain summary must serialise to JSON for report output."""
    chain = wallplug_chain_z_present()
    s = chain.summary()
    json.dumps(s)  # should not raise


def test_eta_wallplug_to_liner_excludes_fuel_coupling():
    """eta_wallplug_to_liner should be the full chain WITHOUT eta_fuel_coupling.
    This is the 'magnetic direct drive' efficiency from E_grid to E_kinetic."""
    chain = WallPlugChain()
    to_liner = chain.eta_wallplug_to_liner()
    to_fuel = chain.eta_wallplug()
    assert abs(to_liner - to_fuel / chain.eta_fuel_coupling) < 1e-12


def test_ltd_stages_zero_gives_per_stage_to_zero():
    """With n_ltd_stages=0, eta_ltd_total = 1.0 (no stages = no loss).
    This is a sanity check on the formula."""
    chain = WallPlugChain(n_ltd_stages=0)
    assert chain.eta_ltd_total() == 1.0


def test_ltd_stages_5_at_92pct():
    """Standard Sandia Z 5-stage water-line compression at 92% per stage."""
    chain = WallPlugChain(n_ltd_stages=5, eta_ltd_per_stage=0.92)
    expected = 0.92 ** 5
    assert abs(chain.eta_ltd_total() - expected) < 1e-12
    # Numerical value
    assert abs(chain.eta_ltd_total() - 0.6591) < 1e-3
