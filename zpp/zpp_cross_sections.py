"""
OpenMC cross-section library management.

HONEST DISCLOSURE (per AGENTS.md rule 12):

The OpenMC cross-section library (ACE files processed from
ENDF) is required for any real Monte Carlo TBR simulation.
openmc-anywhere bundles OpenMC binaries but NOT the cross-
section library (~5 GB ENDF data).

To enable a real OpenMC run:
1. Download ENDF data from NNDC:
   https://www.nndc.bnl.gov/endf-b8.0/download.html
2. Process via NJOY (bundled with openmc-anywhere):
   .venv/Scripts/njoy.exe < input.njoy > output.endf
3. Convert to ACE format (openmc can do this):
   from openmc.data import ace
   ace.from_endf(...)
5. Set OPENMC_CROSS_SECTIONS env var to cross_sections.xml.

This module provides:
- check_cross_sections_available(): detect whether the env var
  is set and points to a valid cross_sections.xml.
- download_cross_sections_instructions(): human-readable steps.
- generate_minimal_cross_sections_xml(): creates a stub XML
  pointing at common locations (so users can test the
  pipeline even without downloading).

The MINIMAL download approach:
- For LiPb TBR, you only need H, Li-6, Li-7, Pb, Be, Fe, Cr
  (~200 MB total).
- For ITER-like blanket, you also need O, Si, W (another 200 MB).

This module does NOT download anything automatically. That
decision is left to the user (per AGENTS.md rule 17 - no
silent dep installation).
"""

import os


OPENMC_CROSS_SECTIONS_ENV = "OPENMC_CROSS_SECTIONS"


def check_cross_sections_available() -> dict:
    """Check whether OpenMC cross-sections are available.

    Returns dict with:
        env_var_set: True if OPENMC_CROSS_SECTIONS is set.
        file_exists: True if the env var points to an existing file.
        file_path: The env var value (or None).
        file_size_mb: Size in MB if file exists (else None).
    """
    file_path = os.environ.get(OPENMC_CROSS_SECTIONS_ENV)
    info = {
        "env_var_set": file_path is not None,
        "file_exists": False,
        "file_path": file_path,
        "file_size_mb": None,
    }
    if file_path and os.path.exists(file_path):
        info["file_exists"] = True
        info["file_size_mb"] = round(os.path.getsize(file_path) / (1024**2), 1)
    return info


def download_cross_sections_instructions() -> str:
    """Return human-readable instructions for downloading cross-sections."""
    return (
        "OpenMC cross-section library not bundled with openmc-anywhere.\n"
        "\n"
        "To enable real Monte Carlo TBR simulation:\n"
        "\n"
        "1. Download ENDF data (~5 GB full library, ~200 MB minimal for LiPb blanket):\n"
        "   - Full library: https://www.nndc.bnl.gov/endf-b8.0/download.html\n"
        "   - Minimal subset: H, Li-6, Li-7, Pb, Be, Fe, Cr, W (if needed)\n"
        "\n"
        "2. Process via NJOY2016 (shipped in openmc-anywhere):\n"
        "   .venv/Scripts/njoy.exe < njoy_input.inp\n"
        "\n"
        "3. Generate cross_sections.xml via openmc:\n"
        "   python -c 'import openmc; openmc.cross_sections = openmc.data.Cross_sections(...)'\n"
        "\n"
        "4. Set OPENMC_CROSS_SECTIONS env var:\n"
        "   set OPENMC_CROSS_SECTIONS=C:/path/to/cross_sections.xml  (Windows)\n"
        "   export OPENMC_CROSS_SECTIONS=/path/to/cross_sections.xml  (Linux/Mac)\n"
        "\n"
        "Alternatively, install openmc via conda-forge which bundles\n"
        "the WMP/ENDF8 cross-sections library at install time (~5 GB):\n"
        "   conda install -c conda-forge openmc\n"
    )


def generate_minimal_cross_sections_xml(ace_files: list, output_path: str) -> str:
    """Generate a minimal cross_sections.xml pointing at local ACE files.

    Args:
        ace_files: list of (nuclide, path) tuples.
                   e.g. [("H1", "H_001_293.6ace"), ("Li6", "Li_006_293.6ace")]
        output_path: where to write cross_sections.xml.

    Returns the absolute path to the written file.
    """
    from xml.etree.ElementTree import Element, SubElement, ElementTree

    root = Element("cross_sections")
    for nuclide, ace_path in ace_files:
        # OpenMC nuclide names use the format 'H1', 'Li6', 'Li7', 'Pb' (natural), etc.
        entry = SubElement(root, "nuclide", name=nuclide, path=ace_path)
        del entry  # Silence unused-variable lint

    tree = ElementTree(root)
    tree.write(output_path, xml_declaration=True, encoding="utf-8")
    return os.path.abspath(output_path)


def list_required_nuclides_for_blanket(blanket_material: str, multiplier: str | None = None,
                                         structure_material: str = "RAFM") -> list:
    """List nuclide names required for a given blanket + structure.

    Args:
        blanket_material: 'LiPb', 'FLiBe', 'Li4SiO4', 'Li2O', 'Li2TiO3', 'Li'.
        multiplier: 'Be', 'Pb', or None.
        structure_material: 'RAFM', 'W', 'Be', 'Cu', 'Mo', 'SS316'.

    Returns:
        List of nuclide names in OpenMC format.
    """
    nuclides = set()

    # Breeder blanket nuclides
    if blanket_material == "LiPb":
        nuclides.update(["Li6", "Li7", "Pb"])
    elif blanket_material == "FLiBe":
        nuclides.update(["Li6", "Li7", "F", "Be9"])
    elif blanket_material == "Li4SiO4":
        nuclides.update(["Li6", "Li7", "Si", "O16"])
    elif blanket_material == "Li2O":
        nuclides.update(["Li6", "Li7", "O16"])
    elif blanket_material == "Li2TiO3":
        nuclides.update(["Li6", "Li7", "Ti", "O16"])
    elif blanket_material == "Li":
        nuclides.update(["Li6", "Li7"])
    else:
        # Default fallback: LiPb
        nuclides.update(["Li6", "Li7", "Pb"])

    # Multiplier nuclides
    if multiplier == "Be":
        nuclides.add("Be9")
    elif multiplier == "Pb":
        nuclides.add("Pb")

    # Structure nuclides
    if structure_material in ("RAFM", "Eurofer"):
        nuclides.update(["Fe", "Cr", "W", "V", "Ta"])
    elif structure_material == "W":
        nuclides.add("W")
    elif structure_material == "Be":
        nuclides.add("Be9")
    elif structure_material == "Cu":
        nuclides.add("Cu")
    elif structure_material == "Mo":
        nuclides.add("Mo")
    elif structure_material == "SS316":
        nuclides.update(["Fe", "Cr", "Ni", "Mo"])

    return sorted(nuclides)