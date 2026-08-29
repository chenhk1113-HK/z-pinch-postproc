# Z-Shot Benchmark Parameters for Validation

> **Purpose**: The published MagLIF shot record we will validate `z-pinch-postproc`
> against in v0.1+. The numbers below are taken from Sandia's public
> publications and the user-uploaded `Z_Machine_plan.pdf` (which cited the
> 26 MA / 80 TW / 130 ns pulse parameters).
> **Status**: v0.0.1-prelim — the synthetic shot in `data/fixtures/` is **not**
> yet tuned to match any real shot. Real-data validation deferred to v0.1.

## Sandia Z machine (driver parameters, public record)

| Parameter | Value | Source |
|---|---|---|
| Stored electrical energy | ~ 11.5 MJ (Z); planned ZN: 20-30 MJ | Sandia Z user guide |
| Peak current | 26 MA (Z); planned ZN: 60-65 MA | Sandia Z user guide |
| Pulse rise time | ~ 130 ns (Z) | Sandia Z user guide |
| Peak power | 80 TW (Z) | Z_Machine_plan.pdf |
| Driver efficiency (stored → liner KE) | ~ 15% (typical, varies by load) | Sandia internal estimates |
| Machine size | 33 m diameter | Z_Machine_plan.pdf |
| Shots since 1997 | 3,300+ | Z_Machine_plan.pdf |

## Z shot 2960 (MagLIF DD record, Oct 2024, PRL)

Reference: Gomez et al., Physical Review Letters, 2024 (10 Oct).
- Peak current: ~ 20 MA (up from 16 MA in earlier record)
- Laser preheat energy: tripling from prior record
- Applied axial magnetic field: 50% increase from prior record
- DD neutron yield: ~ 10¹³ (10x prior record)
- Average ion temperature: doubled from prior record

**Conversion to equivalent DT yield (for our purposes)**:
- 10¹³ DD neutrons at 2.45 MeV each → ~ 3.9×10⁻⁵ J total DD neutron energy
- For DT: same T and ρ but DT reactivity is ~ 100x DD at relevant T → equivalent
  DT yield ~ 100x in neutrons, or ~ 1.5×10¹⁵ DT neutrons
- At 14.1 MeV per DT neutron: ~ 3.4 J total
- The 2.45-MeV neutron also deposits ~ 80% of the reaction energy (the 14.1 MeV
  neutron) → total DD yield is roughly the same as the equivalent DT yield in
  total MeV terms (the 2.45 MeV is the *neutron* energy, total reaction energy
  is 3.65 MeV for DD vs 17.6 MeV for DT)

**The v0.1 validation target**: run zpp_run.py on a profile that reproduces
the 10¹³ DD neutron output → recover ~ 1.5×10¹⁵ equivalent DT neutrons at
the same T, ρ.

## Other publicly-cited MagLIF shots

| Shot | Year | Peak current | Notable |
|---|---|---|---|
| Z 2858 | 2022 | 16 MA | Prior record before Z 2960 |
| Z 3033 | (planned) | > 20 MA | TBD |
| Z 3060 | (planned) | 25-30 MA | TBD |

See `docs/TODO.md` for the v0.2 plan to add multi-shot validation.

## Caveats

- The synthetic shot in `data/fixtures/z2960_synthetic.csv` is a hand-tuned
  Gaussian-like T and ρ profile, **not** the actual Z 2960 history. It is
  chosen so that the post-processor reports a sensible-but-sub-ignition
  result (~ kJ class) for the smoke test. Real-data validation in v0.1
  will replace it with a profile derived from the Gomez et al. paper.
- The T_peak and ρ_peak in the synthetic shot are mid-range MagLIF values
  (8.5 keV, 5 g/cc). Real MagLIF shots typically have T_peak ~ 3-5 keV (not
  8.5) and ρ_peak ~ 1-2 g/cc — the synthetic is closer to NIF ignition
  design than to MagLIF.
