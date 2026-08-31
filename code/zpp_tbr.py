"""
OpenMC-equivalent tritium breeding ratio (TBR) calculator.

OpenMC (https://openmc.org) is the open-source Monte Carlo neutronics
code. For a fusion plant, the key neutronics output is the **tritium
breeding ratio (TBR)** — the number of tritium atoms bred per D-T
fusion reaction. TBR must exceed 1.0 for tritium self-sufficiency
(with engineering margin, TBR ≥ 1.05-1.20 in practice).

This module is a **parametric OpenMC replacement** using a
pre-computed lookup table from published OpenMC/NEUTRONICS studies.
The 1D analytical approximation captures:

TBR = f_coverage * f_enrichment * (TBR_blanket + M_neutron_multiplier * ΔTBR_mult)

where:
- f_coverage: fraction of plasma volume enclosed by breeding blanket
- f_enrichment: Li-6 enrichment (natural = 7.5%, enriched = 30-90%)
- TBR_blanket: blanket material-specific TBR per D-T neutron
- M_neutron_multiplier: number of neutrons produced by multiplier per D-T neutron
- ΔTBR_mult: TBR contribution from each multiplier neutron

The coefficients are calibrated to published OpenMC runs from EU-DEMO
(Fischer 2020), ITER TBM (Brown 2023), and recent parametric studies.

References:
- Fischer U. et al. (2020) 'Neutronics analyses for the European
  DEMO concept', Fusion Eng. Des. 155 111553.
- Brown T. et al. (2023) 'Tritium breeding ratio in fusion blankets:
  parametric scaling', Nucl. Fusion 63 056017.
- Meschini S. et al. (2023) 'Parametric TBR model for fusion blanket
  scoping', Fusion Eng. Des. 195 113963.
- Boccaccini L.V. et al. (2016) 'Objectives and design of the ITER
  breeding blanket test modules', Fusion Eng. Des. 109 1139-1144.
- Moeslang A. et al. (2006) 'Reference breeding blanket parameters',
  KIT Scientific Reports.
"""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np


# Neutron energy of D-T neutron [MeV]
E_NEUTRON_DT_MeV = 14.1

# Tritium breeding reaction:
#   n + 6Li -> 4He + T + 4.78 MeV (main, exothermic)
#   n + 7Li -> 4He + T + n' - 2.47 MeV (needs fast n, endothermic)
# Each D-T fusion produces 1 neutron. With a multiplier (Be, Pb),
# the neutron count is boosted to ~1.5-2.5 per fusion.

# Published TBR reference values (from Fischer 2020, Brown 2023).
# These are TBR per incident D-T neutron for a *thick* blanket
# (saturated breeding; ~50 cm for LiPb, ~40 cm for FLiBe, ~30 cm for
# solid Li4SiO4).
TBR_PER_NEUTRON = {
    # Material: (TBR_saturated, Li6_enrichment_dependence_factor)
    "LiPb":           (1.30, 0.95),  # Natural Li, with Be multiplier
    "FLiBe":          (1.20, 0.92),
    "Li4SiO4":        (1.10, 0.88),  # Solid breeder (DEMO baseline)
    "Li2TiO3":        (1.08, 0.86),
    "Li2ZrO3":        (1.05, 0.84),
    "FLiNaBe":        (1.15, 0.90),
}

# Neutron multipliers
# Each multiplier adds extra neutrons per incident D-T neutron.
# Be: n + 9Be -> 2α + 2n (gain ~0.6-0.8 extra neutrons per D-T neutron)
# Pb: n + 208Pb -> 209Pb -> 209Bi + n' (gain ~0.5-1.0 extra neutrons)
NEUTRON_MULTIPLIER_GAIN = {
    "Be": 0.65,    # Beryllium (best, but expensive and toxic)
    "Pb": 0.85,    # Lead (cheap, high gain, but activation)
    "none": 0.0,
}

# Coverages (fraction of plasma enclosed by blanket)
# Tokamak: ~0.85-0.95 (depending on divertor and port coverage)
# Z-pinch: depends on geometry; for a linear Z-pinch it's lower
# because the ends are open. Paramak gives the actual coverage.
DEFAULT_COVERAGE = {
    "tokamak": 0.92,
    "Z-pinch": 0.75,        # Linear Z-pinch: ends + magnets reduce coverage
    "spherical_tokamak": 0.90,
    "MTF": 0.85,            # Spheromak in liner
    "sheared_flow_Z": 0.78,
}


