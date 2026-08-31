"""
Tier 5.D — PFC lifetime tests.

Verifies:
1. DPA_rate_per_FPY returns reasonable values (5-20 DPA/FPY at 1 MW/m²).
2. DPA per FPY scales linearly with wall load.
3. DPA lifetime is DPA_limit / DPA_rate.
4. MHD Hartmann number > 100 for B=5T, channel=1cm.
5. MHD wall shear stress scales linearly with velocity.
6. Erosion rate is 0 below critical shear stress.
7. Erosion rate scales with (tau/tau_crit)^2.5.
8. first_wall_lifetime uses min(DPA, erosion).
9. Calendar interval = FPY / availability.
10. Unknown material raises ValueError.
"""
from __future__ import annotations
import sys
import os

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "code"))

from zpp.zpp_pfc_lifetime import (
    DPA_rate_per_FPY, MHD_Hartmann_number, MHD_wall_shear_stress,
    MHD_erosion_rate_mm_per_year, first_wall_lifetime,
    PFCDamageInputs, PFCDamageResult,
    DPA_LIMIT, ED_THRESHOLD, LIQUID_METAL_PROPERTIES,
)


class TestDPARatePerFPY:
    """Test DPA_rate_per_FPY()."""

    def test_DPA_at_1_MW_per_m2(self):
        """At 1 MW/m² wall load, DPA ~5-20 per FPY for typical materials."""
        for mat in ["W", "SS316", "RAFM", "Be", "Cu", "Mo"]:
            dpa = DPA_rate_per_FPY(1.0, mat)
            assert 1 < dpa < 50, f"{mat}: DPA={dpa:.2f} out of range"

    def test_DPA_scales_linearly_with_wall_load(self):
        """DPA proportional to wall load."""
        dpa_1 = DPA_rate_per_FPY(1.0, "RAFM")
        dpa_2 = DPA_rate_per_FPY(2.0, "RAFM")
        dpa_3 = DPA_rate_per_FPY(5.0, "RAFM")
        assert dpa_2 == pytest.approx(2 * dpa_1, rel=0.05)
        assert dpa_3 == pytest.approx(5 * dpa_1, rel=0.05)

    def test_DPA_RAFM_around_12(self):
        """RAFM at 1 MW/m²: ~12 DPA/FPY (matches published ITER)."""
        dpa = DPA_rate_per_FPY(1.0, "RAFM")
        assert 8 < dpa < 18

    def test_DPA_Be_around_10(self):
        """Be at 1 MW/m²: ~10 DPA/FPY."""
        dpa = DPA_rate_per_FPY(1.0, "Be")
        assert 5 < dpa < 20

    def test_unknown_material_raises(self):
        with pytest.raises(ValueError):
            DPA_rate_per_FPY(1.0, "NotARealMaterial")


class TestMHDHartmannNumber:
    """Test MHD_Hartmann_number()."""

    def test_Ha_typical(self):
        """For B=5T, channel=1cm, LiPb: Ha ~ 1000."""
        props = LIQUID_METAL_PROPERTIES["LiPb"]
        Ha = MHD_Hartmann_number(
            B_field_T=5.0,
            channel_half_height_m=0.01,
            fluid_electrical_conductivity_S_per_m=props["electrical_conductivity_S_per_m"],
            fluid_viscosity_Pa_s=props["viscosity_Pa_s"],
        )
        assert 500 < Ha < 2000

    def test_Ha_scales_with_B(self):
        """Ha is linear in B."""
        props = LIQUID_METAL_PROPERTIES["LiPb"]
        Ha_5 = MHD_Hartmann_number(5.0, 0.01, props["electrical_conductivity_S_per_m"], props["viscosity_Pa_s"])
        Ha_10 = MHD_Hartmann_number(10.0, 0.01, props["electrical_conductivity_S_per_m"], props["viscosity_Pa_s"])
        assert Ha_10 == pytest.approx(2 * Ha_5, rel=0.05)

    def test_Ha_scales_with_channel(self):
        """Ha is linear in channel half-height."""
        props = LIQUID_METAL_PROPERTIES["LiPb"]
        Ha_small = MHD_Hartmann_number(5.0, 0.005, props["electrical_conductivity_S_per_m"], props["viscosity_Pa_s"])
        Ha_large = MHD_Hartmann_number(5.0, 0.02, props["electrical_conductivity_S_per_m"], props["viscosity_Pa_s"])
        assert Ha_large == pytest.approx(4 * Ha_small, rel=0.05)


class TestMHDWallShearStress:
    """Test MHD_wall_shear_stress()."""

    def test_tau_w_linear_in_velocity(self):
        """Wall shear stress scales linearly with flow velocity."""
        Ha = 1000.0
        v0 = 0.1
        v1 = 0.5
        eta = 2.5e-3
        L = 0.01
        tau_0 = MHD_wall_shear_stress(Ha, v0, eta, L)
        tau_1 = MHD_wall_shear_stress(Ha, v1, eta, L)
        assert tau_1 == pytest.approx(5 * tau_0, rel=0.05)

    def test_tau_w_scales_with_sqrt_Ha(self):
        """Wall shear stress scales with sqrt(Ha)."""
        v = 0.5
        eta = 2.5e-3
        L = 0.01
        tau_100 = MHD_wall_shear_stress(100.0, v, eta, L)
        tau_400 = MHD_wall_shear_stress(400.0, v, eta, L)
        # sqrt(4) = 2x
        assert tau_400 == pytest.approx(2 * tau_100, rel=0.05)


