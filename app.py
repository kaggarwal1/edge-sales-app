"""
Edge Impulse Sales Suite - Final Master Build
Includes: Clean Sidebar Header, TCO ROI Calculator, URL-Encoded English News, Floating Concierge.
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
if "last_chat" not in st.session_state: st.session_state.last_chat = ""

NEWS_API_KEY = _env("NEWS_API_KEY")
GEMINI_API_KEY = _env("GEMINI_API_KEY")
MODEL_NAME = "gemini-1.5-flash" # Updated fallback to modern standard

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
    
    /* SIDEBAR STYLING - Adjusted padding to move header up */
    [data-testid="stSidebar"] {
        background-color: #ffffff !important;
        border-right: 1px solid #e8eaef;
    }
    [data-testid="stSidebar"] * { color: #1a1d26 !important; }
    [data-testid="stSidebarUserContent"] {
        padding-top: 2rem !important; 
    }
    
    .stApp { background: #ffffff; }
    
    .fit-ring {
        text-align: center; padding: 1.5rem; background: #f4f6fb;
        border-radius: 16px 16px 0px 0px; border: 1px solid #e8eaef; border-bottom: none;
    }
    .fit-score { font-size: 3rem; font-weight: 700; color: #0d47a1; }
    h1 { margin-bottom: 0px !important; padding-bottom: 0px !important; }
    .header-subtext { color: #5c6370; margin-top: -5px; font-weight: 500; margin-bottom: 10px; }
    
    /* FLOATING CONCIERGE CSS */
    div[data-testid="stPopover"] {
        position: fixed;
        bottom: 2rem;
        right: 2rem;
        z-index: 9999;
    }
    div[data-testid="stPopover"] > button {
        background-color: #0d47a1;
        color: white;
        border-radius: 30px;
        padding: 0.75rem 1.5rem;
        border: none;
        box-shadow: 0px 6px 16px rgba(0,0,0,0.2);
        font-weight: bold;
        transition: all 0.2s ease-in-out;
    }
    div[data-testid="stPopover"] > button:hover {
        background-color: #002171;
        transform: translateY(-2px);
    }
    </style>
    """, unsafe_allow_html=True)

# --- HELPERS ---
@st.cache_data(ttl=900)
def get_data(ticker):
    try:
        t = yf.Ticker(ticker)
        return t.info, t.history(period="1y")
    except: return {}, pd.DataFrame()

def get_fit_breakdown(info):
    score = 60
    breakdown = [{"Criteria": "Base Qualification", "Points": "+60"}]
    
    sector = info.get("sector", "")
    if sector in ["Technology", "Industrials"]:
        score += 15
        breakdown.append({"Criteria": f"High-Value Sector ({sector})", "Points": "+15"})
    elif sector != "":
        score += 5
        breakdown.append({"Criteria": f"Sector ({sector})", "Points": "+5"})
        
    mc = info.get("marketCap", 0)
    if mc > 100e9:
        score += 13
        breakdown.append({"Criteria": "Enterprise Scale (>100B)", "Points": "+13"})
    elif mc > 10e9:
        score += 8
        breakdown.append({"Criteria": "Large Cap Scale (>10B)", "Points": "+8"})
        
    return min(score, 98), pd.DataFrame(breakdown)

# --- SIDEBAR ---
with st.sidebar:
    # CLEANER, HIGHER HEADER
    st.markdown("<h2 style='margin-top:-10px; font-weight:700; font-size:1.4rem; letter-spacing:-0.5px;'><span style='color:#0d47a1;'>◆</span> Sales Intelligence</h2>", unsafe_allow_html=True)
    
    logo_path = os.path.join(os.path.dirname(__file__), "logo.png")
    if os.path.isfile(logo_path): st.image(logo_path, use_container_width=True)
    
    st.divider()
    app_mode = st.radio("Navigation", ["Executive Summary", "Strategic Playbook", "Weekly News Digest", "ROI Calculator", "Outreach & Export"])
    st.divider()
    st.session_state.ticker = st.text_input("Ticker", st.session_state.ticker).upper().strip()
    st.session_state.persona = st.selectbox("Persona", ["VP Engineering", "CTO", "Head of Mfg", "Innovation Lead"])

# --- DATA LOAD ---
ticker = st.session_state.ticker
info, hist = get_data(ticker)
name = info.get("shortName") or info.get("longName") or ticker

mc = info.get("marketCap", 0)
mc_str = f"${mc/1e9:.2f}B" if mc > 0 else "N/A"

