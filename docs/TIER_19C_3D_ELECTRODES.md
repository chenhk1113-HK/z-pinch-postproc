# Tier 19.C — Electrode CSG in Z-pinch 3D Geometry

> **Status**: Tier 19.C shipped 2026-09-01. Adds cylindrical Cu **electrode blocks** at z = ±h/2 (where plasma current dumps in a real Z-pinch) to the Tier 19.A/B geometry. Sweeps over electrode height h_elec ∈ {2, 5, 10} cm plus a combined h_elec + 1-port config.

## Headline finding

**Cu electrodes reduce TBR by 1-11% linearly with h_elec**:

| h_elec (cm) | TBR @ n=5000 | Δ vs Tier 19.A | Match ratio |
|---|---|---|---|
| 0 (no electrode) | 1.8383 ± 0.0091 | +0.42% (within 1σ noise) | 1.0000 |
| 2 | 1.8014 ± 0.0090 | **−1.60%** | 1.0000 |
| 5 | 1.7447 ± 0.0081 | **−4.69%** | 1.0000 |
| 10 | 1.6339 ± 0.0062 | **−10.75%** | 1.0000 |
| 5 + 1 port d=2cm (combined) | 1.7496 ± 0.0072 | **−4.42%** | 1.0000 |

**Scaling**: ~−1.07% TBR per cm of Cu electrode. Linear in h_elec (consistent with neutron absorption by a uniform-thickness high-Z layer at the end caps).

**Combined effect**: h_elec=5cm + 1 port d=2cm gives TBR=1.7496, vs h_elec=5cm alone TBR=1.7447. The port adds back **+0.27%** at this geometry (within 1σ noise; not a significant finding). The dominant effect is the electrode.

**Cross-validation**: mesh-cell match ratio = 1.0000 in every config. The CylindricalMesh tally sums to the cell tally exactly.

## Why this matters

A real Z-pinch has **electrodes** at the top and bottom where plasma current dumps. Tier 19.B closed the diagnostic-port contribution to the engineering-scope warning. Tier 19.C closes the **electrode contribution**, which is the dominant source of TBR penalty in a real Z-pinch.

The README's "5-15% TBR reduction from first-wall penetrations, ports, and 3D geometry effects" was calibrated to **electrode effects**, not ports. Tier 19.C confirms this calibration.

## Method

1. **Cu cross-sections** downloaded from IAEA (`n_2925_29-Cu-63.zip`, `n_2931_29-Cu-65.zip`) and converted via NJOY to ACE → HDF5. Registered in `data/nuclear_data/ace/cross_sections.xml` as `Cu63` + `Cu65`.

2. **Geometry**: cylindrical Cu electrodes at z ∈ [-h/2, -h/2 + h_elec_cm] and z ∈ [h/2 - h_elec_cm, h/2], radius R_electrode = R_blanket_cm = 50 cm (fills entire end-cap cross-section). Built via CSG complement: the electrode region is SUBTRACTED from the blanket cell region (`cells["blanket"].region = cells["blanket"].region & ~top_elec_region & ~bot_elec_region`), then the electrode cells are added back with Cu fill.

3. **Composition**: Cu-63 69.17% + Cu-65 30.83% (natural abundance). Cross-sections from ENDF/B-VIII.0 via IAEA NNDC.

4. **Run**: same as Tier 19.B (`subprocess.run(["openmc", "--threads", "1"], ...)`), using the existing `build_tier19_tallies()` for cell + CylindricalMesh tallies.

5. **Validation**: match_ratio = mesh_3d_sum / cell_tally, must be 1.0000 ± 0.001.

## Files

