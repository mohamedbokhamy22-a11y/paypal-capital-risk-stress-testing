"""
Unit tests for the KRI calculation engine.
Run:  pytest tests/
"""

import sys
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from stress_test import compute_losses, compute_kris, assign_rag
from reverse_stress import capital_ratio_fn, find_breach_multiplier

STARTING_CAPITAL_BN = 12.0

# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture
def baseline_row() -> pd.Series:
    return pd.Series({
        "scenario": "Baseline",
        "net_revenue_bn": 3.5, "credit_loss_bn": 1.5, "market_loss_bn": 0.4,
        "operational_loss_bn": 0.2, "rwa_bn": 110.0, "hqla_bn": 25.0,
        "net_30d_outflows_bn": 20.0, "top_counterparty_exposure_bn": 3.2,
        "fx_shock_pct": -5.0, "rates_shock_bps": 50.0,
        "net_open_position_bn": 2.0, "duration_years": 3.0,
    })


@pytest.fixture
def all_scenarios() -> pd.DataFrame:
    return pd.read_csv(ROOT / "data" / "scenarios.csv")


# ── Test 1: Capital ratio math is correct ─────────────────────────────────────

def test_capital_ratio_calculation(baseline_row):
    """The capital ratio formula produces the expected value for a known input."""
    # FX loss = 2.0 * 5/100 = 0.10
    # Rates loss = 3.0 * 25.0 * 50/10000 = 0.375
    # Total loss = 1.5 + 0.4 + 0.2 + 0.10 + 0.375 = 2.575
    # Ending cap = 12.0 + 3.5 - 2.575 = 12.925
    # Cap ratio = 100 * 12.925 / 110 ≈ 11.75%
    expected_fx_loss    = 2.0 * 5.0 / 100
    expected_rates_loss = 3.0 * 25.0 * 50.0 / 10_000
    expected_total_loss = 1.5 + 0.4 + 0.2 + expected_fx_loss + expected_rates_loss
    expected_ending_cap = STARTING_CAPITAL_BN + 3.5 - expected_total_loss
    expected_cap_ratio  = 100 * expected_ending_cap / 110.0

    sc = pd.DataFrame([baseline_row])
    sc = compute_losses(sc)
    sc = compute_kris(sc)

    assert abs(sc.iloc[0]["capital_ratio_pct"] - expected_cap_ratio) < 1e-6


# ── Test 2: RAG threshold boundaries ──────────────────────────────────────────

def test_rag_thresholds_capital():
    """Capital RAG assigns GREEN/AMBER/RED at the correct boundaries."""
    def make_sc(cap_ratio):
        # Back-calculate credit_loss_bn to hit the target capital ratio exactly
        # cap_ratio = 100 * ending_cap / rwa, ending_cap = 12 + 3.5 - total_loss
        rwa          = 100.0
        ending_cap   = cap_ratio * rwa / 100
        # zero FX and rates loss (fx_shock=0, rates=0)
        total_loss   = STARTING_CAPITAL_BN + 3.5 - ending_cap
        credit_loss  = max(total_loss, 0.01)
        return pd.DataFrame([{
            "scenario": "test", "net_revenue_bn": 3.5,
            "credit_loss_bn": credit_loss, "market_loss_bn": 0.0,
            "operational_loss_bn": 0.0, "rwa_bn": rwa, "hqla_bn": 10.0,
            "net_30d_outflows_bn": 10.0, "top_counterparty_exposure_bn": 1.0,
            "fx_shock_pct": 0.0, "rates_shock_bps": 0.0,
            "net_open_position_bn": 0.0, "duration_years": 1.0,
        }])

    sc_green = compute_kris(compute_losses(make_sc(10.0)))
    sc_amber = compute_kris(compute_losses(make_sc(8.0)))
    sc_red   = compute_kris(compute_losses(make_sc(6.0)))

    sc_green = assign_rag(sc_green)
    sc_amber = assign_rag(sc_amber)
    sc_red   = assign_rag(sc_red)

    assert sc_green.iloc[0]["capital_status"] == "GREEN"
    assert sc_amber.iloc[0]["capital_status"] == "AMBER"
    assert sc_red.iloc[0]["capital_status"]   == "RED"


# ── Test 3: Recovery trigger fires correctly ───────────────────────────────────

def test_recovery_trigger_fires(all_scenarios):
    """Severe scenario must trigger recovery; Baseline must not."""
    sc = compute_losses(all_scenarios.copy())
    sc = compute_kris(sc)
    sc = assign_rag(sc)

    baseline_row = sc[sc["scenario"] == "Baseline"].iloc[0]
    severe_row   = sc[sc["scenario"] == "Severe"].iloc[0]

    assert baseline_row["recovery_trigger"] is False or baseline_row["recovery_trigger"] == False
    assert severe_row["recovery_trigger"]   is True  or severe_row["recovery_trigger"]   == True


# ── Test 4: FX and rates losses propagate (non-zero) ──────────────────────────

def test_fx_rates_propagation(all_scenarios):
    """Every scenario must produce non-zero FX and rates losses."""
    sc = compute_losses(all_scenarios.copy())

    assert (sc["market_loss_fx_bn"] > 0).all(), "FX loss should be > 0 for all scenarios"
    assert (sc["market_loss_rates_bn"] > 0).all(), "Rates loss should be > 0 for all scenarios"


# ── Test 5: Capital ratio is monotonically decreasing across scenarios ─────────

def test_capital_ratio_monotonicity(all_scenarios):
    """Baseline capital ratio > Adverse > Severe (stress scenarios get worse)."""
    sc = compute_losses(all_scenarios.copy())
    sc = compute_kris(sc)

    ratios = sc.set_index("scenario")["capital_ratio_pct"]
    assert ratios["Baseline"] > ratios["Adverse"] > ratios["Severe"], (
        f"Expected Baseline > Adverse > Severe, got "
        f"{ratios['Baseline']:.2f} > {ratios['Adverse']:.2f} > {ratios['Severe']:.2f}"
    )


# ── Test 6: Reverse stress — Adverse breach multiplier > 1.0 ──────────────────

def test_reverse_stress_adverse_above_one(all_scenarios):
    """Under Adverse, the regulatory floor is not breached at 1× assumed credit losses."""
    adverse_row = all_scenarios[all_scenarios["scenario"] == "Adverse"].iloc[0]
    base_cr = capital_ratio_fn(1.0, adverse_row)
    assert base_cr > 4.5, f"Adverse base capital ratio {base_cr:.2f}% should be above 4.5%"

    mult = find_breach_multiplier(adverse_row)
    assert mult > 1.0, f"Breach multiplier {mult:.2f} should be > 1.0 for Adverse scenario"
