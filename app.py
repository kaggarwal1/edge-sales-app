"""
Edge Impulse Sales Intelligence Suite — Production Build
Fixes: Sidebar Contrast, Header Spacing, Tab Logic, and AI Integration.
"""

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

# --- INITIALIZATION ---
load_dotenv()

def _env(key: str, default: str | None = None) -> str | None:
    try:
        if hasattr(st, "secrets") and key in st.secrets:
            return st.secrets[key]
    except Exception: pass
    return os.getenv(key, default)

if "ticker" not in st.session_state:
    st.session_state.ticker = "DE"
if "persona" not in st.session_state:
    st.session_state.persona = "VP Engineering"
if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = []
if "leaderboard_rows" not in st.session_state:
    st.session_state.leaderboard_rows = pd.DataFrame({
        "Account": ["John Deere", "Siemens", "Bosch", "Schneider", "Honeywell"],
        "Ticker": ["DE", "SIE.DE", "BOSCHLTD.NS", "SU.PA", "HON"],
        "Stage": ["Negotiation", "Discovery", "Proposal", "Qualification", "Discovery"],
        "Est. ARR ($K)": [420, 310, 180, 95, 240]
    })

NEWS_API_KEY = _env("NEWS_API_KEY")
GEMINI_API_KEY = _env("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# --- STYLING ---
st.set_page_config(page_title="Sales Intel", layout="wide")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;700&display=swap');
    html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }
    
    /* SIDEBAR: Pure Black Background + White Text */
    [data-testid="stSidebar"] {
        background-color: #000000 !important;
        border-right: 1px solid #333;
    }
    [data-testid="stSidebar"] * {
        color: #ffffff !important;
    }
    [data-testid="stSidebar"] .stRadio label div p {
        color: #ffffff !important;
    }

    /* MAIN UI */
    .stApp { background: #ffffff; }
    .metric-shell {
        background: #ffffff; border: 1px solid #e8eaef;
        border-radius: 12px; padding: 0.75rem 1rem;
    }
    .fit-ring {
        text-align: center; padding: 1.5rem; background: #f4f6fb;
        border-radius: 16px; border: 1px solid #e8eaef;
    }
    .fit-score { font-size: 3rem; font-weight: 700; color: #0d47a1; }
    
    /* HEADER FIXES */
    h1 { margin-bottom: 0px !important; padding-bottom: 0px !important; }
    .header-subtext { color: #5c6370; margin-top: -5px; font-weight: 500; margin-bottom: 15px; }
    </style>
    """, unsafe_allow_html=True)

# --- DATA HELPERS ---
@st.cache_data(ttl=900)
def get_market_data(ticker):
    try:
        t = yf.Ticker(ticker)
        return t.info, t.history(period="1y")
    except:
        return {}, pd.DataFrame()

def calculate_fit_score(info):
    score = 65
    sector = info.get("sector", "")
    if sector in ("Technology", "Industrials"): score += 15
    if info.get("marketCap", 0) > 50e9: score += 10
    return min(score, 98)

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
    st.session_state.persona = st.selectbox("Persona", ["VP Engineering", "CTO", "Head of Mfg", "Innovation Lead"])

# --- MAIN CONTENT ---
ticker = st.session_state.ticker
info, hist = get_market_data(ticker)
name = info.get("shortName") or info.get("longName") or ticker

# TABS THAT REQUIRE TICKER INFO
if app_mode in ["Executive Summary", "Weekly News Digest", "Outreach & Export"]:
    # HEADER
    col_t, col_m = st.columns([3, 1], vertical_alignment="bottom")
    with col_t:
        st.markdown(f'<h1>{name}</h1>', unsafe_allow_html=True)
        st.markdown(f'<p class="header-subtext">{ticker} &nbsp;·&nbsp; {info.get("sector", "—")} &nbsp;·&nbsp; {info.get("industry", "—")}</p>', unsafe_allow_html=True)
    with col_m:
        st.markdown('<div class="metric-shell">', unsafe_allow_html=True)
        price = info.get("currentPrice") or info.get("regularMarketPrice", 0)
        change = info.get("regularMarketChangePercent", 0)
        st.metric("", f"${price:,.2f}", f"{change:+.2f}%") # Label is empty to remove random text box
        st.markdown('</div>', unsafe_allow_html=True)
    st.divider()

# --- WORKSPACE LOGIC ---

if app_mode == "Executive Summary":
    c1, c2 = st.columns([2, 1])
    with c1:
        st.subheader("Account Narrative")
        st.write(info.get("longBusinessSummary", "Summary unavailable.")[:1000] + "...")
        if not hist.empty:
            fig = go.Figure(go.Scatter(x=hist.index, y=hist["Close"], fill='tozeroy', line=dict(color='#0d47a1')))
            fig.update_layout(height=300, margin=dict(l=0,r=0,t=0,b=0), xaxis_showgrid=False, plot_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig, use_container_width=True)
    with c2:
        score = calculate_fit_score(info)
        st.markdown(f'<div class="fit-ring"><p style="color:#5c6370; font-size:0.7rem; font-weight:700;">STRATEGIC FIT</p><div class="fit-score">{score}</div><p style="color:#1b5e20; font-weight:700;">TIER A</p></div>', unsafe_allow_html=True)

elif app_mode == "Weekly News Digest":
    st.subheader("📰 Strategic Signals")
    if not NEWS_API_KEY:
        st.error("Missing NEWS_API_KEY in secrets.")
    else:
        with st.spinner("Fetching latest news..."):
            url = f"https://newsapi.org/v2/everything?q={name}&apiKey={NEWS_API_KEY}&pageSize=5"
            r = requests.get(url).json()
            articles = r.get("articles", [])
            if not articles:
                st.info("No recent news found.")
            for a in articles:
                st.markdown(f"**{a['title']}**")
                st.caption(f"{a['source']['name']} · [Link]({a['url']})")
                st.write(a['description'])
                st.divider()

elif app_mode == "Account Leaderboard":
    st.subheader("🏆 Sales Pipeline Leaderboard")
    # This tab now works independently of ticker data
    edited_df = st.data_editor(st.session_state.leaderboard_rows, num_rows="dynamic", use_container_width=True, hide_index=True)
    st.session_state.leaderboard_rows = edited_df
    st.download_button("Export to CSV", edited_df.to_csv(index=False), "pipeline.csv")

elif app_mode == "ROI Calculator":
    st.subheader("💰 Edge ROI Model")
    c1, c2 = st.columns(2)
    with c1:
        devs = st.number_input("Devices", value=10000)
        mb = st.slider("MB/Day", 1, 500, 20)
    with c2:
        cost = st.number_input("Cloud Cost $/GB", value=0.12)
        gain = st.slider("Efficiency %", 10, 90, 35)
    
    savings = ((devs * mb * 365) / 1024) * cost * (gain/100)
    st.markdown(f'<div style="background:#f0f4fa; padding:2rem; border-radius:12px; border-left:5px solid #0d47a1;"><h3>Projected Annual Savings</h3><h1 style="color:#1b5e20;">${savings:,.0f}</h1></div>', unsafe_allow_html=True)

elif app_mode == "Outreach & Export":
    st.subheader("✍️ AI Outreach Generator")
    if not GEMINI_API_KEY:
        st.error("Missing GEMINI_API_KEY.")
    else:
        context = st.text_area("Specific Context (e.g. 'met them at CES')", "")
        if st.button("Generate Email Draft", type="primary"):
            model = genai.GenerativeModel('gemini-1.5-flash')
            prompt = f"Write a 150-word sales email to a {st.session_state.persona} at {name}. Mention Edge AI value. Context: {context}"
            response = model.generate_content(prompt)
            st.markdown("### Drafted Email")
            st.write(response.text)

# --- CONCIERGE (Chat) ---
if app_mode != "Account Leaderboard":
    st.divider()
    st.subheader("💬 Account Concierge")
    chat_input = st.chat_input("Ask about this account's strategy...")
    if chat_input:
        with st.chat_message("user"): st.markdown(chat_input)
        if GEMINI_API_KEY:
            model = genai.GenerativeModel('gemini-1.5-flash')
            res = model.generate_content(f"Strategist for {name}. Question: {chat_input}")
            with st.chat_message("assistant"): st.markdown(res.text)
