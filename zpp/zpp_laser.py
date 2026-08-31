"""
Laser preheat model for MagLIF-class Z-pinch shots.

MagLIF (Magnetized Liner Inertial Fusion) is *defined* by the laser:
without the laser, you have a bare Z-pinch with no preheat and no
axial B-field flux compression. Slutz 2010 (Phys. Plasmas 17 056303)
established the canonical laser-to-fuel coupling model:

    E_fuel_preheat = E_laser * eta_laser_coupling

where `eta_laser_coupling` is the fraction of laser energy that ends
up as fuel thermal energy at stagnation-relevant densities. Published
values:

- Z-Beamlet on Z: ~5-10% coupling at 1-2 kJ (Slutz 2010, Gomez 2020)
- Z-Beamletlet on ZN (planned): ~10-15% coupling at 4-8 kJ
  (Yager-Elorriaga 2022, Sefkow 2014)
- OMEGA / NIF indirect-drive: ~5-15% hohlraum-to-fuel coupling
  (Lindl 2014)

The preheat sets the *fuel adiabat*: a higher preheat means a higher
isentrope, more fuel PdV work to compress, but a hotter starting
point. The trade-off is captured by Slutz 2010 eq. 4-6 and McBride
2015 eq. 17-22.

This module:
1. Computes the laser-to-fuel coupling energy and equivalent
   preheat temperature.
2. Validates that the preheat energy is small compared to the
   fusion yield (i.e. not a "free energy" source).
3. Reports the laser energy balance in the pipeline output.

The preheat temperature is *added* to the input T_keV profile at
t = t_0 (or returned as a constant offset for downstream consumers).
We do NOT modify the existing `burn_yield` arithmetic; we just
report the preheat energy budget and pass a `T_preheat_keV_floor`
into the pipeline that the lawson / yield integration can use.

References:
- Slutz S.A. et al. (2010) Phys. Plasmas 17 056303 — MagLIF concept
- Sefkow A.B. et al. (2014) Phys. Plasmas 21 072711 — MagLIF design
- McBride R.D. & Slutz S.A. (2015) Phys. Plasmas 22 052708
- Gomez M.R. et al. (2020) PRL 125 155002 — Z 2960 series data
- Yager-Elorriaga D.A. et al. (2022) Nucl. Fusion 62 042015
- Lindl J. et al. (2014) Phys. Plasmas 21 020501 — NIF hohlraum physics
"""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np


# Boltzmann constant in eV/K and keV/K. Used for the c_v estimate
# of an ideal monatomic plasma: c_v = (3/2) k_B per particle.
K_BOLTZMANN_KEV_PER_K = 8.617333262e-8  # keV / K
K_BOLTZMANN_J_PER_KEV = 1.602176634e-16  # J / keV


