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

# --- SESSION STATE ---
if "ticker" not in st.session_state:
    st.session_state.ticker = "DE"
if "persona" not in st.session_state:
    st.session_state.persona = "VP Engineering"

# --- UI STYLING ---
st.set_page_config(page_title="Edge Impulse Sales Suite", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #ffffff; }
    .score-container { 
        text-align: center; padding: 25px; background: white; 
        border: 1px solid #e6e9ef; border-radius: 15px; 
        box-shadow: 0px 4px 10px rgba(0,0,0,0.03); 
    }
    .recommend-bubble { 
        padding: 8px 18px; border-radius: 25px; font-weight: bold; 
        display: inline-block; color: white; font-size: 0.85em; 
        text-transform: uppercase; 
    }
    .buy { background-color: #28a745; }
    .sell { background-color: #dc3545; }
    .hold { background-color: #ffc107; color: #000; }
    .roi-card { 
        padding: 25px; background-color: #f0f7ff; 
        border-radius: 12px; border-left: 5px solid #007bff; 
    }
    </style>
    """, unsafe_allow_html=True)

# --- VISUAL HELPERS ---
def get_recommendation_label(info):
    rec = info.get('recommendationKey', 'none').lower()
    if 'buy' in rec: return "BUY", "buy"
    if 'sell' in rec: return "SELL", "sell"
    return "HOLD", "hold"

def calculate_fit_score(info):
    score = 72 
    sector = info.get('sector', '')
    if sector == "Industrials": score += 15
    if sector == "Technology": score += 10
    return min(score, 98)

# --- SIDEBAR ---
with st.sidebar:
    if os.path.exists("logo.png"):
        st.image("logo.png", use_container_width=True)
    st.divider()
    app_mode = st.radio("Intelligence Suite", 
                        ["🏠 Executive Summary", "📅 Weekly News Digest", "🏆 Account Leaderboard", 
                         "💰 ROI Calculator", "✍️ Outreach & Export"])
    st.divider()
    st.session_state.ticker = st.text_input("Active Ticker:", st.session_state.ticker).upper()
    st.session_state.persona = st.selectbox("Persona:", ["VP Engineering", "CTO", "Head of Mfg"], index=0)

# --- MAIN LOGIC ---
try:
    ticker = st.session_state.ticker
    stock = yf.Ticker(ticker)
    info = stock.info
    name = info.get('shortName', ticker)

    # 1. RESTORE STOCK PRICE HEADER
    col_h1, col_h2 = st.columns([3, 1])
    with col_h1:
        st.title(f"{name} ({ticker})")
        st.write(f"**Sector:** {info.get('sector')} | **Industry:** {info.get('industry')}")
    with col_h2:
        price = info.get('currentPrice', 0.0)
        change = info.get('regularMarketChangePercent', 0.0)
        st.metric("Price", f"${price}", f"{change:.2f}%")
        label, css_class = get_recommendation_label(info)
        st.markdown(f'<div class="recommend-bubble {css_class}">Analyst: {label}</div>', unsafe_allow_html=True)
    
    st.divider()

    if app_mode == "🏠 Executive Summary":
        col_l, col_r = st.columns([2, 1])
        with col_l:
            st.subheader("Business Summary")
            st.write(info.get('longBusinessSummary', 'No data available.')[:1000] + "...")
        with col_r:
            # 2. RESTORE COLORED FIT SCORE
            score = calculate_fit_score(info)
            st.markdown(f"""
                <div class="score-container">
                    <p style="font-weight:bold; color:#6c757d; margin:0;">STRATEGIC FIT</p>
                    <h1 style="color:#007bff; font-size:70px; margin:0;">{score}</h1>
                    <p style="color:green; font-weight:bold;">HIGH PRIORITY</p>
                </div>
            """, unsafe_allow_html=True)

    elif app_mode == "💰 ROI Calculator":
        st.title("Edge Infrastructure Savings")
        devices = st.number_input("Devices", value=10000)
        mb = st.slider("MB/Day", 1, 500, 20)
        cost = (devices * mb * 30) / 1024 * 0.12 * 12 * 0.9
        st.markdown(f'<div class="roi-card"><h2>Annual Savings: ${cost:,.0f}</h2></div>', unsafe_allow_html=True)

    # ... other tabs logic ...

    # 3. RESTORE CONCIERGE CHAT
    st.divider()
    st.subheader("💬 Account Concierge")
    chat_q = st.chat_input("Ask about this account's AI strategy...")
    if chat_q:
        model = genai.GenerativeModel('gemini-1.5-flash')
        res = model.generate_content(f"Context: {name}. Question: {chat_q}")
        st.write(res.text)

except Exception as e:
    st.error(f"Waiting for valid ticker data... (Error: {e})")
