"""
Capital & Liquidity Stress Testing Engine
PayPal-style KRI monitoring — synthetic data, portfolio exercise only.

Usage:  python stress_test.py
"""

import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data" / "scenarios.csv"
OUT  = ROOT / "outputs"

# ── Structural constants ───────────────────────────────────────────────────────
STARTING_CAPITAL_BN   = 12.0   # illustrative Tier-1-equivalent capital
REGULATORY_FLOOR_PCT  =  4.5   # Basel III CET1 minimum
INTERNAL_CAP_RED      =  7.0   # internal RED threshold
INTERNAL_CAP_AMBER    =  9.0   # internal AMBER threshold
LIQUIDITY_RED         = 100.0  # LCR-style floor (%)
LIQUIDITY_AMBER       = 115.0  # internal AMBER
CONC_AMBER            =  25.0  # counterparty concentration (% of capital)
CONC_RED              =  30.0


# ── Loss computation ───────────────────────────────────────────────────────────
def compute_losses(sc: pd.DataFrame) -> pd.DataFrame:
    """Propagate FX and rates shocks into P&L; sum to total losses."""
    # FX: net open position revalued at shocked rate
    sc["market_loss_fx_bn"] = (
        sc["net_open_position_bn"] * sc["fx_shock_pct"].abs() / 100
    )
    # Rates: duration × HQLA (rate-sensitive securities proxy) × parallel shift
    sc["market_loss_rates_bn"] = (
        sc["duration_years"] * sc["hqla_bn"] * sc["rates_shock_bps"] / 10_000
    )
    sc["total_loss_bn"] = (
        sc["credit_loss_bn"]
        + sc["market_loss_bn"]
        + sc["operational_loss_bn"]
        + sc["market_loss_fx_bn"]
        + sc["market_loss_rates_bn"]
    )
    return sc


# ── KRI computation ────────────────────────────────────────────────────────────
def compute_kris(sc: pd.DataFrame) -> pd.DataFrame:
    sc["ending_capital_bn"]             = STARTING_CAPITAL_BN + sc["net_revenue_bn"] - sc["total_loss_bn"]
    sc["capital_ratio_pct"]             = 100 * sc["ending_capital_bn"] / sc["rwa_bn"]
    sc["liquidity_ratio_pct"]           = 100 * sc["hqla_bn"] / sc["net_30d_outflows_bn"]
    sc["counterparty_concentration_pct"]= 100 * sc["top_counterparty_exposure_bn"] / STARTING_CAPITAL_BN
    sc["mda_distance_bps"]              = ((sc["capital_ratio_pct"] - REGULATORY_FLOOR_PCT) * 100).round(0)
    return sc


# ── RAG thresholds ─────────────────────────────────────────────────────────────
def assign_rag(sc: pd.DataFrame) -> pd.DataFrame:
    sc["capital_status"] = sc["capital_ratio_pct"].apply(
        lambda x: "RED" if x < INTERNAL_CAP_RED else ("AMBER" if x < INTERNAL_CAP_AMBER else "GREEN")
    )
    sc["liquidity_status"] = sc["liquidity_ratio_pct"].apply(
        lambda x: "RED" if x < LIQUIDITY_RED else ("AMBER" if x < LIQUIDITY_AMBER else "GREEN")
    )
    sc["counterparty_status"] = sc["counterparty_concentration_pct"].apply(
        lambda x: "RED" if x > CONC_RED else ("AMBER" if x > CONC_AMBER else "GREEN")
    )
    sc["recovery_trigger"] = (
        (sc["capital_status"] == "RED")
        | (sc["liquidity_status"] == "RED")
        | (sc["counterparty_status"] == "RED")
    )
    return sc


