import streamlit as st
import yfinance as yf
import pandas as pd
import os
import requests
import google.generativeai as genai
import plotly.graph_objects as go
from datetime import datetime, timedelta
from dotenv import load_dotenv

# --- INITIALIZATION ---
load_dotenv()

def _env(key, default=None):
    try:
        if hasattr(st, "secrets") and key in st.secrets:
            return st.secrets[key]
    except: pass
    return os.getenv(key, default)

# Set model to 2.0 to avoid the 404 "Not Found" error
MODEL_NAME = 'gemini-2.0-flash'

if "ticker" not in st.session_state: st.session_state.ticker = "DE"
if "persona" not in st.session_state: st.session_state.persona = "VP Engineering"

NEWS_API_KEY = _env("NEWS_API_KEY")
GEMINI_API_KEY = _env("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# --- UI STYLING (CLEAN WHITE VERSION) ---
st.set_page_config(page_title="Edge Impulse Sales Suite", layout="wide")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;700&display=swap');
    html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }
    
    /* SIDEBAR: White background, Black text as requested */
    [data-testid="stSidebar"] {
        background-color: #ffffff !important;
        border-right: 1px solid #e8eaef;
    }
    [data-testid="stSidebar"] * { color: #1a1d26 !important; }

    /* MAIN UI */
    .stApp { background: #ffffff; }
    .metric-shell {
        background: #ffffff; border: 1px solid #e8eaef;
        border-radius: 12px; padding: 0.5rem 1rem;
    }
    
    /* HEADER TIGHTENING */
    h1 { margin-bottom: 0px !important; padding-bottom: 0px !important; }
    .header-subtext { color: #5c6370; margin-top: -5px; font-weight: 500; margin-bottom: 10px; }
    
    /* REMOVE METRIC LABEL BOX GAPS */
    [data-testid="stMetricLabel"] { display: none; }
    </style>
    """, unsafe_allow_html=True)

# --- HELPERS ---
@st.cache_data(ttl=900)
def get_account_data(ticker):
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
    st.session_state.ticker = st.text_input("Active Ticker", st.session_state.ticker).upper().strip()
    st.session_state.persona = st.selectbox("Target Persona", ["VP Engineering", "CTO", "Head of Mfg", "Director Innovation"])

# --- DATA LOAD ---
ticker = st.session_state.ticker
info, hist = get_account_data(ticker)
name = info.get("shortName") or info.get("longName") or ticker

# --- HEADER SECTION ---
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
        st.write(info.get("longBusinessSummary", "No data available.")[:1000] + "...")
        if not hist.empty:
            fig = go.Figure(go.Scatter(x=hist.index, y=hist["Close"], fill='tozeroy', line=dict(color='#0d47a1')))
            fig.update_layout(height=250, margin=dict(l=0,r=0,t=0,b=0), xaxis_showgrid=False, plot_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig, use_container_width=True)
    with c2:
        st.markdown('<div style="text-align:center; padding:1.5rem; background:#f4f6fb; border-radius:16px;">'
                    '<p style="color:#5c6370; font-size:0.7rem; font-weight:700;">STRATEGIC FIT</p>'
                    f'<h1 style="color:#0d47a1; font-size:3rem;">88</h1>'
                    '<p style="color:#1b5e20; font-weight:700;">TIER A PRIORITY</p></div>', unsafe_allow_html=True)

elif app_mode == "Weekly News Digest":
    st.subheader("📰 Strategic Headlines (English Only)")
    if NEWS_API_KEY:
        with st.spinner("Filtering for high-quality English sources..."):
            # Restricted to major English domains to stop Russian/Spanish results
            domains = "reuters.com,bloomberg.com,techcrunch.com,wsj.com,cnbc.com"
            url = f"https://newsapi.org/v2/everything?q={name}&domains={domains}&language=en&sortBy=publishedAt&apiKey={NEWS_API_KEY}"
            r = requests.get(url).json()
            articles = r.get("articles", [])[:6]
            if articles:
                for a in articles:
                    st.markdown(f"**[{a['title']}]({a['url']})**")
                    st.caption(f"{a['source']['name']} · {a['publishedAt'][:10]}")
                    st.write(a['description'] or "No description available.")
                    st.divider()
            else: st.info("No recent strategic news found in English.")
    else: st.error("NEWS_API_KEY missing.")

elif app_mode == "Account Leaderboard":
    st.subheader("🏆 Portfolio Leaderboard")
    if "leaderboard_rows" not in st.session_state:
        st.session_state.leaderboard_rows = pd.DataFrame({"Account": ["John Deere", "Siemens", "Bosch"], "Ticker": ["DE", "SIE.DE", "BOSCHLTD.NS"], "ARR ($K)": [420, 310, 180]})
    st.data_editor(st.session_state.leaderboard_rows, num_rows="dynamic", use_container_width=True, hide_index=True)

elif app_mode == "ROI Calculator":
    st.subheader("💰 Infrastructure Efficiency")
    c1, c2 = st.columns(2)
    devs = c1.number_input("Total Devices", value=10000)
    mb = c1.slider("MB Data/Day", 1, 500, 20)
    cost = c2.number_input("Cloud Cost ($/GB)", value=0.12)
    gain = c2.slider("Edge AI Efficiency %", 10, 90, 35)
    savings = ((devs * mb * 365) / 1024) * cost * (gain/100)
    st.markdown(f'<div style="background:#f0f4fa; padding:2rem; border-radius:12px; border-left:5px solid #0d47a1;"><h3>Projected Annual Savings</h3><h1 style="color:#1b5e20;">${savings:,.0f}</h1></div>', unsafe_allow_html=True)

elif app_mode == "Outreach & Export":
    st.subheader("✍️ AI Outreach Generator")
    context = st.text_area("Add Custom Context", placeholder="Met them at the Hannover Messe...")
    if st.button("Generate Email"):
        if GEMINI_API_KEY:
            model = genai.GenerativeModel(MODEL_NAME)
            prompt = f"In English only, write a short sales email to a {st.session_state.persona} at {name} about Edge Impulse. Context: {context}"
            res = model.generate_content(prompt)
            st.markdown("---")
            st.write(res.text)

# --- CONCIERGE (Chat) ---
if app_mode != "Account Leaderboard":
    st.divider()
    st.subheader("💬 Account Concierge")
    q = st.chat_input("Ask about this strategy (English only)...")
    if q:
        with st.chat_message("user"): st.markdown(q)
        if GEMINI_API_KEY:
            model = genai.GenerativeModel(MODEL_NAME)
            res = model.generate_content(f"Respond in English only. Act as a strategist for {name}. Question: {q}")
            with st.chat_message("assistant"): st.markdown(res.text)