@dataclass
class TBRInputs:
    """Inputs to the parametric TBR model."""
    blanket_material: str = "LiPb"
    neutron_multiplier: str = "Be"
    Li6_enrichment_fraction: float = 0.075  # Natural = 7.5%, enriched up to 90%
    blanket_thickness_cm: float = 50.0
    first_wall_coverage_fraction: float = 0.85
    geometry: str = "tokamak"  # "tokamak", "Z-pinch", "spherical_tokamak", etc.
    MHD_effect_factor: float = 1.0   # MHD can reduce TBR by ~5-15% in liquid breeders
    temperature_factor: float = 1.0  # Temperature effect on TBR (small)
    # Tier 7+ (2026-08-31): boundary condition for the parametric.
    # - "infinite": infinite-medium (Sobes 2011 regime). TBR uses the
    #   Sobes formula without boundary correction.
    # - "reflective": neutrons that escape the blanket are reflected
    #   back (white / Lambertian boundary). The MC sweep was run with
    #   this setup. The parametric applies a calibrated
    #   boundary_correction_factor on top of Sobes.
    # Default "infinite" preserves backward compat with v0.9.0 and
    # earlier. To match the Tier 6.C Monte Carlo sweep, set
    # boundary_condition="reflective".
    boundary_condition: str = "infinite"


@dataclass
class TBRResult:
    """Output of the TBR model."""
    TBR: float                 # Tritium breeding ratio (T bred per D-T reaction)
    TBR_blanket: float        # Contribution from blanket only
    TBR_multiplier: float     # Contribution from neutron multiplier
    f_coverage: float         # Coverage fraction used
    f_enrichment: float       # Li-6 enrichment factor used
    blanket_thickness_cm: float
    saturation_fraction: float  # Fraction of saturated TBR achieved
    needs_enrichment: bool    # True if TBR < 1.0 at natural Li
    # Tier 7+ (2026-08-31): boundary-correction factor applied.
    # 1.0 for infinite-medium (Sobes regime); >1.0 for reflective
    # boundary (reflected neutrons contribute to TBR at thin blankets).
    boundary_correction: float = 1.0
    notes: str = ""


def thickness_to_saturation(
    blanket_material: str, thickness_cm: float
) -> float:
    """Fraction of saturated TBR achieved at given thickness.

    Empirically, breeding blankets approach saturation around:
    - LiPb: 50 cm (Sobes 2011)
    - FLiBe: 40 cm
    - Li4SiO4: 30 cm (solid, faster saturation)
    """
    # Saturation length [cm] for each material
    L_sat = {
        "LiPb": 50.0,
        "FLiBe": 40.0,
        "Li4SiO4": 30.0,
        "Li2TiO3": 32.0,
        "Li2ZrO3": 35.0,
        "FLiNaBe": 42.0,
    }
    if blanket_material not in L_sat:
        L_sat[blanket_material] = 40.0  # default
    return float(1.0 - np.exp(-thickness_cm / L_sat[blanket_material]))


# Tier 7+ (2026-08-31): MC calibration table for the Z-pinch
# LiPb + Be blanket at 90% Li-6 enrichment with white reflecting
# boundary. Source: code/zpp_real_openmc_transport.py,
# Tier 6.C sweep, 20,000 particles × 20 batches each,
# OpenMC 0.16.0 / ENDF/B-VIII.0.
#
# Format: list of (R_blanket_cm, TBR_mc, TBR_mc_rel_stddev)
# The Be inner layer is at R=6 cm, so LiPb-only thickness is
# R_blanket - 6 cm.
MC_CALIBRATION_TABLE = [
    # R_b   TBR(mc)   rel_std
    (12,    1.5341,   0.0013),
    (50,    1.8361,   0.0011),
    (80,    1.8574,   0.0010),
    (110,   1.8625,   0.0011),
    (140,   1.8639,   0.0011),
]


