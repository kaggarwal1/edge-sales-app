import streamlit as st
import yfinance as yf
import pandas as pd
import os
import requests
import google.generativeai as genai
import plotly.graph_objects as go
import plotly.express as px
import base64
from datetime import datetime, timedelta
from dotenv import load_dotenv

# --- INITIALIZATION ---
load_dotenv()
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# --- SESSION STATE MANAGEMENT ---
if "ticker" not in st.session_state:
    st.session_state.ticker = "DE"
if "persona" not in st.session_state:
    st.session_state.persona = "VP Engineering"

# --- UI CONFIGURATION & BRANDING ---
st.set_page_config(page_title="Edge Impulse | Sales Command Center", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #ffffff; }
    section[data-testid="stSidebar"] { background-color: #f8f9fb; border-right: 1px solid #e6e9ef; }
    .score-container { text-align: center; padding: 25px; background: white; border: 1px solid #e6e9ef; border-radius: 15px; box-shadow: 0px 4px 10px rgba(0,0,0,0.03); }
    .recommend-bubble { padding: 8px 18px; border-radius: 25px; font-weight: bold; display: inline-block; color: white; font-size: 0.85em; text-transform: uppercase; }
    .buy { background-color: #28a745; }
    .sell { background-color: #dc3545; }
    .hold { background-color: #ffc107; color: #000; }
    .roi-card { padding: 25px; background-color: #f0f7ff; border-radius: 12px; border-left: 5px solid #007bff; margin-bottom: 20px; }
    .report-box { padding: 25px; background-color: #f8f9fb; border-radius: 15px; border-left: 5px solid #007bff; margin-bottom: 20px; }
    </style>
    """, unsafe_allow_html=True)

# --- HELPER FUNCTIONS ---
def get_recommendation_label(info):
    rec = info.get('recommendationKey', 'none').lower()
    if 'buy' in rec: return "BUY", "buy"
    if 'sell' in rec: return "SELL", "sell"
    return "HOLD", "hold"

def download_link(content, filename, text):
    b64 = base64.b64encode(content.encode()).decode()
    return f'<a href="data:file/txt;base64,{b64}" download="{filename}" style="text-decoration:none;"><button style="background-color:#007bff;color:white;border:none;padding:10px 20px;border-radius:8px;cursor:pointer;">{text}</button></a>'

def calculate_fit_score(info):
    score = 72 
    industry = info.get('industry', '')
    sector = info.get('sector', '')
    mkt_cap = info.get('marketCap', 0)
    
    if sector == "Technology": score += 10
    if sector == "Industrials": score += 12
    if "Automotive" in industry or "Manufacturing" in industry: score += 10
    if mkt_cap > 50 * 10**9: score += 5
    
    return min(score, 98)

# --- SIDEBAR NAVIGATION ---
with st.sidebar:
    if os.path.exists("logo.png"):
        st.image("logo.png", use_container_width=True)
    else:
        st.title("EDGE IMPULSE")
    
    st.divider()
    
    app_mode = st.radio("Intelligence Suite", 
                        ["🏠 Executive Summary", "📅 Weekly News Digest", "🏆 Account Leaderboard", 
                         "🕸️ Account Map", "💰 ROI Calculator", "📄 Deep Signal (10-K)",
                         "⚔️ Competitive Battlecard", "✍️ Outreach & Export"])
    
    st.divider()
    
    if app_mode == "🏆 Account Leaderboard":
        ticker_input = st.text_input("Enter Tickers (comma separated):", "F, GM, TSLA, TM").upper()
    else:
        # Syncing inputs with session state
        st.session_state.ticker = st.text_input("Active Account Ticker:", st.session_state.ticker).upper()
        st.session_state.persona = st.selectbox("Persona:", ["VP Engineering", "CTO", "Head of Manufacturing", "Director Innovation"], 
                                              index=["VP Engineering", "CTO", "Head of Manufacturing", "Director Innovation"].index(st.session_state.persona))
    sender_name = st.text_input("Your Name:", "Kush")

# --- MAIN APP LOGIC ---
try:
    if app_mode == "🏆 Account Leaderboard":
        st.title("Strategic Portfolio Prioritization")
        st.write("Comparing accounts based on market momentum and Edge AI fit.")
        
        tickers = [t.strip() for t in ticker_input.split(",")]
        comparison_data = []
        
        with st.spinner("Processing portfolio data..."):
            for t in tickers:
                try:
                    s = yf.Ticker(t)
                    inf = s.info
                    score = calculate_fit_score(inf)
                    comparison_data.append({
                        "Ticker": t, "Company": inf.get('shortName', t),
                        "Industry": inf.get('industry', 'N/A'), "Fit Score": score,
                        "Market Cap ($B)": inf.get('marketCap',0)//10**9
                    })
                except: continue
        
        if comparison_data:
            df = pd.DataFrame(comparison_data)
            fig = px.bar(df, x="Company", y="Fit Score", color="Fit Score", color_continuous_scale="Blues")
            st.plotly_chart(fig, use_container_width=True)
            st.dataframe(df.sort_values(by="Fit Score", ascending=False), use_container_width=True)

    else:
        ticker = st.session_state.ticker
        if not ticker:
            st.warning("Please enter a valid ticker symbol.")
            st.stop()
            
        stock = yf.Ticker(ticker)
        info = stock.info
        name = info.get('shortName', ticker)
        
        # SHARED HEADER
        col_h1, col_h2 = st.columns([3, 1])
        with col_h1:
            st.title(f"{name} ({ticker})")
            st.markdown(f"**Sector:** {info.get('sector')} | **Industry:** {info.get('industry')}")
        with col_h2:
            price = info.get('currentPrice', info.get('regularMarketPrice', 0.0))
            change = info.get('regularMarketChangePercent', 0)
            st.metric("Price", f"${price}", f"{change:.2f}%")
            label, css = get_recommendation_label(info)
            st.markdown(f'<div class="recommend-bubble {css}">Analyst View: {label}</div>', unsafe_allow_html=True)
        st.divider()

        if app_mode == "🏠 Executive Summary":
            col_l, col_r = st.columns([2, 1])
            with col_l:
                st.subheader("Account Briefing")
                st.write(info.get('longBusinessSummary', 'No summary available.')[:800] + "...")
            with col_r:
                score = calculate_fit_score(info)
                st.markdown(f"""
                    <div class="score-container">
                        <p style="font-weight:bold; color:#6c757d; margin:0;">OVERALL FIT SCORE</p>
                        <h1 style="color:#007bff; font-size:75px; margin:0;">{score}</h1>
                        <p style="color:green; font-weight:bold;">🔥 DATA-BACKED PRIORITY</p>
                    </div>
                """, unsafe_allow_html=True)

        elif app_mode == "📅 Weekly News Digest":
            st.subheader("7-Day Intelligence Synthesis")
            if st.button("Generate Strategic Takeaways"):
                with st.spinner("Synthesizing weekly headlines..."):
                    seven_days_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
                    q = f'"{name}" AND (AI OR technology OR hardware OR strategy)'
                    url = f"https://newsapi.org/v2/everything?q={q}&from={seven_days_ago}&sortBy=relevancy&apiKey={NEWS_API_KEY}"
                    articles = requests.get(url).json().get('articles', [])
                    
                    if articles:
                        context = "\n".join([f"- {a['title']}" for a in articles[:8]])
                        model = genai.GenerativeModel('gemini-2.5-flash')
                        res = model.generate_content(f"Act as a Sales Research Assistant. Based on this news for {name}, provide: 1. Top 3 Takeaways, 2. The Edge Impulse Angle, 3.
