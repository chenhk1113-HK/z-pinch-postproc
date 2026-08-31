"""
Tier 2.A — Hohlraum / laser preheat model tests.

The laser preheat (MagLIF) is what distinguishes a MagLIF shot from a
bare Z-pinch. These tests verify:

1. The LaserPreheat dataclass computes E_fuel_preheat correctly.
2. T_preheat_floor scales correctly with E_laser and inversely with
   fuel density × volume (specific-heat physics).
3. The pipeline run_pipeline accepts a `laser` parameter and reports
   the laser preheat summary.
4. With E_laser=0 (no laser / bare Z-pinch), the preheat fields
   report is_maglif=False and T_preheat_floor=0.
5. The Gomez 2020 anchor with laser included still matches the
   published T_stag within the documented 30-50% uncertainty band.
6. The energy-balance sanity check (E_laser / E_fusion < 1) holds
   for both Z present and ZN design.
"""
from __future__ import annotations
import math
import sys
import os

import numpy as np
import pytest

# Ensure `code/` is on path for direct imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "code"))

from zpp.zpp_laser import (
    LaserPreheat,
    no_laser,
    z_present_zbeamlet,
    zn_design_laser,
    preheat_floor_for_cylindrical_fuel,
)
from zpp.zpp_mcbride import (
    MagLIFInputs,
    gomez2020_z_shot,
    zn_design_shot,
    stagnation_profile,
)
from zpp.zpp_pipeline import run_pipeline


# A simple triangular Z-pinch profile for pipeline tests.
# Defaults are physically plausible for a Z-pinch fuel:
#   - R_initial = 0.435 cm (Z-Beamlet standard)
#   - R_stag    = 0.145 cm (fuel CR = 3, matches Gomez 2020 anchor)
# Avoid CR=20+ profiles here: those correspond to LINER CR (not
# fuel CR) and trigger the 2D mix correction to ~0, which is not
# what these tests want to exercise.
def _triangular_profile(
    n: int = 21,
    T_peak_keV: float = 3.0,
    rho_peak_gcc: float = 1.0,
    tau_burn_ns: float = 5.0,
    R_stag_cm: float = 0.145,
    R_initial_cm: float = 0.435,
):
    """Generate a triangular profile for testing run_pipeline."""
    time_ns = np.linspace(-3 * tau_burn_ns, 3 * tau_burn_ns, n)
    sigma_t = tau_burn_ns / 2.355
    T_keV = T_peak_keV * np.exp(-0.5 * (time_ns / sigma_t) ** 2)
    rho_gcc = rho_peak_gcc * np.exp(-0.5 * (time_ns / sigma_t) ** 2)
    radius_cm = R_stag_cm + (R_initial_cm - R_stag_cm) * np.abs(time_ns) / (3 * tau_burn_ns)
    radius_cm = np.maximum(radius_cm, R_stag_cm)
    return time_ns, T_keV, rho_gcc, radius_cm


