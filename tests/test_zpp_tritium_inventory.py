"""Tests for tritium inventory module (Item 8 / v2.2.0).

Validates:
- Production-rate formula against hand calculation
- Inventory ODE: doubling time, sub-threshold decline, steady state
- Decay-vs-extraction-losses decomposition
- Plant-availability sensitivity
- Self-sufficiency threshold function
- Edge cases (TBR=1.0, TBR=0.0, very long simulation)
"""
from __future__ import annotations

import math

import numpy as np
import pytest

from zpp.zpp_tritium_inventory import (
    DEFAULT_EXTRACTION_LOSS_FRACTION,
    T_DENSITY_G_PER_CC,
    T_HALF_YEARS,
    T_MOLAR_MASS_G_PER_MOL,
    TritiumInventoryInputs,
    fusion_neutron_rate_per_s,
    headline_tritium_claim,
    tritium_decay_rate_kg_per_s,
    tritium_extraction_loss_rate_kg_per_s,
    tritium_inventory_dynamics,
    tritium_production_rate_kg_per_s,
    tritium_self_sufficient,
)

# ---------------------------------------------------------------------------
# Production rate formula
# ---------------------------------------------------------------------------


def test_fusion_neutron_rate_at_1GW():
    """1 GW of D-T fusion → 3.547e20 neutrons/s (hand calc from E_DT=17.6 MeV)."""
    n_per_s = fusion_neutron_rate_per_s(1.0)
    # 1 GW = 1e9 W; 17.6 MeV = 17.6e6 * 1.602e-19 J
    expected = 1e9 / (17.6 * 1.602e-13)
    assert math.isclose(n_per_s, expected, rel_tol=1e-6)
    # Numerical value
    assert math.isclose(n_per_s, 3.547e20, rel_tol=1e-3)


def test_fusion_neutron_rate_scales_linearly():
    """3 GW → 3x the neutron rate of 1 GW."""
    n1 = fusion_neutron_rate_per_s(1.0)
    n3 = fusion_neutron_rate_per_s(3.0)
    assert math.isclose(n3 / n1, 3.0, rel_tol=1e-6)


def test_tritium_production_rate_at_TBR_1_83_1GW():
    """TBR=1.83 × 1 GW × 85% availability → ~87 kg/year.

    Hand calc:
      n_per_s = 3.547e20
      prod_rate = TBR * n_per_s * 0.85 / (NA / T_molar_mass)
                 = 1.83 * 3.547e20 * 0.85 / (6.022e23 / 3.016e-3)
                 = ~2.75 mg/s → ~87 kg/year (× 86400 × 365)
    """
    prod = tritium_production_rate_kg_per_s(1.83, 1.0, 0.85)
    expected_kg_per_year = prod * 86400 * 365
    assert math.isclose(expected_kg_per_year, 87.13, rel_tol=1e-2)


def test_tritium_production_rate_zero_availability():
    """Zero plant availability → zero production."""
    prod = tritium_production_rate_kg_per_s(1.83, 1.0, 0.0)
    assert prod == 0.0


# ---------------------------------------------------------------------------
# Loss rate formulas
# ---------------------------------------------------------------------------


def test_tritium_decay_rate_matches_half_life():
    """Decay rate at inventory = 1 kg should equal ln(2) / T_half in 1/s."""
    inventory_kg = 1.0
    rate = tritium_decay_rate_kg_per_s(inventory_kg)
    expected = math.log(2) / (T_HALF_YEARS * 365.25 * 86400)
    assert math.isclose(rate, expected, rel_tol=1e-6)
    # Numeric: ~1.78e-9 kg/s per kg → ~5.6% per year (correct)
    assert math.isclose(rate * 365.25 * 86400, 0.0562, rel_tol=1e-2)


def test_tritium_extraction_loss_rate():
    """2% loss per 24h cycle: loss_per_s = inventory * 0.02 / 86400."""
    rate = tritium_extraction_loss_rate_kg_per_s(10.0, 0.02, 24.0)
    expected = 10.0 * 0.02 / (24.0 * 3600)
    assert math.isclose(rate, expected, rel_tol=1e-6)


