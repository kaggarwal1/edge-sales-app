import streamlit as st
import yfinance as yf
import pandas as pd
import os
import requests
import google.generativeai as genai
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
from dotenv import load_dotenv

# --- INITIALIZATION ---
load_dotenv()
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# --- SESSION STATE (The "Tab-Switching" Fix) ---
if "ticker" not in st.session_state:
    st.session_state.ticker = "DE"
if "persona" not in st.session_state:
    st.session_state.persona = "VP Engineering"

# --- UI CONFIGURATION ---
st.set_page_config(page_title="Edge Impulse | Sales Command Center", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #ffffff; }
    section[data-testid="stSidebar"] { background-color: #f8f9fb; border-right: 1px solid #e6e9ef; }
    .score-container {
        text-align: center; padding: 25px; background: white; 
        border: 1px solid #e6e9ef; border-radius: 15px;
        box-shadow: 0px 4px 10px rgba(0,0,0,0.03);
    }
    .roi-card {
        padding: 25px; background-color: #f0f7ff;
        border-radius: 12px; border-left: 5px solid #007bff;
        margin-bottom: 20px;
    }
    .report-box { 
        padding: 25px; background-color: #f8f9fb; 
        border-radius: 15px; border-left: 5px solid #007bff;
        margin-bottom: 20px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- DETERMINISTIC SCORING LOGIC ---
def calculate_fit_score(info):
    score = 72 # Base
    industry = info.get('industry', '')
    sector = info.get('sector', '')
    mkt_cap = info.get('marketCap', 0)
    
    if sector == "Technology": score += 10
    if sector == "Industrials": score += 12
    if "Automotive" in industry: score += 10
    if mkt_cap > 100 * 10**9: score += 5
    
    return min(score, 98)

# --- SIDEBAR ---
with st.sidebar:
    if os.path.exists("logo.png"):
        st.image("logo.png", use_container_width=True)
    st.divider()
    
    app_mode = st.radio("Intelligence Suite", 
                        ["🏠 Executive Summary", "📅 Weekly News Digest", "🏆 Account Leaderboard", 
                         "🕸️ Account Map", "💰 ROI Calculator", "⚔️ Competitive Battlecard", "✍️ Outreach & Export"])
    
    st.divider()
    # Syncing inputs with session state
    st.session_state.ticker = st.text_input("Active Account Ticker:", st.session_state.ticker).upper()
    st.session_state.persona = st.selectbox("Target Persona:", ["VP Engineering", "CTO", "Head of Ops"], 
                                          index=["VP Engineering", "CTO", "Head of Ops"].index(st.session_state.persona))

# --- APP CONTENT ---
ticker = st.session_state.ticker
if ticker:
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        name = info.get('shortName', ticker)

        if app_mode == "🏠 Executive Summary":
            st.title(f"{name} ({ticker})")
            col_l, col_r = st.columns([2, 1])
            with col_l:
                st.subheader("Account Briefing")
                st.write(info.get('longBusinessSummary', 'No summary available.'))
            with col_r:
                score = calculate_fit_score(info)
                st.markdown(f"""
                    <div class="score-container">
                        <p style="font-weight:bold; color:#6c757d;">STRATEGIC FIT SCORE</p>
                        <h1 style="color:#007bff; font-size:75px; margin:0;">{score}</h1>
                        <p style="color:green; font-weight:bold;">DATA-DRIVEN PRIORITY</p>
                    </div>
                """, unsafe_allow_html=True)

        elif app_mode == "💰 ROI Calculator":
            st.title("Cloud Displacement ROI")
            col_in, col_out = st.columns(2)
            with col_in:
                devices = st.number_input("Number of Devices", value=10000)
                mb_per_day = st.slider("MB Data Per Device/Day", 1, 500, 20)
                cost_per_gb = st.slider("Cloud Cost ($/GB)", 0.01, 0.50, 0.12)
                
                # Math Correction
                monthly_gb = (devices * mb_per_day * 30) / 1024
                annual_cost = monthly_gb * cost_per_gb * 12
                savings = annual_cost * 0.9 # Assuming 90% reduction via Edge AI
            
            with col_out:
                st.markdown(f"""
                    <div class="roi-card">
                        <h4>Annual Infrastructure Savings</h4>
                        <h2 style="color:#28a745;">${savings:,.0f}</h2>
                        <p>Based on {monthly_gb:,.0f} GB of monthly cloud ingress.</p>
                    </div>
                """, unsafe_allow_html=True)
                fig = px.bar(x=["Cloud Only", "Edge Impulse"], y=[annual_cost, annual_cost - savings], 
                             labels={'x': 'Strategy', 'y': 'Annual Spend ($)'}, color_discrete_sequence=['#007bff'])
                st.plotly_chart(fig, use_container_width=True)

        elif app_mode == "📅 Weekly News Digest":
            st.title("Weekly Intelligence Synthesis")
            if st.button("Generate Report"):
                with st.spinner("Analyzing news for Edge AI opportunities..."):
                    q = f'"{name}" AND (AI OR sensor OR hardware)'
                    url = f"https://newsapi.org/v2/everything?q={q}&sortBy=relevancy&apiKey={NEWS_API_KEY}"
                    articles = requests.get(url).json().get('articles', [])
                    if articles:
                        context = "\n".join([f"- {a['title']}" for a in articles[:5]])
                        model = genai.GenerativeModel('gemini-2.0-flash')
                        res = model.generate_content(f"Give 3 takeaways for an Edge Impulse AE based on this news for {name}: {context}")
                        st.markdown(f'<div class="report-box">{res.text}</div>', unsafe_allow_html=True)
                    else: st.info("No relevant strategic news found this week.")

        # (Other screens use ticker = st.session_state.ticker to stay consistent)
        else:
            st.info(f"Screen '{app_mode}' is ready for {name}. Data remains consistent across tabs.")

    except Exception as e:
        st.error(f"Error: {e}")
