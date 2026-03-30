"""
Edge Impulse Sales Suite - Final Stable Build
Fixes: Auto-Detects Gemini, Sidebar Contrast, English News, and TCO ROI Model.
"""

import os
import requests
import pandas as pd
import streamlit as st
import yfinance as yf
import google.generativeai as genai
from datetime import datetime
from dotenv import load_dotenv
import plotly.graph_objects as go
import plotly.express as px

# --- CONFIG ---
load_dotenv()

def _env(key: str, default: str = None):
    try:
        if hasattr(st, "secrets") and key in st.secrets:
            return st.secrets[key]
    except: pass
    return os.getenv(key, default)

# --- SESSION STATE ---
if "ticker" not in st.session_state: st.session_state.ticker = "DE"
if "persona" not in st.session_state: st.session_state.persona = "VP Engineering"
if "leaderboard_rows" not in st.session_state:
    st.session_state.leaderboard_rows = pd.DataFrame({
        "Account": ["John Deere", "Siemens", "Bosch", "Schneider", "Honeywell"],
        "Ticker": ["DE", "SIE.DE", "BOSCHLTD.NS", "SU.PA", "HON"],
        "Stage": ["Negotiation", "Discovery", "Proposal", "Qualification", "Discovery"],
        "Est. ARR ($K)": [420, 310, 180, 95, 240]
    })

NEWS_API_KEY = _env("NEWS_API_KEY")
GEMINI_API_KEY = _env("GEMINI_API_KEY")
MODEL_NAME = "gemini-1.5-flash" # Fallback default

# --- AUTO-DETECT BULLETPROOF MODEL FIX ---
if GEMINI_API_KEY: 
    genai.configure(api_key=GEMINI_API_KEY)
    try:
        available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        gemini_models = [m for m in available_models if 'gemini' in m.lower()]
        if gemini_models:
            MODEL_NAME = gemini_models[0]
            for m in gemini_models:
                if 'flash' in m.lower():
                    MODEL_NAME = m
                    break
    except Exception as e:
        print(f"Model fetch error: {e}")