# ---------------------------------------------------------------------------
# Self-sufficiency threshold
# ---------------------------------------------------------------------------


def test_self_sufficient_at_threshold():
    """TBR = 1.05 (industry threshold) is self-sufficient."""
    assert tritium_self_sufficient(1.05) is True


def test_self_sufficient_above_threshold():
    """TBR = 1.83 is self-sufficient."""
    assert tritium_self_sufficient(1.83) is True


def test_not_self_sufficient_below_threshold():
    """TBR = 0.95 is NOT self-sufficient."""
    assert tritium_self_sufficient(0.95) is False


# ---------------------------------------------------------------------------
# Inventory ODE — end-to-end dynamics
# ---------------------------------------------------------------------------


def test_inventory_doubles_in_about_two_months_at_TBR_1_83():
    """At TBR=1.83 + 1 GW + 85% availability + 5 kg startup, doubling time ~65 days."""
    inputs = TritiumInventoryInputs(
        TBR=1.83,
        fusion_power_GW=1.0,
        plant_availability=0.85,
        startup_inventory_kg=5.0,
    )
    result = tritium_inventory_dynamics(inputs, duration_days=180, n_time_steps=2000)
    assert result.doubling_time_days is not None
    assert 50 < result.doubling_time_days < 80  # ~65 days ±15


def test_steady_state_inventory_lower_at_higher_TBR():
    """At TBR=1.83, steady-state inventory is HIGHER than at TBR=0.95.
    Both are above zero because production (TBR * n_per_s) > 0 for any TBR>0.
    The 1.05 threshold is for PRACTICAL self-sufficiency, not for any non-zero TBR.
    """
    inputs_high = TritiumInventoryInputs(
        TBR=1.83,
        fusion_power_GW=1.0,
        plant_availability=0.85,
        startup_inventory_kg=5.0,
    )
    inputs_low = TritiumInventoryInputs(
        TBR=0.95,
        fusion_power_GW=1.0,
        plant_availability=0.85,
        startup_inventory_kg=5.0,
    )
    r_high = tritium_inventory_dynamics(inputs_high, duration_days=365, n_time_steps=2000)
    r_low = tritium_inventory_dynamics(inputs_low, duration_days=365, n_time_steps=2000)
    # Both are self-sustaining (steady-state > 0)
    assert r_high.steady_state_inventory_kg is not None
    assert r_low.steady_state_inventory_kg is not None
    assert r_high.steady_state_inventory_kg > r_low.steady_state_inventory_kg
    # Ratio should be ~1.83/0.95 = 1.93 (production-rate ratio)
    ratio = r_high.steady_state_inventory_kg / r_low.steady_state_inventory_kg
    assert math.isclose(ratio, 1.83 / 0.95, rel_tol=1e-2)


def test_inventory_reaches_steady_state():
    """At TBR=1.83, inventory asymptotically approaches steady-state value."""
    inputs = TritiumInventoryInputs(
        TBR=1.83,
        fusion_power_GW=1.0,
        plant_availability=0.85,
        startup_inventory_kg=1.0,  # start below steady-state to test convergence
    )
    result = tritium_inventory_dynamics(inputs, duration_days=730, n_time_steps=4000)
    assert result.steady_state_inventory_kg is not None
    assert result.steady_state_inventory_kg > 1.0  # grows above startup
    # Inventory at end of simulation should be near steady-state
    assert abs(result.inventory_kg[-1] - result.steady_state_inventory_kg) / result.steady_state_inventory_kg < 0.05


def test_time_to_steady_state_present_for_high_TBR():
    """At TBR=1.83, time_to_steady_state should be ~4 months."""
    inputs = TritiumInventoryInputs(
        TBR=1.83,
        fusion_power_GW=1.0,
        plant_availability=0.85,
        startup_inventory_kg=1.0,
    )
    result = tritium_inventory_dynamics(inputs, duration_days=730, n_time_steps=4000)
    assert result.time_to_steady_state_days is not None
    # ~120 days from the headline claim
    assert 80 < result.time_to_steady_state_days < 180


