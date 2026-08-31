# Z-FFR / Antong Fusion References

> Tier 14 (2026-08-31) — Z-pinch fusion blanket references from
> Peng Xianjue's team at China Academy of Engineering Physics
> (CAEP) and Antong Fusion (the company Peng founded in 2022).

These are the most directly relevant published references for our
`z-pinch-postproc` project because **Z-FFR uses the same Z-pinch
physics we're modeling** — a Z-pinch driver produces 14 MeV D-T
neutrons, which hit an external blanket that we want to model for
tritium breeding.

---

## 1. Antong Fusion (安东聚变)

**Company name**: 安东聚变（北京）科技有限公司
**Founded**: 2022 in Beijing
**Founder**: **Peng Xianjue (彭先觉)** — Chinese Academy of
Engineering (CAE) academician, nuclear engineering expert; formerly
at China Academy of Engineering Physics (CAEP).
**Co-founder & CEO**: Liu Cheng (刘程) — Tsinghua EE PhD.
**CTO**: Yang Qingwei (杨青巍) — formerly Chief Engineer of HL-2M
("new generation artificial sun" tokamak) at Southwestern Institute
of Physics (核工业西南物理研究院).
**Team**: From State Grid, China National Nuclear Corporation,
Tsinghua University.
**Funding**: ~100 million yuan Series A (October 2025) — investors
include Lenovo Star, Qifu Capital, Pangu Chuangfu, Daoyi Capital,
Tsinghua Alumni Fund.
**R&D Center**: Z-pinch capacitor R&D center in Wuxi Liangxi Tech
City (signed April 23, 2026).
**Series name**: 夔牛 (Kui Niu) — proprietary pulsed-power capacitor
tech.

### Antong Fusion technology (Z-pinch)

From their October 2025 China Daily announcement:

> "Z-pinch (Z-Pinch) is a technology that uses pulsed high-current
> to produce high-intensity X-ray radiation. Its core advantage is
> a relatively simple, reliable device structure that can release
> large amounts of X-rays in an extremely short time, instantly
> reaching the fusion threshold... The strong magnetic field force
> drives the plasma to pinch and implode toward the central axis.
> When the plasma hits the target, large amounts of high-intensity
> X-ray radiation are produced, which compresses and heats the
> fusion fuel instantaneously to ignition conditions, releasing
> large amounts of fusion energy...
>
> The high-energy neutrons produced by fusion will be absorbed in
> the **external blanket** and converted into thermal energy,
> entering the heat exchange system to drive steam turbines,
> achieving stable grid-connected power output."

### Three-step roadmap (Antong Fusion)

1. **"雷震子/雷神/雷霆" (Leizhenzi/Thunder God/Thunder Might)**
   series drivers — fusion ignition validation, prototype
   capacitor development.
2. **Z-pinch fusion ignition Q>1** — energy demonstration.
3. **Grid-connected power generation** — commercial plant.

### Antong Fusion commercial roadmap

- 3-year target: small pulsed-power modules for accelerators,
  neutron sources, medical isotope production.
- Competitors globally: **Pacific Fusion**, **Fuse Energy**,
  **ZAP Energy** (USA); **First Light Fusion** (UK).

---

## 2. Z-FFR (Z-pinch Fusion-Fission Hybrid Reactor)

**Concept origin**: Peng Xianjue, 2008 (formal proposal in
Journal of Southwest University of Science and Technology, 2010).

**Z-FFR = Z-pinch driven inertial confinement fusion (ICF) neutron
source + sub-critical fission blanket** (NOT a pure fusion reactor;
this is the hybrid blanket concept).

### Z-FFR published design (Peng Xianjue et al., 2014)

