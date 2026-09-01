# zreview5.docx audit (path-proposal / roadmap review)

> **Document classification**: Series P path-proposal review. Output shape: scope decision per recommendation (Adopt / Defer / Reject), NOT a fix list. The reviewer proposes 12 roadmap items in 4 phases ("Polish", "Scientific Rigor", "Physics Extensions", "Community & Impact"); each item is verified against on-disk state at v1.6.0 and tier-ranked.

> **Verification matrix (V1 + Z1 6-label)**:
> - ✅ **confirmed** — reviewer claim is true AND not yet shipped; ship it.
> - ✅ **valid-deferred** — reviewer claim is true AND worth doing, but genuine-deferred (defer to roadmap).
> - ✅ **already-shipped** — reviewer claim is outdated; the feature already exists in v1.5.0/v1.6.0.
> - ❌ **stale** — reviewer claim is false; the gap it describes has been closed.
> - ⚠️ **internal-inconsistency** — reviewer's framing contradicts itself or its own recommendation.
> - ❌ **projected-as-shipped** — reviewer claims item done that is NOT on disk.

## Phase 1 — Polish & Reproducibility

### Item 1: "Fix the First-Run Experience"

> *"Even after v1.5.0, a new user cloning the repo and following the README will likely hit import errors because the quick-start snippet still uses old paths (`sys.path.insert(0, 'code')`). Action: Update the README to use `pip install -e .` and `import zpp` style imports. Add a `examples/quick_start.ipynb` notebook that actually runs from a fresh clone."*

| Sub-claim | Verdict | Evidence |
|---|---|---|
| README still uses `sys.path.insert(0, 'code')` | ❌ **stale** | `grep -c "sys\.path\.insert" README.md` → 0 hits. Fixed in commit `497326b` (zreview3 P0 closure, 2026-08-31). README quick-start now uses `from zpp.zpp_tbr import compute_TBR, TBRInputs`. |
| Add `examples/quick_start.ipynb` | ✅ **valid-deferred** | No `.ipynb` files anywhere in repo (verified). But also flagged as Z2 "projected-as-shipped" in Zreview 2 and explicitly skipped in two prior sessions (z-pinch Tier 11, genesis-drone R3). User has consistently de-prioritized this. |

**Scope decision**: **Adopt (partial)** — README half is stale (already fixed); notebook half is valid-deferred. **Net effort**: 0 days (already done). Not worth creating the notebook unless the user asks — it's been declined twice.

### Item 2: "Environment Locking & One-Click Reproducibility"

> *"Add a `environment.yml` (Conda) or `Dockerfile` that pins the OpenMC version AND the nuclear data library."*

| Sub-claim | Verdict | Evidence |
|---|---|---|
| No `environment.yml`/`Dockerfile` exists | ✅ **confirmed** | All three files missing (`environment.yml`, `Dockerfile`, `docker-compose.yml`). |
| Nuclear data version is "go download cross sections without knowing which version" | ⚠️ **stale-imprecise** | `pyproject.toml` pins `openmc>=0.16.0,<0.17.0`; `scripts/stamp_provenance.py` records OpenMC version + ENDF/B-VIII.0 release + ACE source on every Tier result; `data/nuclear_data/ace/cross_sections.xml` lists the 47 nuclide files present. **What IS missing is a single user-facing manifest saying "to reproduce, do X with Y."** |

**Scope decision**: **Defer** (1-2 days effort). Worth doing once the project stabilizes past v1.6.0 — a `Dockerfile` that runs `scripts/run_tier18c_sweep.py` end-to-end is the natural reproducibility anchor. **NOT** worth doing before the next cross-validation round, because the cross-section library version may change (Tier 18.C used ENDF/B-VIII.0; FENDL-3.2 is the next likely candidate).

### Item 3: "Automated Benchmark Artifacts"

> *"Add a `benchmarks/` directory with the actual OpenMC `settings.xml`, `materials.xml`, and `tallies.xml` used for each Tier."*

