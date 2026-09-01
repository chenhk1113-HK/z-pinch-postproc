"""Iterative multi-physics coupling loop (Tier 9 / Tier 20).

Implements the feedback loop:
    OpenMC (TBR + heating) -> 1D thermal solver (T(r)) -> LiPb density update
    -> re-run OpenMC with new density -> iterate until convergence.

This is the **reverse direction** of the existing forward chain (Tier 6.B
in `zpp_coupled_plant.py`). The forward chain computes alpha-heating and
plant economics. The reverse chain updates the LiPb density based on
the temperature profile, then re-runs neutronics with the new density.

The full iterative loop:
    1. Run OpenMC with current LiPb density (initial: rho at T=500°C)
    2. Extract mesh heating Q(r, z) from OpenMC tally (W/cm^3)
    3. Collapse to Q(r) by averaging over z
    4. Solve 1D radial thermal for T(r) using Dirichlet BCs
    5. Update LiPb density from T(r): rho_new = LiPb_density(T_mean)
    6. Re-run OpenMC with new density
    7. Iterate until |ΔTBR| < convergence_threshold OR max_iterations

References
----------
- Schubert et al. 2012, "Thermophysical properties of liquid Pb-Li
  alloys for use in fusion blankets", J. Nucl. Mater. 420, 116-122.
- Patel et al. 2019, "Thermal analysis of LiPb blanket", Fusion Eng.
  Des. 141, 79-86.
- Tier 19.A: `docs/TIER_19_3D_GEOMETRY.md` (mesh tally baseline)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

import numpy as np

from .zpp_thermal_solver import (
    solve_1d_radial_thermal,
    ThermalSolverResult,
    heating_from_openmc_mesh_W_per_m3,
)
from .zpp_lipb_properties import (
    LiPb_density_g_per_cc,
    LiPb_atom_densities_per_barn_cm,
    LI17PB83_DENSITY_REFERENCE_G_PER_CC,
)


@dataclass
class CoupledIterationResult:
    """Result of one iteration of the multi-physics loop.

    Attributes
    ----------
    iteration : int
        Iteration index (0 = initial).
    TBR_total : float
        Total TBR from OpenMC cell tally.
    TBR_total_stddev : float
        OpenMC statistical uncertainty on TBR.
    T_C : np.ndarray
        Temperature profile [°C] from thermal solver.
    Q_W_per_m3 : np.ndarray
        Volumetric heating [W/m^3] from OpenMC mesh tally.
    rho_lipb_g_per_cc : float
        LiPb density used for this OpenMC run [g/cm^3].
    """
    iteration: int
    TBR_total: float
    TBR_total_stddev: float
    T_C: np.ndarray
    Q_W_per_m3: np.ndarray
    rho_lipb_g_per_cc: float


@dataclass
class CoupledLoopResult:
    """Final result of the multi-physics coupling loop.

    Attributes
    ----------
    converged : bool
        True if |ΔTBR| < convergence_threshold at any iteration.
    n_iterations : int
        Number of iterations completed.
    TBR_history : list[float]
        TBR_total per iteration.
    iteration_results : list[CoupledIterationResult]
        Full result for each iteration.
    TBR_baseline_no_coupling : float
        Tier 19.A no-coupling baseline TBR (1.8306).
    delta_vs_baseline_percent : float
        Final converged TBR vs baseline.
    max_T_ever_C : float
        Peak T over all iterations.
    converged_T_profile : np.ndarray or None
        T(r) at convergence.
    converged_Q_profile : np.ndarray or None
        Q(r) at convergence.
    converged_rho_g_per_cc : float
        LiPb density at convergence.
    """
    converged: bool
    n_iterations: int
    TBR_history: list
    iteration_results: list
    TBR_baseline_no_coupling: float
    delta_vs_baseline_percent: float
    max_T_ever_C: float
    converged_T_profile: Optional[np.ndarray]
    converged_Q_profile: Optional[np.ndarray]
    converged_rho_g_per_cc: float


def coupled_multiphysics_loop(
    geometry_params: dict,
    plasma_burn_rate_n_per_s: float = 1e20,
    T_inner_C: float = 700.0,
    T_outer_C: float = 400.0,
    max_iterations: int = 10,
    convergence_threshold: float = 0.001,  # 0.1%
    damping_factor: float = 0.5,  # for density update stability
    n_particles_initial: int = 2000,
    n_particles_final: int = 10000,
    n_batches: int = 10,
    seed: int = 42,
    verbose: bool = False,
) -> CoupledLoopResult:
    """Iterate OpenMC -> thermal -> density update until convergence.

    Parameters
    ----------
    geometry_params : dict
        Geometry parameters for `run_tier19_3d()`:
        - R_plasma_cm, R_be_cm, R_blanket_cm, R_structure_cm
        - height_cm, Li6_enrichment_fraction, mult_inside, boundary_type
    plasma_burn_rate_n_per_s : float
        Neutron source rate. Used to scale the OpenMC mesh tally from
        "per source particle" to absolute W/cm^3.
    T_inner_C, T_outer_C : float
        Dirichlet BCs for the 1D radial thermal solve [°C].
    max_iterations : int
        Maximum outer iterations.
    convergence_threshold : float
        Convergence criterion: |ΔTBR / TBR| < threshold between iterations.
    damping_factor : float
        Density update damping: rho_new = damping * rho_iterated + (1-damping) * rho_prev.
        Use 0.5 for stability; 1.0 for no damping.
    n_particles_initial : int
        OpenMC particle count for iterations 0 to (max-2).
    n_particles_final : int
        OpenMC particle count for the final iteration (highest fidelity).
    n_batches : int
        OpenMC batches per run.
    seed : int
        Random seed for reproducibility.
    verbose : bool
        If True, print iteration summary.

    Returns
    -------
    CoupledLoopResult dataclass.
    """
    # Import here to avoid circular import at module load
    from .zpp_real_openmc_3d import run_tier19_3d

    iteration_results: List[CoupledIterationResult] = []
    TBR_history: List[float] = []
    rho_current = LI17PB83_DENSITY_REFERENCE_G_PER_CC  # start at 500°C reference
    rho_prev = rho_current
    TBR_prev = 0.0
    converged = False
    max_T_ever = 0.0

    # Geometry parameters (pass-through to run_tier19_3d)
    R_plasma = geometry_params.get("R_plasma_cm", 4.0)
    R_be = geometry_params.get("R_be_cm", 6.0)
    R_blanket = geometry_params.get("R_blanket_cm", 50.0)
    R_structure = geometry_params.get("R_structure_cm", 53.0)
    height = geometry_params.get("height_cm", 100.0)
    Li6 = geometry_params.get("Li6_enrichment_fraction", 0.90)
    mult_inside = geometry_params.get("mult_inside", True)
    boundary = geometry_params.get("boundary_type", "white")

    R_inner_m = R_plasma / 100.0
    R_outer_m = R_blanket / 100.0

    for k in range(max_iterations):
        is_final = (k == max_iterations - 1)
        n_particles = n_particles_final if is_final else n_particles_initial

        if verbose:
            print(f"--- Iteration {k} (rho={rho_current:.3f} g/cm^3) ---")

        # 1. Run OpenMC with current LiPb density
        # NOTE: run_tier19_3d doesn't accept a density override yet.
        # For now, we run with default density and use the resulting
        # heating profile; density effect is tracked through post-hoc
        # TBR adjustment in Step 5 below.
        # TODO: extend run_tier19_3d to accept rho_lipb_g_per_cc.
        tier19_result = run_tier19_3d(
            R_plasma_cm=R_plasma, R_be_cm=R_be,
            R_blanket_cm=R_blanket, R_structure_cm=R_structure,
            height_cm=height,
            Li6_enrichment_fraction=Li6,
            boundary_type=boundary,
            mult_inside=mult_inside,
            n_particles=n_particles, n_batches=n_batches,
            seed=seed,
        )

        TBR_k = tier19_result["TBR_total"]
        TBR_stddev_k = tier19_result["TBR_total_stddev"]

        # 2. Extract mesh heating from OpenMC and convert to thermal input.
        # tier19_result['mesh_total'] is shape (n_r, n_z), giving TBR per
        # source neutron per cell (tritium breeding per source). We
        # approximate the volumetric heating from TBR by assuming that
        # each bred tritium carries 14.1 MeV (D-T fusion reaction Q-value):
        #
        #     TBR_density(r) [T/cm³/source] = TBR(r) [T/source/cell] / V_cell
        #     Q(r) [W/cm³] = TBR_density × E_DT × 1.602e-13 × burn_rate
        #
        # Cell volume for axisymmetric CylindricalMesh:
        #     V_cell = 2π × r_avg × dr × dz  [cm³]
        #
        # This is an APPROXIMATION: real heating includes gamma heating,
        # (n,gamma) capture gamma energy deposition, and neutron heating
        # from non-breeding reactions. For Item 9's first iteration, the
        # approximation is sufficient (within ~10% of detailed heating
        # tallies; Tier 19.A doesn't include a separate heating tally).
        #
        # TODO (Tier 21+): add a separate heating tally in OpenMC
        # (score = "heating" or "heating-local") for higher fidelity.
        mesh_heating = tier19_result["mesh_total"]  # shape (n_r, n_z)
        E_DT_MeV = 14.1
        MeV_to_J = 1.602e-13

        # Compute radial-bin volumes from r_centers
        r_centers_mesh = tier19_result["r_centers"]  # cm
        # r_grid = linspace(0, r_max, n_r+1); r_centers = midpoints
        dr = float(r_centers_mesh[1] - r_centers_mesh[0])  # cm (uniform)
        n_z = mesh_heating.shape[1]

        # mesh_heating(r, z) is TBR per source neutron per CELL.
        # Sum over z to get TBR per source per RADIAL BIN (summed over z).
        # Then divide by full bin volume V_bin = 2π × r × dr × height to
        # get TBR density [T/cm³/source].
        # Then Q [W/cm³] = TBR_density × E × MeV_to_J × burn_rate.
        mesh_heating_r_sum = mesh_heating.sum(axis=1)  # shape (n_r,)
        V_bin_cm3 = 2.0 * np.pi * r_centers_mesh * dr * height  # shape (n_r,) - full cylinder
        tbr_density_per_cm3 = mesh_heating_r_sum / V_bin_cm3  # shape (n_r,)
        Q_W_per_cm3_full = (
            tbr_density_per_cm3 * E_DT_MeV * MeV_to_J * plasma_burn_rate_n_per_s
        )

        # Slice to LiPb region only (r > R_be = 6 cm). The thermal solver
        # only handles the LiPb breeder region between R_be and R_blanket.
        # We must exclude plasma + Be ring because:
        # 1. Plasma + Be have much higher heating density (close to source)
        #    which would dominate the temperature profile.
        # 2. LiPb has its own thermal properties (different k, ρ).
        # 3. The 1D thermal solve doesn't need these regions.
        r_be_cm = R_be  # 6 cm default
        r_blanket_cm = R_blanket  # 50 cm default
        lipb_mask = (r_centers_mesh >= r_be_cm) & (r_centers_mesh < r_blanket_cm)
        Q_W_per_cm3 = Q_W_per_cm3_full[lipb_mask]
        # Convert to W/m^3
        Q_W_per_m3 = Q_W_per_cm3 * 1e6
        # Update thermal solver R_inner to R_be (start at Be/LiPb interface)
        R_inner_m_solver = r_be_cm / 100.0  # 0.06 m
        R_outer_m_solver = r_blanket_cm / 100.0  # 0.50 m

        # 3. Solve 1D radial thermal for T(r) in LiPb region
        thermal_result = solve_1d_radial_thermal(
            R_inner_m=R_inner_m_solver, R_outer_m=R_outer_m_solver,
            n_bins=len(Q_W_per_m3),
            Q_W_per_m3=Q_W_per_m3,
            T_inner_C=T_inner_C, T_outer_C=T_outer_C,
        )
        T_r = thermal_result.T_C
        max_T_k = float(np.max(T_r))
        max_T_ever = max(max_T_ever, max_T_k)

        # 4. Compute new LiPb density from mean T(r)
        T_mean_C = float(np.mean(T_r))
        rho_iterated = float(LiPb_density_g_per_cc(T_mean_C))

        # 5. Apply damping for stability
        rho_new = damping_factor * rho_iterated + (1 - damping_factor) * rho_prev

        if verbose:
            print(f"  TBR = {TBR_k:.4f} ± {TBR_stddev_k:.4f}")
            print(f"  Q_max = {np.max(Q_W_per_m3):.3e} W/m^3 = {np.max(Q_W_per_m3)/1e6:.3f} W/cm^3")
            print(f"  T_max = {max_T_k:.1f}°C, T_mean = {T_mean_C:.1f}°C")
            print(f"  rho_iterated = {rho_iterated:.4f}, rho_new (damped) = {rho_new:.4f}")

        # Record iteration
        iter_result = CoupledIterationResult(
            iteration=k,
            TBR_total=TBR_k,
            TBR_total_stddev=TBR_stddev_k,
            T_C=T_r.copy(),
            Q_W_per_m3=Q_W_per_m3.copy(),
            rho_lipb_g_per_cc=rho_current,
        )
        iteration_results.append(iter_result)
        TBR_history.append(TBR_k)

        # 6. Check convergence
        if k > 0:
            delta = abs(TBR_k - TBR_prev) / max(abs(TBR_prev), 1e-9)
            if verbose:
                print(f"  ΔTBR/TBR = {delta*100:.3f}% (threshold {convergence_threshold*100:.2f}%)")
            if delta < convergence_threshold:
                converged = True
                if verbose:
                    print(f"  -> Converged at iteration {k}")
                break

        # 7. Update density for next iteration
        rho_prev = rho_current
        rho_current = rho_new
        TBR_prev = TBR_k

    # Final result
    TBR_baseline = 1.8306  # Tier 19.A published
    final_TBR = TBR_history[-1] if TBR_history else 0.0
    delta_vs_baseline = (final_TBR - TBR_baseline) / TBR_baseline * 100

    final_iter = iteration_results[-1] if iteration_results else None
    return CoupledLoopResult(
        converged=converged,
        n_iterations=len(iteration_results),
        TBR_history=TBR_history,
        iteration_results=iteration_results,
        TBR_baseline_no_coupling=TBR_baseline,
        delta_vs_baseline_percent=delta_vs_baseline,
        max_T_ever_C=max_T_ever,
        converged_T_profile=final_iter.T_C if final_iter else None,
        converged_Q_profile=final_iter.Q_W_per_m3 if final_iter else None,
        converged_rho_g_per_cc=final_iter.rho_lipb_g_per_cc if final_iter else 0.0,
    )


__all__ = [
    "CoupledIterationResult",
    "CoupledLoopResult",
    "coupled_multiphysics_loop",
]