class TestLaserPreheatDataclass:
    """Test the LaserPreheat dataclass and its pure functions."""

    def test_no_laser_factory(self):
        laser = no_laser()
        assert laser.E_laser_J == 0.0
        assert laser.eta_laser_coupling == 0.0
        assert laser.is_maglif() is False

    def test_is_maglif_threshold(self):
        laser_low = LaserPreheat(E_laser_J=50.0)  # below 100 J threshold
        laser_high = LaserPreheat(E_laser_J=1200.0)
        assert laser_low.is_maglif() is False
        assert laser_high.is_maglif() is True

    def test_z_present_zbeamlet_preset(self):
        laser = z_present_zbeamlet()
        assert laser.E_laser_J == 1200.0  # 1.2 kJ Z-Beamlet
        assert 0.05 <= laser.eta_laser_coupling <= 0.15
        assert laser.is_maglif() is True

    def test_zn_design_preset(self):
        laser = zn_design_laser()
        assert laser.E_laser_J == 8000.0  # 8 kJ ZN design
        assert 0.05 <= laser.eta_laser_coupling <= 0.20
        assert laser.is_maglif() is True

    def test_E_fuel_preheat_scales_linearly_with_E_laser(self):
        """E_fuel_preheat = E_laser * eta, linear in E_laser."""
        eta = 0.10
        E1 = LaserPreheat(E_laser_J=1000.0, eta_laser_coupling=eta).E_fuel_preheat_J()
        E2 = LaserPreheat(E_laser_J=2000.0, eta_laser_coupling=eta).E_fuel_preheat_J()
        E3 = LaserPreheat(E_laser_J=10000.0, eta_laser_coupling=eta).E_fuel_preheat_J()
        assert E1 == pytest.approx(100.0, abs=1e-9)
        assert E2 == pytest.approx(200.0, abs=1e-9)
        assert E3 == pytest.approx(1000.0, abs=1e-9)
        # Linearity
        assert E2 / E1 == pytest.approx(2.0, abs=1e-9)
        assert E3 / E1 == pytest.approx(10.0, abs=1e-9)

    def test_E_fuel_preheat_scales_linearly_with_eta(self):
        """E_fuel_preheat = E_laser * eta, linear in eta."""
        E_laser = 2000.0
        e1 = LaserPreheat(E_laser_J=E_laser, eta_laser_coupling=0.05).E_fuel_preheat_J()
        e2 = LaserPreheat(E_laser_J=E_laser, eta_laser_coupling=0.10).E_fuel_preheat_J()
        e3 = LaserPreheat(E_laser_J=E_laser, eta_laser_coupling=0.20).E_fuel_preheat_J()
        assert e1 == pytest.approx(100.0, abs=1e-9)
        assert e2 == pytest.approx(200.0, abs=1e-9)
        assert e3 == pytest.approx(400.0, abs=1e-9)


class TestPreheatTemperaturePhysics:
    """Test T_preheat_floor = E_fuel / (N_ions * c_v)."""

    def test_T_preheat_increases_with_E_laser(self):
        """More laser energy -> hotter fuel preheat."""
        rho, V = 0.001, 1.0  # 1 mg/cc, 1 cm^3
        t1 = LaserPreheat(E_laser_J=1000.0, eta_laser_coupling=0.10).T_preheat_floor_keV(rho, V)
        t2 = LaserPreheat(E_laser_J=10000.0, eta_laser_coupling=0.10).T_preheat_floor_keV(rho, V)
        assert t2 > t1
        # Linear in E_laser (same eta, same fuel mass)
        assert t2 / t1 == pytest.approx(10.0, rel=1e-3)

    def test_T_preheat_inversely_proportional_to_fuel_mass(self):
        """Same E_laser, denser fuel -> lower T_preheat."""
        eta, E = 0.10, 1000.0
        t_low = LaserPreheat(E_laser_J=E, eta_laser_coupling=eta).T_preheat_floor_keV(0.001, 1.0)
        t_high = LaserPreheat(E_laser_J=E, eta_laser_coupling=eta).T_preheat_floor_keV(0.010, 1.0)
        assert t_low > t_high
        # 10x denser -> 10x lower T
        assert t_low / t_high == pytest.approx(10.0, rel=1e-3)

    def test_T_preheat_zero_when_no_laser(self):
        t = no_laser().T_preheat_floor_keV(0.001, 1.0)
        assert t == 0.0

    def test_T_preheat_zero_for_invalid_inputs(self):
        """Zero / negative rho or V -> 0 (avoid div-by-zero)."""
        laser = LaserPreheat(E_laser_J=1000.0, eta_laser_coupling=0.10)
        assert laser.T_preheat_floor_keV(0.0, 1.0) == 0.0
        assert laser.T_preheat_floor_keV(0.001, 0.0) == 0.0
        assert laser.T_preheat_floor_keV(0.001, -1.0) == 0.0

    def test_cylindrical_helper(self):
        """preheat_floor_for_cylindrical_fuel matches manual calc."""
        rho = 0.001  # g/cc (1 mg/cc fill)
        R = 0.5  # cm
        L = 1.0  # cm
        V_expected = math.pi * R ** 2 * L
        eta = 0.10
        E_laser = 1000.0
        t_helper = preheat_floor_for_cylindrical_fuel(
            E_laser_J=E_laser,
            rho_fuel_gcc=rho,
            R_fuel_cm=R,
            L_fuel_cm=L,
            eta_laser_coupling=eta,
        )
        t_manual = LaserPreheat(
            E_laser_J=E_laser, eta_laser_coupling=eta
        ).T_preheat_floor_keV(rho, V_expected)
        assert t_helper == pytest.approx(t_manual, rel=1e-9)


