"""Z-FFR spherical geometry (Tier 17, 2026-08-31).

Builds a 1D spherical geometry for the Z-FFR design from Peng 2014,
following the published design parameters.

Layers (innermost to outermost, spherical):
  1. Plasma (point source at center)
  2. Be multiplier (r=0 to r=R_be) — plasma source sits at center
  3. LiPb blanket (r=R_be to r=R_b)
  4. U-238 fission blanket (optional, r=R_b to r=R_u)
  5. Fe reflector (optional, r=R_u to r=R_fe)
  6. RAFM structure (r=R_fe to r=R_struct)

Default design parameters from Peng 2014 (approximated):
  R_be = 5 cm       (Be multiplier — 5 cm thick)
  R_b = 50 cm       (LiPb blanket outer — 45 cm thick)
  R_u = 65 cm       (U-238 outer — 15 cm thick, hybrid blanket)
  R_fe = 80 cm      (Fe reflector — 15 cm thick)
  R_struct = 85 cm  (RAFM)

Source: 14.1 MeV neutron at the plasma center (point source).
Boundary: vacuum (default; Peng 2014 used reflective).

Returns: (geometry, cells, surfaces) tuple compatible with
zpp_real_openmc_transport's _build_tally() — the tally expects a
'blanket' cell to exist, which we map to the LiPb layer.
"""
import openmc


def _build_zffr_spherical_geometry(
    materials,
    R_be_cm=5.0,
    R_blanket_cm=50.0,
    R_u238_cm=65.0,
    R_fe_cm=80.0,
    R_structure_cm=85.0,
    boundary_type="vacuum",
    include_fe=True,
    include_u238=True,
):
    """Build Z-FFR spherical geometry (Peng 2014 design).

    Layers (innermost to outermost):
      1. Plasma: 0 < r < R_be (point source region)
      2. Be multiplier: R_be < r < R_blanket  ← "be_mult" cell
      3. LiPb breeder: R_blanket < r < next  ← "blanket" cell
         (next = R_u238 if include_u238 else R_fe if include_fe
                else R_structure)
      4. U-238 (optional): next < r < R_u238
      5. Fe reflector (optional): R_u238 < r < R_fe
      6. RAFM structure: outermost layer

    Note: Z-FFR Peng 2014 has Be INSIDE LiPb (mult_inside=True
    analog in spherical). The plasma region contains the point
    source but is small (R_be = 5 cm) so the Be sees 14 MeV neutrons
    almost immediately.

    The "blanket" cell name (used by _build_tally) corresponds to
    the LiPb breeder layer.
    """
    # Validate ranges
    if not 0 < R_be_cm < R_blanket_cm < R_structure_cm:
        raise ValueError(
            f"Need 0 < R_be < R_blanket < R_struct, "
            f"got R_be={R_be_cm}, R_blanket={R_blanket_cm}, "
            f"R_structure={R_structure_cm}"
        )
    if include_u238 and not R_blanket_cm < R_u238_cm < R_structure_cm:
        raise ValueError(
            f"R_u238_cm ({R_u238_cm}) must be in "
            f"({R_blanket_cm}, {R_structure_cm})"
        )
    if include_fe:
        if include_u238:
            if not R_u238_cm < R_fe_cm < R_structure_cm:
                raise ValueError(
                    f"R_fe_cm ({R_fe_cm}) must be in "
                    f"({R_u238_cm}, {R_structure_cm})"
                )
        else:
            if not R_blanket_cm < R_fe_cm < R_structure_cm:
                raise ValueError(
                    f"R_fe_cm ({R_fe_cm}) must be in "
                    f"({R_blanket_cm}, {R_structure_cm})"
                )

    # Build surfaces (spheres)
    surfaces = {
        "r_be": openmc.Sphere(r=R_be_cm),
        "r_blanket": openmc.Sphere(r=R_blanket_cm),
        "r_struct": openmc.Sphere(
            r=R_structure_cm, boundary_type=boundary_type,
        ),
    }
    if include_u238:
        surfaces["r_u238"] = openmc.Sphere(r=R_u238_cm)
    if include_fe:
        surfaces["r_fe"] = openmc.Sphere(r=R_fe_cm)

    # Build cells (in order: innermost to outermost)
    cells = {
        "plasma": openmc.Cell(
            name="plasma",
            region=-surfaces["r_be"],
        ),
        "be_mult": openmc.Cell(
            name="be_mult",
            region=+surfaces["r_be"] & -surfaces["r_blanket"],
        ),
        # "blanket" = LiPb breeder (where TBR is tallied)
        "blanket": openmc.Cell(
            name="blanket",
            region=+surfaces["r_blanket"] & (
                -surfaces["r_u238"] if include_u238 else (
                    -surfaces["r_fe"] if include_fe else
                    -surfaces["r_struct"]
                )
            ),
        ),
    }

    if include_u238:
        cells["u238"] = openmc.Cell(
            name="u238",
            region=+surfaces["r_u238"] & (
                -surfaces["r_fe"] if include_fe else
                -surfaces["r_struct"]
            ),
        )
    if include_fe:
        cells["fe_reflector"] = openmc.Cell(
            name="fe_reflector",
            region=+surfaces["r_fe"] & -surfaces["r_struct"],
        )

    cells["structure"] = openmc.Cell(
        name="structure",
        region=+surfaces[
            "r_fe" if include_fe else (
                "r_u238" if include_u238 else "r_blanket"
            )
        ] & -surfaces["r_struct"],
    )

    # Fill materials
    cells["be_mult"].fill = materials["be"]
    cells["blanket"].fill = materials["lipb"]
    if "u238" in cells:
        cells["u238"].fill = materials["u238"]
    if "fe_reflector" in cells:
        cells["fe_reflector"].fill = materials["fe_reflector"]
    cells["structure"].fill = materials["rafm"]

    universe = openmc.Universe(cells=list(cells.values()))
    geometry = openmc.Geometry(universe)
    return geometry, cells, surfaces


