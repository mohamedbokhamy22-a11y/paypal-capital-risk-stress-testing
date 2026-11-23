"""
Interactive Capital & Liquidity Stress Testing Dashboard
Run:  streamlit run dashboard.py
"""

import streamlit as st
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# ── Constants ──────────────────────────────────────────────────────────────────
STARTING_CAPITAL_BN  = 12.0
REGULATORY_FLOOR_PCT =  4.5
INTERNAL_CAP_RED     =  7.0
INTERNAL_CAP_AMBER   =  9.0
LIQUIDITY_RED        = 100.0
LIQUIDITY_AMBER      = 115.0
CONC_AMBER           =  25.0
CONC_RED             =  30.0


def compute_kris(params: dict) -> dict:
    fx_loss    = params["net_open_position_bn"] * abs(params["fx_shock_pct"]) / 100
    rates_loss = params["duration_years"] * params["hqla_bn"] * params["rates_shock_bps"] / 10_000
    total_loss = (params["credit_loss_bn"] + params["market_loss_bn"]
                  + params["operational_loss_bn"] + fx_loss + rates_loss)
    ending_cap = STARTING_CAPITAL_BN + params["net_revenue_bn"] - total_loss
    cap_ratio  = 100 * ending_cap / params["rwa_bn"]
    liq_ratio  = 100 * params["hqla_bn"] / params["net_30d_outflows_bn"]
    conc_pct   = 100 * params["top_counterparty_exposure_bn"] / STARTING_CAPITAL_BN
    mda_bps    = (cap_ratio - REGULATORY_FLOOR_PCT) * 100

    return {
        "fx_loss_bn":     fx_loss,
        "rates_loss_bn":  rates_loss,
        "total_loss_bn":  total_loss,
        "ending_cap_bn":  ending_cap,
        "cap_ratio":      cap_ratio,
        "liq_ratio":      liq_ratio,
        "conc_pct":       conc_pct,
        "mda_bps":        mda_bps,
        "cap_status":     "RED" if cap_ratio < INTERNAL_CAP_RED else ("AMBER" if cap_ratio < INTERNAL_CAP_AMBER else "GREEN"),
        "liq_status":     "RED" if liq_ratio < LIQUIDITY_RED else ("AMBER" if liq_ratio < LIQUIDITY_AMBER else "GREEN"),
        "conc_status":    "RED" if conc_pct > CONC_RED else ("AMBER" if conc_pct > CONC_AMBER else "GREEN"),
    }


def rag_color(status: str) -> str:
    return {"RED": "#e74c3c", "AMBER": "#f39c12", "GREEN": "#27ae60"}.get(status, "#aaa")


def waterfall_fig(params: dict, kris: dict) -> plt.Figure:
    cats   = ["Start\nCapital", "+Revenue", "–Credit", "–Market", "–OpLoss", "–FX*", "–Rates*", "End\nCapital"]
    vals   = [STARTING_CAPITAL_BN, params["net_revenue_bn"],
              -params["credit_loss_bn"], -params["market_loss_bn"],
              -params["operational_loss_bn"], -kris["fx_loss_bn"],
              -kris["rates_loss_bn"], kris["ending_cap_bn"]]
    colors = ["#2c3e50", "#27ae60", "#e74c3c", "#e67e22",
              "#c0392b", "#3498db", "#9b59b6",
              "#27ae60" if kris["ending_cap_bn"] > 0 else "#e74c3c"]

    fig, ax = plt.subplots(figsize=(9, 4))
    ax.bar(cats, [abs(v) for v in vals], color=colors, alpha=0.85, edgecolor="white")
    for i, (c, v) in enumerate(zip(cats, vals)):
        ax.text(i, abs(v) + 0.08, f"${abs(v):.2f}bn", ha="center", va="bottom", fontsize=8)
    ax.axhline(STARTING_CAPITAL_BN * REGULATORY_FLOOR_PCT / 100,
               color="darkred", linewidth=1.5, linestyle="--",
               label=f"Reg. floor equiv. ({REGULATORY_FLOOR_PCT}%)")
    ax.set_ylabel("$bn")
    ax.legend(fontsize=8)
    ax.set_title("Loss Attribution Waterfall  (*FX & Rates shock-propagated)", fontsize=10)
    plt.tight_layout()
    return fig


# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(page_title="Capital Stress Dashboard", layout="wide")
st.title("Capital & Liquidity Stress Testing Dashboard")
st.caption("Synthetic portfolio exercise — all figures are illustrative. Not PayPal data.")

# ── Scenario presets ───────────────────────────────────────────────────────────
PRESETS = {
    "Baseline": dict(net_revenue_bn=3.5, credit_loss_bn=1.5, market_loss_bn=0.4,
                     operational_loss_bn=0.2, rwa_bn=110, hqla_bn=25,
                     net_30d_outflows_bn=20, top_counterparty_exposure_bn=3.2,
                     fx_shock_pct=5, rates_shock_bps=50, net_open_position_bn=2.0, duration_years=3.0),
    "Adverse":  dict(net_revenue_bn=3.0, credit_loss_bn=3.5, market_loss_bn=1.1,
                     operational_loss_bn=0.3, rwa_bn=118, hqla_bn=22,
                     net_30d_outflows_bn=28, top_counterparty_exposure_bn=3.8,
                     fx_shock_pct=12, rates_shock_bps=150, net_open_position_bn=2.0, duration_years=3.0),
    "Severe":   dict(net_revenue_bn=2.5, credit_loss_bn=6.0, market_loss_bn=2.0,
                     operational_loss_bn=0.6, rwa_bn=125, hqla_bn=18,
                     net_30d_outflows_bn=36, top_counterparty_exposure_bn=4.5,
                     fx_shock_pct=20, rates_shock_bps=300, net_open_position_bn=2.0, duration_years=3.0),
}

col_sel, _ = st.columns([2, 8])
with col_sel:
    preset = st.selectbox("Load preset scenario", ["Custom"] + list(PRESETS.keys()))

if preset != "Custom":
    defaults = PRESETS[preset]
else:
    defaults = PRESETS["Adverse"]

# ── Sidebar sliders ────────────────────────────────────────────────────────────
st.sidebar.header("Scenario Parameters")

p = {}
st.sidebar.subheader("Revenue & Credit")
p["net_revenue_bn"]           = st.sidebar.slider("Net Revenue ($bn)",             0.5, 6.0, float(defaults["net_revenue_bn"]), 0.1)
p["credit_loss_bn"]           = st.sidebar.slider("Credit Losses ($bn)",           0.5, 12.0, float(defaults["credit_loss_bn"]), 0.1)

st.sidebar.subheader("Market & Operational")
p["market_loss_bn"]           = st.sidebar.slider("Market Losses ($bn)",           0.0, 5.0, float(defaults["market_loss_bn"]), 0.1)
p["operational_loss_bn"]      = st.sidebar.slider("Operational Losses ($bn)",      0.0, 2.0, float(defaults["operational_loss_bn"]), 0.05)

st.sidebar.subheader("Balance Sheet")
p["rwa_bn"]                   = st.sidebar.slider("Risk-Weighted Assets ($bn)",    80.0, 180.0, float(defaults["rwa_bn"]), 1.0)
p["hqla_bn"]                  = st.sidebar.slider("HQLA / Liquid Assets ($bn)",    5.0, 50.0, float(defaults["hqla_bn"]), 0.5)
p["net_30d_outflows_bn"]      = st.sidebar.slider("30-Day Net Outflows ($bn)",     5.0, 60.0, float(defaults["net_30d_outflows_bn"]), 0.5)
p["top_counterparty_exposure_bn"] = st.sidebar.slider("Top Counterparty Exp. ($bn)", 0.5, 8.0, float(defaults["top_counterparty_exposure_bn"]), 0.1)

st.sidebar.subheader("Market Shocks")
p["fx_shock_pct"]             = st.sidebar.slider("FX Shock (%)",                  0.0, 40.0, float(defaults["fx_shock_pct"]), 0.5)
p["rates_shock_bps"]          = st.sidebar.slider("Rates Shock (bps)",             0.0, 500.0, float(defaults["rates_shock_bps"]), 10.0)
p["net_open_position_bn"]     = st.sidebar.slider("FX Net Open Position ($bn)",    0.0, 10.0, float(defaults["net_open_position_bn"]), 0.1)
p["duration_years"]           = st.sidebar.slider("Portfolio Duration (years)",    0.5, 8.0, float(defaults["duration_years"]), 0.1)