| Sub-claim | Verdict | Evidence |
|---|---|---|
| Tier results are "just numbers in Markdown" | ⚠️ **stale-imprecise** | Each Tier directory has a JSON with `TBR_mc`, `TBR_stddev`, geometry, n_particles, plus provenance stamp. The OPENMC XMLs themselves are written to a `tempfile.TemporaryDirectory()` and discarded after the run (see `zpp/zpp_real_openmc_transport.py:521`). |
| No `benchmarks/` directory | ✅ **confirmed** | `benchmarks/` doesn't exist. But `data/inputs/README.md` (shipped in commit `94384c1`, P1-C) describes the published input decks for Tier 6 + Tier 18.B and points to `scripts/run_tier6_sweep.py` / `scripts/run_tier18b_sweep.py`. |

**Scope decision**: **Defer** (3-5 days effort, partial overlap with Item 7). The current pattern is "reproduction script that builds geometry in-process" — cleaner than dumping XMLs, but doesn't let readers see the raw OpenMC input. Worth doing in conjunction with Item 7 (3D geometry) for the eventual `benchmarks/` directory. **NOT** worth doing in isolation — the reproduction scripts cover 95% of the use case.

## Phase 2 — Scientific Rigor

### Item 4: "Uncertainty Quantification"

> *"For each Tier, run OpenMC with increasing particle counts (1e5, 1e6, 1e7, 1e8) and plot the convergence curve."*

| Sub-claim | Verdict | Evidence |
|---|---|---|
| "TBR numbers are point estimates" | ❌ **stale** | `zpp/zpp_uncertainty.py` (260 lines) provides Monte Carlo propagation with `monte_carlo_propagation()` + `uq_markdown()`. 12 test methods in `tests/test_zpp_uncertainty.py`. **Shipped in Tier 5.C (v0.4)**. |
| "No convergence curves" | ❌ **stale** | `scripts/run_tier6_convergence.py` (shipped in commit `94384c1`) sweeps n ∈ {500, 1000, 2000, 5000, 10000, 20000, 50000} and writes `data/results/2026-09-01_tier6_convergence/tier6_convergence.json` + Markdown. Headline result: TBR asymptotes at **1.80 ± 0.08%** at n=50000; project default n=5000 is **fully converged at 1.80 ± 0.23%**. |

**Scope decision**: **Adopt (closed)** — both sub-claims are stale. Item 4 is **already shipped**. The reviewer is recommending work that the project did 1-2 weeks ago. **Net effort**: 0 days. **The reviewer's verdict sentence** ("single most important scientific upgrade") is correct in spirit but the work is done.

### Item 5: "Cross-Code Validation (Without MCNP)"

> *"Run OpenMC on the ITER TBM (Test Blanket Module) benchmark or the EU DEMO WCLL reference model. If zpp matches those within 1–2%, your method is validated—no MCNP required."*

| Sub-claim | Verdict | Evidence |
|---|---|---|
| No ITER TBM / EU DEMO WCLL validation | ❌ **stale** | **`docs/P1_D_PUBLIC_BENCHMARK_CROSS_VALIDATION.md`** (shipped in commit `e3eeec7`) covers UWFDM-1414 + Furuta 1987 + Peng 2014 + EU DEMO WCLL (Arena 2021) + Novais 2023 FNSF DCLL — **5/5 cross-validation matrix complete**. Tier 18.C specifically reproduces the FNSF 1D ROM geometry and matches the published value within +0.86%. |

**Scope decision**: **Adopt (closed)** — Item 5 is **already shipped**. The reviewer is recommending exactly the work that drop-mcnp.docx → Tier 18.C → v1.6.0 cycle did. **Net effort**: 0 days. **The reviewer's specific concern about MCNP** was already addressed by `drop-mcnp.docx` (2026-09-01), which explicitly redirected this away from MCNP toward public-benchmark comparison. The reviewer writing zreview5 did not see drop-mcnp.docx.

### Item 6: "Sensitivity Analysis"

> *"Use a simple Sobol index or even just a parameter sweep to show which input has the biggest impact on TBR."*

| Sub-claim | Verdict | Evidence |
|---|---|---|
| "No sensitivity analysis" | ❌ **stale** | `zpp/zpp_sensitivity.py` (268 lines, 6 functions) provides OAT tornado + Sobol indices via `tornado_analysis()`, `tornado_markdown()`, `saltelli_sample()`, `sobol_indices()`. **21 test methods** in `tests/test_zpp_sensitivity.py` including Sobol-specific assertions (`test_toy_function_S_i`, `test_sum_S_i_leq_1`, `test_total_indices_greater_than_first`, etc.). **Shipped in Tier 5.C**. |

