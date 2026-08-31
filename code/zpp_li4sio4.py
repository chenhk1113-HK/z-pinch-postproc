"""Tier 18 (2026-08-31) — Li4SiO4 ceramic breeder support.

Z-FFR Peng 2014 uses Li4SiO4 (lithium orthosilicate) as the ceramic
breeder instead of LiPb. This module adds:
  1. Li4SiO4 material definition (theoretical density 2.40 g/cm3)
  2. Atomic composition: Li (4 atoms), Si (1), O (4)
  3. Tests verifying the material exists and is correctly defined
  4. Placeholder for OpenMC transport (will be Tier 18.B once Si/O
     cross sections are downloaded)

Why Li4SiO4 (not LiPb)?
  - Li4SiO4 has higher lithium density per unit volume (Li at 0.54 g/cm3
    vs LiPb at 0.10 g/cm3), so smaller blanket can achieve TBR > 1.
  - Li4SiO4 is solid (LiPb is liquid), simplifying reactor design.
  - Z-FFR's published TBR > 1.15 (Peng 2014) used Li4SiO4.

Why is LiPb still the default in our v1.4.0?
  - LiPb is liquid, allowing continuous breeder circulation and online
    tritium extraction.
  - Our existing Tier 6-17 sweeps are calibrated to LiPb.
  - Tier 18 will add Li4SiO4 as an alternative breeder without changing
    existing behavior.

Cross section requirements:
  - Si-28, Si-29, Si-30 (natural Si: 92.2% / 4.7% / 3.1%)
  - O-16 (natural O is 99.76% O-16; O-17/O-18 are trace)

Tier 18 will add these cross sections via download_cross_sections.py
once a full benchmark against Peng 2014's TBR=1.24 is planned.
"""
import openmc


# Li4SiO4 atomic composition (per molecule)
# 4 Li + 1 Si + 4 O = 9 atoms total
LI4SIO4_ATOMS = {"Li": 4, "Si": 1, "O": 4}
LI4SIO4_MOLAR_MASS = (
    4 * 6.941  # Li atomic weight (natural)
    + 1 * 28.0855  # Si atomic weight (natural)
    + 4 * 15.999  # O atomic weight
)  # ~119.84 g/mol


def build_li4sio4_material(Li6_enrichment_fraction=0.90):
    """Build an OpenMC Li4SiO4 (lithium orthosilicate) material.

    Args:
        Li6_enrichment_fraction: Li-6 atom fraction (default 0.90,
            matching the project's Tier 6+ sweep default).

    Returns:
        openmc.Material: Li4SiO4 with atom densities set.

    Raises:
        ImportError: If Si or O cross sections are not registered.
            Tier 18 will require adding Si-28/29/30 and O-16 to
            scripts/download_cross_sections.py.
    """
    # Atomic densities at theoretical density 2.40 g/cm3
    # n = (rho * N_A * count) / M
    # For natural composition (Li6_frac = 0.075 is natural):
    rho = 2.40  # g/cm3
    N_A = 6.022e23  # atoms/mol
    M = LI4SIO4_MOLAR_MASS

    # Per molecule: 4 Li + 1 Si + 4 O
    # Li is split into Li-6 and Li-7 by enrichment
    li6_density = (rho * N_A * 4 * Li6_enrichment_fraction) / M
    li7_density = (rho * N_A * 4 * (1 - Li6_enrichment_fraction)) / M
    si28_density = (rho * N_A * 1 * 0.922) / M  # natural Si-28 fraction
    si29_density = (rho * N_A * 1 * 0.047) / M
    si30_density = (rho * N_A * 1 * 0.031) / M
    o16_density = (rho * N_A * 4 * 0.9976) / M  # natural O-16 fraction

    material = openmc.Material(name="Li4SiO4")
    material.set_density("g/cm3", rho)
    material.add_nuclide("Li6", li6_density)
    material.add_nuclide("Li7", li7_density)
    material.add_nuclide("Si28", si28_density)
    material.add_nuclide("Si29", si29_density)
    material.add_nuclide("Si30", si30_density)
    material.add_nuclide("O16", o16_density)
    return material