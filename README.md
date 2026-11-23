# Capital & Liquidity Stress Testing — Portfolio Case Study

**Business question:** Under Adverse and Severe macro conditions, does this portfolio maintain adequate capital and liquidity — and how close does it come to the regulatory floor?

**Three key numbers:**
- Severe capital ratio: **3.1%** — breaches the 4.5% Basel III CET1 regulatory floor; Adverse sits at 7.5% (AMBER, recovery trigger via liquidity)
- Adverse reverse stress: credit losses must reach **$7.1bn** (2.0× the $3.5bn assumption) to breach the floor — $3.6bn of headroom
- Monte Carlo (Adverse): **~28%** probability of breaching the 7% internal RED threshold across 10,000 correlated scenarios

> **Important:** Synthetic portfolio exercise using invented data and illustrative thresholds. Not PayPal data, not a regulatory filing, not production risk work.

---

## What this demonstrates

| Skill | Implementation |
|-------|---------------|
| Stress scenario design | 3-scenario CSV (Baseline / Adverse / Severe) with 12 shock parameters |
| KRI computation & RAG | Capital ratio, LCR proxy, counterparty concentration — traffic-light thresholds |
| FX & rates shock propagation | FX loss = net open position × shock; rates loss = duration × HQLA × bps |
| Reverse stress testing | scipy.optimize.brentq finds the credit loss multiplier that breaches the regulatory floor |
| Sensitivity / tornado analysis | ±20% perturbation on 12 inputs, ranked by capital ratio impact |
| Monte Carlo simulation | 10,000 correlated paths (ρ=0.65, Cholesky); breach probability reporting |
| Interactive dashboard | Streamlit: real-time sliders, waterfall chart, scenario comparison |
| Testing | 6 pytest cases: math correctness, RAG boundaries, propagation, monotonicity |
| Risk communication | CRO memo with bottom-line-up-front, management actions, limitations |

---

## Results

### Scenario outcomes

| Scenario | Capital % | Capital | Liquidity % | Liq. | Recovery Trigger |
|----------|-----------|---------|-------------|------|-----------------|
| Baseline | 11.8%     | GREEN   | 125%        | GREEN | No |
| Adverse  | 7.5%      | AMBER   | 78.6%       | RED  | **Yes** |
| Severe   | **3.1%**  | **RED** | 50%         | RED  | **Yes** |

**Key insight (Severe):** Capital ratio of 3.1% is already below the 4.5% regulatory floor — no additional credit deterioration is needed to trigger a breach. The Adverse scenario triggers recovery through *liquidity* (LCR proxy = 79%), not capital. A capital-only view would miss this. ILAAP and ICAAP must be run jointly.

### Reverse stress (Adverse): how far until the floor?

Credit losses must reach **$7.1bn** (2.0× the $3.5bn Adverse assumption) to breach the 4.5% regulatory floor. That is $3.6bn of headroom. The 2D failure frontier shows that combining elevated FX shocks with moderately higher credit losses narrows this quickly.

### Monte Carlo breach probabilities (Adverse, 10,000 paths, ρ=0.65)

| Threshold | Breach Probability |
|-----------|-------------------|
| < 4.5% regulatory floor | ~2.9% |
| < 7.0% internal RED | ~27.9% |
| Recovery trigger | ~91.4% |

### Tornado: dominant capital drivers (Adverse)

1. Credit Losses — ±2.4pp range
2. Net Revenue — ±1.9pp range
3. Risk-Weighted Assets — ±1.6pp range (denominator procyclicality)
4. FX Net Open Position — ±0.8pp range
5. HQLA / Liquid Assets — ±0.7pp range

---

## File structure

```
paypal-capital-risk-stress-testing/
├── data/
│   └── scenarios.csv              # 3 scenarios × 12 inputs
├── stress_test.py                 # KRI engine: losses, ratios, RAG, waterfall chart
├── reverse_stress.py              # Breach multiplier + 2D failure frontier
├── sensitivity.py                 # Tornado ±20% perturbation
├── monte_carlo.py                 # 10,000 correlated paths, breach probabilities
├── dashboard.py                   # Streamlit interactive dashboard
├── tests/
│   └── test_kris.py               # 6 pytest cases
├── outputs/                       # Generated charts and CSVs
├── docs/
│   ├── memo_to_cro.md             # Findings narrative with management actions
│   ├── model_card.md              # Inputs, formulas, limitations, production requirements
│   └── independent_risk_assessment.md  # Second-line challenge + remediation tracking
└── requirements.txt
```

---

## Quick start

```bash
pip install -r requirements.txt

python stress_test.py          # KRI results + waterfall chart
python reverse_stress.py       # Reverse stress + failure frontier
python sensitivity.py          # Tornado chart
python monte_carlo.py          # Monte Carlo breach probabilities

streamlit run dashboard.py     # Interactive dashboard

pytest tests/                  # Run test suite
```

---

## Modeling choices worth explaining

**Why log-normal for credit losses?**  
Credit losses are non-negative and exhibit fat right tails empirically. Log-normal preserves both properties. The σ=$1.5bn parameter is a stylized choice — a production model would calibrate against historical loss data.

**Why ρ=0.65?**  
Credit deterioration and EM FX stress tend to co-move in macro downturns (2008–09, 2020 COVID shock). Assuming independence understates tail risk. 0.65 is a judgment call; the model card documents this and recommends stress-testing at ρ=0.80.

**Why Cholesky and not independent draws?**  
Independent draws would generate scenarios where credit stress is severe but FX is benign — not representative of a correlated macro downturn. Cholesky preserves the target ρ exactly in expectation.

---

## What I would build next

1. **Dynamic RWA migration** — apply a ratings transition matrix so RWA expands endogenously with credit stress (removes static balance sheet assumption)
2. **Empirical ρ calibration** — estimate correlation from historical data rather than using a judgment call
3. **Revenue decomposition** — split net revenue into fee income, NII, and trading revenue with separate stress paths
4. **Liquidity stress cascade** — model intraday liquidity, margin calls, and HQLA monetization haircuts
5. **Scenario generation engine** — translate macro factor paths (GDP, unemployment, credit spreads) into KRI assumptions automatically

---

*All scenario assumptions, thresholds, and figures are synthetic and illustrative only.*