**Scope decision**: **Adopt (closed)** — Item 6 is **already shipped**. Net effort: 0 days.

## Phase 3 — Physics Extensions

### Item 7: "From 1D to 2D/3D Geometry (The Big Leap)"

> *"Integrate DAGMC (Direct Accelerated Geometry Monte Carlo) support. Allow users to import a STEP/STL file of a Z-pinch reactor."*

| Sub-claim | Verdict | Evidence |
|---|---|---|
| "Current model assumes perfect cylinders/spheres" | ✅ **confirmed** | All Tier geometry is 1D infinite cylinder / spherical. README's ⚠️ engineering-scope warning box documents this. |
| "Real Z-pinches have electrodes, diagnostic ports, and feed lines" | ✅ **confirmed** | Realistic 3D geometry would require a new OpenMC geometry model + either voxel mesh (`openmc.RegularMesh` +) or voxelized DAGMC geometry. |

**Scope decision (updated 2026-09-01)**: **Tier 19.A shipped** (mesh tally on existing 1D geometry, 1-2 hours, `data/results/2026-09-01_1707_tier19_3d/tier19_3d_baseline.json`). Mesh conservation check passes: TBR=1.8306 ± 0.0076 matches Tier 18.B (1.8280 ± 0.0060) within 0.4σ, mesh sum / cell tally = 1.0000. **Tier 19.B remains deferred** (electrodes + diagnostic ports CSG, 3-5 days per `docs/P1_P2_IMPLEMENTATION_PLAN.md` P2-A). The reviewer's "STEP/STL import" framing is the right shape for Tier 19.B; the simpler path is a pre-computed 3D voxel mesh from CSG (no DAGMC install required).

### Item 8: "Time-Dependent Tritium Fuel Cycle"

> *"Add a simple time-domain model: Tritium inventory = f(TBR, plasma burn rate, decay, extraction delay)."*

| Sub-claim | Verdict | Evidence |
|---|---|---|
| "Currently the project calculates instantaneous TBR" | ✅ **confirmed** | TBR is instantaneous; no time-integrated tritium inventory. |
| "No time-dependent fuel cycle" | ⚠️ **stale-imprecise** | `zpp/zpp_plant_simulation.py` (306 lines, `simulate_plant()` + `sweep_plant_designs()`) integrates BOP × TBR × geometry × LCOE over plant lifetime. `zpp/zpp_coupled_plant.py` (276 lines) computes n_replacements over plant life + LCOE adjusted for PFC replacement. **What is NOT modeled is time-resolved tritium inventory** (T(t) = T(0) + ∫breeding_rate dt − decay − extraction). The existing plant simulator is economic, not isotopic. |

**Scope decision**: **Defer** (1-2 weeks effort). Worth doing for the JOSS-paper version (Item 11), where tritium self-sufficiency over a plant lifetime is one of the headline claims. NOT the same as the existing plant simulator — that's economic, this is isotopic.

### Item 9: "Multi-Physics Coupling"

> *"Create a simple coupling loop: OpenMC → heat deposition → thermal expansion → density change → OpenMC."*

| Sub-claim | Verdict | Evidence |
|---|---|---|
| "Neutronics doesn't happen in a vacuum" | ✅ **confirmed** | Realistic; the project does not couple neutronics → thermal → neutronics feedback. |
| "No multi-physics coupling" | ⚠️ **stale-imprecise** | `zpp/zpp_coupled_plant.py` couples BOP × neutronics × economics. `zpp/zpp_alpha_heating.py` (14k chars) computes volumetric heating. **What is NOT modeled is the feedback loop** (heating → temperature → density → re-run OpenMC). This is a feedback coupling, not just a forward chain. |

**Scope decision**: **Defer** (2-4 weeks effort). The forward chain exists; the feedback loop is the new work. Requires a thermal-hydraulics solver (or a 1D radial thermal model + iterative density update). Best paired with Item 7 (3D geometry) since density perturbation depends on geometry.

### Item 10: "Surrogate Model / ML Acceleration"

> *"Train a Gaussian Process or neural network on the existing Tier sweep data."*

