"""
Uncertainty quantification via Monte Carlo propagation.

Tier 5.C provides local (tornado) and variance-based (Sobol)
sensitivity analysis. This module adds **Monte Carlo
propagation** which is the gold standard for end-to-end
uncertainty quantification in parametric models.

Approach:
1. Define a list of uncertain parameters with mean and
   stddev (or interval).
2. Sample N parameter sets from the joint distribution
   (default: independent normals truncated to physical bounds).
3. Run end-to-end ZN plant simulation for each sample.
4. Aggregate outputs (TBR, LCOE, P_net) into distributions.
5. Report mean, stddev, percentiles, probability of meeting
   thresholds.

References:
- Helton et al. 2006 (sampling-based UQ for complex models).
- Sobol 2001 (global sensitivity indices).
- Saltelli et al. 2008 (best practices for MC sampling).
"""

import statistics
from dataclasses import dataclass, field

import numpy as np

from zpp_plant_simulation import simulate_plant, PlantDesign
from zpp_comparison import ZN_DESIGN
from zpp_tbr import TBRInputs, compute_TBR


@dataclass
class UncertainParameter:
    """Definition of an uncertain input parameter."""
    name: str
    nominal: float
    stddev: float
    lower_bound: float | None = None
    upper_bound: float | None = None
    distribution: str = "normal"  # 'normal', 'uniform', 'triangular'


@dataclass
class UQResult:
    """Result of Monte Carlo uncertainty propagation."""
    n_samples: int
    random_seed: int
    TBR_mean: float
    TBR_std: float
    TBR_percentiles: dict  # key: percentile (5, 50, 95, 99), value: TBR
    LCOE_mean: float | None  # None if always infinite
    LCOE_std: float | None
    n_below_break_even: int  # number of samples with LCOE=inf
    n_above_TBR_threshold: int  # number with TBR >= 1.05
    parameter_samples: dict = field(default_factory=dict)
    output_samples: dict = field(default_factory=dict)
    notes: str = ""


# Default uncertain parameters for ZN plant
DEFAULT_UNCERTAIN_PARAMS_ZN = [
    UncertainParameter(
        name="MHD_effect_factor",
        nominal=0.9,
        stddev=0.05,
        lower_bound=0.7,
        upper_bound=1.0,
    ),
    UncertainParameter(
        name="blanket_thickness_cm",
        nominal=50.0,
        stddev=5.0,
        lower_bound=30.0,
        upper_bound=100.0,
    ),
    UncertainParameter(
        name="Li6_enrichment_fraction",
        nominal=0.30,
        stddev=0.05,
        lower_bound=0.05,
        upper_bound=0.90,
    ),
    UncertainParameter(
        name="first_wall_coverage_fraction",
        nominal=0.83,
        stddev=0.05,
        lower_bound=0.5,
        upper_bound=1.0,
    ),
    UncertainParameter(
        name="T_hot_K",
        nominal=1200.0,
        stddev=50.0,
        lower_bound=900.0,
        upper_bound=1500.0,
    ),
]


def _sample_normal(rng: np.random.Generator, p: UncertainParameter) -> float:
    """Sample from a normal distribution with bounds."""
    x = rng.normal(p.nominal, p.stddev)
    if p.lower_bound is not None:
        x = max(x, p.lower_bound)
    if p.upper_bound is not None:
        x = min(x, p.upper_bound)
    return x


def _sample_uniform(rng: np.random.Generator, p: UncertainParameter) -> float:
    """Sample from a uniform distribution between lower and upper bounds."""
    lo = p.lower_bound if p.lower_bound is not None else p.nominal
    hi = p.upper_bound if p.upper_bound is not None else p.nominal
    return rng.uniform(lo, hi)


def _sample_param(rng: np.random.Generator, p: UncertainParameter) -> float:
    """Sample from the distribution specified by UncertainParameter."""
    if p.distribution == "normal":
        return _sample_normal(rng, p)
    if p.distribution == "uniform":
        return _sample_uniform(rng, p)
    # Default: normal
    return _sample_normal(rng, p)


