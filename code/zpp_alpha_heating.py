"""
α-heating bootstrap model for Z-pinch fusion shots.

In D-T fusion, 20% of the 17.6 MeV reaction energy is carried by the
3.5 MeV α particle. If the α is stopped in the fuel (rather than
escaping), it deposits its energy as heat, raising the fuel
temperature. This creates a positive feedback loop:

    T -> n_D n_T <σv>(T) -> P_fus -> P_α = f_dep * (E_α/E_DT) * P_fus
    -> dT/dt = P_α / (n * c_v) -> T

The loop either:
- Reaches ignition (self-sustaining burn; required nTτ > 3e21 keV·s/m³
  for D-T), OR
- Quenches (α heating is insufficient to overcome losses).

This module implements a **scoping** α-heating model:
1. Computes α-energy deposition fraction `f_dep(ρR)` from Bosch-Hale
   1992 / NRL formulary α-range data.
2. Computes α-heating power density `P_α` from the McBride T_stag
   and ρR profile.
3. Iteratively solves for the equilibrium temperature `T_eq` where
   P_α = P_brem + P_conduction (simplified).
4. Returns the **α-boost factor** `T_eq / T_stag_no_alpha` and an
   ignition flag.

References:
- Bosch H.-S. & Hale G.M. (1992) Nucl. Fusion 2 611- — α range in DT.
- NRL Plasma Formulary (2019) — bremsstrahlung, α range.
- Atzeni S. & Meyer-ter-Vehn J. (2004) "The Physics of Inertial
  Fusion", Oxford — ignition criterion.
- Slutz S.A. (2021) Phys. Plasmas 28 082101 — ice-burner scaling.
- Hurricane O.A. et al. (2016) Phys. Plasmas 23 022706 — α-heating
  in ICF ignition.

This is NOT a full rad-hydro simulation. It is a parametric scoping
tool that quantifies the α-boost and ignition margin given the
McBride stagnation profile.
"""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np

from zpp_bosch_hale import reactivity_DT_cm3s, E_DT_J, E_DT_MeV


# Physical constants
E_ALPHA_MEV = 3.5                  # α kinetic energy [MeV]
E_ALPHA_J = E_ALPHA_MEV * 1.602176634e-13  # [J]
ALPHA_FRACTION_OF_E_DT = E_ALPHA_J / E_DT_J  # ~0.199
N_AVOGADRO = 6.02214076e23
MOLAR_MASS_DT = 2.5  # g/mol, equimolar D-T

# α range in DT at 3.5 MeV (Bosch-Hale 1992 / NRL formulary):
# ρR_α ≈ 0.32 g/cm² at stagnation T (typical).
# Valid for 1 < T_ion < 50 keV; ranges 0.25-0.45 g/cm² depending
# on T_ion and fuel composition.
ALPHA_RANGE_DT_GCCM = 0.32  # [g/cm²]

# Bremsstrahlung coefficient (NRL formulary 2019):
# P_brem [W/cm³] = 5.35e-31 * n_e * n_i * Z_eff * sqrt(T [keV])
# For D-T, Z_eff ≈ 1, n_e ≈ n_i ≈ n_total (equimolar, Z=1 each).
BREMS_COEFF = 5.35e-31  # [W cm³ / (atoms² keV^0.5)]


def alpha_deposition_fraction(rho_R_gccm: float) -> float:
    """Fraction of α energy deposited locally in the fuel.

    Args:
        rho_R_gccm: Fuel areal density [g/cm²].

    Returns:
        f_dep in [0, 1]. At ρR >> ρR_α (~0.32), nearly all α
        energy is deposited. At ρR << ρR_α, most α escape.

    f_dep(ρR) = 1 - exp(-ρR / ρR_α)
    """
    if rho_R_gccm <= 0:
        return 0.0
    return float(1.0 - np.exp(-rho_R_gccm / ALPHA_RANGE_DT_GCCM))


def bremsstrahlung_power_density(
    n_per_cc: float, T_keV: float
) -> float:
    """Bremsstrahlung power loss density [W/cm³].

    P_brem = 5.35e-31 * n_e * n_i * Z_eff * sqrt(T [keV])

    For D-T equimolar: n_e = n_total (each D/T contributes 1 electron),
    n_i = n_total, Z_eff = 1.
    """
    if n_per_cc <= 0 or T_keV <= 0:
        return 0.0
    return float(BREMS_COEFF * n_per_cc ** 2 * np.sqrt(T_keV))


