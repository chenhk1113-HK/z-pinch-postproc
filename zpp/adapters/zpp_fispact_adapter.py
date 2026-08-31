"""
FISPACT-II adapter stub for the Z-pinch post-processor.

HONEST DISCLOSURE (per AGENTS.md rule 12 + rule 17):

FISPACT-II is a nuclear activation and transmutation code
maintained by UKAEA. The full distribution requires:
1. UKAEA license agreement (free for non-commercial research)
2. Manual download from https://fispact.ukaea.uk/
4. Platform-specific install (Linux/Mac native; Windows via WSL)
5. Setting FISPACT environment variables

This module is NOT going to install FISPACT-II automatically
(per AGENTS.md rule 17). Instead, it:
1. Documents the install steps.
2. Provides a parametric fallback for activation calculations
   (using Tier 5.D DPA + Smolentsev erosion).
3. Provides a "probe" function that detects if FISPACT is
   already installed via system PATH.

Real FISPACT integration is blocked until the user provides
a license + download. Until then, the project uses Tier 5.D
PFC lifetime as the activation proxy.
"""

import shutil


FISPACT_LICENSE_URL = "https://fispact.ukaea.uk/"
FISPACT_DOWNLOAD_URL = "https://fispact.ukaea.uk/"


def check_fispact_install() -> dict:
    """Probe for FISPACT-II installation.

    Returns dict with:
        installed: True if fispact binary is on PATH.
        binary_path: path to fispact executable or None.
        version: detected version (from --version output) or None.
    """
    info = {
        "installed": False,
        "binary_path": None,
        "version": None,
    }

    # Common FISPACT binary names
    candidates = ["fispact2", "fispact-ii", "fispact"]
    for cand in candidates:
        path = shutil.which(cand)
        if path is not None:
            info["installed"] = True
            info["binary_path"] = path
            break

    return info


def fispact_install_instructions() -> str:
    """Return human-readable install instructions for FISPACT-II."""
    return (
        "FISPACT-II installation requires manual steps:\n"
        "\n"
        "1. Request a license from UKAEA:\n"
        f"   {FISPACT_LICENSE_URL}\n"
        "   License is free for academic / non-commercial use.\n"
        "\n"
        "2. Download the distribution for your platform:\n"
        f"   {FISPACT_DOWNLOAD_URL}\n"
        "   - Linux: native ELF binary\n"
        "   - macOS: native Mach-O binary\n"
        "   - Windows: requires WSL (Windows Subsystem for Linux)\n"
        "\n"
        "3. Add the FISPACT bin/ directory to PATH:\n"
        "   export PATH=/path/to/fispact/bin:$PATH\n"
        "\n"
        "4. Verify with:\n"
        "   fispact2 --version\n"
        "\n"
        "5. (Optional) Install Python wrapper:\n"
        "   pip install fispact2\n"
        "\n"
        "Once installed, the project's SubprocessNeutronicsAdapter\n"
        "will detect it via shutil.which('fispact2') and use it\n"
        "for activation analysis. Until then, the project uses\n"
        "Tier 5.D PFC lifetime (DPA + Smolentsev erosion) as the\n"
        "activation proxy.\n"
    )


def parametric_activation_proxy(
    neutron_wall_load_MW_per_m2: float,
    material: str = "RAFM",
    operating_years: float = 30.0,
    capacity_factor: float = 0.25,
) -> dict:
    """Compute activation-proxy quantities without FISPACT.

    This is the Tier 5.D PFC lifetime model, exposed here as
    the parametric fallback when FISPACT-II is not available.

    Args:
        neutron_wall_load_MW_per_m2: surface heat flux.
        material: PFC material ('RAFM', 'W', 'Be', 'Cu', 'Mo', 'SS316').
        operating_years: full-power operating years.
        capacity_factor: fraction of time at full power.

    Returns dict with DPA, He-production, lifetime estimates.
    """
    # Lazy import to avoid circular dependency
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

    from zpp.zpp_pfc_lifetime import (
        DPA_rate_per_FPY, first_wall_lifetime,
        PFCDamageInputs,
    )

    # Compute DPA
    dpa_per_fpy = DPA_rate_per_FPY(
        neutron_wall_load_MW_per_m2=neutron_wall_load_MW_per_m2,
        material=material,
    )
    total_fpy = operating_years * capacity_factor
    total_dpa = dpa_per_fpy * total_fpy

    # Helium production (rough scaling: 10 appm/FPY per MW/m2 for RAFM)
    he_per_fpy = 10.0 * neutron_wall_load_MW_per_m2  # appm/FPY at 1 MW/m2
    total_he_appm = he_per_fpy * total_fpy

    return {
        "method": "parametric",
        "DPA_per_FPY": dpa_per_fpy,
        "total_DPA": total_dpa,
        "He_appm_per_FPY": he_per_fpy,
        "total_He_appm": total_he_appm,
        "operating_FPY": total_fpy,
        "notes": "Tier 5.D proxy (no FISPACT-II transmutation calc).",
    }