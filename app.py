"""
Sales Intelligence Suite — Streamlit dashboard for account research,
pipeline context, and AI-assisted outreach (Gemini).
"""

from __future__ import annotations

import os
import time
from datetime import datetime
from typing import Any

import google.generativeai as genai
import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st
import yfinance as yf
from dotenv import load_dotenv

# --- CONFIG ---
load_dotenv()


def _env(key: str, default: str | None = None) -> str | None:
    try:
        if hasattr(st, "secrets") and key in st.secrets:
            return st.secrets[key]
    except Exception:
        pass
    return os.getenv(key, default)


DEFAULT_TICKER = "DE"


def init_session() -> None:
    if "ticker" not in st.session_state:
        st.session_state.ticker = DEFAULT_TICKER
    if "persona" not in st.session_state:
        st.session_state.persona = "VP Engineering"
    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []
    if "leaderboard_rows" not in st.session_state:
        st.session_state.leaderboard_rows = pd.DataFrame(
            {
                "Account": [
                    "John Deere",
                    "Siemens Mobility",
                    "Bosch Connected",
                    "Schneider Electric",
                    "Honeywell IIoT",
                ],
                "Ticker": ["DE", "SIE.DE", "BOSCHLTD.NS", "SU.PA", "HON"],
                "Stage": ["Negotiation", "Discovery", "Proposal", "Qualification", "Discovery"],
                "Est. ARR ($K)": [420, 310, 180, 95, 240],
                "Champion": ["M. Chen", "A. Weber", "L. Patel", "S. Dubois", "K. Ortiz"],
                "Next step": [
                    "Security review",
                    "POC scope",
                    "Exec alignment",
                    "Technical fit call",
                    "Use-case workshop",
                ],
            }
        )


# --- PAGE (must be first Streamlit command) ---
st.set_page_config(
    page_title="Sales Intelligence Suite",
    page_icon="◆",
    layout="wide",
    initial_sidebar_state="expanded",
)

init_session()

