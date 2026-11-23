# Model Card: Capital & Liquidity Stress Testing Engine

**Version:** 2.0  
**Last updated:** November 2026  
**Author:** Mohamed Bokhamy  
**Purpose:** Portfolio demonstration — synthetic data only

---

## Model Overview

A Python-based stress testing engine that propagates macro shocks (credit deterioration, FX revaluation, rates repricing, market losses, operational losses) through a simplified balance sheet to produce capital ratios, liquidity ratios, and counterparty concentration metrics under three scenarios.

---

## Inputs

| Field | Unit | Source | Stress Sensitivity |
|-------|------|--------|--------------------|
| `net_revenue_bn` | $bn | Synthetic | High — revenue compression is the #2 capital driver |
| `credit_loss_bn` | $bn | Synthetic | Very high — #1 capital driver (tornado rank 1) |
| `market_loss_bn` | $bn | Synthetic | Moderate — pre-shock market losses |
| `operational_loss_bn` | $bn | Synthetic | Low–moderate |
| `rwa_bn` | $bn | Synthetic | High — denominator of capital ratio; static (known limitation) |
| `hqla_bn` | $bn | Synthetic | High — both liquidity ratio numerator and rates loss amplifier |
| `net_30d_outflows_bn` | $bn | Synthetic | High — LCR denominator |
| `top_counterparty_exposure_bn` | $bn | Synthetic | Moderate — concentration KRI |
| `fx_shock_pct` | % | Synthetic | Moderate — interacts with net open position |
| `rates_shock_bps` | bps | Synthetic | Moderate — interacts with HQLA and duration |
| `net_open_position_bn` | $bn | Synthetic | Moderate — scales FX revaluation loss |
| `duration_years` | years | Synthetic | Moderate — scales rates revaluation loss |

---

## Outputs

| Output | Description |
|--------|-------------|
| `capital_ratio_pct` | 100 × ending\_capital / RWA |
| `liquidity_ratio_pct` | 100 × HQLA / 30-day net outflows |
| `counterparty_concentration_pct` | 100 × top exposure / starting capital |
| `mda_distance_bps` | (capital\_ratio − 4.5%) × 100; distance to MDA restriction |
| `capital_status` | RED / AMBER / GREEN vs. internal thresholds |
| `recovery_trigger` | Boolean; fires when any KRI is RED |
| Monte Carlo breach probs | P(capital < 4.5%), P(capital < 7.0%) |
| Reverse stress multiplier | Credit loss multiplier to breach regulatory floor |

---

## Key Formulas

```
FX loss      = net_open_position_bn × |fx_shock_pct| / 100
Rates loss   = duration_years × hqla_bn × rates_shock_bps / 10,000
Total loss   = credit_loss + market_loss + operational_loss + FX loss + rates loss
Ending cap   = starting_capital + net_revenue − total_loss
Capital ratio = 100 × ending_cap / rwa
LCR proxy    = 100 × hqla / net_30d_outflows
```

---

## Distributional Assumptions (Monte Carlo)

| Variable | Distribution | Parameters | Justification |
|----------|-------------|------------|---------------|
| Credit loss | Log-Normal | μ = scenario assumption, σ = $1.5bn | Non-negative support; fat right tail reflects fat-tailed credit loss data |
| FX shock magnitude | Normal (clipped [0, 40%]) | μ = scenario assumption, σ = 5pp | Symmetric around scenario; clip at 0 prevents negative (beneficial) shocks contaminating tail |
| Correlation (ρ) | Cholesky decomposition | ρ = 0.65 | Credit deterioration and EM FX stress co-move in macro downturns; stylized choice, not empirically calibrated |

---

## Known Limitations

1. **Static balance sheet** — RWA does not migrate with credit quality. A BB→B transition during stress would increase RWA by 30–50%, amplifying the capital ratio decline.
2. **No second-round effects** — Liquidity stress → fire sale → mark-to-market loss feedback is not modeled.
3. **Single-factor revenue** — Net revenue is a point estimate; fee income, NII, and trading revenue have different stress behaviors.
4. **ρ = 0.65 is a judgment call** — Not validated against historical episodes. Should be stress-tested at ρ = 0.75–0.85 for tail risk assessment.
5. **Deterministic scenarios** — The base engine (stress_test.py) produces single-point outputs. Uncertainty quantification requires the Monte Carlo module.
6. **No behavioral feedback** — Credit loss model does not account for borrower behavior changes, draw-down of committed facilities, or margin calls.
7. **LCR proxy only** — Does not capture intraday liquidity, settlement risk, or collateral transformation.
8. **Three scenarios** — Basel guidance recommends at least five scenarios including a 1-in-25-year tail event and a reverse stress test. This model covers three base scenarios plus a reverse stress module.

---

## What a Production Version Would Require

- **Data governance layer** — Source-to-report lineage with owner sign-off, refresh frequency, and validation rules for every KRI input
- **Dynamic RWA migration** — Ratings transition matrix applied to credit book to evolve RWA endogenously
- **Empirical calibration** — ρ estimated from historical episodes; credit loss distributions validated against loss data
- **Model validation** — Independent review of all formulas, distributional assumptions, and threshold calibration
- **Governance** — Model Risk Management (MRM) approval, annual recertification, use test evidence
- **Automation** — Scheduled data pulls from source systems (treasury, credit risk, market risk), exception alerts
- **Audit trail** — Immutable log of every scenario run, input snapshot, and output

---

## Regulatory Framework Alignment

| Concept | Reference |
|---------|-----------|
| CET1 minimum 4.5% | Basel III (CRR Article 92) |
| ICAAP | EBA Guidelines EBA/GL/2016/10 |
| ILAAP | EBA Guidelines EBA/GL/2016/09 |
| LCR | Basel III LCR (BCBS 238) |
| Recovery planning triggers | EBA Recovery Planning Guidelines |
| Reverse stress testing | EBA/GL/2017/02 (Stress Testing) |

*All thresholds in this project are illustrative. They are not regulatory minima or PayPal internal thresholds.*
