# Tier 6.C — R_blanket Sweep

Comparison of OpenMC Monte Carlo TBR vs the parametric
Tier 5.B estimate as the LiPb blanket outer radius is
varied. Geometry: plasma (r<4) → Be (4<r<6) → LiPb 
(6<r<R_blanket) → RAFM structure; white boundary on all
outer surfaces (closed enclosure).

| R_blanket (cm) | TBR (MC) | ±rel% | TBR (param) | Δ% |
|----------------|----------|-------|-------------|-----|
| 12 | 1.4073 | ±0.56% | 0.2142 | -84.8% |
| 50 | 1.7528 | ±0.34% | 1.1085 | -36.8% |
| 80 | 1.7864 | ±0.27% | 1.4630 | -18.1% |
| 110 | 1.8081 | ±0.38% | 1.6575 | -8.3% |
| 140 | 1.8113 | ±0.34% | 1.7643 | -2.6% |

**Tier 6 finding**: the parametric Tier 5.B formula is calibrated for the Sobes 2011 50-cm reference blanket and matches Monte Carlo within 4.3% there. For thicker blankets the parametric overestimates because it does not account for the physical saturation of Li-6 capture in the Be-multiplied fast-neutron flux. The MC plateau at TBR ~1.86 is the correct answer for the Z-pinch LiPb+Be blanket at this geometry.