| Sub-claim | Verdict | Evidence |
|---|---|---|
| "OpenMC is minutes to hours per point" | ⚠️ **imprecise** | OpenMC Tier 6 / 18.C runs are **3-12 seconds per point** on this hardware (Tier 18.C smoke: 12s at n=50000). The reviewer may be confusing with the engineering-sign-off problem (3D heterogeneous EU DEMO model), not the project's 1D sweeps. |
| "No surrogate model" | ✅ **confirmed** | No surrogate, no GP, no NN. |
| "Tier sweep data is enough to train" | ⚠️ **imprecise** | Existing Tier sweeps cover ~7 points per dimension at one geometry each — insufficient for a surrogate that's worth anything beyond the swept regime. |

**Scope decision**: **Reject (out-of-scope for personal project)**. The reviewer's framing ("real-time design optimization in a Jupyter notebook") describes a different audience than this project's. The project is **geometry-specific relative trends** (per README engineering-scope callout), not design optimization. If someone wants to train a surrogate, the sweep data is published in `data/results/*/tier*_sweep.json` — they can train it externally. Not worth building inside this project.

## Phase 4 — Community & Impact

### Item 11: "Publish a Software Paper"

> *"JOSS or Fusion Engineering and Design."*

| Sub-claim | Verdict | Evidence |
|---|---|---|
| "Project has enough scope and rigor for a paper" | ✅ **confirmed** | 757 tests pass, 5/5 cross-validation matrix, full provenance stamping. Yes, qualifies. |
| "JOSS or FED" | ✅ **confirmed-aspirational** | JOSS requires a `paper.md` in the repo root + a software archive; FED requires an actual paper draft. Neither exists. |

**Scope decision**: **Defer** (1-2 weeks effort for JOSS, 4-8 weeks for FED). JOSS is the lower-effort path and is well-suited to a personal project. The paper-writing effort should be timed AFTER Tier 18.C-style cross-validation work settles, so the paper's headline result is the methodology itself, not a moving target. **NOT** worth doing right after v1.6.0 (the methodology is still evolving per P1-P2 roadmap).

### Item 12: "Become a Standard Tool for the Z-pinch Community / PyPI Package"

> *"Package `zpp` as a proper Python library on PyPI. Add a simple CLI: `zpp calculate --geometry cylinder --breeder LiPb`."*

| Sub-claim | Verdict | Evidence |
|---|---|---|
| Not on PyPI | ✅ **confirmed** | No PyPI publish; `pyproject.toml` is configured for `pip install -e .` but no `[tool.poetry]` or `[tool.hatch]` metadata for PyPI upload. |
| No simple CLI | ❌ **stale** | `zpp_cli/tbr.py` provides `zpp-tbr` CLI; `zpp_cli/version.py` provides `zpp-version`. Console scripts wired in `pyproject.toml`: `zpp-tbr = "zpp_cli.tbr:main"`. **Shipped in v1.5.0** (commit `fcc42e8`). |
| "Zap Energy and other Z-pinch startups are hiring like crazy" | ✅ **confirmed-context** | True as of writing, but: not a project goal. |

**Scope decision**: **Defer** (2-3 days effort for PyPI publish alone). The PyPI publish is a small remaining step but is a **deliberate scope decision**, not a gap — the project is "personal project out of curiosity, made using Hermes with MiniMax M3 as the coder, Doubao and Grok and other AIs as reviewers. Not associated with any institution" (per README line 3 disclaimer). Publishing to PyPI implies an institutional-grade release process (semver discipline, deprecation policy, issue triage). The current v1.6.0 is a research milestone, not a PyPI release candidate.

If the user wants to publish to PyPI as a personal project, that's a 1-day `python -m build && twine upload` away. But it should be a deliberate decision, not a passive "next step."

## The One-Sentence Verdict

> *"The highest-ROI next step is Phase 2, Item 4 (Uncertainty Quantification): Add error bars and convergence plots to the existing Tiers. It costs almost zero effort (just more CPU time), but it instantly transforms the project from 'a personal script with interesting numbers' into 'a credible scientific tool whose results can be trusted.'"*

**Verdict on the verdict**: ❌ **stale**. Item 4 is **already shipped** — `zpp/zpp_uncertainty.py` provides MC propagation, `scripts/run_tier6_convergence.py` provides the convergence curve, both in v1.6.0. The "lowest-effort highest-ROI" recommendation is a recommendation for work that was done 1-2 weeks ago.