def alpha_heating_power_density(
    rho_gcc: float, T_keV: float, rho_R_gccm: float
) -> float:
    """α-heating power density [W/cm³] in the fuel.

    P_α = f_dep(ρR) * (E_α/E_DT) * P_fus / V
        = f_dep * 0.199 * n_D n_T <σv>(T) * E_DT

    Args:
        rho_gcc:    Fuel mass density [g/cm³].
        T_keV:      Ion temperature [keV].
        rho_R_gccm: Fuel areal density [g/cm²].
    """
    if rho_gcc <= 0 or T_keV <= 0:
        return 0.0
    n_per_cc = rho_gcc * N_AVOGADRO / MOLAR_MASS_DT  # atoms/cm³ (D+T total)
    # For equimolar D-T: n_D = n_T = n/2, so n_D * n_T = n²/4
    n_D_n_T = (n_per_cc / 2.0) ** 2
    sigma_v = reactivity_DT_cm3s(np.array([T_keV]))[0]  # cm³/s
    # P_fus [W/cm³] = n_D n_T <σv> E_DT [J]
    P_fus = n_D_n_T * sigma_v * E_DT_J
    f_dep = alpha_deposition_fraction(rho_R_gccm)
    return float(f_dep * ALPHA_FRACTION_OF_E_DT * P_fus)


