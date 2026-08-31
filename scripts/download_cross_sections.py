"""
Download OpenMC cross-sections for LiPb blanket + RAFM structure.

This downloads ONLY the nuclides needed for a LiPb blanket with
Be neutron multiplier and Ferritic/Martensitic steel structure,
per `code/zpp_cross_sections.py::list_required_nuclides_for_blanket`.

Total download: ~30 MB compressed (much smaller than full 5 GB
ENDF/B-VIII.0 library). The selected nuclides are:

  - H-1:  Structural hydrogen (e.g. water coolant variants)
  - Li-6: Primary tritium breeder
  - Li-7: Secondary tritium breeder (95% of natural Li)
  - Be-9: Neutron multiplier (also Be-7 for completeness)
  - Fe-56: Dominant steel isotope (also 54, 57, 58)
  - Pb-204/206/207/208: Lead (LiPb coolant)

After download, ENDF files are converted to ACE format using
NJOY (bundled with openmc-anywhere at .venv/Scripts/njoy.exe).

OpenMC expects a `cross_sections.xml` listing all ACE files.
"""

import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data" / "nuclear_data"
ENDF_DIR = DATA_DIR / "endf_viii0"
ACE_DIR = DATA_DIR / "ace"
NJOY_EXE = PROJECT_ROOT / ".venv" / "Scripts" / "njoy.exe"


# Nuclides needed for LiPb blanket + structure
# Format: (IAEA filename, output ENDF name)
NUCLIDES = [
    ("n_0125_1-H-1.zip", "H_001_001.endf"),
    ("n_0325_3-Li-6.zip", "Li_003_006.endf"),
    ("n_0328_3-Li-7.zip", "Li_003_007.endf"),
    ("n_0419_4-Be-7.zip", "Be_004_007.endf"),
    ("n_0425_4-Be-9.zip", "Be_004_009.endf"),
    ("n_2625_26-Fe-54.zip", "Fe_026_054.endf"),
    ("n_2628_26-Fe-55.zip", "Fe_026_055.endf"),
    ("n_2631_26-Fe-56.zip", "Fe_026_056.endf"),
    ("n_2634_26-Fe-57.zip", "Fe_026_057.endf"),
    ("n_2637_26-Fe-58.zip", "Fe_026_058.endf"),
    ("n_8225_82-Pb-204.zip", "Pb_082_204.endf"),
    ("n_8228_82-Pb-205.zip", "Pb_082_205.endf"),
    ("n_8231_82-Pb-206.zip", "Pb_082_206.endf"),
    ("n_8234_82-Pb-207.zip", "Pb_082_207.endf"),
    ("n_8237_82-Pb-208.zip", "Pb_082_208.endf"),
    # Tier 16 (2026-08-31): U-238 for hybrid fission blanket (Z-FFR-style).
    ("n_9237_92-U-238.zip", "U_092_238.endf"),
    # Tier 18.B (2026-08-31): Li4SiO4 ceramic breeder needs Si-28/29/30 + O-16
    ("n_1425_14-Si-28.zip", "Si_014_028.endf"),
    ("n_1428_14-Si-29.zip", "Si_014_029.endf"),
    ("n_1431_14-Si-30.zip", "Si_014_030.endf"),
    ("n_0825_8-O-16.zip", "O_008_016.endf"),
    # Tier 17 (2026-08-31): Pb-207 already covered; need O-16 for Li4SiO4
    # ceramic breeder, W-184 for tungsten first wall (Z-FFR design), and
    # Cr-52 / Mn-55 / Ni-58 for EUROFER97 RAFM (more realistic than pure Fe).
    # Skipping for v1.4 — Tier 17 uses simplified spherical geometry.
]

BASE_URL = "https://www-nds.iaea.org/public/download-endf/ENDF-B-VIII.0/n/"


def download_nuclide(filename, dest_dir):
    """Download and unzip one nuclide's ENDF file."""
    url = BASE_URL + filename
    target = dest_dir / filename
    if target.exists():
        return target
    print(f"  Downloading {filename}...")
    # IAEA NNDC requires a non-default User-Agent (blocks urllib default)
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/120.0.0.0 Safari/537.36",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            target.write_bytes(resp.read())
        return target
    except Exception as e:
        print(f"  FAIL: {e}")
        return None


def extract_endf_from_zip(zip_path, endf_dir):
    """Extract .dat file from IAEA nuclide zip, rename to .endf.

    IAEA NNDC zip files contain a single .dat file with the
    ENDF/B-VIII.0 evaluated nuclear data in ENDF-6 format.
    """
    with zipfile.ZipFile(zip_path) as zf:
        for name in zf.namelist():
            if name.endswith(".dat") or name.endswith(".endf"):
                # Extract to a known location
                zf.extract(name, endf_dir)
                src = endf_dir / name
                # Flatten: rename to <endf_name>
                dst = endf_dir / Path(name).stem  # strip .dat
                if src != dst:
                    if dst.exists():
                        dst.unlink()
                    src.rename(dst)
                return dst
    return None