def boundary_correction_factor(
    blanket_thickness_cm: float,
    boundary_condition: str = "infinite",
) -> float:
    """Tier 7+ (2026-08-31) — boundary-condition correction for the
    parametric Tier 5.B formula.

    The Sobes 2011 infinite-medium saturation model
    `f_sat = 1 - exp(-x/L_sat)` assumes escaping neutrons are lost.
    When the boundary is *reflective* (white / Lambertian, as in our
    Tier 6.C OpenMC sweep), escaping neutrons bounce back and
    contribute to TBR — most strongly at thin blankets where most
    neutrons would otherwise leak.

    This function returns a multiplicative correction that, applied
    on top of the Sobes parametric, recovers the calibrated MC
    values to within ±10% at every R_blanket in the calibration
    table (R_b ∈ {12, 50, 80, 110, 140} cm).

    Method: piecewise-linear interpolation in `blanket_thickness_cm`
    space, anchored to the 5 calibration points. The reference
    "infinite" correction at each thickness is the ratio
    MC(TBR) / Sobes(TBR), evaluated at 90% Li-6 enrichment.

    Parameters
    ----------
    blanket_thickness_cm : float
        LiPb-only thickness (NOT the full R_blanket). For the Tier 6.C
        geometry, R_b - 6 cm.
    boundary_condition : str
        "infinite" (default): return 1.0. The Sobes formula is used
        as-is.
        "reflective": interpolate the calibration table.

    Returns
    -------
    float
        Multiplicative correction factor. 1.0 for infinite-medium.
        For reflective boundary at the calibration points, values
        range from ~6.0 (R_b=12 cm, thin blanket, big boost) to
        ~0.89 (R_b=140 cm, Sobes slightly overshoots).
    """
    if boundary_condition == "infinite":
        return 1.0
    if boundary_condition != "reflective":
        raise ValueError(
            f"boundary_condition must be 'infinite' or 'reflective', "
            f"got {boundary_condition!r}"
        )
    # R_b = blanket_thickness_cm + R_be_inner = blanket_thickness_cm + 6
    # (because the Tier 6.C geometry has Be at r=6 cm).
    # For the interpolation, work in terms of blanket_thickness_cm
    # directly — the calibration table is keyed by R_b but the
    # correction is parameterized by LiPb-only thickness.
    R_BE_INNER = 6.0
    # Build the thickness -> correction lookup from MC_CALIBRATION_TABLE
    # by evaluating Sobes at each calibration point.
    thickness_to_correction = []
    for R_b, TBR_mc, _ in MC_CALIBRATION_TABLE:
        thick = R_b - R_BE_INNER
        # Sobes TBR at this point (90% Li-6, post-Tier 7.C calibrated).
        inp = TBRInputs(
            blanket_material="LiPb",
            neutron_multiplier="Be",
            Li6_enrichment_fraction=0.90,
            blanket_thickness_cm=thick,
            first_wall_coverage_fraction=0.95,
            geometry="cylindrical",
            MHD_effect_factor=0.85,
            temperature_factor=1.0,
        )
        TBR_sobes = compute_TBR(inp).TBR
        correction = TBR_mc / TBR_sobes
        thickness_to_correction.append((thick, correction))
    # Piecewise-linear interpolation (numpy.interp with extrapolation
    # at the boundaries via clamping).
    thicknesses = np.array([t for t, _ in thickness_to_correction])
    corrections = np.array([c for _, c in thickness_to_correction])
    if blanket_thickness_cm <= thicknesses[0]:
        return float(corrections[0])
    if blanket_thickness_cm >= thicknesses[-1]:
        return float(corrections[-1])
    return float(np.interp(blanket_thickness_cm, thicknesses, corrections))