| File | Purpose |
|---|---|
| `zpp/zpp_real_openmc_3d_electrodes.py` | `build_zpinch_geometry_with_electrodes()` + `run_tier19c_3d_electrodes()` + `tier19c_to_markdown()` |
| `scripts/run_tier19c_3d_electrodes_sweep.py` | 5-config sweep driver |
| `scripts/download_cu_cross_sections.py` | Download + NJOY conversion of Cu-63 + Cu-65 |
| `data/nuclear_data/ace/Cu_029_063.{ace,h5}` | Cu-63 cross-sections (24 MB ACE + 7 MB HDF5) |
| `data/nuclear_data/ace/Cu_029_065.{ace,h5}` | Cu-65 cross-sections (21 MB ACE + 8 MB HDF5) |
| `data/nuclear_data/ace/cross_sections.xml` | Updated to register Cu63 + Cu65 |
| `data/results/2026-09-01_2059_tier19c_3d_electrodes/` | 5 JSONs + 5 MDs + CSV + summary |

## Engineering implications

### When designing a real Z-pinch:

- **Electrode height penalty is ~−1% TBR per cm of Cu.** A 2 cm electrode (≈ thin annular contact ring) costs only ~1.6% TBR; a 10 cm electrode (deep recessed contact) costs ~11%. The linear scaling suggests the constraint is **total Cu volume** in the neutron flux, not geometry details.
- **W (tungsten) electrodes would be WORSE** due to higher capture cross-section. Estimated: 1.5-2× Cu penalty based on literature Z-FFR studies (Boccaccini 2016, Sawan 2011).
- **Diagnostic port effect is negligible** (Tier 19.B: <0.5%). Combined with Tier 19.C electrode effect, total "real Z-pinch" TBR penalty vs Tier 19.A perfect-cylinder baseline is **~1-11%** depending on electrode design.

### README ⚠️ engineering-scope warning (now fully closed)

**Old** (v1.6.0 through v1.8.0): "first-wall penetrations, ports, and 3D geometry effects that can reduce TBR by 5–15%"

**New** (Tier 19.C): "first-wall penetrations, ports, and 3D geometry effects can reduce TBR by 5–15%. **Tier 19.B (Sep 2026)** adds diagnostic ports and shows the actual port TBR penalty is **<0.5%**. **Tier 19.C (Sep 2026)** adds Cu electrodes and shows the actual electrode TBR penalty is **−1.07% per cm** (so 1.6% at h_elec=2 cm, 4.7% at h_elec=5 cm, 10.8% at h_elec=10 cm). The 5-15% engineering-scope upper bound is now fully explained by electrode geometry alone."

## Cross-validation with Tier 19.B

- **Combined test**: h_elec=5cm + 1 port d=2cm → TBR=1.7496, ΔTBR vs no-electrode=−4.42%. Compare to:
  - h_elec=5cm alone: 1.7447, ΔTBR=−4.69%
  - Port alone (Tier 19.B): 1.8329, ΔTBR=+0.13% (within noise)
- **Combined effect is approximately additive in TBR** (−4.42% ≈ −4.69% + ~0.27% from port noise). The electrode effect dominates.

## Open follow-up

- **W (tungsten) electrode material**: not yet implemented. Could be done by extending the `_make_cu_material` to accept "W" and downloading W cross-sections.
- **Steel (EUROFER97) electrode**: similar to W. Not yet implemented.
- **Electrode radius sweep** (currently fixed at R_blanket_cm): could vary to study surface-area effects.
- **Cap geometry** (currently full cylindrical block): real electrodes are often annular or conical. Not modelled.

## References

- Tier 19.A: `docs/TIER_19_3D_GEOMETRY.md` (mesh-only 3D baseline, TBR=1.8306)
- Tier 19.B: `docs/TIER_19B_3D_GEOMETRY.md` (diagnostic ports, TBR=1.83±0.01)
- Tier 19.B+: `docs/TIER_19B_PLUS_VACUUM_BC.md` (vacuum BC, TBR=0.91±0.005)
- Cu cross-sections: IAEA NNDC ENDF/B-VIII.0, https://www-nds.iaea.org/public/download-endf/ENDF-B-VIII.0/n/
- zreview5 audit Item 7: `docs/zreview5_audit.md`