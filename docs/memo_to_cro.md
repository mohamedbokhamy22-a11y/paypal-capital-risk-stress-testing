# Memo: Capital & Liquidity Stress Test Findings

**To:** Chief Risk Officer  
**From:** Mohamed Bokhamy, Risk Analytics  
**Date:** November 2026  
**Re:** Synthetic Stress Test — Scenario Results, Key Findings, and Recommended Actions

---

*This memo is a portfolio exercise using entirely synthetic data and illustrative thresholds. It is not a regulatory filing, not PayPal data, and not a production risk management output.*

---

## Bottom Line Up Front

Under the **Severe scenario**, this portfolio **breaches the Basel III CET1 regulatory minimum of 4.5%**. The capital ratio falls to **3.1%** — 140bps below the floor. The Adverse scenario is already AMBER on capital (7.5%) and triggers a recovery action through **liquidity** (LCR proxy = 79%, below the 100% internal RED threshold). The reverse stress test on the Adverse scenario shows that credit losses would need to reach **$7.1bn** (2.0× the $3.5bn Adverse assumption) to breach the regulatory floor from that starting point, with $3.6bn of headroom.

Three management actions should be prioritized immediately in a Severe environment:

1. **Halt discretionary capital distributions** (dividends, buybacks) to preserve MDA headroom.
2. **Activate pre-approved contingency funding lines** — HQLA monetization under Severe falls to $18bn, leaving the liquidity ratio at 50% (well below both internal thresholds).
3. **Engage counterparty risk management** — top counterparty exposure reaches 37.5% of starting capital under Severe, above the 30% internal RED threshold.

---

## Scenario Summary

| Scenario | Capital Ratio | Capital Status | Liquidity Ratio | Liq. Status | Recovery Trigger |
|----------|---------------|----------------|-----------------|-------------|------------------|
| Baseline | 11.8%         | GREEN          | 125%            | GREEN       | No               |
| Adverse  | 7.5%          | AMBER          | 79%             | RED         | Yes              |
| Severe   | **3.1%**      | **RED**        | 50%             | RED         | Yes              |

**Key observation (Adverse):** The Adverse scenario triggers a recovery action — not through capital but through **liquidity** (LCR proxy drops to 79%, below the 100% RED floor). Capital at 7.5% is AMBER but above the regulatory minimum. This is the finding most likely to be missed in a capital-only view. ILAAP and ICAAP must be run jointly.

**Key observation (Severe):** Capital ratio of 3.1% is 140bps *below* the 4.5% regulatory floor. This scenario is not stress-but-survivable — it describes a structurally impaired position requiring immediate recapitalization or a managed wind-down assessment.

---

## Dominant Loss Drivers

The tornado sensitivity analysis (±20% perturbation) identifies the following ranking:

1. **Credit losses** — single largest driver of capital ratio variance (~2.4pp range)
2. **Net revenue** — second-highest sensitivity; revenue deterioration is as impactful as credit stress
3. **Risk-weighted assets (RWA)** — denominator effect; a 20% RWA increase in a stress period (procyclicality) is a significant vulnerability
4. **FX net open position** — now fully propagated; $2.0bn open position at 20% FX shock generates $400m loss
5. **HQLA** — matters primarily through the liquidity ratio; also feeds rates loss via duration exposure

**What this means for scenario design:** Future scenario iterations should stress revenue *and* credit simultaneously — isolated credit scenarios understate tail risk because real downturns compress both. The ρ=0.65 correlation assumption in the Monte Carlo is directionally correct; the boundary sensitivity analysis suggests using ρ=0.75–0.80 for a 99th-percentile tail calibration.

---

## Monte Carlo: Breach Probabilities

Under the Adverse scenario with 10,000 correlated simulations:

- **P(capital < 4.5% reg. floor):** ~2.9% — non-trivial; 1-in-34 Adverse paths breach the floor
- **P(capital < 7.0% internal RED):** ~27.9% — material; over 1-in-4 paths trigger internal RED
- **P(recovery trigger):** ~91.4% — in nearly every Adverse simulation, at least one KRI is RED (driven overwhelmingly by the liquidity ratio)

The correlation assumption (ρ=0.65 between credit deterioration and FX stress magnitude) reflects the stylized fact that macro downturns tend to produce simultaneous credit deterioration and EM currency depreciation. Assuming independence would understate the 99th-percentile loss by approximately 15–20%.

---

## Reverse Stress Test: Viability Boundaries

| Scenario | Reg. Floor Breach Point | Credit Loss Headroom |
|----------|------------------------|----------------------|
| Baseline | $9.5bn (6.3× assumed)  | $8.0bn               |
| Adverse  | $7.1bn (2.0×)          | $3.6bn               |
| Severe   | **Already breached**   | n/a                  |

**Key finding:** The Severe scenario is already in breach — the question is not "how much headroom remains" but "what recapitalization or resolution pathway is available." For the Adverse scenario, $3.6bn of headroom is meaningful but not comfortable; the 2D failure frontier shows that a 15–20% FX shock combined with 1.5× credit losses eliminates most of this buffer. This warrants a pre-emptive review of:
- Collateral agreements with the top-5 counterparties
- Whether operational loss reserves are adequate under Severe assumptions
- Whether the $2.5bn net revenue assumption is achievable given revenue compression in a Severe macro environment

---

## Limitations I Would Disclose to a Regulator

1. **Deterministic base scenario:** The base stress_test.py output is point-estimate; the Monte Carlo adds distributional richness but should not replace a full scenario generation process with governance.
2. **Static balance sheet assumption:** RWA does not expand endogenously with credit deterioration. In a real downturn, RWA migration (BBB→BB→B) would amplify the capital ratio decline.
3. **No second-round effects:** The model does not capture feedback loops (e.g., liquidity stress → asset fire sales → mark-to-market losses → further capital deterioration).
4. **Revenue simplification:** Net revenue is a single input; in reality it must decompose into fee income, net interest margin, and trading revenue — each with different stress behaviors.
5. **Correlation structure:** ρ=0.65 is a judgment call. It should be validated against historical episodes (2008–09, 2015 EM selloff, 2020 COVID shock) and stress-tested at ρ=0.85.
6. **No liquidity stress beyond LCR:** The model does not capture intraday liquidity, settlement risk, or the interplay between funding liquidity and market liquidity.

---

## What I Would Build Next

| Priority | Enhancement | Why It Matters |
|----------|-------------|----------------|
| 1 | Dynamic RWA migration (ratings transition matrix) | Removes static balance sheet assumption |
| 2 | Liquidity stress cascade model | Current LCR-only view misses intraday and collateral calls |
| 3 | Scenario generation engine (macro factors → KRI translation) | Replaces manual CSV inputs with model-driven scenarios |
| 4 | Historical calibration of correlation structure | Replaces ρ=0.65 judgment with data-driven estimate |
| 5 | Management action effectiveness testing | Quantifies which actions restore capital fastest under which scenario |

---

*All figures in this memo are derived from synthetic data for portfolio demonstration purposes only.*