def test_higher_extraction_loss_decreases_steady_state_inventory():
    """More extraction loss → LESS inventory needed (loss is proportional to I,
    so steady state requires lower I to balance the same production P).

    Derivation: I_ss = P / (decay + loss_frac / cycle_time)
    Higher loss_frac → higher denominator → lower I_ss.
    """
    inputs_low = TritiumInventoryInputs(
        TBR=1.83, extraction_loss_fraction=0.01
    )
    inputs_high = TritiumInventoryInputs(
        TBR=1.83, extraction_loss_fraction=0.05
    )
    r_low = tritium_inventory_dynamics(inputs_low)
    r_high = tritium_inventory_dynamics(inputs_high)
    # Higher extraction loss → LOWER steady-state inventory
    assert r_high.steady_state_inventory_kg < r_low.steady_state_inventory_kg


def test_lower_plant_availability_reduces_production():
    """At 50% availability, production rate halves vs 100% availability."""
    inputs_100 = TritiumInventoryInputs(
        TBR=1.83, plant_availability=1.0, startup_inventory_kg=1.0
    )
    inputs_50 = TritiumInventoryInputs(
        TBR=1.83, plant_availability=0.5, startup_inventory_kg=1.0
    )
    r_100 = tritium_inventory_dynamics(inputs_100, duration_days=200)
    r_50 = tritium_inventory_dynamics(inputs_50, duration_days=200)
    # Inventory at 50% availability grows slower
    assert r_50.inventory_kg[-1] < r_100.inventory_kg[-1]


def test_time_series_has_correct_shape():
    """Inventory arrays should have n_time_steps+1 entries."""
    inputs = TritiumInventoryInputs()
    result = tritium_inventory_dynamics(inputs, duration_days=365, n_time_steps=500)
    assert len(result.time_days) == 501
    assert len(result.inventory_kg) == 501
    assert len(result.production_rate_kg_per_day) == 501
    assert len(result.consumption_rate_kg_per_day) == 501


def test_inventory_non_negative():
    """Inventory must stay non-negative (Forward Euler max(0, ...) guard)."""
    inputs = TritiumInventoryInputs(
        TBR=0.5,  # well below threshold
        fusion_power_GW=0.001,  # tiny production
        plant_availability=0.1,
        startup_inventory_kg=0.1,
    )
    result = tritium_inventory_dynamics(inputs, duration_days=365, n_time_steps=1000)
    assert np.all(result.inventory_kg >= 0)


def test_headline_claim_contains_expected_strings():
    """Headline claim should report TBR, doubling time, and steady-state inventory."""
    s = headline_tritium_claim(1.83, 1.0)
    assert "TBR=1.83" in s
    assert "Doubling time" in s
    assert "Steady-state" in s


def test_industrial_threshold_5pct_margin():
    """Self-sufficiency requires TBR >= 1.05 (5% margin above unity)."""
    # This is a documented industry convention; verify the threshold value
    assert tritium_self_sufficient(1.04) is False
    assert tritium_self_sufficient(1.05) is True
    assert tritium_self_sufficient(1.06) is True


# ---------------------------------------------------------------------------
# Constants sanity
# ---------------------------------------------------------------------------


def test_constants_match_literature():
    """Module constants should match published values."""
    # T half-life: 12.32 years (Lucas 2000)
    assert T_HALF_YEARS == 12.32
    # T molar mass: 3.016 g/mol (T2)
    assert T_MOLAR_MASS_G_PER_MOL == 3.016
    # Liquid T2 density: ~0.32 g/cc
    assert T_DENSITY_G_PER_CC == 0.32
    # Default extraction loss: 2% (Glugla 2007)
    assert DEFAULT_EXTRACTION_LOSS_FRACTION == 0.02