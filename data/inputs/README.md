# `data/inputs/` — OpenMC input decks (per drop-mcnp.docx §P1-C)

This directory documents the **published input geometries** for each Tier
result in `data/results/<date>_<tier>_*`. Each Tier directory's
`*_sweep.json` carries a provenance block (added by
`scripts/stamp_provenance.py`) recording OpenMC version, ENDF release,
and source-particle count.

## How to reproduce a published Tier

For Tiers that have a `scripts/run_tier<N>_<name>.py` reproduction script,
the one-liner is:

```bash
export OPENMC_CROSS_SECTIONS=data/nuclear_data/ace/cross_sections.xml
python scripts/run_tier<N>_<name>.py
```

This regenerates the corresponding `data/results/<date>_<tier>_*` JSON
+ MD summary. Wall-time per Tier is typically 5–120 seconds depending
on `n_particles` and `n_batches`.

## Currently published reproduction scripts

| Script | Tier | Result file | Wall |
|---|---|---|---|
| `scripts/run_tier6_sweep.py` | Tier 6 LiPb baseline (Be outside) | `data/results/2026-08-31_tier6_baseline/tier6_lipb_baseline.json` | ~14s at n=5000 |
| `scripts/run_tier6_convergence.py` | Tier 6 convergence sweep (n ∈ {500…50000}) | `data/results/<date>_tier6_convergence/tier6_convergence.{json,md}` | ~4 min total |
| `scripts/run_tier18b_sweep.py` | Tier 18.B Li₄SiO₄ (Be inside) | `data/results/2026-08-31_tier18b_li4sio4/tier18b_li4sio4_sweep.json` | ~6s at n=5000 |

The Tier 18.B script's geometry is published as a docstring at the
top of `scripts/run_tier18b_sweep.py` so a reader can audit the
specific R_plasma / R_be / R_blanket / R_struct / Li-6 enrichment /
boundary condition without reading the code.

## Tier-by-Tier geometry reference

### Tier 6 LiPb baseline (cylindrical, point-source)
```
R_plasma   = 4.0 cm
R_be       = 52.0 cm   (Be OUTSIDE the blanket)
R_blanket  = 50.0 cm   (LiPb)
R_struct   = 53.0 cm
height     = 100.0 cm
Li-6       = 0.90      (90% enriched)
BC         = reflective (white) on all outer surfaces
source     = 14.1 MeV D-T neutron, isotropic point source at origin
n_particles = 5000, n_batches = 10
```
Material: `_build_blanket_materials(Li6_enrichment_fraction=0.90)` returns
`{"lipb": Li17Pb83 with 90% Li-6, "be": Be-9, "structure": RAFM steel}`.

### Tier 18.B Li₄SiO₄ (Be INSIDE, ceramic breeder)
```
R_plasma   = 4.0 cm
R_be       = 6.0 cm    (Be INSIDE the blanket)
R_blanket  = 50.0 cm   (Li₄SiO₄ instead of LiPb)
R_struct   = 53.0 cm
height     = 100.0 cm
Li-6       = 0.90
BC         = reflective (white)
source     = 14.1 MeV D-T neutron, isotropic point source at origin
n_particles = 5000, n_batches = 10
```
Material: Li₄SiO₄ with 90% Li-6 enrichment (built by
`zpp.zpp_li4sio4.build_li4sio4_material(Li6_enrichment_fraction=0.90)`),
density 2.40 g/cm³, Si/O natural composition.

**Layer-order note**: the ~2% TBR difference between Tier 6 baseline
(`TBR=1.80`) and Tier 18.B LiPb (`TBR=1.83`) is the Be-inside-vs-outside
flip, not a measurement bug. Both numbers are correct for their respective
layer orders.

## Cross-section provenance

All Tier runs use the cross sections downloaded by
`scripts/download_cross_sections.py`:

- **ENDF release**: ENDF/B-VIII.0
- **Source**: openmc-anywhere (Python wheel from PyPI) + IAEA mirror
- **Nuclides included**: Li-6/7, Be-9, Fe-54/56/57/58, Pb-204/206/207/208,
  Si-28/29/30 (Tier 18+ only), O-16 (Tier 18+ only)
- **Total download size**: ~30 MB compressed (vs. ~5 GB for the full
  ENDF/B-VIII.0 library; we download only the nuclides needed for
  Z-pinch LiPb blankets with Si/O for ceramic breeders)

After download, ENDF files are converted to OpenMC's ACE format via
NJOY (bundled with `openmc-anywhere` at `.venv/Scripts/njoy.exe`).