# ── Loss attribution waterfall chart ──────────────────────────────────────────
def plot_waterfall(sc: pd.DataFrame) -> None:
    scenarios = sc["scenario"].tolist()
    n = len(scenarios)
    fig, axes = plt.subplots(1, n, figsize=(5 * n, 5), sharey=False)
    if n == 1:
        axes = [axes]

    for ax, (_, row) in zip(axes, sc.iterrows()):
        categories = [
            "Starting\nCapital", "+ Revenue",
            "– Credit\nLoss", "– Market\nLoss", "– Op\nLoss",
            "– FX\nLoss*", "– Rates\nLoss*", "Ending\nCapital",
        ]
        values = [
            STARTING_CAPITAL_BN,
            row["net_revenue_bn"],
            -row["credit_loss_bn"],
            -row["market_loss_bn"],
            -row["operational_loss_bn"],
            -row["market_loss_fx_bn"],
            -row["market_loss_rates_bn"],
            row["ending_capital_bn"],
        ]
        colors = ["#2c3e50", "#27ae60", "#e74c3c", "#e67e22",
                  "#c0392b", "#3498db", "#9b59b6", "#2c3e50"]
        bar_colors = [c if v >= 0 else "#e74c3c" for c, v in zip(colors, values)]
        bar_colors[0] = "#2c3e50"
        bar_colors[-1] = "#27ae60" if row["ending_capital_bn"] > 0 else "#e74c3c"

        ax.bar(categories, [abs(v) for v in values], color=bar_colors, alpha=0.85, edgecolor="white")
        ax.axhline(STARTING_CAPITAL_BN * REGULATORY_FLOOR_PCT / 100 * row["rwa_bn"] / row["rwa_bn"],
                   color="darkred", linewidth=1.5, linestyle="--",
                   label=f"Reg. floor equiv.\n({REGULATORY_FLOOR_PCT}% × RWA)")
        for i, (cat, val) in enumerate(zip(categories, values)):
            ax.text(i, abs(val) + 0.1, f"${abs(val):.2f}bn", ha="center", va="bottom", fontsize=7.5)
        ax.set_title(f"{row['scenario']}\nCapital: {row['capital_ratio_pct']:.1f}% ({row['capital_status']})",
                     fontsize=10, fontweight="bold")
        ax.set_ylabel("$bn")
        ax.tick_params(axis="x", labelsize=7.5)
        ax.legend(fontsize=7)

    plt.suptitle("Loss Attribution Waterfall — FX and Rates Losses Now Propagated\n"
                 "*FX loss = net open position × shock  |  Rates loss = duration × HQLA × shock\n"
                 "Synthetic portfolio exercise — all figures are illustrative",
                 fontsize=9, style="italic")
    plt.tight_layout()
    plt.savefig(OUT / "loss_waterfall.png", dpi=150, bbox_inches="tight")
    plt.close()


# ── Outputs ────────────────────────────────────────────────────────────────────
def write_csv(sc: pd.DataFrame) -> None:
    cols = [
        "scenario", "capital_ratio_pct", "liquidity_ratio_pct",
        "counterparty_concentration_pct", "market_loss_fx_bn", "market_loss_rates_bn",
        "total_loss_bn", "ending_capital_bn", "mda_distance_bps",
        "fx_shock_pct", "rates_shock_bps",
        "capital_status", "liquidity_status", "counterparty_status", "recovery_trigger",
    ]
    sc[cols].round(3).to_csv(OUT / "risk_kri_summary.csv", index=False)