# --- HEADER ---
col_t, col_m = st.columns([3, 1], vertical_alignment="bottom")
with col_t:
    st.markdown(f'<h1>{name}</h1>', unsafe_allow_html=True)
    st.markdown(f'<p class="header-subtext">{ticker} &nbsp;·&nbsp; {info.get("sector", "—")} &nbsp;·&nbsp; Market Cap: {mc_str}</p>', unsafe_allow_html=True)
with col_m:
    price = info.get("currentPrice") or info.get("regularMarketPrice", 0)
    change = info.get("regularMarketChangePercent", 0)
    color = "#1b5e20" if change >= 0 else "#dc3545"
    st.markdown(f'<div style="text-align:right;"><h2 style="margin:0;">${price:,.2f}</h2><p style="color:{color}; margin:0; font-weight:700;">{change:+.2f}%</p></div>', unsafe_allow_html=True)
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
        score, df_breakdown = get_fit_breakdown(info)
        tier = "TIER A" if score >= 80 else "TIER B"
        color = "#1b5e20" if score >= 80 else "#e65100"
        
        st.markdown(f'<div class="fit-ring"><p class="header-subtext">STRATEGIC FIT</p><div class="fit-score">{score}</div><p style="color:{color}; font-weight:700;">{tier}</p></div>', unsafe_allow_html=True)
        st.dataframe(df_breakdown, hide_index=True, use_container_width=True)

