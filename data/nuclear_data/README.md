# data/nuclear_data/ — cross-section provenance

This directory holds ENDF/B-VIII.0 neutron cross sections used by
OpenMC for blanket neutronics simulations.

## Layout

```
data/nuclear_data/
├── endf_viii0/          # Source ENDF files (gitignored, ~111 MB)
│   ├── *.endf           # 16 nuclides, ENDF/B-VIII.0
│   └── ...
└── ace/                 # Generated ACE + HDF5 files (gitignored, ~727 MB)
    ├── *.ace            # ACE-format cross sections (NJOY output)
    ├── *.h5             # HDF5 format (OpenMC native)
    └── cross_sections.xml  # MANIFEST (the ONLY tracked file)
```

## What is tracked

Only `data/nuclear_data/ace/cross_sections.xml` (the manifest) is
tracked in git. It registers all nuclides + paths. The `.endf`, `.ace`,
and `.h5` files are gitignored — they are regenerable from
`scripts/download_cross_sections.py`.

## Why we don't commit 838 MB of cross sections

- **Git repo size**: 838 MB committed would inflate the repo ~400×
  for a ~2 MB codebase. GitHub warns at 1 GB, blocks at 5 GB.
- **Reproducibility**: cross sections are versioned (ENDF/B-VIII.0)
  and the script pins the exact IAEA URL.
- **CI efficiency**: CI regenerates fresh on every run (~5 min NJOY
  compilation cost, but parallelized by matrix).

## How to regenerate

```bash
# Download ENDF + run NJOY + register in cross_sections.xml
python scripts/download_cross_sections.py

# Takes ~5-10 min on first run; subsequent runs are no-op if files exist
```

## Nuclides included (16)

| Z | Symbol | A | Notes |
|---|---|---|---|
| 1 | H | 1 | Hydrogen (in LiPb coolant) |
| 3 | Li | 6 | Li-6 (enriched, breeds tritium via (n,T)α) |
| 3 | Li | 7 | Li-7 (breeds via (n,n'α)T) |
| 4 | Be | 7 | Be-7 (minor, in some LiPb formulations) |
| 4 | Be | 9 | Be-9 (neutron multiplier via (n,2n)) |
| 26 | Fe | 54-58 | Steel structure / reflector |
| 82 | Pb | 204-208 | Lead in LiPb coolant |
| 92 | U | 238 | Optional fission blanket (Tier 16) |

## Tier 18 additions (planned)

For Li4SiO4 ceramic breeder (Z-FFR Peng 2014 design):
- Si-28, Si-29, Si-30 (silicon in breeder)
- O-16 (oxygen in breeder)

These will be added via `scripts/download_cross_sections.py` once Tier 18 ships.

## Sources

- **IAEA ENDF/B-VIII.0**: https://www-nds.iaea.org/exfor/endf.htm
- **NJOY 2016**: converts ENDF → ACE for OpenMC
- **OpenMC 0.16.x**: reads ACE or HDF5