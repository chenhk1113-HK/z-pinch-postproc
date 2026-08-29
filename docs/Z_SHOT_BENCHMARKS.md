# Z-Shot Benchmark Parameters for Validation

> **Purpose**: The published Z-machine + MagLIF shot record we use to
> validate `z-pinch-postproc` against in v0.1.0+. These numbers are
> the ground truth that the post-processor must reproduce within the
> published uncertainties.

## 1. Sandia Z present-day (Gomez 2020 PRL 125 155002)

The published record for a representative 20 MA MagLIF shot on Z
(Gomez 2020 PRL 125 155002, the "Z 2960-class" data):

| Quantity | Value | Reference |
|---|---|---|
| Peak current I_peak | **20 MA** | Yager-Elorriaga 2022 table 1 |
| Pre-applied B-field B_z0 | **16 T** | Yager-Elorriaga 2022 table 1 |
| Laser preheat E_laser | **1.2 kJ** | Yager-Elorriaga 2022 table 1 |
| Burn-averaged T_ion | **3.1 keV** | Gomez 2020 PRL 125 155002 |
| Primary DD neutron yield | **1.1e13** | Gomez 2020 PRL 125 155002 |
| D-T equivalent yield | **2 kJ** | (DD × ~180 conversion) |
| Fuel CR | **~3** | (fuel column, not liner) |
| Liner CR | **~25** | (Gomez 2020 reports this) |
| Fuel R_stag | **1-2 mm** | Slutz 2010, McBride 2015 |
| Stagnation τ_burn | **~1 ns** (layer) / ~5 ns (integrated) | Hansen 2021 SULI |
| Magnetic field BR | **40 T·cm** | Yager-Elorriaga 2022 |
| Wall-plug efficiency | **~4%** | Hansen 2021 SULI |

## 2. Sandia ZN design (60 MA target)

The published design for the proposed ZN upgrade (60-65 MA, LTD
technology). Per Yager-Elorriaga 2022, "At currents exceeding 65 MA,
the high gains required for fusion energy could be achievable."

| Quantity | Value | Reference |
|---|---|---|
| Peak current I_peak | **60-65 MA** | Yager-Elorriaga 2022 |
| Pre-applied B-field B_z0 | **30 T** | (assumed 2x present) |
| Laser preheat E_laser | **8 kJ** | ZN design target |
| Magnetic direct drive η_liner | **up to 20%** | Yager-Elorriaga 2022 |
| Wall-plug efficiency (target) | **~12-15%** | (our ZN design chain) |
| Required G | **~50-100** | (1 / (η_E × f_recirc × η_wp)) |
| Multi-MJ yields | **(ice-burner scaling)** | Yager-Elorriaga 2022 |

## 3. Pacific Fusion (commercial target)

Per Pacific Fusion company materials and the Sandia 2024-2025 news
cycle, the commercial design is "3x Z's stored energy" with a
rep-rate architecture.

| Quantity | Value | Reference |
|---|---|---|
| Stored energy | **3x Z** (~70 MJ) | PF company materials |
| Rep-rate target | **>1 Hz** | (commercial scale) |
| Wall-plug efficiency (target) | **~13-20%** | (our PF design chain) |

## 4. Validation thresholds

For a post-processor run on the Gomez 2020 equivalent profile, the
following quantities should be in the published ranges:

| Quantity | Expected range | Test |
|---|---|---|
| T_stag | 2-4 keV | `test_mcbride_profile_has_realistic_shape` |
| Fuel CR | 2-5 | `test_mcbride_profile_has_realistic_shape` |
| R_stag | 1-2 mm | `test_mcbride_profile_has_realistic_shape` |
| τ_burn | 0.5-10 ns | `test_mcbride_profile_has_realistic_shape` |
| E_fusion | 0.1-10 kJ | `test_real_data_post_processor_yields_kJ_class` |
| Q_eng | < 0.01 | `test_real_data_Q_eng_below_one` |
| P_stag (fuel nT) | 0.5-100 Mbar | `test_real_data_P_stag_in_mbar_range` |
| Fuel CR | 2-5 | `test_real_data_CR_matches_published` |
| Lawson nTτ | 1e17-1e21 keV s/m^3 | `test_real_data_lawson_below_break_even_class` |

## 5. What this post-processor does NOT validate

- 2D/3D effects: sausage, kink, MRT, helical structure, mix. These
  require full rad-MHD (Gorgon, HYDRA, FLASH).
- α-heating bootstrap (v0.3+).
- Tritium breeding ratio (v0.2+, OpenMC + Paramak).
- LCOE / cost analysis (v0.2+).
- Real Z-shot full-1D profiles (Gomez 2020 publishes point-summary
  data; we use the McBride semi-analytic equivalent).