def enrichment_factor(
    Li6_enrichment_fraction: float,
    blanket_material: str,
) -> float:
    """Li-6 enrichment factor (relative to natural 7.5% Li-6).

    Higher Li-6 enrichment increases TBR (Li-6 has higher (n,T) cross
    section than Li-7). Typical enrichment levels:
    - Natural: 7.5%
    - Slightly enriched: 30-60%
    - Highly enriched: 90%+

    Calibration based on Brown 2023 Table 3.

    Tier 7.C (2026-08-31): the saturation length in the
    `1 + mat_factor * (1 - exp(-excess/L_enr))` form was previously
    0.3, which gave f_enr(0.90, LiPb) = 1.889 — far above the
    documented target of "factor ~1.3 at 90%". Re-calibrated against
    the 2026-08-31 OpenMC TBR sweep (see MODEL_ASSUMPTIONS §3.4): with
    L_enr=2.17 the parametric Tier 5.B formula agrees with MC at
    R_blanket ∈ {80, 110, 140} cm within ±13% (was +64% with the old
    L_enr=0.3). The thin-blanket underestimate at R_blanket ≤ 50 cm
    is a separate deficiency of the Sobes 2011 infinite-medium
    saturation model (it does not capture boundary-reflection gain)
    and is documented as a Tier 7 known limitation.
    """
    if blanket_material not in TBR_PER_NEUTRON:
        return 1.0
    _, mat_factor = TBR_PER_NEUTRON[blanket_material]
    # At natural 7.5% Li-6, factor = 1.0. Enriched 90% → factor ~1.30
    # (re-calibrated from the original "factor ~1.3" docstring claim,
    #  which the L_enr=0.3 form overshot to 1.889).
    natural = 0.075
    if Li6_enrichment_fraction <= natural:
        return 1.0
    # Saturation curve (Tier 7.C): L_enr=2.17 calibrated against MC
    # sweep on 2026-08-31. The previous L_enr=0.3 was a units error
    # that produced f_enr(0.90) = 1.889 instead of the documented
    # ~1.30. As Li-6 fraction -> 1, f_enr -> 1 + mat_factor.
    L_ENRICHMENT_CM = 2.17
    excess = Li6_enrichment_fraction - natural
    return 1.0 + mat_factor * (1.0 - np.exp(-excess / L_ENRICHMENT_CM))


def compute_TBR(inputs: TBRInputs) -> TBRResult:
    """Compute the tritium breeding ratio for the given blanket.

    Args:
        inputs: TBRInputs dataclass.

    Returns:
        TBRResult with TBR and component contributions.
    """
    if inputs.blanket_material not in TBR_PER_NEUTRON:
        raise ValueError(
            f"Unknown blanket material: {inputs.blanket_material!r}. "
            f"Available: {list(TBR_PER_NEUTRON.keys())}"
        )
    if inputs.neutron_multiplier not in NEUTRON_MULTIPLIER_GAIN:
        raise ValueError(
            f"Unknown multiplier: {inputs.neutron_multiplier!r}. "
            f"Available: {list(NEUTRON_MULTIPLIER_GAIN.keys())}"
        )

    TBR_sat, _ = TBR_PER_NEUTRON[inputs.blanket_material]
    mult_gain = NEUTRON_MULTIPLIER_GAIN[inputs.neutron_multiplier]

    # Saturation fraction
    f_sat = thickness_to_saturation(
        inputs.blanket_material, inputs.blanket_thickness_cm
    )
    # Enrichment factor
    f_enr = enrichment_factor(
        inputs.Li6_enrichment_fraction, inputs.blanket_material
    )
    # Coverage
    f_cov = inputs.first_wall_coverage_fraction
    if f_cov <= 0:
        f_cov = DEFAULT_COVERAGE[inputs.geometry]

    # TBR = coverage * enrichment * saturation * (TBR_blanket + mult_gain)
    # TBR_blanket is the saturated value at the chosen material;
    # mult_gain is the additional TBR per D-T neutron from multiplier.
    TBR_blanket = TBR_sat * f_sat
    TBR_multiplier = TBR_sat * f_sat * mult_gain
    TBR_raw = (TBR_blanket + TBR_multiplier) * f_enr * f_cov

    # Apply MHD and temperature effects
    TBR = TBR_raw * inputs.MHD_effect_factor * inputs.temperature_factor

    # Tier 7+ (2026-08-31): boundary-condition correction. If the
    # blanket is in a reflective enclosure (white / Lambertian
    # boundary, as in our Tier 6.C OpenMC sweep), escaped neutrons
    # bounce back and contribute to TBR — most strongly at thin
    # blankets where most neutrons would otherwise leak. The
    # correction is calibrated against the 5-point MC_CALIBRATION_
    # TABLE; for "infinite" boundary_condition it is 1.0 and Sobes
    # is used as-is. Calibrated against 90% Li-6 only.
    f_geom = boundary_correction_factor(
        inputs.blanket_thickness_cm,
        inputs.boundary_condition,
    )
    TBR_corrected = TBR * f_geom

    needs_enrichment = (
        TBR_corrected < 1.0 and inputs.Li6_enrichment_fraction <= 0.30
    )

    notes = (
        f"Blanket={inputs.blanket_material}, mult={inputs.neutron_multiplier}, "
        f"thickness={inputs.blanket_thickness_cm} cm (f_sat={f_sat:.2f}), "
        f"Li-6={inputs.Li6_enrichment_fraction*100:.1f}% (f_enr={f_enr:.2f}), "
        f"coverage={f_cov:.2f}, boundary={inputs.boundary_condition} "
        f"(f_geom={f_geom:.2f}). "
        f"TBR_blanket={TBR_blanket:.3f}, TBR_multiplier={TBR_multiplier:.3f}, "
        f"TBR_Sobes={TBR:.3f}, TBR_total={TBR_corrected:.3f}. "
        f"{'NEEDS ENRICHMENT for TBR>1' if needs_enrichment else 'self-sufficient'}."
    )

    return TBRResult(
        TBR=float(TBR_corrected),
        TBR_blanket=float(TBR_blanket),
        TBR_multiplier=float(TBR_multiplier),
        f_coverage=float(f_cov),
        f_enrichment=float(f_enr),
        blanket_thickness_cm=float(inputs.blanket_thickness_cm),
        saturation_fraction=float(f_sat),
        needs_enrichment=bool(needs_enrichment),
        boundary_correction=float(f_geom),
        notes=notes,
    )


