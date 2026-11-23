"""
Reverse Stress Test
Finds the credit-loss multiplier that drives capital ratio to the 4.5% Basel CET1 floor,
then plots a 2D failure frontier showing how credit loss and FX shock interact.

Usage:  python reverse_stress.py
"""

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path
from scipy.optimize import brentq

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data" / "scenarios.csv"
OUT  = ROOT / "outputs"

STARTING_CAPITAL_BN  = 12.0
REGULATORY_FLOOR_PCT =  4.5   # Basel III CET1 minimum
INTERNAL_RED_PCT     =  7.0   # internal RED threshold


# ── Core capital ratio function ────────────────────────────────────────────────
def capital_ratio_fn(credit_mult: float, row: pd.Series) -> float:
    """Capital ratio for a given credit loss multiplier applied to a base scenario row."""
    credit_loss   = row["credit_loss_bn"] * credit_mult
    fx_loss       = row["net_open_position_bn"] * abs(row["fx_shock_pct"]) / 100
    rates_loss    = row["duration_years"] * row["hqla_bn"] * row["rates_shock_bps"] / 10_000
    total_loss    = credit_loss + row["market_loss_bn"] + row["operational_loss_bn"] + fx_loss + rates_loss
    ending_cap    = STARTING_CAPITAL_BN + row["net_revenue_bn"] - total_loss
    return 100 * ending_cap / row["rwa_bn"]


def find_breach_multiplier(row: pd.Series, floor: float = REGULATORY_FLOOR_PCT) -> float:
    """Binary search for the credit loss multiplier that hits the regulatory floor."""
    if capital_ratio_fn(1.0, row) <= floor:
        return 1.0           # already in breach at base assumptions
    if capital_ratio_fn(15.0, row) > floor:
        return float("inf")  # cannot breach even at 15× credit losses
    return brentq(lambda m: capital_ratio_fn(m, row) - floor, 1.0, 15.0, xtol=1e-6)


# ── 2D failure frontier ────────────────────────────────────────────────────────
def plot_failure_frontier(sc: pd.DataFrame) -> None:
    """
    For the Adverse scenario: vary credit loss multiplier (x-axis) and FX shock
    magnitude (y-axis), colour by capital ratio. Black contour = 4.5% reg. floor.
    Dashed red = 7% internal RED threshold.
    """
    adv = sc[sc["scenario"] == "Adverse"].iloc[0]

    credit_mults = np.linspace(0.4, 4.0, 80)
    fx_magnitudes = np.linspace(1, 35, 80)
    Z = np.zeros((len(fx_magnitudes), len(credit_mults)))

    for i, fx_mag in enumerate(fx_magnitudes):
        for j, cm in enumerate(credit_mults):
            row_mod = adv.copy()
            row_mod["fx_shock_pct"] = -fx_mag
            Z[i, j] = capital_ratio_fn(cm, row_mod)

    fig, ax = plt.subplots(figsize=(10, 7))
    cf = ax.contourf(credit_mults, fx_magnitudes, Z, levels=25, cmap="RdYlGn", vmin=0, vmax=16)
    plt.colorbar(cf, label="Capital Ratio (%)", ax=ax)

    # Regulatory floor contour
    cs_floor = ax.contour(credit_mults, fx_magnitudes, Z,
                          levels=[REGULATORY_FLOOR_PCT], colors="black", linewidths=2.5)
    ax.clabel(cs_floor, fmt={REGULATORY_FLOOR_PCT: f"{REGULATORY_FLOOR_PCT}pct floor"}, fontsize=9)

    # Internal RED threshold
    cs_red = ax.contour(credit_mults, fx_magnitudes, Z,
                        levels=[INTERNAL_RED_PCT], colors="darkred", linewidths=1.8, linestyles="--")
    ax.clabel(cs_red, fmt={INTERNAL_RED_PCT: f"{INTERNAL_RED_PCT}pct RED"}, fontsize=9)

    # Mark the assumed Adverse scenario point
    ax.plot(1.0, abs(adv["fx_shock_pct"]), "o", color="navy", markersize=10, zorder=5,
            label=f"Adverse scenario\n(1× credit loss, {abs(adv['fx_shock_pct']):.0f}% FX shock)")

    ax.set_xlabel("Credit Loss Multiplier (× Adverse assumption of $3.5bn)", fontsize=11)
    ax.set_ylabel("FX Shock Magnitude (%)", fontsize=11)
    ax.set_title(
        "Reverse Stress Test: Capital Ratio Failure Frontier — Adverse Scenario\n"
        "Black line = 4.5% Basel CET1 minimum  |  Dashed red = 7% internal RED threshold\n"
        "Synthetic portfolio exercise — all assumptions are illustrative",
        fontsize=10,
    )
    ax.legend(fontsize=9, loc="upper left")

    # Annotate zones
    ax.text(3.2, 30, "BREACH ZONE\n(capital < 4.5%)", color="darkred",
            fontsize=10, fontweight="bold", ha="center")
    ax.text(0.7, 5, "SAFE ZONE\n(capital > 7%)", color="darkgreen",
            fontsize=10, fontweight="bold", ha="center")

    plt.tight_layout()
    plt.savefig(OUT / "reverse_stress_frontier.png", dpi=150, bbox_inches="tight")
    plt.close()
    print("  Saved → outputs/reverse_stress_frontier.png")


