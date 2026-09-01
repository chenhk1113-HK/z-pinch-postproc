"""1D radial thermal solver for LiPb breeder (Tier 9 / Tier 20 multi-physics).

Solves the steady-state cylindrical heat equation for temperature T(r)
in the LiPb breeder region between R_inner (=R_plasma) and R_outer
(=R_blanket):

    (1/r) d/dr ( r * k(T) * dT/dr ) + Q(r) = 0

where:
    k(T) = LiPb thermal conductivity [W/m/K] (Schubert 2012)
    Q(r) = volumetric heating [W/cm^3] (from OpenMC tally)

Boundary conditions: Dirichlet at both ends
    T(R_inner) = T_inner
    T(R_outer) = T_outer

The solver uses second-order finite differences on a uniform radial
mesh and the Thomas algorithm (tridiagonal matrix solver) for O(N)
solution.

Assumptions:
- Steady-state (no transient term; quasi-static coupling)
- 1D radial (axial profile assumed uniform — Z-pinch has reflective
  symmetry in z for the central blanket region)
- k(T) varies linearly with T (Schubert 2012 fit), but for the solver
  we use k evaluated at the reference temperature (500°C) as a constant.
  Iterative nonlinear solve is unnecessary at this fidelity.

References
----------
- Incropera & DeWitt 2002, "Fundamentals of Heat and Mass Transfer",
  5th ed., Wiley. Chapter 4 (cylindrical conduction).
- Patel et al. 2019, "Thermal analysis of LiPb blanket", Fusion Eng.
  Des. 141, 79-86 (validation of cylindrical thermal model).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .zpp_lipb_properties import LiPb_thermal_conductivity_W_per_mK


@dataclass
class ThermalSolverResult:
    """Output of the 1D radial thermal solver.

    Attributes
    ----------
    r_centers_m : np.ndarray
        Radial cell centers [m]. Shape (n_bins,).
    T_C : np.ndarray
        Temperature at each radial cell [°C]. Shape (n_bins,).
    Q_W_per_m3 : np.ndarray
        Volumetric heating at each radial cell [W/m^3]. Shape (n_bins,).
    T_inner_C : float
        Temperature at R_inner (=R_plasma) [°C].
    T_outer_C : float
        Temperature at R_outer (=R_blanket) [°C].
    k_W_per_mK : np.ndarray
        Thermal conductivity used at each cell [W/m/K].
    max_T_C : float
        Peak temperature in the LiPb breeder [°C].
    max_T_r_m : float
        Radial location of peak temperature [m].
    """
    r_centers_m: np.ndarray
    T_C: np.ndarray
    Q_W_per_m3: np.ndarray
    T_inner_C: float
    T_outer_C: float
    k_W_per_mK: np.ndarray
    max_T_C: float
    max_T_r_m: float


def solve_1d_radial_thermal(
    R_inner_m: float,
    R_outer_m: float,
    n_bins: int,
    Q_W_per_m3: np.ndarray | None,
    T_inner_C: float,
    T_outer_C: float,
    k_T_inner_W_per_mK: float | None = None,
    k_T_outer_W_per_mK: float | None = None,
) -> ThermalSolverResult:
    """Solve 1D radial steady-state heat equation in cylindrical LiPb.

    Equation: (1/r) d/dr (r * k * dT/dr) + Q(r) = 0
    BCs: T(R_inner) = T_inner, T(R_outer) = T_outer

    Parameters
    ----------
    R_inner_m : float
        Inner radius (plasma-facing) [m]. Typically R_plasma = 0.04 m.
    R_outer_m : float
        Outer radius (blanket/structure interface) [m]. Typically
        R_blanket = 0.50 m.
    n_bins : int
        Number of radial bins (same as Tier 19.A CylindricalMesh
        = 30).
    Q_W_per_m3 : np.ndarray or None
        Volumetric heating at each radial cell [W/m^3]. Shape
        (n_bins,). If None, uses Q=0 (zero heating — pure conduction
        from boundary T_inner to T_outer).
    T_inner_C : float
        Dirichlet BC at R_inner [°C]. Typical value: 600-800°C
        (plasma-facing wall temperature).
    T_outer_C : float
        Dirichlet BC at R_outer [°C]. Typical value: 400-500°C
        (RAFM structure interface temperature).
    k_T_inner_W_per_mK : float or None
        Thermal conductivity at T_inner [W/m/K]. If None, uses
        Schubert 2012 linear fit evaluated at T_inner.
    k_T_outer_W_per_mK : float or None
        Thermal conductivity at T_outer [W/m/K]. If None, uses
        Schubert 2012 linear fit evaluated at T_outer.

    Returns
    -------
    ThermalSolverResult dataclass with T(r) profile + diagnostics.

    Notes
    -----
    The thermal conductivity is taken as a piecewise-constant average
    of k(T_inner) and k(T_outer). This is a standard approximation for
    LiPb at operating temperatures (250-700°C), where k varies by
    only ~30% across the range.
    """
    if R_inner_m >= R_outer_m:
        raise ValueError(f"R_inner_m ({R_inner_m}) must be < R_outer_m ({R_outer_m})")
    if n_bins < 3:
        raise ValueError(f"n_bins must be >= 3, got {n_bins}")

    # Default k(T) values
    if k_T_inner_W_per_mK is None:
        k_T_inner_W_per_mK = float(LiPb_thermal_conductivity_W_per_mK(T_inner_C))
    if k_T_outer_W_per_mK is None:
        k_T_outer_W_per_mK = float(LiPb_thermal_conductivity_W_per_mK(T_outer_C))

    # Use average k for the entire breeder (piecewise-constant approximation)
    k_avg = 0.5 * (k_T_inner_W_per_mK + k_T_outer_W_per_mK)

    if Q_W_per_m3 is None:
        Q_W_per_m3 = np.zeros(n_bins)
    Q_W_per_m3 = np.asarray(Q_W_per_m3, dtype=float)
    if Q_W_per_m3.shape != (n_bins,):
        raise ValueError(
            f"Q_W_per_m3 shape {Q_W_per_m3.shape} != ({n_bins},)"
        )

    # Radial mesh (cell centers, uniform spacing)
    r_edges = np.linspace(R_inner_m, R_outer_m, n_bins + 1)
    r_centers = 0.5 * (r_edges[1:] + r_edges[:-1])
    dr = r_edges[1] - r_edges[0]

    # Discretize using conservative form (Incropera & DeWitt 2002 §4.2):
    #   (1/r) d/dr (r * k * dT/dr) + Q = 0
    #
    # Conservative finite-difference on uniform mesh:
    #   [ r_{i+1/2} * (T_{i+1} - T_i) - r_{i-1/2} * (T_i - T_{i-1}) ] / (r_i * dr) = -Q_i
    #
    # where r_{i±1/2} = r_i ± dr/2 (cell faces).
    #
    # Multiply through by r_i:
    #   r_{i+1/2} * T_{i+1} - (r_{i+1/2} + r_{i-1/2}) * T_i + r_{i-1/2} * T_{i-1} = -Q_i * r_i * dr
    #
    # Note r_{i+1/2} + r_{i-1/2} = 2 * r_i. So:
    #   T_{i-1} * (r_{i-1/2}) - 2*r_i * T_i + T_{i+1} * (r_{i+1/2}) = -Q_i * r_i * dr
    #
    # Coefficients: a_i = r_{i-1/2}, b_i = -2*r_i, c_i = r_{i+1/2}, rhs = -Q_i * r_i * dr
    a = np.zeros(n_bins)
    b = np.zeros(n_bins)
    c = np.zeros(n_bins)
    rhs = np.zeros(n_bins)

    for i in range(n_bins):
        r_i = r_centers[i]
        r_minus_half = r_i - dr / 2.0  # r_{i-1/2}
        r_plus_half = r_i + dr / 2.0   # r_{i+1/2}
        # Coefficients include k (the thermal conductivity must multiply
        # the divergence terms; for the conservative discretization:
        #   a[i] = k * r_{i-1/2}, b[i] = -2*k*r_i, c[i] = k * r_{i+1/2}
        a[i] = k_avg * r_minus_half
        b[i] = -2.0 * k_avg * r_i
        c[i] = k_avg * r_plus_half
        rhs[i] = -Q_W_per_m3[i] * r_i * dr ** 2

    # Boundary conditions: T(R_inner) = T_inner and T(R_outer) = T_outer
    # are enforced at the cell FACES using ghost-cell approach.
    #
    # Inner BC at r=R_inner (face of cell 0):
    #   Ghost cell at i=-1: T_{-1} = 2*T_inner - T[0]
    #   Substitute into cell 0's equation:
    #     a[0]*(2*T_inner - T[0]) + b[0]*T[0] + c[0]*T[1] = rhs[0]
    #     => (b[0] - a[0])*T[0] + c[0]*T[1] = rhs[0] - 2*a[0]*T_inner
    #   Modifications: b[0] -= a[0],  rhs[0] -= 2*a[0]*T_inner
    #
    # Outer BC at r=R_outer (face of cell n-1):
    #   Ghost cell at i=n: T_n = 2*T_outer - T[n-1]
    #   Substitute into cell n-1's equation:
    #     a[n-1]*T[n-2] + b[n-1]*T[n-1] + c[n-1]*(2*T_outer - T[n-1]) = rhs[n-1]
    #     => a[n-1]*T[n-2] + (b[n-1] - c[n-1])*T[n-1] = rhs[n-1] - 2*c[n-1]*T_outer
    #   Modifications: b[n-1] -= c[n-1],  rhs[n-1] -= 2*c[n-1]*T_outer
    b[0] -= a[0]
    rhs[0] -= 2.0 * a[0] * T_inner_C
    b[n_bins - 1] -= c[n_bins - 1]
    rhs[n_bins - 1] -= 2.0 * c[n_bins - 1] * T_outer_C

    # Now solve the full n x n tridiagonal system for T[0..n-1].
    T_solution = _thomas_algorithm(a, b, c, rhs)
    T_full = T_solution

    # Find peak temperature
    i_max = int(np.argmax(T_full))
    max_T = float(T_full[i_max])
    max_T_r = float(r_centers[i_max])

    # k used at each cell (constant = k_avg for this solver)
    k_array = np.full(n_bins, k_avg)

    return ThermalSolverResult(
        r_centers_m=r_centers,
        T_C=T_full,
        Q_W_per_m3=Q_W_per_m3,
        T_inner_C=T_inner_C,
        T_outer_C=T_outer_C,
        k_W_per_mK=k_array,
        max_T_C=max_T,
        max_T_r_m=max_T_r,
    )


def _thomas_algorithm(a: np.ndarray, b: np.ndarray, c: np.ndarray,
                      d: np.ndarray) -> np.ndarray:
    """Solve tridiagonal system Ax = d using Thomas algorithm.

    A has sub-diagonal a, diagonal b, super-diagonal c. All length N.
    """
    n = len(b)
    c_ = np.zeros(n)
    d_ = np.zeros(n)
    x = np.zeros(n)

    c_[0] = c[0] / b[0]
    d_[0] = d[0] / b[0]
    for i in range(1, n):
        denom = b[i] - a[i] * c_[i - 1]
        c_[i] = c[i] / denom
        d_[i] = (d[i] - a[i] * d_[i - 1]) / denom

    x[n - 1] = d_[n - 1]
    for i in range(n - 2, -1, -1):
        x[i] = d_[i] - c_[i] * x[i + 1]

    return x


# ============================================================================
# Convenience wrapper: convert OpenMC mesh heating (W/cm^3) to thermal input
# ============================================================================

def heating_from_openmc_mesh_W_per_m3(
    mesh_tally_W_per_cm3_per_axial_bin: np.ndarray,
    n_axial_bins: int = 30,
    z_half_height_m: float = 0.5,
) -> np.ndarray:
    """Convert OpenMC cylindrical-mesh heating to per-radial-bin W/m^3.

    OpenMC CylindricalMesh tally gives Q(r, z) in W/cm^3 (or per source
    particle depending on normalization). For 1D radial thermal solve,
    we collapse the axial bins to get Q(r) = average over z.

    Parameters
    ----------
    mesh_tally_W_per_cm3_per_axial_bin : np.ndarray
        Shape (n_r, n_axial). OpenMC cylindrical-mesh heating per cell.
    n_axial_bins : int
        Number of axial bins (default 30, matches Tier 19.A).
    z_half_height_m : float
        Half-height of the mesh in meters. Default 0.5 (= 50 cm half-height).

    Returns
    -------
    Q_W_per_m3 : np.ndarray
        Shape (n_r,). Volumetric heating in W/m^3 (after axial collapse).
        To get W/cm^3, divide by 1e6.
    """
    if mesh_tally_W_per_cm3_per_axial_bin.ndim != 2:
        raise ValueError(
            f"mesh_tally shape {mesh_tally_W_per_cm3_per_axial_bin.shape} "
            "must be 2D (n_r, n_axial)"
        )
    # Axial collapse (simple mean)
    Q_W_per_cm3 = mesh_tally_W_per_cm3_per_axial_bin.mean(axis=1)
    # Convert W/cm^3 -> W/m^3
    return Q_W_per_cm3 * 1e6


# ============================================================================
# Module-level exports
# ============================================================================
__all__ = [
    "ThermalSolverResult",
    "solve_1d_radial_thermal",
    "heating_from_openmc_mesh_W_per_m3",
]