def alpha_boost_iterative(
    rho_gcc: float,
    T_initial_keV: float,
    rho_R_gccm: float,
    max_iter: int = 50,
    tol_keV: float = 0.01,
    include_conduction: bool = False,
) -> dict:
    """Iteratively solve for equilibrium T_eq with α-heating.

    The temperature update is:
        T_new = T + (P_α - P_loss) * dt / (n * c_v)

    where c_v = (3/2) k_B per particle for an ideal monatomic plasma,
    P_loss = P_brem (always) + P_conduction (if include_conduction=True).

    For convergence we use a simple relaxation: each iteration
    replaces T with a weighted average of T_old and T_new. This
    converges to the fixed point T_eq where P_α = P_loss.

    Args:
        rho_gcc:    Fuel density [g/cm³].
        T_initial_keV: Starting temperature (McBride T_stag) [keV].
        rho_R_gccm: Fuel areal density [g/cm²].
        max_iter:   Maximum iterations.
        tol_keV:    Convergence tolerance [keV].
        include_conduction: If True, include a simple conduction-loss
            model (P_cond = const * T / R²_stag). Default False.

    Returns:
        dict with:
        - T_eq_keV: equilibrium temperature [keV]
        - T_initial_keV: input starting temperature
        - boost_factor: T_eq / T_initial
        - ignited: True if T_eq > T_initial + 0.5 keV (significant α boost)
        - n_iterations: number of iterations to converge
        - P_alpha_W_per_cm3: equilibrium α-heating power density
        - P_brem_W_per_cm3: equilibrium bremsstrahlung loss density
        - rho_R_alphas: number of α ranges in the fuel (ρR / ρR_α)
    """
    if rho_gcc <= 0 or T_initial_keV <= 0:
        return {
            "T_eq_keV": T_initial_keV,
            "T_initial_keV": T_initial_keV,
            "boost_factor": 1.0,
            "ignited": False,
            "n_iterations": 0,
            "P_alpha_W_per_cm3": 0.0,
            "P_brem_W_per_cm3": 0.0,
            "rho_R_alphas": 0.0,
        }

    n_per_cc = rho_gcc * N_AVOGADRO / MOLAR_MASS_DT
    k_B_keV_per_K = 8.617333262e-8  # keV/K
    # c_v = (3/2) k_B per particle [keV/K per atom]
    cv_per_atom_keV_per_K = 1.5 * k_B_keV_per_K

    # Conduction model (very simple): P_cond = κ₀ T / R² where
    # κ₀ is a fiducial Spitzer-like coefficient. Used only as
    # a "conduction-on" toggle for the test suite.
    if include_conduction:
        # Use R_stag from ρR: R_stag ≈ ρR / ρ (1D cylindrical).
        # Then P_cond ≈ 5e-5 * T / R_stag² [W/cm³] — a coarse scaling
        # calibrated so ZN-stagnation (R=0.1 cm, T=5 keV) gives
        # P_cond ~ 0.025 W/cm³ (comparable to bremsstrahlung).
        R_stag_cm = rho_R_gccm / rho_gcc if rho_gcc > 0 else 1.0
        conduction_coeff = 5e-5  # [W / (cm³ · keV / cm²)]
    else:
        R_stag_cm = 1.0
        conduction_coeff = 0.0

    T = float(T_initial_keV)
    T_CAP_KEV = 50.0  # physical max for fusion plasma (above this, ion
                       # population is non-thermal and the model breaks
                       # down; Bosch-Hale 1992 valid range is 0.2-100 keV).
                       # Crossing this cap signals alpha runaway = ignition.
    P_alpha = 0.0
    P_brem = 0.0
    for it in range(max_iter):
        P_alpha = alpha_heating_power_density(rho_gcc, T, rho_R_gccm)
        P_brem = bremsstrahlung_power_density(n_per_cc, T)
        P_cond = conduction_coeff * T / R_stag_cm ** 2 if include_conduction else 0.0
        P_net = P_alpha - P_brem - P_cond

        # Heat capacity: n * c_v [keV/cm³/K]
        # Energy density: n [atoms/cm³] * c_v [keV/K] * T [K]
        # Convert: 1 eV = 11604 K
        T_K = T / k_B_keV_per_K
        # dT/dt = P_net [W/cm³] / (n * c_v [J/K/cm³])
        # n [atoms/cm³] * c_v_J_per_K = n * 1.5 * k_B_J_per_K = n * 1.5 * 1.38e-23
        # = n * 2.07e-23 J/K/cm³
        cv_J_per_cm3_per_K = n_per_cc * 1.5 * 1.380649e-23
        # dt for one "alpha-heating timescale" — calibrate to converge
        # fast but stable. Use dt = 1 ns = 1e-9 s.
        dt_s = 1e-9
        dT_keV = P_net * dt_s / cv_J_per_cm3_per_K * k_B_keV_per_K

        # Relaxation: T_new = T + 0.5 * dT (half-step for stability)
        T_new = T + 0.5 * dT_keV
        # T cannot go negative or below 0.1 keV
        T_new = max(0.1, T_new)
        # Clamp at physical max
        T_new = min(T_new, T_CAP_KEV)

        if abs(T_new - T) < tol_keV:
            T = T_new
            break
        T = T_new

    # If T hits the cap, the model is in alpha runaway = ignition.
    # Mark ignited and use the cap value as T_eq (the actual T would
    # be higher, but our model can't predict the runaway steady state).
    hit_cap = T >= T_CAP_KEV - tol_keV
    boost = T / T_initial_keV if T_initial_keV > 0 else 1.0
    return {
        "T_eq_keV": float(T),
        "T_initial_keV": float(T_initial_keV),
        "boost_factor": float(boost),
        "ignited": bool(hit_cap or (T - T_initial_keV) > 0.5),
        "hit_cap": bool(hit_cap),
        "n_iterations": int(it + 1),
        "P_alpha_W_per_cm3": float(P_alpha),
        "P_brem_W_per_cm3": float(P_brem),
        "rho_R_alphas": float(rho_R_gccm / ALPHA_RANGE_DT_GCCM),
    }


@dataclass
class AlphaHeatingResult:
    """Result of an α-heating bootstrap calculation."""
    T_eq_keV: float
    T_initial_keV: float
    boost_factor: float
    ignited: bool
    rho_R_gccm: float
    rho_R_alphas: float  # ρR / ρR_α (number of α ranges in the fuel)
    f_dep: float         # α deposition fraction
    P_alpha_W_per_cm3: float
    P_brem_W_per_cm3: float
    P_net_W_per_cm3: float  # P_α - P_brem
    Q_with_alpha: float   # Engineering gain with α boost
    Q_without_alpha: float  # Engineering gain without α boost
    notes: str


