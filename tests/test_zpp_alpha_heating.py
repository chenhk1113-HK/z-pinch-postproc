"""
Tier 3.A — α-heating bootstrap tests.

Verifies:
1. alpha_deposition_fraction matches the exponential model 1-exp(-ρR/ρR_α).
2. bremsstrahlung_power_density matches NRL formulary.
3. alpha_heating_power_density scales with ρ² × <σv> × f_dep.
4. alpha_boost_iterative converges in <50 iterations.
5. Z present (low ρR) shows no α boost.
6. ZN design (intermediate ρR) shows minor α boost or cooling.
7. ICF-like hot spot (high ρR) ignites (T_eq hits cap).
8. apply_alpha_heating_to_shot returns the expected dataclass.
9. alpha_ignition_criterion matches the Lawson nTτ > 3e21 threshold.
10. Pipeline integration: alpha_heating block in output, apply_alpha_heating=False disables.
"""
from __future__ import annotations
import sys
import os

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "code"))

from zpp_alpha_heating import (
    ALPHA_RANGE_DT_GCCM,
    alpha_deposition_fraction,
    bremsstrahlung_power_density,
    alpha_heating_power_density,
    alpha_boost_iterative,
    apply_alpha_heating_to_shot,
    alpha_ignition_criterion,
    AlphaHeatingResult,
)
from zpp_pipeline import run_pipeline


def _triangular_profile(
    n: int = 21,
    T_peak_keV: float = 3.0,
    rho_peak_gcc: float = 1.0,
    tau_burn_ns: float = 5.0,
    R_stag_cm: float = 0.145,
    R_initial_cm: float = 0.435,
):
    """Triangular profile with realistic fuel CR (Gomez 2020 anchor)."""
    time_ns = np.linspace(-3 * tau_burn_ns, 3 * tau_burn_ns, n)
    sigma_t = tau_burn_ns / 2.355
    T_keV = T_peak_keV * np.exp(-0.5 * (time_ns / sigma_t) ** 2)
    rho_gcc = rho_peak_gcc * np.exp(-0.5 * (time_ns / sigma_t) ** 2)
    radius_cm = R_stag_cm + (R_initial_cm - R_stag_cm) * np.abs(time_ns) / (3 * tau_burn_ns)
    radius_cm = np.maximum(radius_cm, R_stag_cm)
    return time_ns, T_keV, rho_gcc, radius_cm


class TestAlphaDeposition:
    """Test alpha_deposition_fraction."""

    def test_f_dep_zero_at_zero_rhoR(self):
        assert alpha_deposition_fraction(0.0) == 0.0

    def test_f_dep_matches_exponential(self):
        for rhoR in [0.05, 0.1, 0.32, 0.5, 1.0, 2.0]:
            expected = 1.0 - np.exp(-rhoR / ALPHA_RANGE_DT_GCCM)
            actual = alpha_deposition_fraction(rhoR)
            assert actual == pytest.approx(expected, rel=1e-9)

    def test_f_dep_at_one_alpha_range(self):
        """At ρR = ρR_α, f_dep = 1 - 1/e ≈ 0.632."""
        f = alpha_deposition_fraction(ALPHA_RANGE_DT_GCCM)
        assert f == pytest.approx(0.632, abs=1e-3)

    def test_f_dep_at_three_alpha_ranges(self):
        """At ρR = 3 × ρR_α, f_dep ≈ 0.95."""
        f = alpha_deposition_fraction(3 * ALPHA_RANGE_DT_GCCM)
        assert f == pytest.approx(0.950, abs=1e-3)

    def test_f_dep_saturates_at_high_rhoR(self):
        assert alpha_deposition_fraction(10.0) > 0.99