# ── Compute ────────────────────────────────────────────────────────────────────
kris = compute_kris(p)

# ── KRI Tiles ─────────────────────────────────────────────────────────────────
st.subheader("Key Risk Indicators")
c1, c2, c3, c4 = st.columns(4)

def kri_tile(col, label, value, status, fmt=".1f"):
    color = rag_color(status)
    col.markdown(
        f"<div style='border-left:5px solid {color}; padding:10px; background:#1e1e2e; border-radius:4px'>"
        f"<div style='font-size:0.75em;color:#aaa'>{label}</div>"
        f"<div style='font-size:1.8em;font-weight:bold;color:{color}'>{value:{fmt}}%</div>"
        f"<div style='font-size:0.8em;color:{color};font-weight:bold'>{status}</div>"
        f"</div>", unsafe_allow_html=True)

kri_tile(c1, "Capital Ratio",        kris["cap_ratio"],  kris["cap_status"])
kri_tile(c2, "Liquidity Ratio (LCR)", kris["liq_ratio"], kris["liq_status"])
kri_tile(c3, "Counterparty Conc.",   kris["conc_pct"],   kris["conc_status"])
c4.metric("MDA Distance", f"{kris['mda_bps']:.0f} bps",
          delta=f"{kris['mda_bps'] - 250:.0f} bps vs. 250bps target")

# Recovery trigger banner
recovery = kris["cap_status"] == "RED" or kris["liq_status"] == "RED" or kris["conc_status"] == "RED"
if recovery:
    st.error("⚠ RECOVERY TRIGGER ACTIVE — one or more KRIs in RED")
else:
    st.success("No recovery trigger — all KRIs within tolerance")

# ── Loss Attribution ───────────────────────────────────────────────────────────
st.subheader("Loss Attribution")
col_wf, col_tbl = st.columns([6, 4])

with col_wf:
    st.pyplot(waterfall_fig(p, kris))

with col_tbl:
    st.markdown("**Loss Breakdown**")
    tbl = pd.DataFrame({
        "Component": ["Credit Losses", "Market Losses", "Operational Losses",
                       "FX Revaluation*", "Rates Revaluation*", "Total Losses"],
        "Amount ($bn)": [p["credit_loss_bn"], p["market_loss_bn"], p["operational_loss_bn"],
                          kris["fx_loss_bn"], kris["rates_loss_bn"], kris["total_loss_bn"]],
    })
    tbl["Amount ($bn)"] = tbl["Amount ($bn)"].map(lambda x: f"${x:.3f}bn")
    st.dataframe(tbl, hide_index=True, use_container_width=True)

    st.markdown(f"""
    | | |
    |---|---|
    | Starting capital | ${STARTING_CAPITAL_BN:.1f}bn |
    | Net revenue | ${p['net_revenue_bn']:.2f}bn |
    | Ending capital | **${kris['ending_cap_bn']:.3f}bn** |
    | Capital ratio | **{kris['cap_ratio']:.2f}%** |
    | Reg. floor (4.5%) | {'+' if kris['mda_bps'] >= 0 else ''}{kris['mda_bps']:.0f}bps |
    """)

# ── Scenario comparison table ──────────────────────────────────────────────────
st.subheader("Scenario Comparison")
rows = []
for name, pset in PRESETS.items():
    k = compute_kris(pset)
    rows.append({
        "Scenario":        name,
        "Capital %":       f"{k['cap_ratio']:.1f}%",
        "Capital Status":  k["cap_status"],
        "Liquidity %":     f"{k['liq_ratio']:.1f}%",
        "Liq. Status":     k["liq_status"],
        "Conc. %":         f"{k['conc_pct']:.1f}%",
        "Total Loss $bn":  f"${k['total_loss_bn']:.2f}bn",
        "MDA (bps)":       f"{k['mda_bps']:.0f}",
        "Recovery Trigger": "⚠ YES" if (k["cap_status"] == "RED" or k["liq_status"] == "RED" or k["conc_status"] == "RED") else "NO",
    })
st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)

st.caption("*FX loss = net open position × |FX shock %|  |  Rates loss = duration × HQLA × shock (bps/10,000)")