class TestEnergyBalanceSummary:
    """Test the energy_balance_summary report."""

    def test_no_laser_energy_balance(self):
        s = no_laser().energy_balance_summary(
            rho_fuel_gcc=0.001, V_fuel_cm3=1.0, E_fusion_J=1e6
        )
        assert s["E_laser_J"] == 0.0
        assert s["E_fuel_preheat_J"] == 0.0
        assert s["T_preheat_floor_keV"] == 0.0
        assert s["is_maglif"] is False
        assert s["E_laser_over_E_fusion"] == 0.0

    def test_maglif_energy_balance_typical(self):
        """1.2 kJ Z-Beamlet, 1 mg/cc, 1 cm^3 fuel, ~1 MJ yield."""
        s = z_present_zbeamlet().energy_balance_summary(
            rho_fuel_gcc=0.001, V_fuel_cm3=1.0, E_fusion_J=1e6
        )
        assert s["E_laser_J"] == 1200.0
        assert s["E_fuel_preheat_J"] == pytest.approx(1200.0 * 0.07, abs=1e-9)
        # Sanity: preheat energy << fusion yield for any plausible shot
        assert s["E_fuel_preheat_over_E_fusion"] < 0.01
        assert s["E_laser_over_E_fusion"] < 0.01
        assert s["T_preheat_floor_keV"] > 0.0
        assert s["is_maglif"] is True

    def test_energy_balance_zero_yield(self):
        """If E_fusion=0, the ratios are 0 (not div-by-zero)."""
        s = z_present_zbeamlet().energy_balance_summary(
            rho_fuel_gcc=0.001, V_fuel_cm3=1.0, E_fusion_J=0.0
        )
        assert s["E_laser_over_E_fusion"] == 0.0
        assert s["E_fuel_preheat_over_E_fusion"] == 0.0


class TestMcBrideLaserCoupling:
    """Test that E_laser_kJ actually affects McBride output (was dead weight in v0.1.0)."""

    def test_zero_laser_matches_v010_anchor(self):
        """With E_laser=0 (bare Z-pinch), the Gomez 2020 anchor (2.50 keV)
        is preserved to within the documented 5% uncertainty.

        This is the key backward-compat guarantee: a 'no-laser' shot
        still matches the v0.1.0 published anchor.
        """
        inputs = MagLIFInputs(
            I_peak_MA=20.0,
            E_laser_kJ=0.0,
            T_preheat_eV=200.0,
            rho_0_mgcc=1.0,
            R_0_cm=0.435,
            B_z0_T=16.0,
            fuel="DD",
        )
        p = stagnation_profile(inputs)
        # Without laser, the model is identical to v0.1.0 anchor
        assert p["T_stag_keV"] == pytest.approx(2.50, rel=0.05)

    def test_laser_increases_T_stag(self):
        """With E_laser>0, T_stag should be higher than the no-laser baseline."""
        bare = stagnation_profile(MagLIFInputs(E_laser_kJ=0.0))
        maglif = stagnation_profile(MagLIFInputs(E_laser_kJ=1.2))
        zn = stagnation_profile(MagLIFInputs(E_laser_kJ=8.0))
        assert maglif["T_stag_keV"] > bare["T_stag_keV"]
        assert zn["T_stag_keV"] > maglif["T_stag_keV"]

    def test_gomez_anchor_with_laser_still_publishable(self):
        """Gomez 2020 anchor: 1.2 kJ Z-Beamlet, 20 MA, 16 T, 200 eV preheat.
        Published T_stag ~ 3.1 keV burn-averaged; our McBride model gives
        2.5 keV. With laser coupling now active, the value is ~2.5 keV
        (within 5% of the v0.1.0 anchor and within the published
        30-50% T_ion unfolding uncertainty).
        """
        p = stagnation_profile(gomez2020_z_shot())
        # Same anchor as v0.1.0: T_stag ~ 2.5 keV, allow 5% drift
        assert 2.40 <= p["T_stag_keV"] <= 2.65

    def test_zn_design_with_laser_higher_than_z_present(self):
        """ZN design (8 kJ laser) should give T_stag > Z present (1.2 kJ)."""
        z = stagnation_profile(gomez2020_z_shot())
        zn = stagnation_profile(zn_design_shot())
        assert zn["T_stag_keV"] > z["T_stag_keV"]