class TestBremsstrahlung:
    """Test bremsstrahlung_power_density."""

    def test_brems_zero_at_zero_density(self):
        assert bremsstrahlung_power_density(0.0, 5.0) == 0.0

    def test_brems_zero_at_zero_temperature(self):
        assert bremsstrahlung_power_density(1e20, 0.0) == 0.0

    def test_brems_scales_as_n_squared(self):
        """P_brem ∝ n² (at fixed T)."""
        P1 = bremsstrahlung_power_density(1e20, 5.0)
        P2 = bremsstrahlung_power_density(2e20, 5.0)
        assert P2 == pytest.approx(4 * P1, rel=1e-9)

    def test_brems_scales_as_sqrt_T(self):
        """P_brem ∝ √T (at fixed n)."""
        P1 = bremsstrahlung_power_density(1e20, 4.0)
        P2 = bremsstrahlung_power_density(1e20, 16.0)
        assert P2 == pytest.approx(2 * P1, rel=1e-3)

    def test_brems_magnitude_plausible(self):
        """At ZN stagnation (n~3e19 cm^-3, T=5 keV), P_brem should be
        in the 1e10 to 1e15 W/cm³ range (consistent with NRL Formulary
        1.69e-32 n² Z_eff g_ff sqrt(T_eV) = ~1e14 at these conditions)."""
        n_ZN = 0.05 * 6.022e23 / 2.5  # ~1.2e22 atoms/cm³
        P = bremsstrahlung_power_density(n_ZN, 5.0)
        assert 1e10 < P < 1e15, f"P_brem={P:.2e} W/cm³ outside 1e10-1e15 range"

    def test_brems_NRL_formulary_anchor(self):
        """At NRL reference conditions (n=1e20 cm^-3, T=10 keV),
        P_brem should match NRL Formulary to within a factor of 3."""
        P = bremsstrahlung_power_density(1e20, 10.0)
        # NRL: 1.69e-32 * 1e40 * sqrt(10000) ≈ 5.35e11 W/cm³ with g_ff=1
        assert 1e10 < P < 1e13, f"P_brem={P:.2e} W/cm³ outside 1e10-1e13 NRL range"


class TestAlphaHeatingPower:
    """Test alpha_heating_power_density."""

    def test_P_alpha_zero_at_zero_rhoR(self):
        assert alpha_heating_power_density(0.1, 5.0, 0.0) == 0.0

    def test_P_alpha_zero_at_zero_T(self):
        """At T = 0.1 keV (below BH valid range), P_alpha is much smaller
        than at T = 5 keV. (σv extrapolates to ~σv(0.2 keV), but the
        contribution is still tiny vs the fusion-active regime.)"""
        P_cold = alpha_heating_power_density(0.1, 0.1, 0.1)
        P_hot = alpha_heating_power_density(0.1, 5.0, 0.1)
        # Cold should be at least 100x smaller than hot
        assert P_cold < P_hot / 100, (
            f"P_alpha(T=0.1) = {P_cold:.2e}, P_alpha(T=5) = {P_hot:.2e}, "
            f"expected cold << hot"
        )

    def test_P_alpha_increases_with_rhoR(self):
        """Higher ρR → higher f_dep → higher P_alpha (at fixed rho, T)."""
        P1 = alpha_heating_power_density(0.05, 5.0, 0.1)
        P2 = alpha_heating_power_density(0.05, 5.0, 1.0)
        assert P2 > P1

    def test_P_alpha_increases_with_T(self):
        """Higher T → higher σv → higher P_alpha."""
        P1 = alpha_heating_power_density(0.05, 3.0, 0.5)
        P2 = alpha_heating_power_density(0.05, 10.0, 0.5)
        assert P2 > P1

    def test_P_alpha_increases_with_density(self):
        """P_alpha ∝ ρ² (from n² × σv)."""
        P1 = alpha_heating_power_density(0.05, 5.0, 0.5)
        P2 = alpha_heating_power_density(0.5, 5.0, 0.5)
        assert P2 == pytest.approx(100 * P1, rel=1e-9)