| Parameter | Value |
|---|---|
| Fusion driver | Z-pinch, 50 MA peak current (planned) |
| Fusion neutron source power | 150 MW thermal |
| Rep rate | 0.1 Hz |
| Single-shot fusion yield | 2000-3000 MJ (with local-volume ignition target) |
| Fusion Q (engineering) | >1 |
| Blanket energy amplification | >10× |
| Total thermal power | 3 GW (after blanket amplification) |
| Electrical output | 1 GW (30% steam cycle efficiency) |
| Net energy gain | >60× |
| Plant footprint | 1000 MW output |
| **TBR target** | **> 1.15** (conservative) |
| **TBR achieved (paper design)** | **> 1.24** |
| **TBR with hybrid fission blanket** | **up to 1.5** |
| Fissile breeding ratio | > 2.0 |
| Capital cost (target) | 200亿 yuan ($28B USD) for 1 GW |
| Electricity cost target | 0.1 元/kWh |

### Z-FFR blanket structure (Peng Xianjue patent CN104240772A)

- **Lithium-lead (LiPb) eutectic** as primary breeder
- **Beryllium (Be) multiplier** zone (same as our Tier 5/6 baseline)
- **Depleted uranium (DU)** sub-critical fission blanket for
  energy multiplication
- **Natural uranium or PWR spent fuel** as feedstock
- TBR > 1.15, energy multiplication > 10, fissile breeding > 2.0

### Z-FFR engineering demo timeline (Peng 2026 update)

- **2018-2025**: Build 50-70 MA Z-pinch driver (PTS — Primary Test
  Stand upgrade at CAEP).
- **2029**: National 50 MA large-scale device expected.
- **2030**: Start Z-FFR construction.
- **2032**: Demo experimental heating reactor.
- **2035**: Engineering demo plant.
- **2040-2050**: Commercial deployment.

### Z-FFR's long-life capacitor requirement

- Charge/discharge > 3×10⁶ cycles
- Repetition rate 0.1 Hz
- 50 MA peak current
- 4-driver prototype demonstration under construction
- This is what Antong Fusion's Kui Niu series addresses

---

## 3. Key published references for our project

### Tier 14.A — Peng Xianjue (2010)
**"Z-pinch fusion fission hybrid reactor, the energy technology
road with great competitive power"**
Journal of Southwest University of Science and Technology 25(4), 1-4.
**The original Z-FFR concept paper.** Establishes the feasibility
argument for Z-pinch-driven fusion-fission hybrid energy.

### Tier 14.B — Peng Xianjue, Wang Zhen (2014)
**"Conceptual research on Z-pinch driven fusion-fission hybrid
reactor"**
High Power Laser and Particle Beams 26(9), 1-6.
DOI: 10.11884/HPLPB201426.090201.
**The blanket design paper.** Models the Z-FFR blanket,
neutron balance, flux, power density, burnup.

### Tier 14.C — Li Z H, Huang H W, Wang Z et al. (2014)
**"Conceptual design of Z-Pinch driven fusion fission hybrid power
reactor"**
High Power Laser and Particle Beams 25(10), 1-7.

### Tier 14.D — Gao Xiang, Wan Yuanxi, Ding Ning, Peng Xianjue (2018)
**"Frontier Issues and Progress of Controlled Nuclear Fusion
Science and Technology"**
Strategic Study of CAE 20(3), 25-31.
DOI: 10.15302/J-SSCAE-2018.03.004.
**The CAE policy review paper.** Recommends China build a 50-70 MA
Z-pinch driver 2018-2025, start Z-FFR from 2030, demo plant from 2035.

### Tier 14.E — Peng Xianjue, Liu Cheng'an, Shi Xueming (2019)
**"核能未来与Z箍缩驱动聚变裂变混合堆"** (Nuclear Energy Future
and Z-pinch Driven Fusion-Fission Hybrid Reactor)
国防工业出版社 (National Defense Industry Press).
**The full Z-FFR book.** 10+ years of CAEP Z-pinch fusion research
compiled into one volume.

### Tier 14.F — CN104240772A (2014)
**"Z-pinch driven fusion-fission hybrid energy reactor"**
Google Patent. Peng Xianjue et al.
The blanket design specification: TBR > 1.15, energy multiplication
> 10, fissile breeding > 2.0.

### Tier 14.G — Simulations of fusion chamber dynamics (2016)
**"Simulations of fusion chamber dynamics and first wall response
in a Z-pinch driven fusion–fission hybrid power reactor (Z-FFR)"**
Fusion Engineering and Design (2016).
The first-wall response simulation under Z-pinch neutron pulses.