def monte_carlo_propagation(
    uncertain_params: list[UncertainParameter],
    n_samples: int = 1000,
    random_seed: int = 42,
    nameplate_MW: float = 100.0,
) -> UQResult:
    """Run Monte Carlo propagation through the ZN plant simulation.

    Args:
        uncertain_params: list of UncertainParameter.
        n_samples: number of Monte Carlo samples.
        random_seed: RNG seed for reproducibility.
        nameplate_MW: design nameplate.

    Returns UQResult with distributions of TBR, LCOE, P_net.
    """
    rng = np.random.default_rng(random_seed)

    # Sample parameter sets
    param_samples = {p.name: [] for p in uncertain_params}
    for _ in range(n_samples):
        for p in uncertain_params:
            param_samples[p.name].append(_sample_param(rng, p))

    # Run simulation for each sample
    TBR_samples = []
    LCOE_samples = []
    P_net_samples = []
    n_below_break_even = 0
    n_above_TBR_threshold = 0
    threshold = 1.05

    base_design = ZN_DESIGN
    for i in range(n_samples):
        # Build inputs from samples
        params = {p.name: param_samples[p.name][i] for p in uncertain_params}
        # Construct TBR inputs (override defaults)
        inp = TBRInputs(
            blanket_material="LiPb",
            neutron_multiplier="Be",
            blanket_thickness_cm=params["blanket_thickness_cm"],
            Li6_enrichment_fraction=params["Li6_enrichment_fraction"],
            first_wall_coverage_fraction=params["first_wall_coverage_fraction"],
            geometry="Z-pinch",
            MHD_effect_factor=params["MHD_effect_factor"],
        )
        tbr_result = compute_TBR(inp)
        TBR_samples.append(tbr_result.TBR)

        if tbr_result.TBR >= threshold:
            n_above_TBR_threshold += 1

        # Build plant design and run coupled sim
        # Note: Q_eng from base ZN design is sub-break-even, so most
        # samples will have LCOE=inf. We still capture the result.
        plant = PlantDesign(
            name=f"sample_{i}",
            T_hot_K=params["T_hot_K"],
        )
        sim = simulate_plant(base_design, plant, nameplate_MW=nameplate_MW)
        LCOE_samples.append(sim.LCOE_USD_per_MWh)
        P_net_samples.append(sim.P_net_electric_MW)
        if sim.LCOE_above_break_even is False:
            n_below_break_even += 1

    # Aggregate statistics
    tbr_arr = np.array(TBR_samples)
    LCOE_arr = np.array(LCOE_samples)

    TBR_mean = float(np.mean(tbr_arr))
    TBR_std = float(np.std(tbr_arr))
    TBR_pct = {
        5: float(np.percentile(tbr_arr, 5)),
        50: float(np.percentile(tbr_arr, 50)),
        95: float(np.percentile(tbr_arr, 95)),
        99: float(np.percentile(tbr_arr, 99)),
    }

    # LCOE: only compute stats on finite values
    finite_mask = np.isfinite(LCOE_arr)
    if np.any(finite_mask):
        LCOE_mean = float(np.mean(LCOE_arr[finite_mask]))
        LCOE_std = float(np.std(LCOE_arr[finite_mask]))
    else:
        LCOE_mean = None
        LCOE_std = None

    return UQResult(
        n_samples=n_samples,
        random_seed=random_seed,
        TBR_mean=TBR_mean,
        TBR_std=TBR_std,
        TBR_percentiles=TBR_pct,
        LCOE_mean=LCOE_mean,
        LCOE_std=LCOE_std,
        n_below_break_even=n_below_break_even,
        n_above_TBR_threshold=n_above_TBR_threshold,
        parameter_samples=param_samples,
        output_samples={"TBR": TBR_samples, "LCOE": LCOE_samples, "P_net": P_net_samples},
        notes=f"MC propagation with {n_samples} samples; seed={random_seed}",
    )


def uq_markdown(result: UQResult) -> str:
    """Format UQResult as Markdown."""
    lines = ["# Uncertainty quantification result", ""]
    lines.append(f"- **Samples**: {result.n_samples}")
    lines.append(f"- **Random seed**: {result.random_seed}")
    lines.append("")
    lines.append("## TBR distribution")
    lines.append("")
    lines.append(f"- **Mean**: {result.TBR_mean:.4f}")
    lines.append(f"- **Std**: {result.TBR_std:.4f}")
    lines.append(f"- **5th percentile**: {result.TBR_percentiles[5]:.4f}")
    lines.append(f"- **Median**: {result.TBR_percentiles[50]:.4f}")
    lines.append(f"- **95th percentile**: {result.TBR_percentiles[95]:.4f}")
    lines.append(f"- **99th percentile**: {result.TBR_percentiles[99]:.4f}")
    lines.append(f"- **P(TBR >= 1.05)**: {result.n_above_TBR_threshold / result.n_samples:.2%}")
    lines.append("")
    lines.append("## LCOE distribution")
    lines.append("")
    if result.LCOE_mean is not None:
        lines.append(f"- **Mean (finite samples)**: ${result.LCOE_mean:.2f}/MWh")
        lines.append(f"- **Std (finite samples)**: ${result.LCOE_std:.2f}/MWh")
    else:
        lines.append("- **No samples had finite LCOE** (ZN plant is sub-break-even).")
    lines.append(f"- **Samples below break-even**: {result.n_below_break_even}/{result.n_samples}")
    lines.append("")
    lines.append("## Notes")
    lines.append("")
    lines.append(result.notes)
    return "\n".join(lines)