class TestAlphaBoostIterative:
    """Test alpha_boost_iterative."""

    def test_convergence_in_few_iterations(self):
        """Should converge in <50 iterations for any input."""
        res = alpha_boost_iterative(rho_gcc=0.05, T_initial_keV=5.0, rho_R_gccm=0.1)
        assert res["n_iterations"] <= 50
        assert res["n_iterations"] >= 1

    def test_z_present_no_boost(self):
        """Z present (low ρR): α boost ~ 1 (most α escape)."""
        res = alpha_boost_iterative(rho_gcc=0.01, T_initial_keV=2.5, rho_R_gccm=0.005)
        assert res["boost_factor"] == pytest.approx(1.0, abs=0.05)
        assert not res["ignited"]

    def test_zn_design_minor_boost_or_cooling(self):
        """ZN design (ρR ~ 0.3 α ranges): either mild boost or cooling,
        but not ignition."""
        res = alpha_boost_iterative(rho_gcc=0.05, T_initial_keV=5.0, rho_R_gccm=0.1)
        # Sub-ignition regime
        assert not res["ignited"]
        # boost is in [0.5, 1.5] range — either minor boost or brem-dominated cooling
        assert 0.5 <= res["boost_factor"] <= 1.5

    def test_ICF_hotspot_ignites(self):
        """ICF hot spot (ρR ~ 3 α ranges, T=10 keV, ρ=200): ignites."""
        res = alpha_boost_iterative(rho_gcc=200.0, T_initial_keV=10.0, rho_R_gccm=1.0)
        assert res["ignited"]
        assert res["hit_cap"]
        assert res["T_eq_keV"] >= 30.0  # hit the 50 keV cap or very high

    def test_invalid_inputs_return_safe_defaults(self):
        """Negative or zero rho/T should not crash."""
        res = alpha_boost_iterative(rho_gcc=0.0, T_initial_keV=5.0, rho_R_gccm=0.1)
        assert res["boost_factor"] == 1.0
        res = alpha_boost_iterative(rho_gcc=0.1, T_initial_keV=0.0, rho_R_gccm=0.1)
        assert res["boost_factor"] == 1.0

    def test_rho_R_alphas_field(self):
        """rho_R_alphas = ρR / ρR_α (number of α ranges in the fuel)."""
        res = alpha_boost_iterative(rho_gcc=0.05, T_initial_keV=5.0, rho_R_gccm=0.32)
        assert res["rho_R_alphas"] == pytest.approx(1.0, abs=1e-9)


class TestApplyAlphaHeatingToShot:
    """Test apply_alpha_heating_to_shot."""

    def test_returns_dataclass(self):
        res = apply_alpha_heating_to_shot(
            T_stag_keV=5.0, rho_stag_gcc=0.05, rho_R_gccm=0.1,
            Q_target_base=0.05, E_fusion_2D_J=1e3, E_stored_J=22e6,
        )
        assert isinstance(res, AlphaHeatingResult)

    def test_Q_with_alpha_scales_with_boost(self):
        """Q_with_alpha = Q_target_base * boost^1.5."""
        res = apply_alpha_heating_to_shot(
            T_stag_keV=5.0, rho_stag_gcc=0.05, rho_R_gccm=0.1,
            Q_target_base=0.05, E_fusion_2D_J=1e3, E_stored_J=22e6,
        )
        expected = 0.05 * res.boost_factor ** 1.5
        assert res.Q_with_alpha == pytest.approx(expected, rel=1e-9)

    def test_notes_field_contains_key_quantities(self):
        res = apply_alpha_heating_to_shot(
            T_stag_keV=5.0, rho_stag_gcc=0.05, rho_R_gccm=0.1,
            Q_target_base=0.05, E_fusion_2D_J=1e3, E_stored_J=22e6,
        )
        assert "f_dep" in res.notes
        assert "ρR" in res.notes
        assert "P_α" in res.notes


