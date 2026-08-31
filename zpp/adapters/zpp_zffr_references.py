"""Tier 14 (2026-08-31) — Z-FFR / Antong Fusion reference data.

Captures the published Z-pinch fusion blanket design data from
Peng Xianjue's team at China Academy of Engineering Physics
(CAEP) and Antong Fusion (the commercial spin-out).

References (see docs/zffr_references.md for full bibliography):
  [1] Peng Xianjue, Wang Zhen (2014). Conceptual research on
      Z-pinch driven fusion-fission hybrid reactor. High Power
      Laser and Particle Beams 26(9), 1-6.
      DOI: 10.11884/HPLPB201426.090201.
  [2] Peng Xianjue (2010). Z-pinch fusion fission hybrid reactor,
      the energy technology road with great competitive power.
      Journal of Southwest University of Science and Technology
      25(4), 1-4.
  [3] Gao Xiang, Wan Yuanxi, Ding Ning, Peng Xianjue (2018).
      Frontier Issues and Progress of Controlled Nuclear Fusion
      Science and Technology. Strategic Study of CAE 20(3), 25-31.
      DOI: 10.15302/J-SSCAE-2018.03.004.
  [4] CN104240772A. Z-pinch driven fusion-fission hybrid energy
      reactor. Patent, Peng Xianjue et al., 2014.
  [5] Fusion Engineering and Design (2020). Neutronics conceptual
      research on a hybrid blanket of China fusion (CAEP team,
      Peng Xianjue as supervisor).
      DOI: 10.1016/j.fusengdes.2020.111787.
"""

# === Z-FFR Design Targets ===

# Peng Xianjue's published Z-FFR blanket target.
# Source: Peng 2014 [1], 钛媒体 coverage.
ZFFR_TARGET_TBR = 1.15  # conservative TBR target

# Achieved TBR in actual Z-FFR design (per 钛媒体 / Antong Fusion
# press materials). The hybrid blanket (with fissionable fuel)
# can reach TBR > 1.5, but the pure-fusion Z-pinch blanket
# target is 1.15-1.24.
ZFFR_ACHIEVED_TBR = 1.24  # published achieved design value

# 14 MeV D-T neutron source power from the Z-pinch driver.
# Source: Peng 2014 [1], 2018 CAE strategy paper [3].
ZFFR_NEUTRON_SOURCE_POWER_MW = 150.0

# Z-pinch pulse repetition rate (Hz).
ZFFR_REP_RATE_HZ = 0.1  # one pulse every 10 seconds

# Net electrical output (MW) after fission blanket amplification.
# 150 MW fusion neutron source × 10× energy multiplication
# = ~1500 MW thermal, ~600 MW electric at 40% thermal efficiency.
ZFFR_NET_ELECTRIC_MW = 600.0

# === Antong Fusion Company Facts ===

# Year Antong Fusion (安东聚变, 安东聚变(北京)科技有限公司) was founded.
ANTONG_FUSION_FOUNDED = 2022

# Founder (CAE academician, nuclear engineering expert).
ANTONG_FUSION_FOUNDER = "Peng Xianjue (彭先觉), CAE academician"

# Co-founder (Tsinghua EE PhD, CEO).
ANTONG_FUSION_CEO = "Liu Cheng (刘程)"

# CTO (formerly Chief Engineer of HL-2M tokamak).
ANTONG_FUSION_CTO = "Yang Qingwei (杨青巍)"

# Series A funding (~100 million yuan, October 2025).
ANTONG_FUSION_SERIES_A_MILLION_RMB = 100.0

# === Key References (full citations in docs/zffr_references.md) ===

ZFFR_KEY_REFERENCES = [
    "Peng Xianjue & Wang Zhen, 'Conceptual research on Z-pinch driven "
    "fusion-fission hybrid reactor', High Power Laser and Particle "
    "Beams 26(9), 1-6 (2014). DOI: 10.11884/HPLPB201426.090201.",
    "Peng Xianjue, 'Z-pinch fusion fission hybrid reactor, the energy "
    "technology road with great competitive power', Journal of "
    "Southwest University of Science and Technology 25(4), 1-4 (2010).",
    "Gao Xiang, Wan Yuanxi, Ding Ning, Peng Xianjue, 'Frontier Issues "
    "and Progress of Controlled Nuclear Fusion Science and "
    "Technology', Strategic Study of CAE 20(3), 25-31 (2018). "
    "DOI: 10.15302/J-SSCAE-2018.03.004.",
    "CN104240772A. 'Z-pinch driven fusion-fission hybrid energy "
    "reactor'. Patent, Peng Xianjue et al., 2014.",
    "Peng Xianjue (supervisor), 'Neutronics conceptual research on a "
    "hybrid blanket of China fusion', Fusion Engineering and Design "
    "(2020). DOI: 10.1016/j.fusengdes.2020.111787.",
]


def summary() -> str:
    """One-line summary of Z-FFR / Antong Fusion data."""
    return (
        f"Z-FFR (Peng 2014): {ZFFR_NEUTRON_SOURCE_POWER_MW:.0f} MW Z-pinch "
        f"neutron source, target TBR {ZFFR_TARGET_TBR:.2f} (achieved "
        f"{ZFFR_ACHIEVED_TBR:.2f}), {ZFFR_NET_ELECTRIC_MW:.0f} MW net "
        f"electric. Antong Fusion founded {ANTONG_FUSION_FOUNDED} by "
        f"{ANTONG_FUSION_FOUNDER}."
    )