### Tier 14.H — Hybrid blanket neutronics paper (2020)
**"Neutronics conceptual research on a hybrid blanket of china
fusion"** (Fusion Engineering and Design 2020, S0920379620302635).
**Peng Xianjue is listed as supervisor.** Directly applicable to
our TBR work.

---

## 4. Comparison with our project

| Parameter | Our Z-pinch | Z-FFR (Peng 2014) |
|---|---|---|
| Driver | (modeled externally) | 50 MA Z-pinch |
| Geometry | Cylindrical plasma | Cylindrical hohlraum/target |
| Source | 14 MeV D-T point source | 14 MeV D-T point source |
| Blanket | LiPb + Be | LiPb + Be + U (fission) |
| TBR target | ≥ 1.0 self-sufficient | ≥ 1.15 conservative |
| TBR achieved | ~1.5-1.86 (Tier 8 closed-form) | 1.24 (paper design), 1.5 (with fission) |
| Boundary BC | Vacuum / white | Vacuum (room temperature) |
| Geometry scale | R_b ∈ [12, 140] cm | Full plant scale |
| MC calibration | OpenMC 0.16.0 + ENDF/B-VIII.0 | Not published in detail |

**Our Tier 5 → Tier 8 chain is calibrated for the Z-pinch ICF
neutron source + LiPb+Be blanket geometry that Z-FFR also uses.**
The Z-FFR papers provide:
1. Independent TBR target (>1.15) for our validation.
2. Independent blanket structure (LiPb + Be + U) — our LiPb+Be
   case is the no-fission sub-case.
3. Engineering constraints (neutron pulse energy deposition,
   first wall lifetime) for our documentation.

---

## 5. Implications for v1.3+

1. **Tier 12 — Be placement correction**: Z-FFR uses Be + LiPb
   layer arrangement that may differ from our `mult_inside=True`
   default. Peng's papers show multi-layer Be+LiPb+Be arrangements.
2. **Tier 13 — Fe reflector sweep**: Z-FFR blanket includes a
   depleted uranium layer (not Fe), but the engineering demo
   may use Fe reflectors for cost reasons. Our Fe-reflector sweep
   is directly applicable.
3. **Tier 14 — Z-FFR coupling**: We could add a `zpp_zffr.py`
   module that wraps our TBR calculator with Z-FFR-specific
   parameters (50 MA driver, 0.1 Hz rep rate, depleted uranium
   blanket, etc.) for direct comparison with the Peng 2014
   published design.

---

## 6. What's NOT in the published references

- **Z-FFR blanket neutronics is published in summary form only.**
  Detailed MCNP/OpenMC models are not open-source.
- **Antong Fusion's capacitor specs are commercial.** The
  "100 ns pulse, tens of kA, 10⁶ cycles" spec is published but
  the actual design is proprietary.
- **No published Z-FFR benchmark comparable to Furuta 1987 or
  Youssef/Sawan UCLA-Wisconsin LiPb benchmark.** Our Tier 9 Furuta
  validation is the only independent MC validation we have.

---

## 7. Sources (Chinese)

- China Daily (English): https://caijing.chinadaily.com.cn/a/202510/22/WS68f89001a310c4deea5eda68.html
- 深圳核博会: https://www.cinie.net/article/53426.html
- 证券时报: https://stcn.com/article/detail/3595391.html
- 钛媒体: https://www.tmtpost.com/7976983.html
- 中国工程院: https://www.cae.cn/cae/html/main/col35/2014-06/05/20140605175333328908319_1.html
- 工程院 (CAE Strategic Study 2018): https://www.engineering.org.cn/sscae/CN/PDF/10.15302/J-SSCAE-2018.03.004
- 高功率激光与粒子束 (HPLPB): https://www.cpsjournals.cn/article/doi/10.11884/HPLPB201426.090201
- 中国工程物理研究院 patent CN104240772A: https://patents.google.com/patent/CN104240772A/zh
- Fusion Energy Base: https://www.fusionenergybase.com/projects/z-ffr
