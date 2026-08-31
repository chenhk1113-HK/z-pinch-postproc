# Architecture

`z-pinch-postproc` is organized into two integrated modules that share
the same `code/` namespace:

1. **Yield post-processor** — computes fusion engineering metrics
   from radiation-MHD profile data.
2. **Blanket neutronics (TBR calculator)** — computes tritium breeding
   ratio for LiPb/Be/Fe/U-238 blankets via parametric formula or
   OpenMC Monte Carlo.

## Module map (Tier-organized)

### Tier 1-4 — Yield post-processor (v0.1.0-v0.4.0)

```
code/
├── zpp_io.py                  # Input/output for 1D rad-MHD profiles
├── zpp_bosch_hale.py          # D-T reactivity <σv> parameterization
├── zpp_alpha_heating.py       # α-particle energy deposition model
├── zpp_lawson.py              # Lawson triple product integrator
├── zpp_geometry.py            # Geometry helpers
├── zpp_coupled_plant.py       # Plant-level gain chain
└── zpp_economics.py           # Cost-of-electricity calculator
```

These modules take a single 1D profile (e.g. from FLASH) and produce
the eight engineering metrics listed in `README.md`.

### Tier 5-8 — Parametric TBR formula (v0.5.0-v0.8.0)

```
code/
├── zpp_tbr.py                 # Parametric TBR formula (Sobes-style)
├── zpp_geometry_tbr.py        # Piecewise-linear interpolation (Tier 12)
└── zpp_tbr_diagnose.py        # TBR deconstruction tool (Tier 11)
```

The parametric formula is calibrated against OpenMC transport via the
piecewise-linear interpolation table. Trade: ~milliseconds per query
vs ~1-2 minutes per query for OpenMC.

### Tier 9-11 — Validation, sweep, deconstruction (v1.2.0)

```
code/
├── zpp_real_openmc_transport.py  # OpenMC wrapper (Tier 6)
└── tests/test_zpp_tier*.py       # Tier-specific tests
```

Tier 9 — Furuta 1987 natural-Li sphere benchmark (validation).
Tier 10 — Extended sweep across R_blanket, Li-6, mult_inside.
Tier 11 — TBR deconstruction tool that surfaces Tier 7 finding
   (R_b=50 non-monotonicity).

### Tier 12-14 — Be placement, Fe reflector, Antong refs (v1.3.0)

```
code/
└── zpp_zffr_references.py     # Z-FFR Antong Fusion reference catalog
docs/
└── zffr_references.md         # Antong Fusion bibliography
```

Tier 12 — Be placement (inside vs outside LiPb) calibration table.
Tier 13 — Fe reflector sweep (counterintuitive finding: HURTS).
Tier 14 — Antong Fusion (安东聚变) reference catalog.

### Tier 15-17 — Honest failure, U-238, Z-FFR spherical (v1.4.0)

```
code/
├── zpp_real_openmc_transport.py  # Extended with R_u238_cm parameter
└── zpp_zffr_spherical.py         # 1D spherical Z-FFR geometry
data/nuclear_data/                # 16 nuclides including U-238
├── endf_viii0/                   # ENDF/B-VIII.0 source files
└── ace/cross_sections.xml        # Registered nuclide list
```

Tier 15 — Honest negative: smooth closed-form for mult_inside=False.
Tier 16 — U-238 hybrid blanket sweep (counterintuitive: −26% TBR).
Tier 17 — Z-FFR spherical geometry validation (TBR=1.44 EXCEEDS
   Peng's published 1.15-1.24 target).

## Design philosophy

### 1. Two-level calibration hierarchy

The parametric formula is **fast** but approximate. OpenMC is **slow**
but accurate. The design is:
- Use the parametric formula for parameter sweeps (millions of points).
- Use OpenMC for validation at representative points.
- Calibrate the parametric formula against OpenMC at 5-10 anchor points.

This gives the user **fast feedback** for design exploration with
**honest validation** at the chosen design points.

### 2. Honest negative findings

If a feature doesn't work as expected, document the failure rather than
paper over it. Examples:

- Tier 9: Furuta 1987 closed-form overshoots pure-Li sphere by +106%.
- Tier 13: Fe reflector HURTS TBR by 14% in cylindrical geometry.
- Tier 15: No smooth closed-form fits mult_inside=False within 5%.
- Tier 16: U-238 HURTS TBR by 26% in cylindrical geometry.

These are **features** because they tell the user where the tool's
blind spots are, so they don't trust it in regimes it hasn't been
validated against.

### 3. Tier-based development

Each Tier adds one feature or one validation. This makes the codebase
easy to understand (you can read Tier-by-Tier) and easy to extend
(add Tier N+1).

### 4. Tier-specific test files

Each Tier has a corresponding `tests/test_zpp_tier<N>.py` file. This
makes test failures easy to localize ("Tier 15 failed" tells you
exactly which feature broke).

### 5. Reproducibility

- Pin all dependencies in `requirements.txt`.
- Pin all cross section versions in `data/nuclear_data/`.
- Document all input parameters in test docstrings.
- Use git tags for releases (v0.5.0, v0.6.0, ..., v1.4.0).

## Data flow (Tier 16-17 example)

```
User config:
  R_blanket_cm = 50, Li6_enrichment_fraction = 0.90,
  mult_inside = True, R_u238_cm = 60, R_fe_cm = 75

code/zpp_real_openmc_transport.py:
  _build_blanket_materials()          # creates openmc.Materials
  _build_zpinch_geometry(materials,   # creates openmc.Geometry
                         R_u238_cm=60, R_fe_cm=75)
  _build_tally(geometry, surfaces)    # creates openmc.Tally
  openmc.Model() + openmc.run()       # runs MC transport
  → returns RealOpenMCTBRResult

code/zpp_zffr_spherical.py (Tier 17):
  _build_zffr_spherical_geometry()    # spherical variant
  run_zffr_spherical_tbr()            # thin wrapper
```

## File layout (top-level)

```
z-pinch-postproc/
├── README.md                       # Main README
├── ARCHITECTURE.md                 # This file
├── CONTRIBUTING.md                 # Contribution guide
├── CITATION.cff                    # GitHub citation
├── LICENSE                         # MIT
├── CHANGELOG.md                    # Version history
├── MODEL_ASSUMPTIONS_AND_LIMITATIONS.md   # Physics assumptions
├── PLAN_v0.1.md                    # Original project plan
├── requirements.txt                # Pinned dependencies
├── pyproject.toml                  # Python project config
├── code/                           # Implementation modules
├── tests/                          # pytest tests
├── data/                           # Reference data
│   ├── nuclear_data/               # ENDF + ACE cross sections
│   └── results/                    # MC sweep results (per-Tier)
├── docs/                           # Additional documentation
│   └── zffr_references.md
└── scripts/                        # Cross-section download, etc.
```