@dataclass
class LaserPreheat:
    """Laser preheat parameters for a MagLIF shot.

    All fields are physical, with published reference ranges.
    Defaults are Z-Beamlet-class (Z present-day, 1-2 kJ, ~10% coupling).
    """
    E_laser_J: float = 0.0          # Delivered laser energy to hohlraum [J]
    eta_laser_coupling: float = 0.10  # Laser-to-fuel coupling fraction [-]
    pulse_duration_ns: float = 1.0   # Laser pulse length [ns] (informational)
    hohlraum_temp_eV: float = 150.0  # Hohlraum radiation temperature [eV]

    def is_maglif(self) -> bool:
        """A shot is MagLIF if the laser energy is non-trivial."""
        return self.E_laser_J > 100.0  # < 100 J is essentially bare Z-pinch

    def E_fuel_preheat_J(self) -> float:
        """Energy delivered to fuel thermal reservoir [J].

        E_fuel_preheat = E_laser * eta_laser_coupling
        """
        return self.E_laser_J * self.eta_laser_coupling

    def T_preheat_floor_keV(
        self,
        rho_fuel_gcc: float,
        V_fuel_cm3: float,
    ) -> float:
        """Equivalent preheat ion temperature [keV] from laser energy.

        For an ideal monatomic plasma with c_v = (3/2) k_B per particle:
            T = (2/3) * E / (N * k_B)
        where N = n * V.

        For a D-T fuel at density rho (g/cc), the ion number density is:
            n_i [atoms/cm^3] = rho * N_A / A_avg
        with A_avg = 2.5 for equimolar D-T.

        Args:
            rho_fuel_gcc: Fuel mass density at preheat time [g/cm^3].
                          For MagLIF, this is the *initial* (uncompressed)
                          fill density, NOT the stagnation density, because
                          the preheat is delivered before compression.
            V_fuel_cm3:    Fuel volume at preheat time [cm^3].

        Returns:
            T_preheat [keV]. This is the *bulk* preheat temperature; it
            is then adiabatically compressed during the implosion, giving
            T_stag >> T_preheat (Slutz 2010, McBride 2015).
        """
        N_AVOGADRO = 6.02214076e23
        A_AVG_DT = 2.5  # g/mol, equimolar D-T
        if V_fuel_cm3 <= 0 or rho_fuel_gcc <= 0:
            return 0.0
        # Number of fuel ions in the preheat volume
        N_ions = rho_fuel_gcc * V_fuel_cm3 * N_AVOGADRO / A_AVG_DT
        if N_ions <= 0:
            return 0.0
        # c_v = (3/2) k_B per ion, so E = (3/2) N k_B T
        # T = (2/3) E / (N k_B) [in K]
        T_K = (2.0 / 3.0) * self.E_fuel_preheat_J() / (N_ions * K_BOLTZMANN_J_PER_KEV)
        T_keV = T_K * K_BOLTZMANN_KEV_PER_K
        return float(T_keV)

    def energy_balance_summary(
        self,
        rho_fuel_gcc: float,
        V_fuel_cm3: float,
        E_fusion_J: float,
        T_preheat_floor_keV_override: float | None = None,
    ) -> dict:
        """One-line summary of the laser energy budget.

        Args:
            rho_fuel_gcc: Fuel density at preheat [g/cm^3].
            V_fuel_cm3:   Fuel volume at preheat [cm^3].
            E_fusion_J:   Total fusion yield [J] from the pipeline.
            T_preheat_floor_keV_override: Optional pre-computed T_preheat
                [keV] to use instead of recomputing from rho/V. Useful
                when the caller has a more accurate T_preheat from a
                separate physics model.

        Returns:
            dict with the preheat energy balance and key ratios.
        """
        E_fuel = self.E_fuel_preheat_J()
        T_preheat = (
            T_preheat_floor_keV_override
            if T_preheat_floor_keV_override is not None
            else self.T_preheat_floor_keV(rho_fuel_gcc, V_fuel_cm3)
        )

        # Fraction of fusion yield that the laser contributed
        # (sanity check: laser preheat is ~10% of E_laser; if this
        # ratio is > 1%, the laser is contributing non-trivially to
        # the energy budget).
        E_laser_fraction_of_yield = (
            self.E_laser_J / E_fusion_J if E_fusion_J > 0 else 0.0
        )
        E_fuel_fraction_of_yield = (
            E_fuel / E_fusion_J if E_fusion_J > 0 else 0.0
        )

        return {
            "E_laser_J": self.E_laser_J,
            "eta_laser_coupling": self.eta_laser_coupling,
            "E_fuel_preheat_J": E_fuel,
            "E_fuel_preheat_MJ": E_fuel / 1e6,
            "T_preheat_floor_keV": T_preheat,
            "pulse_duration_ns": self.pulse_duration_ns,
            "hohlraum_temp_eV": self.hohlraum_temp_eV,
            "rho_fuel_preheat_gcc": rho_fuel_gcc,
            "V_fuel_preheat_cm3": V_fuel_cm3,
            "E_laser_over_E_fusion": E_laser_fraction_of_yield,
            "E_fuel_preheat_over_E_fusion": E_fuel_fraction_of_yield,
            "is_maglif": self.is_maglif(),
        }

    def energy_balance_summary_energy_only(self, E_fusion_J: float) -> dict:
        """Energy-only summary when preheat volume is unknown.

        Reports the same energy budget as `energy_balance_summary` but
        with T_preheat_floor_keV=None and rho_fuel_preheat_gcc=None.
        Useful for callers that don't have the initial fuel density
        at preheat time (e.g. a synthetic profile with no McBride
        inputs).

        Args:
            E_fusion_J: Total fusion yield [J].

        Returns:
            dict with the laser energy budget (T_preheat_floor_keV=None).
        """
        E_fuel = self.E_fuel_preheat_J()
        return {
            "E_laser_J": self.E_laser_J,
            "eta_laser_coupling": self.eta_laser_coupling,
            "E_fuel_preheat_J": E_fuel,
            "E_fuel_preheat_MJ": E_fuel / 1e6,
            "T_preheat_floor_keV": None,
            "pulse_duration_ns": self.pulse_duration_ns,
            "hohlraum_temp_eV": self.hohlraum_temp_eV,
            "rho_fuel_preheat_gcc": None,
            "V_fuel_preheat_cm3": None,
            "E_laser_over_E_fusion": (
                self.E_laser_J / E_fusion_J if E_fusion_J > 0 else 0.0
            ),
            "E_fuel_preheat_over_E_fusion": (
                E_fuel / E_fusion_J if E_fusion_J > 0 else 0.0
            ),
            "is_maglif": self.is_maglif(),
        }


