"""
Tornado Sensitivity Analysis
Perturbs each scenario input ±20% and measures impact on capital ratio.
Answers: which variable matters most? Which is immaterial?

Usage:  python sensitivity.py
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

STARTING_CAPITAL_BN = 12.0
REGULATORY_FLOOR_PCT = 4.5
INTERNAL_RED_PCT     = 7.0
PERTURBATION         = 0.20   # ±20%

NUMERIC_INPUTS = [
    "net_revenue_bn", "credit_loss_bn", "market_loss_bn", "operational_loss_bn",
    "rwa_bn", "hqla_bn", "net_30d_outflows_bn", "top_counterparty_exposure_bn",
    "fx_shock_pct", "rates_shock_bps", "net_open_position_bn", "duration_years",
]

LABELS = {
    "net_revenue_bn":               "Net Revenue",
    "credit_loss_bn":               "Credit Losses",
    "market_loss_bn":               "Market Losses (pre-shock)",
    "operational_loss_bn":          "Operational Losses",
    "rwa_bn":                       "Risk-Weighted Assets",
    "hqla_bn":                      "HQLA / Liquid Assets",
    "net_30d_outflows_bn":          "30-Day Outflows",
    "top_counterparty_exposure_bn": "Top Counterparty Exposure",
    "fx_shock_pct":                 "FX Shock (%)",
    "rates_shock_bps":              "Rates Shock (bps)",
    "net_open_position_bn":         "FX Net Open Position ($bn)",
    "duration_years":               "Portfolio Duration (years)",
}


def capital_ratio_fn(row: pd.Series) -> float:
    fx_loss    = row["net_open_position_bn"] * abs(row["fx_shock_pct"]) / 100
    rates_loss = row["duration_years"] * row["hqla_bn"] * row["rates_shock_bps"] / 10_000
    total_loss = (row["credit_loss_bn"] + row["market_loss_bn"]
                  + row["operational_loss_bn"] + fx_loss + rates_loss)
    ending_cap = STARTING_CAPITAL_BN + row["net_revenue_bn"] - total_loss
    return 100 * ending_cap / row["rwa_bn"]


def run_tornado(sc: pd.DataFrame, scenario: str) -> tuple[float, pd.DataFrame]:
    base_row = sc[sc["scenario"] == scenario].iloc[0].copy()
    base_cr  = capital_ratio_fn(base_row)
    results  = []

    for col in NUMERIC_INPUTS:
        base_val = base_row[col]

        row_up = base_row.copy()
        row_up[col] = base_val * (1 + PERTURBATION)
        cr_up = capital_ratio_fn(row_up)

        row_dn = base_row.copy()
        row_dn[col] = base_val * (1 - PERTURBATION)
        cr_dn = capital_ratio_fn(row_dn)

        results.append({
            "variable":  LABELS[col],
            "delta_up":  cr_up - base_cr,
            "delta_dn":  cr_dn - base_cr,
            "range_pp":  abs(cr_up - cr_dn),
        })

    df = pd.DataFrame(results).sort_values("range_pp", ascending=False).reset_index(drop=True)
    return base_cr, df


def plot_tornado(df: pd.DataFrame, scenario: str, base_cr: float) -> None:
    fig, ax = plt.subplots(figsize=(10, 7))

    for i, row in df.iterrows():
        lo = min(row["delta_up"], row["delta_dn"])
        hi = max(row["delta_up"], row["delta_dn"])
        # positive side = green, negative side = red
        if hi > 0:
            ax.barh(i, hi, left=0,  height=0.6, color="#27ae60", alpha=0.78, edgecolor="white")
        if lo < 0:
            ax.barh(i, lo, left=0,  height=0.6, color="#e74c3c", alpha=0.78, edgecolor="white")

        label_x = hi + 0.08 if abs(hi) >= abs(lo) else lo - 0.08
        ha = "left" if abs(hi) >= abs(lo) else "right"
        ax.text(label_x, i, f"±{row['range_pp']:.1f}pp", va="center", fontsize=8.5,
                ha=ha, color="#333")

    ax.set_yticks(range(len(df)))
    ax.set_yticklabels(df["variable"], fontsize=9)
    ax.axvline(0, color="black", linewidth=1.2)

    # Reg floor distance
    floor_dist = -(base_cr - REGULATORY_FLOOR_PCT)
    red_dist   = -(base_cr - INTERNAL_RED_PCT)
    ax.axvline(floor_dist, color="darkred", linewidth=1.5, linestyle="--",
               label=f"Reg. floor distance ({floor_dist:+.1f}pp)")
    ax.axvline(red_dist, color="red", linewidth=1.2, linestyle=":",
               label=f"Internal RED distance ({red_dist:+.1f}pp)")

    ax.set_xlabel("Change in Capital Ratio (percentage points)", fontsize=10)
    ax.set_title(
        f"Tornado Sensitivity — {scenario} Scenario\n"
        f"Base capital ratio: {base_cr:.1f}%  |  Bars show ±{PERTURBATION*100:.0f}% perturbation on each input\n"
        f"Synthetic portfolio exercise — all assumptions are illustrative",
        fontsize=10,
    )
    ax.legend(fontsize=8, loc="lower right")
    plt.tight_layout()
    plt.savefig(OUT / f"tornado_{scenario.lower()}.png", dpi=150, bbox_inches="tight")
    plt.close()


def main() -> None:
    OUT.mkdir(exist_ok=True)
    sc = pd.read_csv(DATA)

    print(f"\n── Tornado Sensitivity (±{PERTURBATION*100:.0f}% perturbation on each input) ──────────────")
    all_results = {}

    for scenario in sc["scenario"]:
        base_cr, df = run_tornado(sc, scenario)
        all_results[scenario] = (base_cr, df)

        print(f"\n  {scenario}  (base capital ratio: {base_cr:.1f}%)")
        print(f"  {'Variable':<35} {'Range (pp)':>10}  {'Up +20%':>10}  {'Dn -20%':>10}")
        for _, r in df.iterrows():
            print(f"  {r['variable']:<35} {r['range_pp']:>10.2f}  {r['delta_up']:>+10.2f}  {r['delta_dn']:>+10.2f}")

        df.to_csv(OUT / f"tornado_{scenario.lower()}.csv", index=False)
        plot_tornado(df, scenario, base_cr)
        print(f"  Saved → outputs/tornado_{scenario.lower()}.png")

    # Key findings across scenarios
    print("\n── Key Findings ─────────────────────────────────────────────────────")
    for scenario, (base_cr, df) in all_results.items():
        top2  = df.head(2)["variable"].tolist()
        least = df.tail(1)["variable"].iloc[0]
        top_range = df.iloc[0]["range_pp"]
        print(f"  {scenario}: [{top2[0]}] is the dominant driver (±{top_range:.1f}pp range).")
        print(f"             [{top2[1]}] is second. [{least}] is least material — de-prioritize in scenario design.")


if __name__ == "__main__":
    main()