The reviewer is writing against **stale project state** — specifically, the v1.5.0 state visible in the CHANGELOG header, not the v1.6.0 state after the cross-validation + Tier 18.C ship. Half of the reviewer's "next steps" are recommendations for already-shipped work.

## What this review actually adds value on

| Item | Value |
|---|---|
| Item 1 (First-Run Experience) | Already shipped; reviewer's stale citation of `sys.path.insert(0, 'code')` flagged a fix that landed 1 day ago in commit `497326b` |
| Item 2 (Environment Locking) | **Real gap**. A `Dockerfile` is the right reproducibility anchor for the post-v1.6.0 era |
| Item 3 (Benchmark Artifacts) | Partial — `data/inputs/README.md` covers Tier 6 + 18.B; Tier 9/13/16/17 don't have published decks yet |
| Item 4 (UQ) | Stale recommendation for shipped work |
| Item 5 (Cross-Code Validation) | Stale recommendation for shipped work (the entire drop-mcnp.docx → Tier 18.C chain is what this reviewer is suggesting) |
| Item 6 (Sensitivity) | Stale recommendation for shipped work |
| Item 7 (3D Geometry) | **Real, high-value gap, partially closed (Tier 19.A)**. Tier 19.A (mesh tally) shipped 2026-09-01; Tier 19.B (electrodes + ports CSG) still pending |
| Item 8 (Time-Dependent Fuel Cycle) | **Real gap, but smaller**. Forward chain exists; feedback loop doesn't |
| Item 9 (Multi-Physics Coupling) | **Real gap**. The most physics-rich item |
| Item 10 (Surrogate/ML) | **Reject**. Out of project scope |
| Item 11 (Software Paper) | Defer until methodology stabilizes (after 2 more Tier rounds) |
| Item 12 (PyPI) | Defer; current scope is research milestone, not library release |

**Net summary (updated 2026-09-01)**: 4 of 12 items already shipped at audit time; reviewer unaware. Of the remaining 5 "real gaps": **Item 7 (Tier 19.A)** shipped 2026-09-01 (mesh tally only); **Item 2 (Dockerfile)** permanently cancelled per user directive. Net remaining real gaps: **Items 8, 9, 11** (time-dependent fuel cycle, multi-physics coupling, JOSS paper). Items 10/12 still rejected as out-of-scope.

## Recommended next-step prioritization (post-audit)

1. ~~**Item 7 (3D geometry, 1-3 weeks)** — highest-value remaining work.~~ **Tier 19.A shipped 2026-09-01** (mesh tally only, ~1-2 hours). **Tier 19.B** (electrodes + ports CSG, 3-5 days) remains open and will close the README ⚠️ engineering-scope warning box.
2. ~~**Item 2 (Dockerfile, 1-2 days)** — small, high-credibility, easy ship.~~ **Item 2 cancelled 2026-09-01 per user directive** (project is Docker-free).
3. **Item 11 (JOSS paper, 1-2 weeks)** — natural publication milestone after Tier 19.B + 9 close.

Skip for now: Item 10 (out of scope), Item 12 (deliberate non-goal), Item 8 (smaller value than 7/9), Item 9 (pairs with 7, do them together).

## See also

- [`docs/P1_P2_IMPLEMENTATION_PLAN.md`](P1_P2_IMPLEMENTATION_PLAN.md) — the existing roadmap this reviewer is partially echoing
- [`docs/P1_D_PUBLIC_BENCHMARK_CROSS_VALIDATION.md`](P1_D_PUBLIC_BENCHMARK_CROSS_VALIDATION.md) — Item 5's already-shipped answer
- [`zpp/zpp_uncertainty.py`](../../zpp/zpp_uncertainty.py) — Item 4's already-shipped answer
- [`zpp/zpp_sensitivity.py`](../../zpp/zpp_sensitivity.py) — Item 6's already-shipped answer
- [`scripts/run_tier6_convergence.py`](../../scripts/run_tier6_convergence.py) — Item 4's convergence-curve answer
- Commit `497326b` (zreview3 P0 closure) — Item 1's README half
- Commit `94384c1` (P1 provenance + convergence + reproducibility) — Items 4 + 5 + 6 partial
- Commit `e3eeec7` (P1-D cross-validation) — Item 5's full cross-validation matrix