"""
Monte Carlo Stress Simulation
Draws 10,000 correlated credit-loss and FX-shock scenarios, computes capital ratio
distribution, and reports breach probabilities.

Correlation structure: credit losses and FX shock magnitude are positively correlated
(ρ = 0.65) — both worsen simultaneously in a macro downturn. This is a deliberate
modeling choice; assuming independence would understate tail risk.

Usage:  python monte_carlo.py
"""

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data" / "scenarios.csv"
OUT  = ROOT / "outputs"
np.random.seed(42)   # deterministic; change for sensitivity checks

STARTING_CAPITAL_BN  = 12.0
N_SIMULATIONS        = 10_000
CORR_CREDIT_FX       = 0.65   # positive: credit deterioration and FX stress co-move
REGULATORY_FLOOR     =  4.5   # Basel III CET1 minimum
INTERNAL_RED         =  7.0
INTERNAL_AMBER       =  9.0


def simulate_capital_ratios(base_row: pd.Series) -> np.ndarray:
    """
    Sample 10,000 capital ratios by drawing correlated credit loss and FX shock
    from parametric distributions centered on the base scenario.

    Credit loss ~ Log-Normal (preserves non-negativity, fat right tail)
    FX shock    ~ Normal (symmetric around scenario assumption, clipped at 0 and 40%)
    """
    # Build correlation matrix and draw via Cholesky
    cov = np.array([[1.0, CORR_CREDIT_FX], [CORR_CREDIT_FX, 1.0]])
    L   = np.linalg.cholesky(cov)
    Z   = np.random.standard_normal((2, N_SIMULATIONS))
    corr_draws = L @ Z   # shape (2, N)

    # Credit loss: log-normal, mean = scenario assumption, std = 1.5bn
    mu_cl    = base_row["credit_loss_bn"]
    sigma_cl = 1.5
    sigma_ln = np.sqrt(np.log(1 + (sigma_cl / mu_cl) ** 2))
    mu_ln    = np.log(mu_cl) - 0.5 * sigma_ln ** 2
    credit_losses = np.exp(mu_ln + sigma_ln * corr_draws[0])

    # FX shock: normal, mean = scenario assumption, std = 5pp, clipped [0, 40]
    mu_fx    = abs(base_row["fx_shock_pct"])
    sigma_fx = 5.0
    fx_shocks = np.clip(mu_fx + sigma_fx * corr_draws[1], 0, 40)

    # Fixed structural parameters from base scenario
    market_loss   = base_row["market_loss_bn"]
    op_loss       = base_row["operational_loss_bn"]
    rwa           = base_row["rwa_bn"]
    net_rev       = base_row["net_revenue_bn"]
    hqla          = base_row["hqla_bn"]
    rates_bps     = base_row["rates_shock_bps"]
    net_open_pos  = base_row["net_open_position_bn"]
    duration      = base_row["duration_years"]

    fx_loss    = net_open_pos  * fx_shocks / 100
    rates_loss = duration * hqla * rates_bps / 10_000

    total_loss    = credit_losses + market_loss + op_loss + fx_loss + rates_loss
    ending_cap    = STARTING_CAPITAL_BN + net_rev - total_loss
    capital_ratios = 100 * ending_cap / rwa

    return capital_ratios


def compute_stats(capital_ratios: np.ndarray) -> dict:
    pcts = [1, 5, 10, 25, 50, 75, 90, 95, 99]
    return {
        "percentiles": {p: float(np.percentile(capital_ratios, p)) for p in pcts},
        "p_breach_regulatory":   float((capital_ratios < REGULATORY_FLOOR).mean() * 100),
        "p_breach_internal_red": float((capital_ratios < INTERNAL_RED).mean()      * 100),
        "p_recovery_trigger":    float((capital_ratios < INTERNAL_AMBER).mean()    * 100),
        "mean":                  float(capital_ratios.mean()),
        "std":                   float(capital_ratios.std()),
    }