NEWS_API_KEY = _env("NEWS_API_KEY")
GEMINI_API_KEY = _env("GEMINI_API_KEY")
GEMINI_MODEL = _env("GEMINI_MODEL", "gemini-1.5-flash")
FMP_API_KEY = _env("FMP_API_KEY")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# --- REFINED STYLING ---
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }
    
    .stApp {
        background: #ffffff;
        color: #1a1d26;
    }

    /* SIDEBAR FIX: Force text white on black background */
    [data-testid="stSidebar"] {
        background: #0f1419 !important;
        border-right: 1px solid #2d333b;
    }
    [data-testid="stSidebar"] label, 
    [data-testid="stSidebar"] .stMarkdown p, 
    [data-testid="stSidebar"] .stCaption, 
    [data-testid="stSidebar"] span,
    [data-testid="stSidebar"] .stRadio label p { 
        color: #ffffff !important; 
    }
    
    /* Metrics and Layout cleanup */
    .metric-shell {
        background: #ffffff;
        border: 1px solid #e8eaef;
        border-radius: 12px;
        padding: 0.75rem 1rem;
        box-shadow: 0 1px 2px rgba(15, 20, 25, 0.04);
    }
    
    .fit-ring {
        text-align: center;
        padding: 1.5rem;
        background: #f4f6fb;
        border: 1px solid #e8eaef;
        border-radius: 16px;
    }

    .fit-score {
        font-size: 3rem;
        font-weight: 700;
        color: #0d47a1;
    }

    .analyst-pill {
        display: inline-block;
        padding: 0.25rem 0.6rem;
        border-radius: 6px;
        font-size: 0.75rem;
        font-weight: 700;
        margin-top: 0.5rem;
    }
    .pill-buy { background: #1b5e20; color: #fff; }
    .pill-sell { background: #b71c1c; color: #fff; }
    .pill-hold { background: #e65100; color: #fff; }
    
    .section-label {
        font-size: 0.65rem;
        font-weight: 700;
        letter-spacing: 0.1em;
        text-transform: uppercase;
        color: #5c6370;
    }
    
    /* Tighten Title area */
    h1 { margin-bottom: 0px !important; padding-bottom: 0px !important; }
    </style>
    """,
    unsafe_allow_html=True,
)


# --- HELPERS ---

def get_recommendation_label(info: dict[str, Any]) -> tuple[str, str]:
    rec = str(info.get("recommendationKey", "none")).lower()
    if "buy" in rec:
        return "BUY", "pill-buy"
    if "sell" in rec:
        return "SELL", "pill-sell"
    return "HOLD", "hold" if "hold" in rec else "pill-hold"


def _safe_float(val: Any, default: float = 0.0) -> float:
    try:
        return float(val) if val is not None else default
    except (TypeError, ValueError):
        return default


def calculate_fit_score(info: dict[str, Any]) -> tuple[int, str, str]:
    score = 52
    sector = (info.get("sector") or "").strip()
    industry = (info.get("industry") or "").lower()
    if sector in ("Technology", "Industrials"): score += 14
    if any(k in industry for k in ("semiconductor", "machinery", "electrical", "auto", "aerospace")): score += 10
    mc = _safe_float(info.get("marketCap"), 0)
    if mc > 50e9: score += 8
    score = max(18, min(score, 97))
    if score >= 78: return score, "Tier A — prioritize", "tier-a"
    if score >= 58: return score, "Tier B — nurture", "tier-b"
    return score, "Tier C — qualify", "tier-c"


@st.cache_data(ttl=900)
def get_market_snapshot(ticker: str):
    info, hist, warning = {}, pd.DataFrame(), None
    try:
        t = yf.Ticker(ticker)
        info = t.info
        hist = t.history(period="1y")
    except Exception as e:
        warning = str(e)
    return info, hist, warning


# --- SIDEBAR ---
with st.sidebar:
    st.markdown("### 🏦 Sales Suite")
    logo_path = os.path.join(os.path.dirname(__file__), "logo.png")
    if os.path.isfile(logo_path):
        st.image(logo_path, use_container_width=True)
    
    st.divider()
    app_mode = st.radio("Navigation", ["Executive Summary", "Weekly News Digest", "Account Leaderboard", "ROI Calculator", "Outreach & Export"])
    
    st.divider()
    st.session_state.ticker = st.text_input("Ticker Symbol", st.session_state.ticker).upper().strip()
    st.session_state.persona = st.selectbox("Persona", ["VP Engineering", "CTO", "Head of Manufacturing", "Director Innovation"])
    
    if st.button("Refresh Data"):
        get_market_snapshot.clear()
        st.rerun()

# --- MAIN PAGE ---
ticker = st.session_state.ticker or DEFAULT_TICKER
info, hist, yf_warning = get_market_snapshot(ticker)

name = info.get("shortName") or info.get("longName") or ticker
sector = info.get("sector", "—")
industry = info.get("industry", "—")
price = _safe_float(info.get("currentPrice") or info.get("regularMarketPrice"))
change_pct = _safe_float(info.get("regularMarketChangePercent"))

# HEADER SECTION
col_title, col_metric = st.columns([3, 1], vertical_alignment="bottom")

with col_title:
    # Manual HTML for title to remove default padding/margins causing the "empty portion"
    st.markdown(f'<h1 style="margin-bottom:0px; padding-bottom:0px;">{name}</h1>', unsafe_allow_html=True)
    st.markdown(f'<p style="color:#5c6370; margin-top:0px; font-weight:500;">{ticker} &nbsp;·&nbsp; {sector} &nbsp;·&nbsp; {industry}</p>', unsafe_allow_html=True)

with col_metric:
    st.markdown('<div class="metric-shell">', unsafe_allow_html=True)
    # Removing the label string "" removes the "random text box" above the price
    st.metric("", f"${price:,.2f}" if price else "—", f"{change_pct:+.2f}%")
    label, pill_cls = get_recommendation_label(info)
    st.markdown(f'<span class="analyst-pill {pill_cls}">Consensus: {label}</span>', unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

st.divider()

# WORKSPACE LOGIC
if app_mode == "Executive Summary":
    score, tier_label, tier_cls = calculate_fit_score(info)
    c1, c2, c3 = st.columns([2, 1, 1])
    
    with c1:
        st.subheader("Business Context")
        summary = info.get("longBusinessSummary", "Summary unavailable.")
        st.write(summary[:800] + "...")
        if not hist.empty:
            fig = go.Figure(go.Scatter(x=hist.index, y=hist["Close"], fill='tozeroy', line=dict(color='#0d47a1')))
            fig.update_layout(height=300, margin=dict(l=0,r=0,t=0,b=0), xaxis_showgrid=False, plot_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig, use_container_width=True)

    with c2:
        st.markdown(f'<div class="fit-ring"><div class="section-label">Fit Score</div><div class="fit-score">{score}</div><p>{tier_label}</p></div>', unsafe_allow_html=True)

    with c3:
        mc = _safe_float(info.get("marketCap"), 0)
        st.markdown(f'<div class="metric-shell"><p class="section-label">Market Cap</p><h3>${mc/1e9:.1f}B</h3><p class="section-label">Employees</p><h3>{info.get("fullTimeEmployees", "—"):,}</h3></div>', unsafe_allow_html=True)

elif app_mode == "ROI Calculator":
    st.subheader("Infrastructure ROI Model")
    c_left, c_right = st.columns(2)
    with c_left:
        devices = st.number_input("Devices", value=10000)
        mb = st.slider("MB/Day", 1, 500, 20)
    with c_right:
        cost_gb = st.number_input("Cloud $/GB", value=0.12)
        gain = st.slider("Efficiency %", 5, 80, 35)
    
    annual_save = ((devices * mb * 365) / 1024) * cost_gb * (gain/100)
    st.markdown(f'<div style="background:#f0f4fa; padding:2rem; border-radius:12px; border-left:5px solid #0d47a1;"><h2>Projected Annual Savings</h2><h1 style="color:#1b5e20;">${annual_save:,.0f}</h1></div>', unsafe_allow_html=True)

# ACCOUNT CONCIERGE (Chat)
st.divider()
st.subheader("💬 Account Concierge")
prompt = st.chat_input("Ask a question about this account strategy...")

if prompt:
    st.session_state.chat_messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"): st.markdown(prompt)
    with st.chat_message("assistant"):
        if GEMINI_API_KEY:
            model = genai.GenerativeModel(GEMINI_MODEL)
            response = model.generate_content(f"Act as a sales strategist for {name}. Question: {prompt}")
            st.markdown(response.text)
            st.session_state.chat_messages.append({"role": "assistant", "content": response.text})
        else:
            st.error("API Key missing.")
