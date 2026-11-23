# Independent Risk Assessment (Portfolio / Synthetic)

*Second-line-style challenge memo for the synthetic capital stress testing exercise.*  
*Not a regulatory document. All thresholds and data are illustrative.*

---

## Scope

Independent review of the synthetic stress-testing process, covering assumption quality, data propagation integrity, scenario severity, model completeness, and documentation standards.

---

## Findings and Remediation Status

| # | Finding | Severity | Remediation | Status |
|---|---------|----------|-------------|--------|
| F-01 | FX shock (fx\_shock\_pct) and rates shock (rates\_shock\_bps) were present in scenario inputs but had **zero effect on capital calculations** — columns were decorative | Critical | Implemented `compute_losses()` with full FX and rates propagation; added `net_open_position_bn` and `duration_years` to `scenarios.csv` | **CLOSED** — `stress_test.py` v2 |
| F-02 | No reverse stress test — model could not answer "how bad does it need to get before we breach?" | High | Built `reverse_stress.py` using `scipy.optimize.brentq`; produces breach multiplier and 2D failure frontier | **CLOSED** — `reverse_stress.py` |
| F-03 | No sensitivity analysis — unknown which inputs drive capital ratio variance | High | Built `sensitivity.py` with ±20% tornado perturbation on 12 inputs | **CLOSED** — `sensitivity.py` |
| F-04 | No uncertainty quantification — single-point scenario outputs cannot express tail risk | High | Built `monte_carlo.py` with 10,000 correlated paths; reports P(capital < 4.5%) and P(capital < 7%) | **CLOSED** — `monte_carlo.py` |
| F-05 | Credit loss calibration not benchmarked to historical or forward-looking data | Medium | Acknowledged in `docs/model_card.md` as known limitation; ρ=0.65 documented as judgment call | **OPEN — model limitation** |
| F-06 | Static balance sheet: RWA does not migrate under stress (procyclicality not modeled) | Medium | Documented in `docs/model_card.md` and `docs/memo_to_cro.md` as priority enhancement #1 | **OPEN — roadmap item** |
| F-07 | No second-round feedback effects (liquidity stress → fire sale → MTM loss) | Medium | Documented as known limitation in model card | **OPEN — out of scope for v2** |
| F-08 | No test suite — calculations were unverified | Medium | Built `tests/test_kris.py` with 6 pytest cases covering capital math, RAG boundaries, recovery trigger, FX propagation, monotonicity, and reverse stress | **CLOSED** — `tests/test_kris.py` |
| F-09 | Framework documents (ICAAP pack, mock regulatory submission, recovery plan) presented as artifacts without demonstrated methodology link | Low | Removed these files; replaced with `docs/model_card.md` (methodology) and `docs/memo_to_cro.md` (findings narrative) | **CLOSED** |
| F-10 | No interactive exploration capability | Low | Built `dashboard.py` Streamlit dashboard with real-time sliders and waterfall chart | **CLOSED** — `dashboard.py` |

---

## Independent Challenge (Post-Remediation)

**What is now working:**
- FX and rates shocks fully propagate through to capital ratio — the model is no longer decorative
- Reverse stress test quantifies viability boundaries (Adverse: $9.6bn before floor breach; Severe: $6.3bn)
- Tornado analysis confirms credit losses as the dominant driver (#1) with net revenue as the second-highest sensitivity — this has scenario design implications
- Monte Carlo shows meaningful breach probabilities under Adverse (~18% chance of breaching 7% internal RED) that would be invisible in a point-estimate framework

**Remaining material limitations:**
1. Static RWA is the most significant unresolved structural gap — a 30% RWA migration under Severe would reduce the capital ratio by ~1.5–2pp, potentially pushing from 5.9% toward the regulatory floor
2. ρ=0.65 drives Monte Carlo tail outcomes significantly; should be stress-tested at ρ=0.80 and validated against 2008–09 and 2020 data
3. Revenue remains a point estimate — a revenue stress (fee income compression, NII pressure) under Adverse/Severe would materially worsen outcomes; the memo to CRO highlights this

**Recommended next review trigger:** When RWA migration is added to the model (roadmap item F-06), re-run this assessment to verify the capital ratio monotonicity across scenarios holds and that Severe still doesn't breach the regulatory floor under combined credit + RWA stress.

---

## Sign-off (Illustrative)

| Role | Name | Date |
|------|------|------|
| Model developer | Mohamed Bokhamy | November 2026 |
| Independent reviewer | [Vacant — portfolio exercise] | — |
| Model Risk Management | [Vacant — portfolio exercise] | — |