# --- UI STYLING ---
st.set_page_config(page_title="Sales Intelligence", layout="wide")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;700&display=swap');
    html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }
    
    [data-testid="stSidebar"] {
        background-color: #ffffff !important;
        border-right: 1px solid #e8eaef;
    }
    [data-testid="stSidebar"] * { color: #1a1d26 !important; }
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
    h1 { margin-bottom: 0px !important; padding-bottom: 0px !important; }
    .header-subtext { color: #5c6370; margin-top: -5px; font-weight: 500; margin-bottom: 10px; }
    [data-testid="stMetricLabel"] { display: none; }
    </style>
    """, unsafe_allow_html=True)

# --- HELPERS ---
@st.cache_data(ttl=900)
def get_data(ticker):
    try:
        t = yf.Ticker(ticker)
        return t.info, t.history(period="1y")
    except: return {}, pd.DataFrame()

# --- SIDEBAR ---
with st.sidebar:
    st.markdown("### 🏦 Sales Intelligence")
    logo_path = os.path.join(os.path.dirname(__file__), "logo.png")
    if os.path.isfile(logo_path): st.image(logo_path, use_container_width=True)
    
    st.divider()
    app_mode = st.radio("Navigation", ["Executive Summary", "Weekly News Digest", "Account Leaderboard", "ROI Calculator", "Outreach & Export"])
    st.divider()
    st.session_state.ticker = st.text_input("Ticker", st.session_state.ticker).upper().strip()
    st.session_state.persona = st.selectbox("Persona", ["VP Engineering", "CTO", "Head of Mfg", "Innovation Lead"])

# --- DATA LOAD ---
ticker = st.session_state.ticker
info, hist = get_data(ticker)
name = info.get("shortName") or info.get("longName") or ticker

# --- HEADER ---
if app_mode in ["Executive Summary", "Weekly News Digest", "Outreach & Export"]:
    col_t, col_m = st.columns([3, 1], vertical_alignment="bottom")
    with col_t:
        st.markdown(f'<h1>{name}</h1>', unsafe_allow_html=True)
        st.markdown(f'<p class="header-subtext">{ticker} &nbsp;·&nbsp; {info.get("sector", "—")} &nbsp;·&nbsp; {info.get("industry", "—")}</p>', unsafe_allow_html=True)
    with col_m:
        st.markdown('<div class="metric-shell">', unsafe_allow_html=True)
        price = info.get("currentPrice") or info.get("regularMarketPrice", 0)
        change = info.get("regularMarketChangePercent", 0)
        st.metric("", f"${price:,.2f}", f"{change:+.2f}%")
        st.markdown('</div>', unsafe_allow_html=True)
    st.divider()

# --- TABS ---
if app_mode == "Executive Summary":
    c1, c2 = st.columns([2, 1])
    with c1:
        st.subheader("Business Summary")
        st.write(info.get("longBusinessSummary", "Summary unavailable.")[:1000] + "...")
        if not hist.empty:
            fig = go.Figure(go.Scatter(x=hist.index, y=hist["Close"], fill='tozeroy', line=dict(color='#0d47a1')))
            fig.update_layout(height=280, margin=dict(l=0,r=0,t=0,b=0), xaxis_showgrid=False, plot_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig, use_container_width=True)
    with c2:
        score = 88 if info.get("sector") in ["Technology", "Industrials"] else 60
        st.markdown(f'<div class="fit-ring"><p class="header-subtext">STRATEGIC FIT</p><div class="fit-score">{score}</div><p style="color:#1b5e20; font-weight:700;">TIER A</p></div>', unsafe_allow_html=True)

elif app_mode == "Weekly News Digest":
    st.subheader("📰 Strategic Headlines (English Only)")
    if NEWS_API_KEY:
        with st.spinner("Searching English sources..."):
            domains = "reuters.com,bloomberg.com,techcrunch.com,wsj.com,cnbc.com"
            url = f"https://newsapi.org/v2/everything?q={name}&domains={domains}&language=en&sortBy=publishedAt&apiKey={NEWS_API_KEY}"
            try:
                r = requests.get(url).json()
                articles = r.get("articles", [])[:5]
                if articles:
                    for a in articles:
                        st.markdown(f"**[{a['title']}]({a['url']})**")
                        st.caption(f"{a['source']['name']} · {a['publishedAt'][:10]}")
                        st.write(a['description'] or "")
                        st.divider()
                else: st.info("No recent English news found.")
            except:
                st.error("Error connecting to News API.")
    else: st.error("NEWS_API_KEY missing.")

elif app_mode == "Account Leaderboard":
    st.subheader("🏆 Portfolio Leaderboard")
    edited = st.data_editor(st.session_state.leaderboard_rows, num_rows="dynamic", use_container_width=True, hide_index=True)
    st.session_state.leaderboard_rows = edited

elif app_mode == "ROI Calculator":
    st.subheader("💰 3-Year Total Cost of Ownership (TCO)")
    
    # Inputs
    c1, c2, c3 = st.columns(3)
    with c1:
        devs = st.number_input("Fleet Size (Devices)", min_value=1000, value=25000, step=1000)
        mb = st.slider("Data/Device/Day (MB)", 1, 500, 50)
    with c2:
        cloud_cost = st.number_input("Cloud Compute + Storage ($/GB)", value=0.15, format="%.2f")
        data_reduction = st.slider("Edge Data Reduction %", 50, 99, 95)
    with c3:
        edge_license = st.number_input("Edge Impulse SaaS Fee ($/Yr)", value=75000, step=5000)

    # Core Math
    annual_gb = (devs * mb * 365) / 1024
    annual_cloud_cost = annual_gb * cloud_cost
    annual_edge_cloud_cost = annual_cloud_cost * (1 - (data_reduction / 100))
    annual_edge_total = edge_license + annual_edge_cloud_cost

    # Plotly Forecast Data
    years = [1, 2, 3]
    cloud_cum = [annual_cloud_cost * y for y in years]
    edge_cum = [annual_edge_total * y for y in years]
    
    df_roi = pd.DataFrame({
        "Year": ["Year 1", "Year 2", "Year 3", "Year 1", "Year 2", "Year 3"],
        "Cumulative Cost ($)": cloud_cum + edge_cum,
        "Architecture": ["Big Cloud (Status Quo)"]*3 + ["Edge Impulse"]*3
    })

    fig = px.line(df_roi, x="Year", y="Cumulative Cost ($)", color="Architecture", 
                  color_discrete_map={"Big Cloud (Status Quo)": "#dc3545", "Edge Impulse": "#1b5e20"},
                  markers=True)
    fig.update_layout(height=350, margin=dict(l=0,r=0,t=30,b=0), xaxis_title="", plot_bgcolor='rgba(0,0,0,0)')
    
    # Visualization Layout
    col_chart, col_metrics = st.columns([2, 1])
    with col_chart:
        st.plotly_chart(fig, use_container_width=True)
    with col_metrics:
        savings_y3 = cloud_cum[2] - edge_cum[2]
        st.markdown(f'''
            <div style="background:#f0f4fa; padding:1.5rem; border-radius:12px; border-left:5px solid #0d47a1; margin-bottom: 1rem;">
                <p style="color:#5c6370; font-size:0.8rem; font-weight:700; margin:0;">YEAR 3 CUMULATIVE SAVINGS</p>
                <h2 style="color:#1b5e20; margin:0;">${savings_y3:,.0f}</h2>
            </div>
            <div style="padding:1rem; border:1px solid #e8eaef; border-radius:12px;">
                <p style="margin:0; font-size:0.9rem;"><b>Annual Cloud Bill:</b> ${annual_cloud_cost:,.0f}</p>
                <p style="margin:0; font-size:0.9rem;"><b>Annual Edge Bill:</b> ${annual_edge_total:,.0f}</p>
                <p style="margin:0; font-size:0.8rem; color:#5c6370;">*(Includes ${edge_license:,} SaaS fee)*</p>
            </div>
        ''', unsafe_allow_html=True)

elif app_mode == "Outreach & Export":
    st.subheader("✍️ AI Outreach")
    if GEMINI_API_KEY:
        context = st.text_area("Custom Context", placeholder="e.g. They just opened a new plant in Texas.")
        if st.button("Generate Email"):
            with st.spinner(f"Writing draft using model: {MODEL_NAME}..."):
                model = genai.GenerativeModel(MODEL_NAME)
                prompt = f"In English only, write a short, professional sales email to a {st.session_state.persona} at {name} about Edge AI. Context: {context}"
                res = model.generate_content(prompt)
                st.markdown("---")
                st.write(res.text)

# --- CONCIERGE (Chat) ---
if app_mode != "Account Leaderboard":
    st.divider()
    st.subheader("💬 Account Concierge")
    q = st.chat_input("Ask a question (English only)...")
    if q:
        with st.chat_message("user"): st.markdown(q)
        if GEMINI_API_KEY:
            model = genai.GenerativeModel(MODEL_NAME)
            res = model.generate_content(f"Respond in English only. Context: {name}. Question: {q}")
            with st.chat_message("assistant"): st.markdown(res.text)
