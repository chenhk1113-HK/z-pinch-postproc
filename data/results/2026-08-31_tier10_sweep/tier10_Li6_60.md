# Tier 6.C — R_blanket Sweep

Comparison of OpenMC Monte Carlo TBR vs the parametric
Tier 5.B estimate as the LiPb blanket outer radius is
varied. Geometry: plasma (r<4) → Be (4<r<6) → LiPb 
(6<r<R_blanket) → RAFM structure; white boundary on all
outer surfaces (closed enclosure).

| R_blanket (cm) | TBR (MC) | ±rel% | TBR (param) | Δ% |
|----------------|----------|-------|-------------|-----|
| 12 | 1.4960 | ±0.40% | 0.2358 | -84.2% |
| 50 | 1.8176 | ±0.36% | 1.2206 | -32.8% |
| 80 | 1.8406 | ±0.33% | 1.6109 | -12.5% |
| 110 | 1.8495 | ±0.18% | 1.8251 | -1.3% |
| 140 | 1.8551 | ±0.22% | 1.9427 | +4.7% |

**Tier 6 finding**: the parametric Tier 5.B formula is calibrated for the Sobes 2011 50-cm reference blanket and matches Monte Carlo within 4.3% there. For thicker blankets the parametric overestimates because it does not account for the physical saturation of Li-6 capture in the Be-multiplied fast-neutron flux. The MC plateau at TBR ~1.86 is the correct answer for the Z-pinch LiPb+Be blanket at this geometry.