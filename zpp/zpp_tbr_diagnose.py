"""Tier 11 (2026-08-31) — Sobes-formula deconstruction / diagnostic tool.

The Tier 7 investigation found that the Sobes 2011 infinite-medium
parametric Tier 5.B formula has TWO embedded overcounts when applied
to our Z-pinch geometry:

  1. ASYMPTOTE OVERCOUNT: the Sobes formula predicts TBR_sat = 2.25 at
     infinite blanket thickness (90% Li-6, post-Tier 7.C calibrated),
     but the MC plateau is 1.86. This 21% gap is a setup-dependent
     constant because our Z-pinch geometry has a finite-radius Be
     multiplier that saturates in a thin inner layer (rather than
     contributing throughout the whole blanket as Sobes assumes).

  2. THIN-BLANKET UNDERESTIMATE: at thin blankets (R_b <= 50 cm),
     Sobes underestimates by 28-83% because it doesn't capture
     white-boundary reflection gain from a finite-radius reflective
     enclosure. Fixed by the Tier 8 closed-form albedo correction.

The deconstruction tool lets a user decompose any TBR calculation
into its named components, see what each contributes, and flag
which components are plausibly overcounting in their specific
geometry.

Output is structured (TBRDeconstruction dataclass) and includes a
markdown formatter for human-readable reports.

Usage:
    from zpp.zpp_tbr_diagnose import deconstruct_tbr, deconstruction_markdown
    d = deconstruct_tbr(tbr_inputs, mc_value=1.84)
    print(deconstruction_markdown(d))
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from zpp.zpp_tbr import (
    TBRInputs,
    TBRResult,
    compute_TBR,
    thickness_to_saturation,
    enrichment_factor,
    boundary_correction_factor,
    TBR_PER_NEUTRON,
    NEUTRON_MULTIPLIER_GAIN,
    DEFAULT_COVERAGE,
    MC_CALIBRATION_TABLE,
    ASYMPTOTE_RATIO_REFLECTIVE,
    ALBEDO_BETA_REFLECTIVE,
)


# Tier 7.C calibrated values: these are the "honest" reference values
# that the Tier 5.B formula should reproduce after the Li-6 enrichment
# calibration fix. They serve as the benchmark for flagging overcounts.
SOBES_ASYMPTOTE_90PCT = (
    TBR_PER_NEUTRON["LiPb"][0]   # TBR_sat = 1.30 (LiPb)
    * (1 + NEUTRON_MULTIPLIER_GAIN["Be"])  # 1 + 0.65 = 1.65
    * enrichment_factor(0.90, "LiPb")  # 1.300
    * 0.95  # coverage
    * 0.85  # MHD factor (default)
)
# = 1.30 * 1.65 * 1.300 * 0.95 * 0.85 = 2.252

# Tier 8 calibrated MC plateau at the same enrichment/coverage:
MC_PLATEAU_REFLECTIVE = 1.86  # From 2026-08-31 OpenMC sweep

# Sobes 2011 published validity range (Tier 7 finding):
SOBES_VALID_LI6_MIN = 0.30  # Below this, Li-6 (n,T) cross-section
                            # approximation breaks down
SOBES_VALID_LI6_MAX = 0.95  # Above this, self-shielding dominates
SOBES_VALID_THICKNESS_MIN_CM = 30.0  # Below 30 cm, saturation formula
                                      # f_sat = 1 - exp(-x/L) doesn't apply
SOBES_VALID_COVERAGE_MIN = 0.50  # Below 50% coverage, geometric effects
                                  # dominate (out of Sobes regime)


@dataclass
class ComponentContribution:
    """A single named component of the TBR calculation."""
    name: str
    value: float              # The numeric value of the factor (e.g. f_sat)
    contribution: float       # Its contribution to total TBR (multiplicative)
    description: str          # Human-readable explanation
    is_overcounting: bool = False  # True if outside Sobes validity range
    note: str = ""            # Extra info on this component


@dataclass
class TBRDeconstruction:
    """Full deconstruction of a TBR calculation into named components."""
    inputs: TBRInputs
    tbr_sobes: float            # Sobes TBR (without boundary correction)
    tbr_corrected: float        # Final TBR (with boundary correction)
    components: list = field(default_factory=list)
    mc_reference: Optional[float] = None  # Optional MC value for comparison
    self_sufficient: bool = False
    overall_warnings: list = field(default_factory=list)

    @property
    def delta_pct_vs_mc(self) -> Optional[float]:
        """If mc_reference is set, return (TBR - MC) / MC as fraction.
        None otherwise."""
        if self.mc_reference is None or self.mc_reference == 0:
            return None
        return (self.tbr_corrected - self.mc_reference) / self.mc_reference


def deconstruct_tbr(
    inputs: TBRInputs,
    mc_reference: Optional[float] = None,
) -> TBRDeconstruction:
    """Decompose a TBR calculation into named components with diagnostics.

    Parameters
    ----------
    inputs : TBRInputs
        The blanket design inputs to evaluate.
    mc_reference : float, optional
        If provided, the actual MC measurement (e.g. from OpenMC) to
        compare against. The delta is reported in `delta_pct_vs_mc`.

    Returns
    -------
    TBRDeconstruction
        Structured deconstruction with per-component contributions
        and overcounting warnings.
    """
    # Compute the base TBR (no boundary correction) so we can isolate
    # the boundary effect as its own component.
    inp_infinite = TBRInputs(**{**inputs.__dict__, "boundary_condition": "infinite"})
    result_sobes = compute_TBR(inp_infinite)
    result_corrected = compute_TBR(inputs)

    TBR_sat = TBR_PER_NEUTRON[inputs.blanket_material][0]
    mult_gain = NEUTRON_MULTIPLIER_GAIN[inputs.neutron_multiplier]

    f_sat = thickness_to_saturation(inputs.blanket_material, inputs.blanket_thickness_cm)
    f_enr = enrichment_factor(inputs.Li6_enrichment_fraction, inputs.blanket_material)
    # Some inputs use "cylindrical" (OpenMC geometry) instead of the
    # more specific "Z-pinch". Treat cylindrical as Z-pinch for the
    # default coverage lookup.
    geom_for_default = inputs.geometry
    if geom_for_default == "cylindrical":
        geom_for_default = "Z-pinch"
    f_cov = inputs.first_wall_coverage_fraction or DEFAULT_COVERAGE[geom_for_default]
    f_geom = result_corrected.boundary_correction

    # Per-component contributions to the Sobes TBR (TBR_raw):
    # TBR_raw = (TBR_sat * f_sat + TBR_sat * f_sat * mult_gain) * f_enr * f_cov * MHD * temp
    TBR_blanket = TBR_sat * f_sat
    TBR_multiplier = TBR_sat * f_sat * mult_gain
    TBR_raw_pre_enr = (TBR_blanket + TBR_multiplier)
    TBR_raw_pre_cov = TBR_raw_pre_enr * f_enr
    TBR_sobes_raw = TBR_raw_pre_cov * f_cov * inputs.MHD_effect_factor * inputs.temperature_factor

    components = []

    # Component 1: TBR_sat (saturated TBR per source neutron)
    components.append(ComponentContribution(
        name="TBR_sat (saturated)",
        value=TBR_sat,
        contribution=TBR_sat * f_sat,
        description=(
            f"Saturated TBR per source neutron for {inputs.blanket_material} "
            f"(Sobes 2011, includes Be multiplier gain). Value: {TBR_sat:.3f}."
        ),
        note="Sobes 2011 reference value; assumes infinite-medium geometry.",
    ))

    # Component 2: f_sat (saturation fraction)
    f_sat_valid = inputs.blanket_thickness_cm >= SOBES_VALID_THICKNESS_MIN_CM
    components.append(ComponentContribution(
        name="f_sat (saturation fraction)",
        value=f_sat,
        contribution=f_sat,
        description=(
            f"Fraction of saturated TBR achieved at thickness="
            f"{inputs.blanket_thickness_cm} cm. Sobes formula: "
            f"f_sat = 1 - exp(-x/L_sat) with L_sat={50.0 if inputs.blanket_material=='LiPb' else '?'} cm."
        ),
        is_overcounting=(not f_sat_valid),
        note=(
            f"Below {SOBES_VALID_THICKNESS_MIN_CM} cm, the Sobes saturation "
            f"formula doesn't apply (thin-blanket regime)."
            if not f_sat_valid else "Within Sobes validity range."
        ),
    ))

    # Component 3: Be multiplier
    components.append(ComponentContribution(
        name="Be multiplier",
        value=mult_gain,
        contribution=TBR_blanket * mult_gain,
        description=(
            f"Additional TBR per source neutron from {inputs.neutron_multiplier} "
            f"(n,2n) multiplication. Multiplier gain: {mult_gain:.2f}."
        ),
        note=(
            "⚠ Assumes Be contributes throughout the WHOLE blanket. "
            "In a Z-pinch with finite-radius Be layer, Be saturates in a "
            "thin ~2 cm inner layer. This is the source of the 21% "
            "asymptote overcount (Tier 7 finding)."
        ),
    ))

    # Component 4: f_enr (Li-6 enrichment)
    f_enr_valid = SOBES_VALID_LI6_MIN <= inputs.Li6_enrichment_fraction <= SOBES_VALID_LI6_MAX
    components.append(ComponentContribution(
        name="f_enr (Li-6 enrichment)",
        value=f_enr,
        contribution=f_enr,
        description=(
            f"Enrichment factor at Li-6={inputs.Li6_enrichment_fraction*100:.1f}%. "
            f"f_enr = 1 + mat_factor * (1 - exp(-excess/L_enr)), "
            f"L_enr=2.17 (Tier 7.C calibrated)."
        ),
        is_overcounting=(not f_enr_valid),
        note=(
            f"Outside Sobes validity range "
            f"[{SOBES_VALID_LI6_MIN*100:.0f}%, {SOBES_VALID_LI6_MAX*100:.0f}%]."
            if not f_enr_valid
            else "Within Sobes validity range."
        ),
    ))

    # Component 5: f_cov (first-wall coverage)
    f_cov_valid = f_cov >= SOBES_VALID_COVERAGE_MIN
    components.append(ComponentContribution(
        name="f_cov (first-wall coverage)",
        value=f_cov,
        contribution=f_cov,
        description=(
            f"First-wall coverage fraction. Defaults to "
            f"{DEFAULT_COVERAGE[geom_for_default]:.2f} for {geom_for_default} "
            f"if not specified."
        ),
        is_overcounting=(not f_cov_valid),
        note=(
            f"Below {SOBES_VALID_COVERAGE_MIN*100:.0f}% coverage, geometric "
            f"effects dominate."
            if not f_cov_valid else "Within Sobes validity range."
        ),
    ))

    # Component 6: MHD_effect_factor
    components.append(ComponentContribution(
        name="MHD effect",
        value=inputs.MHD_effect_factor,
        contribution=inputs.MHD_effect_factor,
        description=(
            f"Magnetohydrodynamic effect on liquid breeders. Reduces TBR by "
            f"{(1-inputs.MHD_effect_factor)*100:.0f}% in our model."
        ),
    ))

    # Component 7: temperature_factor
    components.append(ComponentContribution(
        name="Temperature factor",
        value=inputs.temperature_factor,
        contribution=inputs.temperature_factor,
        description="Temperature effect on cross-sections (small, ~1%).",
    ))

    # Component 8: f_geom (boundary correction, Tier 8)
    if f_geom != 1.0:
        components.append(ComponentContribution(
            name="f_geom (boundary correction)",
            value=f_geom,
            contribution=f_geom,
            description=(
                f"Tier 8 closed-form albedo correction for "
                f"{inputs.boundary_condition} boundary. f_geom = "
                f"ASYMPTOTE_RATIO / (1 - ALBEDO_BETA * (1-f_sat)) "
                f"= {ASYMPTOTE_RATIO_REFLECTIVE:.4f} / (1 - "
                f"{ALBEDO_BETA_REFLECTIVE:.3f}*(1-{f_sat:.3f})) "
                f"= {f_geom:.4f}."
            ),
            note=(
                f"Capture the reflection gain from "
                f"{inputs.boundary_condition} boundary. Replaces the "
                f"Tier 7+ piecewise-linear interpolation."
            ),
        ))

    # Build warnings list
    warnings = []
    if inputs.Li6_enrichment_fraction < SOBES_VALID_LI6_MIN:
        warnings.append(
            f"Li-6 enrichment {inputs.Li6_enrichment_fraction*100:.1f}% is below "
            f"Sobes validity ({SOBES_VALID_LI6_MIN*100:.0f}%). The Li-6 (n,T) "
            f"cross-section approximation breaks down at low enrichment. "
            f"Use a different parametric for natural-lithium blankets."
        )
    if inputs.blanket_thickness_cm < SOBES_VALID_THICKNESS_MIN_CM:
        warnings.append(
            f"Thickness {inputs.blanket_thickness_cm} cm is below the Sobes "
            f"validity range ({SOBES_VALID_THICKNESS_MIN_CM} cm). At thin "
            f"blankets, the saturation formula doesn't apply. Use the Tier 8 "
            f"closed-form albedo correction."
        )
    if inputs.boundary_condition == "reflective":
        warnings.append(
            "Boundary_condition='reflective' assumes a perfectly reflecting "
            "white/Lambertian boundary (the lab best-case). Real plants "
            "have open ends; use 'infinite' for engineering scoping."
        )
    if result_corrected.TBR > SOBES_ASYMPTOTE_90PCT * 1.005:
        warnings.append(
            f"TBR ({result_corrected.TBR:.3f}) is above the Sobes "
            f"asymptote ({SOBES_ASYMPTOTE_90PCT:.3f}). This is suspicious "
            f"unless you're using boundary_condition='reflective' — check "
            f"the inputs and the boundary_condition."
        )

    return TBRDeconstruction(
        inputs=inputs,
        tbr_sobes=result_sobes.TBR,
        tbr_corrected=result_corrected.TBR,
        components=components,
        mc_reference=mc_reference,
        self_sufficient=result_corrected.TBR >= 1.0,
        overall_warnings=warnings,
    )


def deconstruction_markdown(d: TBRDeconstruction) -> str:
    """Format a TBRDeconstruction as a human-readable markdown report.

    Useful for printing to console, embedding in reports, or sending
    to Telegram via Hermes.
    """
    lines = []
    lines.append(f"# TBR Deconstruction — {d.inputs.blanket_material}+{d.inputs.neutron_multiplier}")
    lines.append("")
    lines.append(f"**Inputs**: thickness={d.inputs.blanket_thickness_cm} cm, "
                 f"Li-6={d.inputs.Li6_enrichment_fraction*100:.1f}%, "
                 f"coverage={d.inputs.first_wall_coverage_fraction or DEFAULT_COVERAGE[geom_for_default]:.2f}, "
                 f"geometry={d.inputs.geometry}, "
                 f"boundary={d.inputs.boundary_condition}")
    lines.append("")
    lines.append("## Named components")
    lines.append("")
    lines.append("| # | Component | Value | Contribution | Overcounting? | Note |")
    lines.append("|---|---|---|---|---|---|")
    for i, c in enumerate(d.components, 1):
        flag = "⚠ YES" if c.is_overcounting else "no"
        note = c.note.replace("\n", " ") if c.note else c.description
        if len(note) > 80:
            note = note[:77] + "..."
        lines.append(f"| {i} | {c.name} | {c.value:.4f} | "
                     f"×{c.contribution:.4f} → {c.value*c.contribution:.4f} | "
                     f"{flag} | {note} |")
    lines.append("")
    lines.append("## Final TBR")
    lines.append("")
    lines.append(f"- **TBR (Sobes, no boundary correction)**: {d.tbr_sobes:.4f}")
    lines.append(f"- **TBR (with boundary correction)**: {d.tbr_corrected:.4f}")
    lines.append(f"- **Self-sufficient**: {'YES ✓' if d.self_sufficient else 'NO ✗'}")
    if d.mc_reference is not None:
        delta = d.delta_pct_vs_mc * 100
        sign = "+" if delta >= 0 else ""
        lines.append(f"- **MC reference**: {d.mc_reference:.4f}")
        lines.append(f"- **Delta vs MC**: {sign}{delta:.2f}%")
    lines.append("")
    if d.overall_warnings:
        lines.append("## Warnings")
        lines.append("")
        for w in d.overall_warnings:
            lines.append(f"- ⚠ {w}")
        lines.append("")
    lines.append("--- Tier 11 / Sobes deconstruction tool (2026-08-31)")
    return "\n".join(lines)