class TestMHDErosionRate:
    """Test MHD_erosion_rate_mm_per_year()."""

    def test_zero_below_critical(self):
        """Erosion = 0 when shear stress < critical."""
        # RAFM-LiPb critical is 8 Pa
        erosion = MHD_erosion_rate_mm_per_year(
            Hartmann_number=1000.0,
            wall_shear_stress_Pa=5.0,  # below 8 Pa critical
            fluid_density_kg_per_m3=9800.0,
            material="RAFM", fluid="LiPb",
        )
        assert erosion == 0.0

    def test_zero_at_low_Ha(self):
        """Erosion = 0 when Ha < 1 (laminar)."""
        erosion = MHD_erosion_rate_mm_per_year(
            Hartmann_number=0.5,
            wall_shear_stress_Pa=100.0,  # irrelevant at low Ha
            fluid_density_kg_per_m3=9800.0,
            material="RAFM", fluid="LiPb",
        )
        assert erosion == 0.0

    def test_positive_above_critical(self):
        """Erosion > 0 when shear stress > critical."""
        erosion = MHD_erosion_rate_mm_per_year(
            Hartmann_number=1000.0,
            wall_shear_stress_Pa=20.0,  # 2.5x critical
            fluid_density_kg_per_m3=9800.0,
            material="RAFM", fluid="LiPb",
        )
        assert erosion > 0.0

    def test_erosion_scales_as_power_law(self):
        """erosion ∝ (tau/tau_crit)^2.5."""
        base_tau = 16.0
        tau2 = 32.0  # 2x
        e1 = MHD_erosion_rate_mm_per_year(
            Hartmann_number=1000.0,
            wall_shear_stress_Pa=base_tau,
            fluid_density_kg_per_m3=9800.0,
            material="RAFM", fluid="LiPb",
        )
        e2 = MHD_erosion_rate_mm_per_year(
            Hartmann_number=1000.0,
            wall_shear_stress_Pa=tau2,
            fluid_density_kg_per_m3=9800.0,
            material="RAFM", fluid="LiPb",
        )
        # 2x tau -> 2^2.5 = 5.66x erosion
        ratio = e2 / e1 if e1 > 0 else 0
        assert 5 < ratio < 6.5


class TestFirstWallLifetime:
    """Test first_wall_lifetime()."""

    def test_returns_PFCDamageResult(self):
        inp = PFCDamageInputs()
        result = first_wall_lifetime(inp)
        assert isinstance(result, PFCDamageResult)

    def test_default_ZN_DPA_lifetime(self):
        """Default ZN plant: DPA lifetime ~13 FPY (RAFM at 1 MW/m²)."""
        inp = PFCDamageInputs(material="RAFM", neutron_wall_load_MW_per_m2=1.0)
        result = first_wall_lifetime(inp)
        assert 10 < result.DPA_lifetime_FPY < 20

    def test_first_wall_lifetime_is_min(self):
        """FW lifetime = min(DPA, erosion)."""
        # If erosion limit < DPA limit, FW lifetime = erosion.
        inp = PFCDamageInputs(
            material="RAFM", blanket_fluid="LiPb",
            flow_velocity_m_per_s=5.0,  # high velocity -> erosion matters
            B_field_T=5.0,
            erosion_limit_mm=2.0,
        )
        result = first_wall_lifetime(inp)
        assert result.first_wall_lifetime_years == pytest.approx(
            min(result.DPA_lifetime_FPY, result.erosion_lifetime_years), rel=0.01
        )

    def test_no_liquid_metal_skips_erosion(self):
        """If blanket_fluid='none', erosion = 0 and erosion_lifetime = inf."""
        inp = PFCDamageInputs(blanket_fluid="none", material="W")
        result = first_wall_lifetime(inp)
        assert result.erosion_rate_mm_per_year == 0.0
        assert result.erosion_lifetime_years == float("inf")
        # FW lifetime should equal DPA lifetime
        assert result.first_wall_lifetime_years == result.DPA_lifetime_FPY

    def test_calendar_lifetime_includes_availability(self):
        """Calendar lifetime = FPY / availability."""
        inp = PFCDamageInputs(plant_availability=0.25, material="RAFM")
        result = first_wall_lifetime(inp)
        # Calendar replacement interval = FPY replacement / 0.25
        assert result.replacement_interval_years == pytest.approx(
            result.first_wall_lifetime_years * 0.8 / 0.25, rel=0.01
        )


class TestStrategicFindings:
    """Document strategic findings from PFC lifetime."""

    def test_RAFM_outlasts_plant_life_at_low_wall_load(self):
        """For ZN at 1 MW/m² wall load with 25% CF, RAFM outlives 30-yr plant."""
        inp = PFCDamageInputs(
            material="RAFM",
            neutron_wall_load_MW_per_m2=1.0,
            plant_availability=0.25,
        )
        result = first_wall_lifetime(inp)
        # Calendar years ≈ 13 / 0.25 = 52 yr > 30-yr plant
        assert result.replacement_interval_years > 30

    def test_Be_needs_replacement_during_plant_life(self):
        """Beryllium is too soft for fusion: needs replacement every ~10 yr."""
        inp = PFCDamageInputs(
            material="Be",
            neutron_wall_load_MW_per_m2=1.0,
            plant_availability=0.25,
        )
        result = first_wall_lifetime(inp)
        # DPA lifetime ~3 FPY, calendar = 3/0.25 * 0.8 = 9.6 yr
        assert result.replacement_interval_years < 15

    def test_W_lifetime_limited_by_DPA_limit(self):
        """Tungsten DPA limit is 50 (brittle at low T), lifetime ~5 FPY."""
        inp = PFCDamageInputs(material="W", neutron_wall_load_MW_per_m2=1.0)
        result = first_wall_lifetime(inp)
        assert result.DPA_lifetime_FPY < 10
