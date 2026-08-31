"""
Sensitivity analysis for the integrated ZN plant simulation.

Tier 5.A wired BOP × TBR × geometry × LCOE. Tier 5.C quantifies
which inputs have the most impact on the outputs.

Two methods:
1. **OAT (one-at-a-time) tornado**: perturb each input ±10% and
   measure the % change in each output. Produces a ranked list of
   "what matters most" for each output.
2. **Sobol indices** (variance-based): compute first-order S_i and
   total-effect S_Ti for each input using Saltelli sampling and
   the Jansen estimator. More rigorous but requires ~256+ samples.

For a scoping study, the OAT tornado is usually sufficient. Sobol
is provided for rigorous design optimization.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable
import numpy as np

from zpp.zpp_plant_simulation import (
    PlantDesign, simulate_plant, PlantSimulationResult,
)
from zpp.zpp_comparison import (
    ZN_DESIGN, ConceptParameters,
)


@dataclass
class TornadoEntry:
    """One bar in a tornado chart."""
    param_name: str
    base_value: float
    low_value: float        # value at -10% perturbation
    high_value: float       # value at +10% perturbation
    low_output: float       # output at low_value
    high_output: float      # output at high_value
    base_output: float      # output at base_value
    sensitivity_pct: float  # max(%change_low, %change_high)
    rank: int = 0

    @property
    def swing(self) -> float:
        """Absolute swing in output from low to high perturbation."""
        return abs(self.high_output - self.low_output)


def tornado_analysis(
    output_name: str,
    base_design: PlantDesign,
    concept: ConceptParameters = None,
    perturbation_frac: float = 0.10,
    param_overrides: dict = None,
    nameplate_MW: float = 100.0,
    capacity_factor: float = 0.25,
) -> list:
    """One-at-a-time tornado analysis for one output.

    For each numeric parameter in PlantDesign, perturb by ±perturbation_frac,
    run the simulation, and compute the % change in the chosen output.

    Args:
        output_name: Which output to analyse. One of:
            - "TBR"
            - "eta_E_plant"
            - "LCOE_USD_per_MWh"
            - "P_net_electric_MW"
            - "tritium_self_sufficient" (bool)
            - "LCOE_above_break_even" (bool)
            - "meets_TBR_threshold" (bool)
            - "meets_LCOE_target" (bool)
            - "meets_commercial_power" (bool)
        base_design: Baseline PlantDesign.
        concept: Fusion concept (default ZN_DESIGN).
        perturbation_frac: Fraction to perturb each param (default 0.10).
        param_overrides: Dict of {param_name: [low, base, high]} for
            non-default variations. Default: use perturbation_frac.
        nameplate_MW, capacity_factor: Plant sizing.

    Returns:
        list of TornadoEntry, sorted by sensitivity descending.
    """
    if concept is None:
        concept = ZN_DESIGN
    # 1. Base run
    base_result = simulate_plant(concept, base_design, nameplate_MW, capacity_factor)
    base_output = _get_output(base_result, output_name)
    # 2. Identify numeric fields in PlantDesign
    numeric_fields = [
        f.name for f in base_design.__dataclass_fields__.values()
        if f.name not in ("name", "cycle", "geometry_name",
                          "blanket_material", "neutron_multiplier")
        and isinstance(getattr(base_design, f.name), (int, float))
        and not isinstance(getattr(base_design, f.name), bool)
    ]
    entries = []
    for param in numeric_fields:
        base_value = float(getattr(base_design, param))
        if base_value == 0:
            continue
        low_value = base_value * (1 - perturbation_frac)
        high_value = base_value * (1 + perturbation_frac)
        if param_overrides and param in param_overrides:
            low_value, base_value, high_value = param_overrides[param]
        # Low perturbation
        design_low = _replace_field(base_design, param, low_value)
        result_low = simulate_plant(concept, design_low, nameplate_MW, capacity_factor)
        output_low = _get_output(result_low, output_name)
        # High perturbation
        design_high = _replace_field(base_design, param, high_value)
        result_high = simulate_plant(concept, design_high, nameplate_MW, capacity_factor)
        output_high = _get_output(result_high, output_name)
        # Compute sensitivity
        if isinstance(base_output, bool):
            sens_pct = 0.0
        elif base_output == 0:
            sens_pct = max(abs(output_low), abs(output_high))
        elif base_output == float("inf") or base_output == float("-inf"):
            # Both inf -> no sensitivity
            if output_low == float("inf") and output_high == float("inf"):
                sens_pct = 0.0
            else:
                sens_pct = 100.0  # perturbs away from inf
        else:
            low_change = abs((output_low - base_output) / base_output) * 100
            high_change = abs((output_high - base_output) / base_output) * 100
            sens_pct = max(low_change, high_change)
        entries.append(TornadoEntry(
            param_name=param,
            base_value=base_value,
            low_value=low_value,
            high_value=high_value,
            low_output=output_low,
            high_output=output_high,
            base_output=base_output,
            sensitivity_pct=sens_pct,
        ))
    # Sort by sensitivity descending
    entries.sort(key=lambda e: e.sensitivity_pct, reverse=True)
    for i, e in enumerate(entries):
        e.rank = i + 1
    return entries


def tornado_markdown(entries: list, output_name: str) -> str:
    """Format a tornado as Markdown."""
    headers = ["Rank", "Param", "Base", "Low", "High", "Base Out", "Low Out", "High Out", "Sens (%)"]
    lines = [
        f"# Tornado: {output_name}\n",
        "| " + " | ".join(headers) + " |",
        "|" + "|".join(["---"] * len(headers)) + "|",
    ]
    for e in entries:
        lines.append("| " + " | ".join([
            str(e.rank), e.param_name,
            f"{e.base_value:.4g}", f"{e.low_value:.4g}", f"{e.high_value:.4g}",
            _fmt(e.base_output), _fmt(e.low_output), _fmt(e.high_output),
            f"{e.sensitivity_pct:.2f}",
        ]) + " |")
    return "\n".join(lines)


def _fmt(x) -> str:
    if isinstance(x, bool):
        return str(x)
    if isinstance(x, float) and (x == float("inf") or x == float("-inf")):
        return "inf"
    if isinstance(x, float):
        return f"{x:.4g}"
    return str(x)


def _get_output(result: PlantSimulationResult, output_name: str):
    """Get an output attribute by name."""
    return getattr(result, output_name)


def _replace_field(obj, field_name: str, new_value):
    """Return a copy of obj with field_name replaced."""
    from dataclasses import replace
    return replace(obj, **{field_name: new_value})


# ---------------------------------------------------------------------------
# Sobol indices (variance-based sensitivity)
# ---------------------------------------------------------------------------
# Saltelli's sampling scheme: N (N+2k) samples for k params.
# Jansen estimator for first-order S_i and total S_Ti.
# Reference: Saltelli et al. (2010) Computer Physics Communications 181 259.

def saltelli_sample(
    bounds: list,
    n_samples: int,
    seed: int = None,
) -> tuple:
    """Saltelli's scheme for Sobol analysis.

    Returns:
        (A, B, AB) where:
        - A: matrix of n_samples × k params
        - B: matrix of n_samples × k params (independent of A)
        - AB[i]: A with column i replaced by B's column i
    """
    rng = np.random.default_rng(seed)
    k = len(bounds)
    A = np.zeros((n_samples, k))
    B = np.zeros((n_samples, k))
    for j in range(k):
        low, high = bounds[j]
        A[:, j] = rng.uniform(low, high, n_samples)
        B[:, j] = rng.uniform(low, high, n_samples)
    AB = [A.copy() for _ in range(k)]
    for i in range(k):
        AB[i][:, i] = B[:, i]
    return A, B, AB


def sobol_indices(
    evaluate: Callable,
    bounds: list,
    n_samples: int = 256,
    seed: int = 42,
) -> dict:
    """Compute first-order S_i and total S_Ti Sobol indices.

    Args:
        evaluate: Function that takes a 1D array of parameter values
            and returns a scalar output.
        bounds: List of [low, high] for each parameter.
        n_samples: Number of base samples (total: n*(k+2) evaluations).
        seed: RNG seed for reproducibility.

    Returns:
        dict with:
            - "S_i": first-order indices (k,)
            - "S_Ti": total-effect indices (k,)
            - "param_names": if passed via evaluate signature
            - "n_evaluations": int (total evaluations)
    """
    k = len(bounds)
    A, B, AB = saltelli_sample(bounds, n_samples, seed)
    # Evaluate
    Y_A = np.array([evaluate(A[i]) for i in range(n_samples)])
    Y_B = np.array([evaluate(B[i]) for i in range(n_samples)])
    Y_AB = np.zeros((n_samples, k))
    for i in range(k):
        Y_AB[:, i] = np.array([evaluate(AB[i][j]) for j in range(n_samples)])
    # Variance
    Y_combined = np.concatenate([Y_A, Y_B])
    var_Y = np.var(Y_combined, ddof=1)
    # First-order S_i (Saltelli 2010 Eq. (b))
    S_i = np.zeros(k)
    for i in range(k):
        S_i[i] = np.mean(Y_B * (Y_AB[:, i] - Y_A)) / var_Y
    # Total S_Ti (Jansen estimator)
    S_Ti = np.zeros(k)
    for i in range(k):
        S_Ti[i] = 0.5 * np.mean((Y_A - Y_AB[:, i]) ** 2) / var_Y
    return {
        "S_i": S_i,
        "S_Ti": S_Ti,
        "var_Y": var_Y,
        "n_evaluations": (k + 2) * n_samples,
        "n_samples": n_samples,
        "param_names": None,
    }
