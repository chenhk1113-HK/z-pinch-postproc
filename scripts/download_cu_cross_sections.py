"""Download Cu cross-sections (Cu-63, Cu-65) from IAEA + convert ENDF → ACE via NJOY."""
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

PROJECT_ROOT = Path(r"C:\Users\lamkuenai\projects\z-pinch-postproc")
DATA_DIR = PROJECT_ROOT / "data" / "nuclear_data"
ENDF_DIR = DATA_DIR / "endf_viii0"
ACE_DIR = DATA_DIR / "ace"
NJOY_EXE = PROJECT_ROOT / ".venv" / "Scripts" / "njoy.exe"

# Cu nuclides (Tier 19.C electrode material)
NUCLIDES = [
    ("n_2925_29-Cu-63.zip", "Cu_029_063.endf"),
    ("n_2931_29-Cu-65.zip", "Cu_029_065.endf"),
]
BASE_URL = "https://www-nds.iaea.org/public/download-endf/ENDF-B-VIII.0/n/"


def download_one(filename, dest_dir):
    """Download and unzip one nuclide's ENDF file from IAEA."""
    url = BASE_URL + filename
    zip_path = dest_dir / filename
    if zip_path.exists():
        print(f"  {filename}: zip already present")
        return zip_path
    print(f"  Downloading {filename} from IAEA...")
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    })
    with urllib.request.urlopen(req, timeout=60) as resp:
        zip_path.write_bytes(resp.read())
    print(f"    OK ({zip_path.stat().st_size} bytes)")
    return zip_path


def extract_zip(zip_path, endf_name, extract_dir):
    """Extract the ENDF file from the zip.

    IAEA packages ENDF files as `.dat` (or sometimes `.endf` for newer
    releases). Same format, different extension. `endf_name` is the
    canonical name to extract to (e.g. Cu_029_063.endf).
    """
    with zipfile.ZipFile(zip_path) as zf:
        # Find any data file (.dat, .endf, or just the only file)
        data_members = [
            n for n in zf.namelist()
            if n.endswith(('.dat', '.endf')) and not n.startswith('MACROSCOPIC')
        ]
        if not data_members:
            raise RuntimeError(f"No data file in {zip_path.name}: {zf.namelist()}")
        # Extract the data file. IAEA names use format n_NNNN_ZZ-Elem-MASS.dat
        # but the project convention is Elem_ZZZ_MMMM.endf.
        # The mapping is given by the (zip_name, endf_name) tuple pair.
        for member in data_members:
            member_name = Path(member).name.replace('.dat', '.endf')
            target = extract_dir / Path(member_name).name
            # We may have extracted under the old name first — overwrite.
            if target.exists():
                target.unlink()
            with zf.open(member) as src, open(target, 'wb') as dst:
                shutil.copyfileobj(src, dst)
            print(f"    Extracted: {target.name} ({target.stat().st_size} bytes)")
        # Rename to canonical name
        for member in data_members:
            member_name = Path(member).name.replace('.dat', '.endf')
            actual = extract_dir / Path(member_name).name
            if endf_name not in (p.name for p in extract_dir.iterdir()):
                actual.rename(extract_dir / endf_name)
                print(f"    Renamed {actual.name} -> {endf_name}")


def convert_one(endf_path, njoy_exec):
    """Convert ENDF → ACE via openmc.data.njoy.make_ace."""
    import openmc.data

    # Resolve njoy_exec to absolute path
    njoy_abs = str(Path(njoy_exec).resolve())

    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            openmc.data.njoy.make_ace(
                str(endf_path),
                njoy_exec=njoy_abs,
                output_dir=tmpdir,
                acer=os.path.join(tmpdir, "ace"),
            )
        except Exception as e:
            print(f"    NJOY failed: {type(e).__name__}: {e}")
            return None

        # NJOY writes ACE to 'ace' (the acer arg value)
        src = os.path.join(tmpdir, "ace")
        if not os.path.exists(src):
            # try alternate name (some openmc versions)
            for f in os.listdir(tmpdir):
                if f.endswith(".ace") or f == "ace":
                    src = os.path.join(tmpdir, f)
                    break
        if not os.path.exists(src):
            print(f"    NJOY did not produce ACE file in {tmpdir}")
            return None

        # Move to ACE_DIR with stem.ace
        target = ACE_DIR / f"{endf_path.stem}.ace"
        shutil.copy(src, target)
        print(f"    -> {target.name} ({target.stat().st_size} bytes)")
        return target


def main():
    ENDF_DIR.mkdir(parents=True, exist_ok=True)
    ACE_DIR.mkdir(parents=True, exist_ok=True)

    for zip_name, endf_name in NUCLIDES:
        endf_path = ENDF_DIR / endf_name
        if not endf_path.exists():
            print(f"\n=== {endf_name} ===")
            zip_path = download_one(zip_name, ENDF_DIR)
            extract_zip(zip_path, endf_name, ENDF_DIR)
        else:
            print(f"\n=== {endf_name}: ENDF already present ===")

        # Convert ENDF -> ACE
        ace_path = ACE_DIR / f"{endf_path.stem}.ace"
        if not ace_path.exists():
            convert_one(endf_path, NJOY_EXE)
        else:
            print(f"  ACE already present: {ace_path.name}")

    # Convert ACE -> HDF5 via IncidentNeutron.from_ace (project's pattern)
    print("\n=== Converting ACE -> HDF5 ===")
    import openmc.data
    for endf_name in [e for _, e in NUCLIDES]:
        endf_path = ENDF_DIR / endf_name
        h5_path = ACE_DIR / f"{endf_path.stem}.h5"
        ace_path = ACE_DIR / f"{endf_path.stem}.ace"
        if h5_path.exists():
            print(f"  {h5_path.name}: already present")
            continue
        if not ace_path.exists():
            print(f"  {endf_name}: no ACE file, skip")
            continue
        try:
            print(f"  Converting {ace_path.name} -> HDF5...")
            nuc = openmc.data.IncidentNeutron.from_ace(str(ace_path))
            nuc.export_to_hdf5(str(h5_path))
            print(f"    -> {h5_path.name} ({h5_path.stat().st_size} bytes)")
        except Exception as e:
            print(f"    Failed: {e}")

    print("\n=== Summary ===")
    print("ACE files for Cu:")
    for f in ACE_DIR.glob("Cu_*"):
        print(f"  {f.name} ({f.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