def write_markdown(sc: pd.DataFrame) -> None:
    lines = [
        "# Stress Test Results",
        "",
        "*Synthetic portfolio exercise. All figures and thresholds are illustrative only.*",
        "",
        "## KRI Summary",
        "",
        "| Scenario | Capital % | Liq % | Conc % | FX Loss | Rates Loss | Total Loss | Capital | Liquidity | Conc | MDA (bps) | Trigger |",
        "|----------|-----------|-------|--------|---------|------------|------------|---------|-----------|------|-----------|---------|",
    ]
    for _, r in sc.iterrows():
        lines.append(
            f"| {r['scenario']} | {r['capital_ratio_pct']:.1f}% | {r['liquidity_ratio_pct']:.1f}% | "
            f"{r['counterparty_concentration_pct']:.1f}% | ${r['market_loss_fx_bn']:.2f}bn | "
            f"${r['market_loss_rates_bn']:.2f}bn | ${r['total_loss_bn']:.2f}bn | "
            f"**{r['capital_status']}** | **{r['liquidity_status']}** | **{r['counterparty_status']}** | "
            f"{r['mda_distance_bps']:.0f} | {'⚠ YES' if r['recovery_trigger'] else 'NO'} |"
        )

    lines += ["", "## Loss Attribution by Scenario", ""]
    for _, r in sc.iterrows():
        lines += [
            f"### {r['scenario']}",
            f"| Loss Type | Amount | Note |",
            f"|-----------|--------|------|",
            f"| Credit losses | ${r['credit_loss_bn']:.2f}bn | Scenario input |",
            f"| Market losses (pre-shock) | ${r['market_loss_bn']:.2f}bn | Scenario input |",
            f"| Operational losses | ${r['operational_loss_bn']:.2f}bn | Scenario input |",
            f"| **FX revaluation** | **${r['market_loss_fx_bn']:.2f}bn** | Net open position × {abs(r['fx_shock_pct']):.0f}% shock — *now propagated* |",
            f"| **Rates revaluation** | **${r['market_loss_rates_bn']:.2f}bn** | Duration × HQLA × {r['rates_shock_bps']:.0f}bps shock — *now propagated* |",
            f"| **Total losses** | **${r['total_loss_bn']:.2f}bn** | |",
            f"| Ending capital | ${r['ending_capital_bn']:.2f}bn | Capital ratio: {r['capital_ratio_pct']:.1f}% |",
            f"| MDA distance | {r['mda_distance_bps']:.0f}bps | Above 4.5% Basel CET1 floor |",
            "",
        ]

    lines += [
        "## Methodology Notes",
        "",
        f"- Starting capital: ${STARTING_CAPITAL_BN:.1f}bn (illustrative Tier-1-equivalent)",
        f"- Regulatory floor: {REGULATORY_FLOOR_PCT}% (Basel III CET1 minimum)",
        f"- FX loss = net open position ($2.0bn) × |FX shock %|",
        f"- Rates loss = portfolio duration (3.0yr) × HQLA × rates shock (bps/10,000)",
        "- Internal thresholds are illustrative; not PayPal thresholds or regulatory minima",
        "",
        "---",
        "_Generated by stress_test.py — Synthetic portfolio exercise_",
    ]
    (OUT / "stress_test_results.md").write_text("\n".join(lines), encoding="utf-8")


# ── Main ───────────────────────────────────────────────────────────────────────
def main() -> None:
    OUT.mkdir(exist_ok=True)
    sc = pd.read_csv(DATA)
    sc = compute_losses(sc)
    sc = compute_kris(sc)
    sc = assign_rag(sc)

    write_csv(sc)
    write_markdown(sc)
    plot_waterfall(sc)

    print("\n── KRI Results ──────────────────────────────────────────────────────")
    display_cols = [
        "scenario", "capital_ratio_pct", "liquidity_ratio_pct",
        "counterparty_concentration_pct", "market_loss_fx_bn", "market_loss_rates_bn",
        "capital_status", "liquidity_status", "counterparty_status", "recovery_trigger",
    ]
    print(sc[display_cols].round(2).to_string(index=False))

    print("\n── Loss Attribution (FX + Rates now propagated) ─────────────────────")
    for _, r in sc.iterrows():
        print(f"  {r['scenario']:10s}  "
              f"FX ${r['market_loss_fx_bn']:.2f}bn  "
              f"+ Rates ${r['market_loss_rates_bn']:.2f}bn  "
              f"→ Total ${r['total_loss_bn']:.2f}bn  "
              f"→ Capital {r['capital_ratio_pct']:.1f}%  "
              f"({r['capital_status']})  "
              f"MDA {r['mda_distance_bps']:.0f}bps")

    print("\n  Outputs: outputs/risk_kri_summary.csv, stress_test_results.md, loss_waterfall.png")


if __name__ == "__main__":
    main()