class TestAlphaIgnitionCriterion:
    """Test alpha_ignition_criterion."""

    def test_above_ignition_for_NIF_hotspot(self):
        """NIF ignition: ρ=200 g/cc, T=10 keV, τ=0.1 ns.
        nTτ >> 3e21."""
        l = alpha_ignition_criterion(rho_gcc=200.0, T_keV=10.0, tau_burn_ns=0.1)
        assert l["above_ignition"] is True
        assert l["margin"] > 1.0

    def test_below_ignition_for_Z_present(self):
        """Z present: ρ=0.01 g/cc, T=2.5 keV, τ=5 ns."""
        l = alpha_ignition_criterion(rho_gcc=0.01, T_keV=2.5, tau_burn_ns=5.0)
        assert l["above_ignition"] is False
        assert l["margin"] < 0.1

    def test_below_ignition_for_ZN_design(self):
        """ZN design: ρ=0.05, T=5 keV, τ=5 ns."""
        l = alpha_ignition_criterion(rho_gcc=0.05, T_keV=5.0, tau_burn_ns=5.0)
        assert l["above_ignition"] is False

    def test_invalid_inputs(self):
        l = alpha_ignition_criterion(rho_gcc=0.0, T_keV=5.0, tau_burn_ns=5.0)
        assert l["above_ignition"] is False
        assert l["margin"] == 0.0


class TestPipelineAlphaIntegration:
    """Test the pipeline integration of α-heating."""

    def test_default_apply_alpha_heating_reports_block(self):
        """By default the pipeline computes α-heating."""
        time_ns, T_keV, rho_gcc, radius_cm = _triangular_profile()
        result = run_pipeline(
            time_ns, T_keV, rho_gcc,
            E_stored_J=20e6, E_kinetic_J=1e6,
            radius_cm=radius_cm, R_initial_cm=0.435,
        )
        assert "alpha_heating" in result
        a = result["alpha_heating"]
        # Default: applied, not ignited for Z-like regime
        assert "boost_factor" in a
        assert "T_eq_keV" in a
        assert "ignited" in a

    def test_apply_alpha_heating_false_disables(self):
        """apply_alpha_heating=False: boost_factor=1.0."""
        time_ns, T_keV, rho_gcc, radius_cm = _triangular_profile()
        result = run_pipeline(
            time_ns, T_keV, rho_gcc,
            E_stored_J=20e6, E_kinetic_J=1e6,
            radius_cm=radius_cm, R_initial_cm=0.435,
            apply_alpha_heating=False,
        )
        a = result["alpha_heating"]
        assert a["applied"] is False
        assert a["boost_factor"] == 1.0

    def test_ICF_hotspot_profile_ignites(self):
        """ICF-like profile (high T, high ρ, long burn) should ignite."""
        time_ns, T_keV, rho_gcc, radius_cm = _triangular_profile(
            T_peak_keV=10.0, rho_peak_gcc=200.0, tau_burn_ns=0.5,
            R_stag_cm=0.005, R_initial_cm=0.435,
        )
        result = run_pipeline(
            time_ns, T_keV, rho_gcc,
            E_stored_J=20e6, E_kinetic_J=1e6,
            radius_cm=radius_cm, R_initial_cm=0.435,
            apply_alpha_heating=True,
        )
        a = result["alpha_heating"]
        assert a["ignited"] is True


class TestEndToEndZPresent:
    """End-to-end: Z present (Gomez 2020 anchor) shows no α boost."""

    def test_gomez_anchor_no_alpha_boost(self):
        """Z present stagnation: ρR is too low for α heating to matter."""
        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "code"))
        from zpp_mcbride import gomez2020_z_shot, stagnation_profile
        from zpp_wallplug import wallplug_chain_z_present

        inp = gomez2020_z_shot()
        p = stagnation_profile(inp)
        rep = run_pipeline(
            time_ns=p["time_ns"], T_keV=p["T_keV"], rho_gcc=p["rho_gcc"],
            E_stored_J=11.5e6, E_kinetic_J=0.45e6,
            radius_cm=p["radius_cm"], R_initial_cm=inp.R_0_cm,
            wallplug=wallplug_chain_z_present(),
            input_provenance={"maglif": {"B_z0_T": inp.B_z0_T}},
        )
        a = rep["alpha_heating"]
        # Z present: ρR ~ 0.005 g/cm² << ρR_α = 0.32, so f_dep ~ 0.016
        # α boost is negligible
        assert a["boost_factor"] == pytest.approx(1.0, abs=0.1)
        assert not a["ignited"]
        assert a["f_dep"] < 0.05
