# MODEL ASSUMPTIONS AND LIMITATIONS — z-pinch-postproc

**Version:** v0.0.1-prelim (2026-08-29)
**Status:** Pre-flight + scaffold. No real-data validation yet.
**Per:** `Z_Machine_plan.pdf` (user-uploaded, 2026-08-29), open-source landscape survey.

This document is the **single concise top-level reference** for every
assumption, fixed parameter, approximation, and known limitation in the
project. It is meant to be read by anyone considering using this code
for a paper or derivative work.

---

## Executive summary — at-a-glance

### What this code does

A small pure-Python post-processor that ingests a 1D rad-MHD profile
(time-series of ion temperature, fuel density, column density, radius)
plus a few driver parameters, and computes the engineering metrics
relevant to a Z-pinch fusion power plant (target gain, engineering gain,
wall-plug efficiency, burn-weighted Lawson, stagnation pressure, yield).

### What this code does NOT do

- It is not a rad-MHD solver. We call FLASH, ESTHER, HYDRA, WarpX, Smilei,
  or MACH2 — we do not replace them.
- It is not a driver circuit model. We take the driver current / stored
  energy / driver efficiency as input scalars.
- It is not a neutronics / blanket / BOP model. The wall-plug chain
  uses a single η_helper efficiency factor (default 0.40 = thermal →
  electrical, Brayton-cycle typical).

### What's new in v0.0.1-prelim

- Synthetic-shot smoke test passes
- Bosch-Hale D-T reactivity parametrisation, 0.2-100 keV
- CSV / JSON I/O
- Eight engineering metrics in a single output JSON
- This MODEL_ASSUMPTIONS doc + PLAN_v0.1 + README + OPEN_SOURCE_LANDSCAPE

### Standing limitations (acknowledged)

| # | Limitation | Status |
|---|---|---|
| 1 | No real-data validation yet | v0.1 (Z-shot 2960) |
| 2 | η_helper is a single scalar, not a Brayton-cycle model | v0.2 (PROCESS) |
| 3 | No alpha-heating bootstrap | v0.3 (Slutz 2021 scaling) |
| 4 | No TBR coupling | v0.3 (OpenMC + Paramak) |
| 5 | 1D-only post-processor | v0.4 (if needed; most MagLIF fits are 1D anyway) |
| 6 | Synthetic fixture is not yet tuned to a real shot | v0.1 |

---

## 1. What physics is INCLUDED

| Item | Reference | Module |
|---|---|---|
| D-T reactivity <σv>_DT | Bosch & Hale 1992, NIFS data | `code/zpp_bosch_hale.py` |
| 1D burn integration over time | Standard inertial-confinement yield formula | `code/zpp_pipeline.py::burn_yield` |
| Burn-weighted Lawson triple product | Standard ⟨nTτ⟩_DT | `code/zpp_lawson.py` |
| Target gain Q_target = E_fus / E_kinetic | Standard | `code/zpp_pipeline.py` |
| Engineering gain Q_eng = E_fus / E_stored | Standard | `code/zpp_pipeline.py` |
| Wall-plug efficiency chain (driver × helper) | Standard | `code/zpp_pipeline.py` |
| Stagnation pressure estimate | P = 2 nT (Boltzmann ×2 for compression) | `code/zpp_pipeline.py` |
| Convergence ratio | R_initial / R_stag | `code/zpp_pipeline.py` |

## 2. What physics is OMITTED (deferred)

- **Driver circuit model** (Marx generators, LTDs, water transmission
  lines, pulse-forming networks) — input is taken from upstream rad-MHD
  or driver sim.
- **Rad-MHD simulation** — we ingest, not compute.
- **Neutronics** (TBR, neutron energy deposition, shutdown dose rate) — OpenMC
  + Paramak + ALARA, deferred to v0.2.
- **BOP / Brayton cycle / LCOE** — PROCESS, deferred to v0.2.
- **Alpha-heating bootstrap** — Slutz 2021 scaling, deferred to v0.3.
- **2D / 3D effects** (sausage / kink instabilities, mix, wall modes) —
  most published MagLIF fits are 1D; deferred unless 2D profile is provided.
- **Magnetic flux diffusion / Nernst effect** — driver-level effect, input.

## 3. Fixed parameters (v0.0.1 defaults)

| Parameter | Default | Why |
|---|---|---|
| D-T reaction energy | 17.6 MeV | Standard |
| D-T branching ratio | 1.0 (all → He-4 + n + 17.6 MeV) | Approximation (ignores DD/DHe3 branches) |
| η_helper (thermal → electrical) | 0.40 | Typical Brayton cycle, 0.35-0.45 range |
| D-T number density ratio | 0.5:0.5 (equimolar) | Stoichiometric |
| Burn-window detection | T > 1 keV AND ρ > 0.1 g/cm³ | Heuristic; can be overridden in CLI |
| Time units | ns | All input time arrays expected in ns |
| Energy units in output | MJ (primary), J (secondary) | Convenience |

## 4. Approximations

| Approximation | Where | Impact |
|---|---|---|
| 1D cylindrical geometry | zpp_pipeline.burn_yield | Ignores 3D mix; expected ≤30% error on yield |
| Equimolar D-T | zpp_pipeline.composition | Real MagLIF shots use 1:1 D-T or pure D (DD) — switchable in CLI |
| Static η_helper (no temperature-dependent BOP) | zpp_pipeline.gain_chain | v0.2 replaces with PROCESS |
| No alpha heating in v0.0.1 | zpp_pipeline.burn_yield | v0.3 adds Slutz 2021 scaling |
| No back-reaction of fusion products on implosion | not modeled | The implosion is taken as fixed history; the post-processor only reads the T, ρ, ρR history |

## 5. Known tensions (acknowledged)

| Tension | Source | Project stance |
|---|---|---|
| The Bosch-Hale parametrisation is valid 0.2-100 keV; below 0.2 keV (relevant for sub-keV implosions) extrapolation can be off | Bosch & Hale 1992, Table VII | Documented; CLI warns if T_min < 0.2 keV |
| The synthetic shot in v0.0.1 is a Gaussian T/ρ profile, not a real shot's history | This is intentional for testing | v0.1 will add a real Z-shot 2960 fixture |
| The η_helper default of 0.40 is a Brayton-cycle number, but a Z-pinch plant might use a more exotic cycle | No published Z-pinch plant design yet | Documented; CLI accepts override |

## 6. Standing version

`v0.0.1-prelim` (2026-08-29). All "what's new" entries above refer to the
initial scaffold. No real-data validation, no neutronics coupling, no
BOP coupling, no alpha heating. Each deferred item maps to a planned
future version (v0.1 - v0.4).

## 7. Verification

- `python -m py_compile code/zpp_run.py code/zpp_pipeline.py code/zpp_bosch_hale.py code/zpp_lawson.py code/zpp_io.py` → exit 0
- `pytest tests/ -v` → all smoke tests pass
- Output JSON validates against the schema in `PLAN_v0.1.md §5.3`