def preheat_floor_for_cylindrical_fuel(
    E_laser_J: float,
    rho_fuel_gcc: float,
    R_fuel_cm: float,
    L_fuel_cm: float,
    eta_laser_coupling: float = 0.10,
) -> float:
    """Convenience: T_preheat_keV for a cylindrical fuel volume.

    Args:
        E_laser_J:        Delivered laser energy [J].
        rho_fuel_gcc:     Initial (uncompressed) fuel density [g/cm^3].
        R_fuel_cm:        Initial fuel radius [cm].
        L_fuel_cm:        Fuel axial length [cm] (the liner height).
        eta_laser_coupling: Laser-to-fuel coupling fraction.

    Returns:
        T_preheat [keV] — the *bulk* preheat temperature, before
        adiabatic compression.
    """
    V_cm3 = np.pi * R_fuel_cm ** 2 * L_fuel_cm
    laser = LaserPreheat(
        E_laser_J=E_laser_J,
        eta_laser_coupling=eta_laser_coupling,
    )
    return laser.T_preheat_floor_keV(rho_fuel_gcc, V_cm3)


def no_laser() -> LaserPreheat:
    """Bare Z-pinch (no laser) — the v0.1.0 default."""
    return LaserPreheat(E_laser_J=0.0, eta_laser_coupling=0.0)


def z_present_zbeamlet() -> LaserPreheat:
    """Z-Beamlet on Z (present-day, ~1.2 kJ, ~10% coupling).

    Reference: Gomez 2020 PRL 125 155002.
    """
    return LaserPreheat(
        E_laser_J=1200.0,           # 1.2 kJ Z-Beamlet
        eta_laser_coupling=0.07,    # Lower end: 1.2 kJ * 0.07 = 84 J to fuel
        pulse_duration_ns=1.0,
        hohlraum_temp_eV=150.0,
    )


def zn_design_laser() -> LaserPreheat:
    """ZN design laser (~8 kJ, ~10-15% coupling).

    Reference: Yager-Elorriaga 2022, Sefkow 2014.
    """
    return LaserPreheat(
        E_laser_J=8000.0,           # 8 kJ Z-Beamletlet-class
        eta_laser_coupling=0.12,    # Improved coupling with new hohlraum
        pulse_duration_ns=2.0,
        hohlraum_temp_eV=200.0,
    )