# ── Main ───────────────────────────────────────────────────────────────────────
def main() -> None:
    OUT.mkdir(exist_ok=True)
    sc = pd.read_csv(DATA)

    print("\n── Reverse Stress Test ──────────────────────────────────────────────")
    print(f"   Target: capital ratio = {REGULATORY_FLOOR_PCT}% (Basel III CET1 minimum)\n")

    results = []
    for _, row in sc.iterrows():
        base_cr = capital_ratio_fn(1.0, row)
        mult    = find_breach_multiplier(row, floor=REGULATORY_FLOOR_PCT)
        red_mult = find_breach_multiplier(row, floor=INTERNAL_RED_PCT)

        breach_loss = row["credit_loss_bn"] * mult if mult != float("inf") else float("nan")
        headroom    = breach_loss - row["credit_loss_bn"] if mult != float("inf") else float("nan")

        results.append({
            "scenario":                    row["scenario"],
            "base_capital_ratio_pct":      round(base_cr, 2),
            "credit_loss_breach_mult":     round(mult, 2) if mult != float("inf") else "N/A",
            "breach_credit_loss_bn":       round(breach_loss, 2) if mult != float("inf") else "N/A",
            "assumed_credit_loss_bn":      row["credit_loss_bn"],
            "headroom_above_assumed_bn":   round(headroom, 2) if mult != float("inf") else "N/A",
            "internal_red_breach_mult":    round(red_mult, 2) if red_mult != float("inf") else "N/A",
        })

        print(f"  {row['scenario']} (base capital ratio: {base_cr:.1f}%)")
        if mult == 1.0:
            print(f"    ⚠ Already in regulatory breach at assumed credit losses")
        elif mult == float("inf"):
            print(f"    Capital cannot breach regulatory floor even at 15× credit losses")
        else:
            print(f"    Regulatory floor breach: credit losses must reach ${breach_loss:.2f}bn "
                  f"({mult:.2f}× assumed ${row['credit_loss_bn']:.1f}bn)")
            print(f"    Headroom above assumed: ${headroom:.2f}bn")
        if red_mult != float("inf") and red_mult > 1.0:
            print(f"    Internal RED threshold (7%): reached at {red_mult:.2f}× assumed credit losses")
        print()

    df = pd.DataFrame(results)
    df.to_csv(OUT / "reverse_stress_results.csv", index=False)
    print("  Saved → outputs/reverse_stress_results.csv")

    plot_failure_frontier(sc)

    # Key narrative sentence for README/memo
    adv = next(r for r in results if r["scenario"] == "Adverse")
    print(f"\n  Key finding: Under the Adverse scenario, capital breaches the 4.5% regulatory")
    print(f"  floor if credit losses reach ${adv['breach_credit_loss_bn']:.2f}bn "
          f"({adv['credit_loss_breach_mult']:.1f}× the assumed ${adv['assumed_credit_loss_bn']:.1f}bn).")
    print(f"  This is ${adv['headroom_above_assumed_bn']:.2f}bn of headroom above the scenario assumption.")


if __name__ == "__main__":
    main()