def convert_endf_to_ace(endf_path, ace_dir, njoy_exec):
    """Use openmc.data.njoy.make_ace() to convert ENDF to ACE.

    Uses the bundled NJOY2016 binary at njoy_exec.
    The ACE file is written to CWD with the name 'ace', then moved
    to ace_dir/<stem>.ace.
    """
    try:
        import openmc.data
    except ImportError:
        print("  openmc not installed; skip ACE conversion")
        return None
    try:
        # Run NJOY in a tempdir that already has all inputs/outputs
        # make_ace writes intermediate NJOY tapes + final 'ace' file
        # to output_dir (the final ACE file is named 'ace' regardless
        # of `acer=` kwarg when output_dir is given — verified empirically).
        import tempfile, shutil
        with tempfile.TemporaryDirectory() as tmpdir:
            openmc.data.njoy.make_ace(
                str(endf_path),
                njoy_exec=njoy_exec,
                output_dir=tmpdir,
                acer=os.path.join(tmpdir, "ace"),
            )
            # The final file in tmpdir is named 'ace'
            src = os.path.join(tmpdir, "ace")
            if not os.path.exists(src):
                # Try alternate name
                for f in os.listdir(tmpdir):
                    if f.endswith(".ace") or f == "ace":
                        src = os.path.join(tmpdir, f)
                        break
            dst = ace_dir / (endf_path.stem + ".ace")
            shutil.copy(src, dst)
        return dst
    except Exception as e:
        print(f"  ACE conversion failed for {endf_path.name}: {e}")
        return None


def build_cross_sections_xml(ace_dir):
    """Build the cross_sections.xml file OpenMC needs.

    OpenMC DataLibrary requires HDF5 (.h5) files, not raw ACE.
    We convert ACE -> HDF5 on the fly and register those.
    """
    import openmc.data
    library = openmc.data.DataLibrary()
    ace_files = sorted(ace_dir.glob("*.ace"))
    n_hdf5 = 0
    for ace_path in ace_files:
        h5_path = ace_dir / (ace_path.stem + ".h5")
        if not h5_path.exists():
            try:
                nuc = openmc.data.IncidentNeutron.from_ace(str(ace_path))
                nuc.export_to_hdf5(str(h5_path))
                n_hdf5 += 1
            except Exception as e:
                print(f"  Failed to convert {ace_path.name}: {e}")
                continue
        try:
            library.register_file(str(h5_path))
        except Exception as e:
            print(f"  Failed to register {h5_path.name}: {e}")
    xml_path = ace_dir / "cross_sections.xml"
    library.export_to_xml(str(xml_path))
    print(f"  Registered {len(library)} nuclides as HDF5")
    return xml_path


def main():
    print("=== Tier 8.A — Cross-sections download ===")
    print(f"Target: {DATA_DIR}")
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    ENDF_DIR.mkdir(parents=True, exist_ok=True)
    ACE_DIR.mkdir(parents=True, exist_ok=True)

    njoy_exec = str(NJOY_EXE)
    if not os.path.exists(njoy_exec):
        print(f"FATAL: NJOY not found at {njoy_exec}")
        sys.exit(1)
    print(f"Using NJOY: {njoy_exec}")

    # Step 1: Download + extract ENDF
    print(f"\n[1/3] Downloading {len(NUCLIDES)} nuclide ENDF files...")
    for filename, endf_name in NUCLIDES:
        zip_path = download_nuclide(filename, DATA_DIR)
        if zip_path is None:
            continue
        endf_path = ENDF_DIR / endf_name
        if endf_path.exists():
            continue
        extracted = extract_endf_from_zip(zip_path, ENDF_DIR)
        if extracted:
            # Rename to clean convention
            extracted.rename(endf_path)
    n_endf = len(list(ENDF_DIR.glob("*.endf")))
    print(f"  Got {n_endf}/{len(NUCLIDES)} ENDF files")

    # Step 2: Convert ENDF -> ACE via NJOY
    print(f"\n[2/3] Converting ENDF -> ACE via NJOY...")
    n_ace = 0
    for endf_path in sorted(ENDF_DIR.glob("*.endf")):
        ace_path = ACE_DIR / (endf_path.stem + ".ace")
        if ace_path.exists():
            n_ace += 1
            continue
        result = convert_endf_to_ace(endf_path, ACE_DIR, njoy_exec)
        if result:
            n_ace += 1
    print(f"  Got {n_ace} ACE files")

    # Step 3: Build cross_sections.xml
    print(f"\n[3/3] Building cross_sections.xml...")
    xml_path = build_cross_sections_xml(ACE_DIR)
    print(f"  Wrote {xml_path}")
    print(f"  Set OPENMC_CROSS_SECTIONS={xml_path}")


if __name__ == "__main__":
    main()