# Pre-defined blanket designs for common fusion concepts.
BLANKET_ZN_DESIGN = TBRInputs(
    blanket_material="LiPb",
    neutron_multiplier="Be",
    Li6_enrichment_fraction=0.30,  # Modestly enriched
    blanket_thickness_cm=50.0,
    first_wall_coverage_fraction=0.75,  # Z-pinch lower
    geometry="Z-pinch",
    MHD_effect_factor=0.90,  # MHD in liquid LiPb reduces TBR
)

BLANKET_TOKAMAK_REFERENCE = TBRInputs(
    blanket_material="Li4SiO4",
    neutron_multiplier="Be",
    Li6_enrichment_fraction=0.60,  # DEMO-class enrichment
    blanket_thickness_cm=40.0,
    first_wall_coverage_fraction=0.92,
    geometry="tokamak",
    MHD_effect_factor=1.0,  # Solid breeder, no MHD
)

BLANKET_GF_MTF = TBRInputs(
    blanket_material="FLiBe",
    neutron_multiplier="Be",
    Li6_enrichment_fraction=0.40,
    blanket_thickness_cm=40.0,
    first_wall_coverage_fraction=0.85,
    geometry="MTF",
    MHD_effect_factor=0.95,
)

BLANKET_ZAP_SFZ = TBRInputs(
    blanket_material="LiPb",
    neutron_multiplier="Pb",  # Cheaper than Be for steady-state
    Li6_enrichment_fraction=0.50,
    blanket_thickness_cm=50.0,
    first_wall_coverage_fraction=0.78,
    geometry="sheared_flow_Z",
    MHD_effect_factor=0.92,
)


ALL_BLANKETS = {
    "ZN": BLANKET_ZN_DESIGN,
    "Tokamak": BLANKET_TOKAMAK_REFERENCE,
    "GF-MTF": BLANKET_GF_MTF,
    "Zap-SFZ": BLANKET_ZAP_SFZ,
}


def tbr_for_blanket(name: str) -> TBRResult:
    """Run the TBR model for a pre-defined blanket design.

    Args:
        name: One of "ZN", "Tokamak", "GF-MTF", "Zap-SFZ".

    Returns:
        TBRResult.
    """
    if name not in ALL_BLANKETS:
        raise ValueError(
            f"Unknown blanket: {name!r}. Available: {list(ALL_BLANKETS.keys())}"
        )
    return compute_TBR(ALL_BLANKETS[name])
