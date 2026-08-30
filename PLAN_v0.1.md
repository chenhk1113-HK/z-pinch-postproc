# z-pinch-postproc — PLAN v0.1

> **Standing version**: `0.6.1` (2026-08-30)
> **Status**: v0.6.1 shipped (560 tests passing). v0.6.0 (subprocess adapters, coupled plant sim, extended cost model, optimization, real PROCESS integration). v0.6.1 adds Real OpenMC integration via openmc-anywhere (unofficial PyPI package, no conda required). PROCESS + OpenMC installed; Paramak + FISPACT-II still pending. v0.7 planned for OpenMC cross-sections download + Paramak + FISPACT-II + uncertainty quantification.
> **Per**: Z_Machine_plan.pdf (user-uploaded, 2026-08-29) + open-source survey
> (see `docs/OPEN_SOURCE_LANDSCAPE.md`).

---

## 1. The question

**Can a small, open-source post-processor recover the published engineering
metrics for a MagLIF-class Z-pinch shot — given only a 1D rad-MHD profile of
the imploded fuel and a few driver parameters — and serve as the **stable
seam** between any of the seven existing rad-MHD codes (FLASH, HYDRA,
ESTHER, WarpX, Smilei, MACH2) and the engineering layers (neutronics,
thermal-hydraulics, balance-of-plant) that come after?**

If yes, then this becomes the smallest possible "glue" that lets a fusion
plant simulation accept output from any upstream driver simulation, and the
giant engineering layers downstream (OpenMC, OpenFOAM, PROCESS) can be wired
to it the same way regardless of which driver is plugged in.

If no, then we learn what the missing physics is and what to add.

## 2. Why this matters

The user-uploaded `Z_Machine_plan.pdf` documented the **seven** open-source
frameworks that span pulsed-power Z-pinch physics, neutronics, and BOP
(see `docs/OPEN_SOURCE_LANDSCAPE.md`). The doc's conclusion was that
**no end-to-end coupled driver-to-grid simulation exists in open source**
for Z-pinch fusion plants. The natural smallest-missing-piece is a
post-processor that converts any 1D rad-MHD profile into the same
engineering-metric JSON.

This project ships that post-processor, plus the validation against the
publicly-known Z-shot parameters (Z 2960 series is the most-cited MagLIF
shot record; see `docs/Z_SHOT_BENCHMARKS.md`).

## 3. What's in v0.1 scope (this round)

| Item | Status | Notes |
|---|---|---|
| `code/zpp_run.py` CLI | ✅ shipped | ingest CSV/JSON profile → report JSON |
| `code/zpp_pipeline.py` core | ✅ shipped | integrate reactivity + chain gains |
| `code/zpp_bosch_hale.py` | ✅ shipped | D-T <σv> parametrisation, 1-100 keV |
| `code/zpp_lawson.py` | ✅ shipped | burn-weighted ⟨nTτ⟩_DT |
| `code/zpp_io.py` | ✅ shipped | CSV/JSON reader + writer |
| Synthetic shot fixture | ✅ shipped | tests/fixtures/z2960_synthetic.csv |
| Smoke test | ✅ shipped | tests/test_zpp_pipeline.py |
| Bosch-Hale table regression | ✅ shipped | tests/test_zpp_bosch_hale.py |
| README + MODEL_ASSUMPTIONS + docs/OPEN_SOURCE_LANDSCAPE | ✅ shipped | |
| v0.1 + Z-shot 2960 real-data validation | ⏳ deferred | requires reading the actual paper data file |
| Multi-shot validation (Z 2858, 2960, 3033, 3060) | ⏳ deferred | v0.2 |
| Wall-plug efficiency chain (driver → BOP) | ⏳ deferred | v0.2 with PROCESS |
| Alpha-heating bootstrap model | ⏳ deferred | v0.3 |
| Tritium breeding ratio coupling to OpenMC | ⏳ deferred | v0.3 |

## 4. What's explicitly out of scope (deferred)

- Running FLASH or any rad-MHD code ourselves. We **call** them, we don't **be** them.
- A driver circuit model (Marx banks, LTDs, water transmission lines). We take
  the current profile as input from the upstream simulation.
- A neutronics or blanket model. OpenMC + Paramak exist for this; we **link** to them, we don't reimplement.
- A BOP / Brayton / LCOE model. PROCESS exists. We use a single η_helper efficiency
  factor in v0.1 and replace it with a PROCESS call in v0.2.

## 5. Methodology

### 5.1 Input contract (CSV or JSON)

Required columns / fields:

| Field | Type | Units | Source |
|---|---|---|---|
| `time_ns` | array[float] | ns | from rad-MHD profile (or synthetic) |
| `ion_temp_keV` | array[float] | keV | from rad-MHD profile |
| `fuel_density_gcc` | array[float] | g/cm³ | from rad-MHD profile (DT mass density) |
| `fuel_column_density` | array[float] | g/cm² | from rad-MHD profile (for areal-density burn) |
| `radius_cm` | array[float] | cm | optional, for stagnation pressure |
| `driver_E_stored_MJ` | scalar | MJ | driver (Marx + LTD) |
| `driver_efficiency` | scalar | - | driver, 0.05-0.20 typical |
| `liner_KE_MJ` | scalar | MJ | from rad-MHD or driver sim |

### 5.2 Computed quantities

1. **D-T reactivity** ⟨σv⟩_DT from `zpp_bosch_hale.py` (Bosch-Hale 1992 parametrisation, valid 0.2-100 keV).
2. **Fusion power density** P_fus = n_D × n_T × ⟨σv⟩_DT × E_fus (E_fus = 17.6 MeV per D-T reaction).
3. **Total yield** E_fus = ∫ P_fus × V × dt over the burn window.
4. **Target gain** Q_target = E_fus / E_kinetic.
5. **Engineering gain** Q_eng = E_fus / E_stored.
6. **Wall-plug efficiency** η_wp = E_fus / E_grid = Q_eng × η_driver × η_helper.
7. **Burn-weighted Lawson** ⟨nTτ⟩_DT = ∫ n × T × dτ / ∫ dτ.
8. **Stagnation pressure** P_stag = n_stag × T_stag × 2 (Boltzmann ×2 for dynamic compression).
9. **Convergence ratio** CR = R_initial / R_stag.

### 5.3 Output contract (JSON)

```json
{
  "input_provenance": {
    "source_file": "data/fixtures/z2960_synthetic.csv",
    "simulator": "synthetic",
    "shot_id": "z2960_synthetic",
    "n_samples": 1000,
    "timestamp": "2026-08-29T..."
  },
  "results": {
    "E_fusion_MJ": 0.12,
    "E_fusion_J": 1.2e+05,
    "Q_target": 0.024,
    "Q_eng": 0.010,
    "eta_wallplug": 0.0015,
    "tau_burn_ns": 12.5,
    "lawson_nTtau_DT": 4.2e15,
    "P_stag_GPa": 18.3,
    "convergence_ratio": 22.5
  },
  "derived": {
    "rho_initial_gcc": 0.7,
    "rho_stag_gcc": 1.4,
    "T_peak_keV": 8.5,
    "areal_density_gccm": 0.85,
    "yields_DDn_per_shot": 8.4e10
  }
}
```

## 6. Validation plan

- **v0.1**: synthetic shot (Gaussian T and ρ profiles) recovers the closed-form yield
  to within 5%. Smoke test in `tests/test_zpp_pipeline.py`.
- **v0.2**: real Z-shot 2960 data. Reference: Gomez et al., PRL 2024. Expected yield
  ~ 10¹² DD neutrons; we compute the equivalent DT yield assuming the same ion
  temperature and density.
- **v0.3**: Z-shot 2858 + 3033 + 3060 multi-shot validation.
- **v0.4**: α-heating bootstrap model — check the burn-wave propagation under
  the Slutz 2021 "ice-burner" scaling.
- **v0.5**: PROCESS-based η_helper for the wall-plug chain.

## 7. Why a small post-processor (not a full platform)

The user-uploaded doc's seven frameworks already cover the big pieces.
A monolithic reimplementation would (a) duplicate existing well-tested
code, (b) be a multi-year project, (c) be redundant with FLASH, OpenMC,
PROCESS etc. A small post-processor is:

- **Useful immediately** — anyone running a 1D FLASH or ESTHER simulation
  can pipe the output through `zpp_run.py` and get engineering metrics
  in seconds.
- **Composable** — sits naturally between the driver layer (upstream
  simulators) and the engineering layer (OpenMC, PROCESS).
- **Honest about its limits** — it doesn't pretend to be a rad-MHD
  solver or a reactor design tool. The MODEL_ASSUMPTIONS doc makes
  every approximation explicit.
- **Shippable in a single round** — fits the user's preferred cadence
  (PDF + ZIP, multi-round, with layman interleave).

## 8. Standing state

- **v0.0.1-prelim** is the initial scaffold. No real-data validation yet.
- **v0.1** is the first "useful" round — real Z-shot 2960, engineering
  metrics recovered, README explains the input/output contract.
- **v0.2** is the round where we link to OpenMC for tritium breeding and
  PROCESS for the wall-plug chain.
- **v0.3** is the round where we add the α-heating bootstrap model.
- **v0.4+** is the research roadmap (see `docs/TODO.md`).

## 9. Change history

| Date | Change | Source |
|---|---|---|
| 2026-08-29 | Initial scaffold v0.0.1-prelim. PLAN + README + MODEL_ASSUMPTIONS + OPEN_SOURCE_LANDSCAPE + synthetic shot + smoke test shipped. | Z_Machine_plan.pdf (user-uploaded), this turn |