def apply_alpha_heating_to_shot(
    T_stag_keV: float,
    rho_stag_gcc: float,
    rho_R_gccm: float,
    Q_target_base: float,
    E_fusion_2D_J: float,
    E_stored_J: float,
    max_iter: int = 50,
) -> AlphaHeatingResult:
    """Compute the α-heating boost for a shot and update Q_target.

    Args:
        T_stag_keV:    Stagnation temperature from McBride (no α) [keV].
        rho_stag_gcc:  Stagnation fuel density [g/cm³].
        rho_R_gccm:    Areal density [g/cm²].
        Q_target_base: Q_target = E_fus / E_kinetic (no α) [dimensionless].
        E_fusion_2D_J: 2D-corrected yield (already in pipeline output) [J].
        E_stored_J:    Driver stored energy [J].
        max_iter:      Iteration bound for the α-boost solve.

    Returns:
        AlphaHeatingResult with T_eq, boost factor, and updated Q_target.
    """
    res = alpha_boost_iterative(
        rho_gcc=rho_stag_gcc,
        T_initial_keV=T_stag_keV,
        rho_R_gccm=rho_R_gccm,
        max_iter=max_iter,
    )

    boost = res["boost_factor"]
    # Q_target scales roughly as T² in the 1-10 keV range; using
    # σv ∝ exp(-const/T) is more accurate but boost^2 is a useful
    # first-order scaling. We use a conservative boost^1.5 (the
    # σv scaling at 3 keV is approximately T^1.5).
    Q_with_alpha = Q_target_base * boost ** 1.5

    # Energy gain scales as the burn yield; if boost → T_eq, then
    # E_fus_new ~ E_fus_old * (σv(T_eq)/σv(T_stag))
    # Approximated by boost^1.5 (same scaling as Q_target).
    E_fusion_with_alpha_J = E_fusion_2D_J * boost ** 1.5

    f_dep = alpha_deposition_fraction(rho_R_gccm)
    notes = (
        f"ρR = {rho_R_gccm:.3f} g/cm² = {res['rho_R_alphas']:.2f} α ranges. "
        f"f_dep = {f_dep:.3f}. T_stag -> T_eq = {T_stag_keV:.2f} -> {res['T_eq_keV']:.2f} keV "
        f"(boost {boost:.2f}x). "
        f"P_α = {res['P_alpha_W_per_cm3']:.2e} W/cm³, "
        f"P_brem = {res['P_brem_W_per_cm3']:.2e} W/cm³."
    )

    return AlphaHeatingResult(
        T_eq_keV=res["T_eq_keV"],
        T_initial_keV=res["T_initial_keV"],
        boost_factor=res["boost_factor"],
        ignited=res["ignited"],
        rho_R_gccm=rho_R_gccm,
        rho_R_alphas=res["rho_R_alphas"],
        f_dep=f_dep,
        P_alpha_W_per_cm3=res["P_alpha_W_per_cm3"],
        P_brem_W_per_cm3=res["P_brem_W_per_cm3"],
        P_net_W_per_cm3=res["P_alpha_W_per_cm3"] - res["P_brem_W_per_cm3"],
        Q_with_alpha=Q_with_alpha,
        Q_without_alpha=Q_target_base,
        notes=notes,
    )


def alpha_ignition_criterion(
    rho_gcc: float, T_keV: float, tau_burn_ns: float
) -> dict:
    """Check the Lawson ignition criterion nTτ > 3e21 keV·s/m³ for D-T.

    Args:
        rho_gcc:    Fuel density [g/cm³].
        T_keV:      Ion temperature [keV].
        tau_burn_ns: Burn duration [ns].

    Returns:
        dict with n_per_cc, nT_keV_per_cc, nTtau [in keV·s/m³],
        above_ignition (True/False), margin (factor above threshold).
    """
    if rho_gcc <= 0 or T_keV <= 0 or tau_burn_ns <= 0:
        return {
            "n_per_cc": 0.0, "nT_keV_per_cc": 0.0,
            "nTtau_keVs_per_m3": 0.0,
            "above_ignition": False, "margin": 0.0,
        }
    n_per_cc = rho_gcc * N_AVOGADRO / MOLAR_MASS_DT
    nT_keV_per_cc = n_per_cc * T_keV
    # nTτ in SI: nT [atoms/cm³ * keV] * τ [s] = nTτ [atoms·keV·s/cm³]
    # Convert to m³: multiply by 1e6 (since 1 m³ = 1e6 cm³)
    nTtau_keVs_per_m3 = nT_keV_per_cc * tau_burn_ns * 1e-9 * 1e6
    threshold = 3e21  # keV·s/m³ (Lawson ignition criterion for D-T)
    margin = nTtau_keVs_per_m3 / threshold if threshold > 0 else 0.0
    return {
        "n_per_cc": float(n_per_cc),
        "nT_keV_per_cc": float(nT_keV_per_cc),
        "nTtau_keVs_per_m3": float(nTtau_keVs_per_m3),
        "above_ignition": bool(nTtau_keVs_per_m3 >= threshold),
        "margin": float(margin),
    }
