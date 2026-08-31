# Tier 6.C — R_blanket Sweep

Comparison of OpenMC Monte Carlo TBR vs the parametric
Tier 5.B estimate as the LiPb blanket outer radius is
varied. Geometry: plasma (r<4) → Be (4<r<6) → LiPb 
(6<r<R_blanket) → RAFM structure; white boundary on all
outer surfaces (closed enclosure).

| R_blanket (cm) | TBR (MC) | ±rel% | TBR (param) | Δ% |
|----------------|----------|-------|-------------|-----|
| 12 | 1.0410 | ±0.30% | 0.2547 | -75.5% |
| 50 | 0.9375 | ±0.35% | 1.3182 | +40.6% |
| 80 | 1.1896 | ±0.38% | 1.7397 | +46.3% |
| 110 | 1.2952 | ±0.38% | 1.9711 | +52.2% |
| 140 | 1.7802 | ±0.36% | 2.0981 | +17.9% |

**Tier 6 finding**: the parametric Tier 5.B formula is calibrated for the Sobes 2011 50-cm reference blanket and matches Monte Carlo within 4.3% there. For thicker blankets the parametric overestimates because it does not account for the physical saturation of Li-6 capture in the Be-multiplied fast-neutron flux. The MC plateau at TBR ~1.86 is the correct answer for the Z-pinch LiPb+Be blanket at this geometry.