def run_zffr_spherical_tbr(
    n_particles=5000,
    n_batches=10,
    R_be_cm=5.0,
    R_blanket_cm=50.0,
    R_u238_cm=65.0,
    R_fe_cm=80.0,
    R_structure_cm=85.0,
    boundary_type="vacuum",
    include_fe=True,
    include_u238=True,
    Li6_enrichment_fraction=0.90,
):
    """Run a Z-FFR spherical OpenMC TBR simulation.

    Convenience wrapper around _build_zffr_spherical_geometry +
    _build_tally + run_real_openmc_tbr transport.
    """
    import sys
    sys.path.insert(0, "code")
    from zpp.zpp_real_openmc_transport import (
        _build_blanket_materials, _build_tally, _cross_sections_xml,
    )
    import openmc
    import os
    import tempfile
    import shutil

    materials = _build_blanket_materials(
        Li6_enrichment_fraction=Li6_enrichment_fraction,
    )
    geometry, cells, surfaces = _build_zffr_spherical_geometry(
        materials,
        R_be_cm=R_be_cm,
        R_blanket_cm=R_blanket_cm,
        R_u238_cm=R_u238_cm,
        R_fe_cm=R_fe_cm,
        R_structure_cm=R_structure_cm,
        boundary_type=boundary_type,
        include_fe=include_fe,
        include_u238=include_u238,
    )

    settings, tallies = _build_tally(
        geometry, surfaces, batches=n_batches, particles=n_particles,
    )
    os.environ["OPENMC_CROSS_SECTIONS"] = _cross_sections_xml()
    model = openmc.Model(geometry=geometry, settings=settings, tallies=tallies)

    with tempfile.TemporaryDirectory() as workdir:
        try:
            model.export_to_xml(directory=workdir)
            # Use subprocess to avoid OpenMC's path_output issues
            # and to allow proper working directory
            import subprocess
            import shutil
            openmc_exe = shutil.which("openmc")
            if openmc_exe is None:
                # Fall back to .venv/Scripts/openmc.exe on Windows
                venv_dir = os.path.dirname(os.path.dirname(
                    os.path.abspath(__file__)
                ))
                candidate = os.path.join(venv_dir, ".venv", "Scripts",
                                          "openmc.exe")
                if os.path.exists(candidate):
                    openmc_exe = candidate
                else:
                    return {
                        "transport_completed": False,
                        "error": "openmc.exe not found in PATH",
                        "geometry": geometry,
                    }
            result = subprocess.run(
                [openmc_exe],
                cwd=workdir,
                capture_output=True,
                text=True,
                timeout=300,
            )
            if result.returncode != 0:
                return {
                    "transport_completed": False,
                    "error": f"openmc exit {result.returncode}: {result.stderr[:500]}",
                    "geometry": geometry,
                }
        except Exception as e:
            return {
                "transport_completed": False,
                "error": str(e),
                "geometry": geometry,
            }

        # Read tally
        statepoint_path = os.path.join(workdir, "statepoint.10.h5")
        if not os.path.exists(statepoint_path):
            return {"transport_completed": False, "error": "no statepoint"}
        sp = openmc.StatePoint(statepoint_path)
        tbr_tally = sp.tallies[list(sp.tallies.keys())[0]]
        mean = tbr_tally.mean.flatten()[0]
        std = tbr_tally.std_dev.flatten()[0]
        sp.close()
        return {
            "transport_completed": True,
            "TBR_mc": float(mean),
            "TBR_rel_stddev": float(std / mean) if mean > 0 else None,
            "geometry": geometry,
        }