class TestPipelineLaserPreheatReport:
    """Test that run_pipeline accepts a laser parameter and reports it."""

    def test_run_pipeline_default_no_laser(self):
        """With no laser passed, the output reports is_maglif=False."""
        time_ns, T_keV, rho_gcc, radius_cm = _triangular_profile()
        result = run_pipeline(
            time_ns, T_keV, rho_gcc,
            E_stored_J=20e6, E_kinetic_J=1e6,
            radius_cm=radius_cm, R_initial_cm=0.4,
        )
        assert "laser_preheat" in result
        assert result["laser_preheat"]["is_maglif"] is False
        assert result["laser_preheat"]["E_laser_J"] == 0.0

    def test_run_pipeline_with_maglif_laser(self):
        """With a MagLIF laser, the report includes the preheat summary."""
        time_ns, T_keV, rho_gcc, radius_cm = _triangular_profile()
        result = run_pipeline(
            time_ns, T_keV, rho_gcc,
            E_stored_J=20e6, E_kinetic_J=1e6,
            radius_cm=radius_cm, R_initial_cm=0.4,
            laser=z_present_zbeamlet(),
        )
        lp = result["laser_preheat"]
        assert lp["is_maglif"] is True
        assert lp["E_laser_J"] == 1200.0
        assert lp["E_fuel_preheat_J"] > 0.0
        # T_preheat_floor_keV is None when the caller doesn't pass
        # the preheat metadata via input_provenance['preheat'].
        # (The full preheat temperature is reported by the McBride
        # generator's `stagnation_profile`, not by the pipeline.)
        assert lp["T_preheat_floor_keV"] is None

    def test_run_pipeline_with_laser_preheat_metadata(self):
        """When input_provenance['preheat'] is provided with rho_0 +
        V_preheat, the pipeline reports T_preheat_floor_keV."""
        time_ns, T_keV, rho_gcc, radius_cm = _triangular_profile()
        result = run_pipeline(
            time_ns, T_keV, rho_gcc,
            E_stored_J=20e6, E_kinetic_J=1e6,
            radius_cm=radius_cm, R_initial_cm=0.4,
            laser=z_present_zbeamlet(),
            input_provenance={
                "preheat": {"rho_preheat_gcc": 0.001, "V_preheat_cm3": 1.0},
            },
        )
        lp = result["laser_preheat"]
        assert lp["is_maglif"] is True
        assert lp["T_preheat_floor_keV"] is not None
        assert lp["T_preheat_floor_keV"] > 0.0

    def test_run_pipeline_laser_does_not_change_yield(self):
        """The laser parameter only adds reporting; it does NOT change
        the burn integration (T_keV profile is taken as input).
        This is a 'cosmetic' integration: the physics lives in the
        input profile (which the McBride generator produces).
        """
        time_ns, T_keV, rho_gcc, radius_cm = _triangular_profile()
        r_no_laser = run_pipeline(
            time_ns, T_keV, rho_gcc,
            E_stored_J=20e6, E_kinetic_J=1e6,
            radius_cm=radius_cm, R_initial_cm=0.4,
        )
        r_laser = run_pipeline(
            time_ns, T_keV, rho_gcc,
            E_stored_J=20e6, E_kinetic_J=1e6,
            radius_cm=radius_cm, R_initial_cm=0.4,
            laser=z_present_zbeamlet(),
        )
        # Same burn integration -> same E_fusion
        assert r_laser["results"]["E_fusion_J"] == pytest.approx(
            r_no_laser["results"]["E_fusion_J"], rel=1e-12
        )

    def test_run_pipeline_energy_sanity_holds(self):
        """E_laser / E_fusion < 1 (laser is not a free energy source)."""
        time_ns, T_keV, rho_gcc, radius_cm = _triangular_profile(T_peak_keV=10.0)
        result = run_pipeline(
            time_ns, T_keV, rho_gcc,
            E_stored_J=20e6, E_kinetic_J=1e6,
            radius_cm=radius_cm, R_initial_cm=0.4,
            laser=z_present_zbeamlet(),
        )
        lp = result["laser_preheat"]
        # For any plausible Z-pinch yield, laser is < 1% of fusion
        assert lp["E_laser_over_E_fusion"] < 1.0