elif app_mode == "Strategic Playbook":
    st.subheader("🎯 Account-Specific Edge AI Use Cases")
    st.write(f"Generate targeted use-cases based on {name}'s public business profile.")
    
    if st.button("Generate Strategic Use Cases", type="primary"):
        if GEMINI_API_KEY:
            with st.spinner("Analyzing business model..."):
                model = genai.GenerativeModel(MODEL_NAME)
                prompt = f"Act as a pre-sales engineer. Based on {name}'s business model in the {info.get('sector', 'corporate')} sector, suggest 3 highly specific Edge AI use cases. Format as bullet points with bold titles. Keep it strictly focused on hardware, sensors, computer vision, or predictive maintenance. English only."
                res = model.generate_content(prompt)
                st.markdown(f"<div style='background:#f4f6fb; padding:1.5rem; border-radius:12px; margin-top:1rem;'>{res.text}</div>", unsafe_allow_html=True)
        else:
            st.error("API Key missing.")
            
    st.divider()
    
    st.subheader("⚔️ Competitive Intelligence Matrix")
    c1, c2 = st.columns([1, 1])
    
    with c1:
        st.markdown("**Market Landscape**")
        df_comp = pd.DataFrame({
            "Competitor": ["Edge Impulse", "AWS SageMaker Edge", "STMicroelectronics", "DIY (TensorFlow Lite)"],
            "Hardware Agnosticism": [95, 30, 10, 90],
            "Developer Velocity": [90, 50, 70, 15],
            "Color": ["#0d47a1", "#f57c00", "#1976d2", "#616161"]
        })
        fig = px.scatter(df_comp, x="Hardware Agnosticism", y="Developer Velocity", text="Competitor", size=[20,15,15,15], color="Color", color_discrete_map="identity")
        fig.update_traces(textposition='top center', textfont=dict(size=12, color='#1a1d26'))
        fig.add_hline(y=50, line_dash="dot", line_color="#bdbdbd")
        fig.add_vline(x=50, line_dash="dot", line_color="#bdbdbd")
        fig.update_layout(height=350, margin=dict(l=0,r=0,t=20,b=0), xaxis_range=[0,105], yaxis_range=[0,110], plot_bgcolor='rgba(0,0,0,0)', showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    with c2:
        st.markdown("**Battlecard Selector**")
        comp = st.selectbox("Select Competitor to view Takedown:", ["AWS SageMaker Edge", "STMicroelectronics / Hardware Lock-in", "DIY / Open Source (TF Lite)"])
        
        if "AWS" in comp:
            pitch = "End-to-end ML in the cloud, seamless integration with existing AWS billing and S3 lakes."
            landmines = "• How much will egress fees cost to stream raw sensor data to AWS for training?\n• What happens when your remote device loses internet connectivity?"
            knockout = "Edge Impulse runs completely offline on any silicon. Zero cloud-lock in, zero hidden data egress fees, and inference takes microseconds without a network round-trip."
        elif "STMicro" in comp:
            pitch = "Highly optimized anomaly detection that runs perfectly on STM32 chips."
            landmines = "• What happens if supply chain issues force you to switch to NXP or TI chips next year?\n• Can it handle complex computer vision, or just basic vibration data?"
            knockout = "Edge Impulse is 100% hardware agnostic. Write the model once and deploy it to ST, NXP, Arduino, or custom Linux gateways. Don't let software dictate your supply chain."
        else:
            pitch = "It's open-source and free. We have smart engineers who can build the pipeline from scratch."
            landmines = "• How many months of engineering time will be spent building MLOps infrastructure instead of the core product?\n• How will you handle data versioning and drift monitoring across 10,000 devices?"
            knockout = "DIY isn't free—it costs millions in engineering hours and delays time-to-market by 12+ months. Edge Impulse provides enterprise infrastructure out-of-the-box so engineers focus on the application, not the plumbing."
            
        st.markdown(f"<div class='battlecard-box'><b>Their Pitch:</b><br>{pitch}</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='battlecard-box landmine-box' style='margin-top:10px;'><b>💣 Landmine Questions to Ask:</b><br>{landmines}</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='battlecard-box knockout-box' style='margin-top:10px;'><b>🥊 The Knockout Punch:</b><br>{knockout}</div>", unsafe_allow_html=True)

elif app_mode == "Weekly News Digest":
    st.subheader("📰 Strategic Headlines (English Only)")
    if NEWS_API_KEY:
        with st.spinner("Searching top English sources..."):
            url = "https://newsapi.org/v2/everything"
            params = {
                "q": f'"{name}" OR {ticker}',
                "domains": "reuters.com,bloomberg.com,wsj.com,cnbc.com,finance.yahoo.com,forbes.com",
                "language": "en",
                "sortBy": "relevancy",
                "apiKey": NEWS_API_KEY
            }
            try:
                r = requests.get(url, params=params).json()
                articles = r.get("articles", [])
                valid_articles = [a for a in articles if a.get("title") and "[Removed]" not in a["title"]][:6]
                if valid_articles:
                    for a in valid_articles:
                        st.markdown(f"**[{a['title']}]({a['url']})**")
                        st.caption(f"{a['source']['name']} · {a['publishedAt'][:10]}")
                        st.write(a.get('description') or "")
                        st.divider()
                else: 
                    st.info("No recent strategic English news found. (Try adjusting the ticker).")
            except Exception as e:
                st.error(f"Error connecting to News API: {e}")
    else: 
        st.error("NEWS_API_KEY missing.")

elif app_mode == "ROI Calculator":
    st.subheader("💰 3-Year Total Cost of Ownership (TCO)")
    c1, c2, c3 = st.columns(3)
    with c1:
        devs = st.number_input("Fleet Size (Devices)", min_value=1000, value=25000, step=1000)
        mb = st.slider("Data/Device/Day (MB)", 1, 500, 50)
    with c2:
        cloud_cost = st.number_input("Cloud Compute + Storage ($/GB)", value=0.15, format="%.2f")
        data_reduction = st.slider("Edge Data Reduction %", 50, 99, 95)
    with c3:
        edge_license = st.number_input("Edge Impulse SaaS Fee ($/Yr)", value=75000, step=5000)

    annual_gb = (devs * mb * 365) / 1024
    annual_cloud_cost = annual_gb * cloud_cost
    annual_edge_cloud_cost = annual_cloud_cost * (1 - (data_reduction / 100))
    annual_edge_total = edge_license + annual_edge_cloud_cost

    years = [1, 2, 3]
    cloud_cum = [annual_cloud_cost * y for y in years]
    edge_cum = [annual_edge_total * y for y in years]
    
    df_roi = pd.DataFrame({
        "Year": ["Year 1", "Year 2", "Year 3", "Year 1", "Year 2", "Year 3"],
        "Cumulative Cost ($)": cloud_cum + edge_cum,
        "Architecture": ["Big Cloud (Status Quo)"]*3 + ["Edge Impulse"]*3
    })

    fig = px.line(df_roi, x="Year", y="Cumulative Cost ($)", color="Architecture", color_discrete_map={"Big Cloud (Status Quo)": "#dc3545", "Edge Impulse": "#1b5e20"}, markers=True)
    fig.update_layout(height=350, margin=dict(l=0,r=0,t=30,b=0), xaxis_title="", plot_bgcolor='rgba(0,0,0,0)')
    
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

# --- FLOATING CONCIERGE BUBBLE ---
with st.popover("💬 Account Concierge"):
    st.markdown(f"**Ask AI about {name}**")
    q = st.text_input("Message...", key="concierge_q")
    if st.button("Send", use_container_width=True):
        if GEMINI_API_KEY and q:
            with st.spinner("Analyzing..."):
                model = genai.GenerativeModel(MODEL_NAME)
                res = model.generate_content(f"Respond in English only. Act as an enterprise AE strategist for {name}. Question: {q}")
                st.session_state.last_chat = res.text
        else:
            st.error("Please enter a question or check your API key.")
            
    if st.session_state.last_chat:
        st.markdown("---")
        st.markdown(st.session_state.last_chat)