def plot_distribution(capital_ratios: np.ndarray, stats: dict, scenario: str) -> None:
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))

    # ── Histogram ──────────────────────────────────────────────────────────────
    ax1.hist(capital_ratios, bins=100, color="#6c63ff", alpha=0.72,
             edgecolor="white", linewidth=0.3, density=False)

    ymax = ax1.get_ylim()[1]
    ax1.fill_betweenx([0, ymax * 1.05], 0, REGULATORY_FLOOR,
                      alpha=0.10, color="darkred", zorder=0)
    ax1.axvline(REGULATORY_FLOOR, color="darkred", linewidth=2.0,
                label=f"Reg. floor {REGULATORY_FLOOR}%  "
                      f"(breach prob: {stats['p_breach_regulatory']:.1f}%)")
    ax1.axvline(INTERNAL_RED, color="red", linewidth=1.5, linestyle="--",
                label=f"Internal RED {INTERNAL_RED}%  "
                      f"(breach prob: {stats['p_breach_internal_red']:.1f}%)")
    ax1.axvline(stats["percentiles"][5], color="black", linewidth=1.5, linestyle="-",
                label=f"5th pct: {stats['percentiles'][5]:.1f}%")
    ax1.axvline(stats["percentiles"][50], color="navy", linewidth=1.5, linestyle="-.",
                label=f"Median: {stats['percentiles'][50]:.1f}%")

    ax1.set_xlabel("Capital Ratio (%)", fontsize=10)
    ax1.set_ylabel("Frequency", fontsize=10)
    ax1.set_title(
        f"Capital Ratio Distribution — {scenario}\n"
        f"{N_SIMULATIONS:,} Monte Carlo paths | ρ(credit, FX) = {CORR_CREDIT_FX}",
        fontsize=10,
    )
    ax1.legend(fontsize=7.5)
    ax1.set_ylim(0, ymax * 1.05)

    # ── CDF ────────────────────────────────────────────────────────────────────
    sorted_cr = np.sort(capital_ratios)
    cdf = np.arange(1, len(sorted_cr) + 1) / len(sorted_cr) * 100

    ax2.plot(sorted_cr, cdf, color="#6c63ff", linewidth=2)
    ax2.axvline(REGULATORY_FLOOR, color="darkred", linewidth=2, linestyle="-",
                label=f"4.5% floor: {stats['p_breach_regulatory']:.1f}% breach")
    ax2.axvline(INTERNAL_RED, color="red", linewidth=1.5, linestyle="--",
                label=f"7% RED: {stats['p_breach_internal_red']:.1f}% breach")
    ax2.axhline(5,  color="gray", linewidth=0.8, linestyle=":", alpha=0.6)
    ax2.axhline(1,  color="gray", linewidth=0.8, linestyle=":", alpha=0.6)
    ax2.axhline(10, color="gray", linewidth=0.8, linestyle=":", alpha=0.6)

    ax2.set_xlabel("Capital Ratio (%)", fontsize=10)
    ax2.set_ylabel("Cumulative Probability (%)", fontsize=10)
    ax2.set_title("Cumulative Distribution Function\nP(capital ratio < x)", fontsize=10)
    ax2.legend(fontsize=7.5)
    ax2.set_ylim(0, 100)
    ax2.grid(True, alpha=0.25)

    plt.suptitle(
        "Monte Carlo Stress Simulation — Synthetic Portfolio Exercise\n"
        "All assumptions are illustrative only. ρ = 0.65 reflects co-movement of credit and FX stress.",
        fontsize=8.5, style="italic", y=1.01,
    )
    plt.tight_layout()
    fname = f"monte_carlo_{scenario.lower()}.png"
    plt.savefig(OUT / fname, dpi=150, bbox_inches="tight")
    plt.close()
    return fname


def main() -> None:
    OUT.mkdir(exist_ok=True)
    sc = pd.read_csv(DATA)

    print(f"\n── Monte Carlo Simulation ({N_SIMULATIONS:,} paths per scenario) ──────────────────")
    print(f"   Correlation: credit loss ↔ FX shock magnitude  ρ = {CORR_CREDIT_FX}")
    print(f"   Credit loss: Log-Normal  |  FX shock: Normal (clipped [0, 40%])\n")

    all_stats = {}
    for _, row in sc.iterrows():
        scenario = row["scenario"]
        capital_ratios = simulate_capital_ratios(row)
        stats = compute_stats(capital_ratios)
        all_stats[scenario] = stats

        print(f"  {scenario}:")
        print(f"    Distribution:   mean={stats['mean']:.1f}%  std={stats['std']:.1f}%")
        pcts = stats["percentiles"]
        print(f"    Percentiles:    1st={pcts[1]:.1f}%  5th={pcts[5]:.1f}%  "
              f"25th={pcts[25]:.1f}%  median={pcts[50]:.1f}%  95th={pcts[95]:.1f}%")
        print(f"    Breach probabilities:")
        print(f"      P(capital < {REGULATORY_FLOOR}% reg. floor):  {stats['p_breach_regulatory']:5.1f}%")
        print(f"      P(capital < {INTERNAL_RED}% internal RED):   {stats['p_breach_internal_red']:5.1f}%")
        print(f"      P(recovery trigger):         {stats['p_recovery_trigger']:5.1f}%")

        fname = plot_distribution(capital_ratios, stats, scenario)
        print(f"    Saved → outputs/{fname}\n")

        # Save percentile table
        pct_df = pd.DataFrame([
            {"percentile": p, "capital_ratio_pct": round(v, 3)}
            for p, v in stats["percentiles"].items()
        ])
        pct_df["scenario"] = scenario
        pct_df.to_csv(OUT / f"monte_carlo_{scenario.lower()}_percentiles.csv", index=False)

    # Cross-scenario summary
    print("── Cross-Scenario Breach Probabilities ──────────────────────────────")
    print(f"  {'Scenario':<12} {'P(< 4.5%)':>10} {'P(< 7.0%)':>10} {'P(trigger)':>12}")
    for sc_name, stats in all_stats.items():
        print(f"  {sc_name:<12} {stats['p_breach_regulatory']:>9.1f}%  "
              f"{stats['p_breach_internal_red']:>9.1f}%  "
              f"{stats['p_recovery_trigger']:>11.1f}%")


if __name__ == "__main__":
    main()
