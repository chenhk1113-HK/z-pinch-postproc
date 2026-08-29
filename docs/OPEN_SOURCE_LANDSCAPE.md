# Open-Source Landscape for Z-Pinch Fusion Simulation

> **Date**: 2026-08-29
> **Source**: User-uploaded `Z_Machine_plan.pdf` + web research + GitHub topic search
> **Purpose**: Catalog the existing OSS frameworks that span the relevant physics
> regimes, so `z-pinch-postproc` can be a small *post-processor* that sits
> between upstream simulators and downstream engineering layers, not a
> monolithic re-implementation.

## TL;DR

There is **no end-to-end open-source coupled driver-to-grid simulation for
Z-pinch fusion**. The seven frameworks the user-uploaded doc lists each
own one slice of the stack. `z-pinch-postproc` ships the missing **stable
seam** — a tiny post-processor that ingests any 1D rad-MHD profile and
emits the engineering metrics that downstream neutronics / BOP layers
can consume.

---

## The seven frameworks (verified, in research order)

### 1. Plasma dynamics & Z-pinch physics (driver + target)

| Code | Maintainer | License | Status | Repo |
|---|---|---|---|---|
| **FLASH** | Flash Center, U. Rochester | BSD-3 | Production. Sandia uses it for MagLIF target design. 4,900+ users, 1,300+ papers. | flash.rochester.edu |
| **WarpX** | DOE Exascale Computing Project | BSD-3 | Production. GPU-accelerated 3D EM PIC. | github.com/BLAST-WarpX/warpx |
| **Smilei** | SMILEI collaboration | CeCILL-B | Production. Open-source PIC. | smileipic.github.io/Smilei |
| **ESTHER** | CEA (France), open-sourced recently | Open | 1D Lagrangian rad-hydro. | github.com/CEA-France/ESTHER |
| **Gorgon / HYDRA** | Sandia / AWE / LLNL | Restricted | Lab-internal, not generally available. We do **not** target this. | — |
| **MACH2 / MACH codes** | Various (LANL, U. Michigan) | Restricted / per-institution | 2D MHD Z-pinch, used in research papers. Not a clean public build. | — |

**What we use from these**: We call FLASH / ESTHER / WarpX / Smilei for
the 1D rad-MHD profile. We do not run them; the user is expected to
either (a) point zpp_run.py at a CSV/JSON they produced with one of
these codes, or (b) use the synthetic-shot fixture in v0.0.1.

### 2. Neutronics & fusion blanket

| Code | Maintainer | License | Repo |
|---|---|---|---|
| **OpenMC** | MIT + Argonne | MIT | github.com/openmc-dev/openmc |
| **DAGMC** (CAD geometry for OpenMC) | U. Wisconsin | — | github.com/svalinn/DAGMC |
| **Paramak** | (built on OpenMC) | — | github.com/fusion-energy/paramak |
| **ALARA** | U. Wisconsin | — | github.com/svalinn/ALARA |

**What we use**: deferred to v0.2 (TBR coupling to OpenMC for the
liquid-Pb first wall).

### 3. Coolant thermal-hydraulics

| Code | Maintainer | License | Domain |
|---|---|---|---|
| **OpenFOAM** | OpenFOAM Foundation | GPL-3 | mhdFoam for liquid-Pb / PbLi MHD |
| **nekRS / Nek5000** | Argonne | Apache-2 | High-order spectral CFD |
| **PyRK** | — | BSD-3 | Point kinetics for liquid-cooled nuclear |

**What we use**: deferred to v0.2 (Brayton-cycle thermal → electric).

### 4. Whole-plant systems

| Code | Maintainer | License | Domain |
|---|---|---|---|
| **PROCESS** | UKAEA | MIT | Fusion plant systems code, Brayton/Rankine, LCOE |
| **OpenFUSIONToolkit** | — | — | Plasma + engineering, mentioned in awesome-ML-plasma-physics |
| **bluemira** | — | LGPL-2.1 | Integrated multi-disciplinary design tool |

**What we use**: deferred to v0.2 (PROCESS call to replace the static
η_helper scalar).

### 5. Adjacent / supporting OSS

| Code | Domain | Use for us |
|---|---|---|
| **Mach2 talks / Eric Meier (LANL)** | Z-pinch 2D MHD | Reference, not direct code |
| **PARAMAGNET** (Henry Watkins, GitHub) | Laser-plasma MHD | Adjacent reference for the long-pulse regime |
| **OpenFUSIONToolkit** | Plasma + engineering | Reference for the systems layer |
| **kripnerl/fusion-open-source** (GitHub topic) | Curated list of 38+ fusion OSS projects | Discovery |
| **awesome-ML-in-plasma-physics** (kharitonov-ivan, GitHub) | Curated ML + plasma list | Future: ROM / surrogate models |

## What we explicitly do NOT cover (and why)

| Gap | Why we don't cover it | Who does |
|---|---|---|
| Driver circuit (Marx, LTD, water lines) | Out of scope for v0.0.1; would need a 1D/2D circuit solver | Sandia internal (SCREAMER, BERTHA); commercial (Eagle Harbor Tech) |
| Rad-MHD simulation | We ingest, not compute | FLASH, ESTHER, HYDRA, MACH2 |
| 3D MHD instabilities (sausage, kink) | v0.4+ if needed | MACH2, HYDRA, Gorgon |
| Burn-wave propagation / alpha-heating | v0.3 (Slutz 2021 scaling) | FLASH, Sandia internal |
| Neutronics / TBR | v0.2 (OpenMC) | OpenMC, ALARA |
| BOP / LCOE | v0.2 (PROCESS) | PROCESS |
| Tritium handling / safety | Out of scope | Not in OSS, mostly lab-internal |

## Standing state

`z-pinch-postproc v0.0.1-prelim` (this commit) ships:
- Bosch-Hale D-T reactivity
- 1D burn integration
- 8 engineering metrics
- Synthetic-shot smoke test
- This open-source-landscape doc

The next rounds will add real-data validation (Z-shot 2960), then neutronics
coupling (OpenMC), then BOP coupling (PROCESS), then alpha-heating.
