"""
Sales Intelligence Suite — Streamlit dashboard for account research,
pipeline context, and AI-assisted outreach (Gemini).
"""

from __future__ import annotations

import os
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

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# Professional palette: restrained, high-contrast, suitable for client-facing demos
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,400;0,9..40,500;0,9..40,600;0,9..40,700;1,9..40,400&display=swap');
    html, body, [class*="css"] { font-family: 'DM Sans', system-ui, sans-serif; }
    .stApp {
        background: linear-gradient(180deg, #f8f9fc 0%, #ffffff 32%);
        color: #1a1d26;
    }
    .block-container { padding-top: 1.5rem; max-width: 1280px; }
    h1 { font-weight: 700; letter-spacing: -0.02em; color: #0f1419; }
    h2, h3 { font-weight: 600; color: #1a1d26; }
    [data-testid="stSidebar"] {
        background: #0f1419;
        border-right: 1px solid #e8eaef;
    }
    [data-testid="stSidebar"] .stMarkdown, [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] span { color: #e8eaef !important; }
    [data-testid="stSidebar"] .stRadio label { font-weight: 500; }
    .metric-shell {
        background: #ffffff;
        border: 1px solid #e8eaef;
        border-radius: 12px;
        padding: 1rem 1.25rem;
        box-shadow: 0 1px 2px rgba(15, 20, 25, 0.04);
    }
    .fit-ring {
        text-align: center;
        padding: 1.5rem;
        background: linear-gradient(145deg, #ffffff 0%, #f4f6fb 100%);
        border: 1px solid #e8eaef;
        border-radius: 16px;
    }
    .fit-score {
        font-size: 3.25rem;
        font-weight: 700;
        line-height: 1;
        margin: 0.25rem 0;
        background: linear-gradient(135deg, #0d47a1 0%, #1565c0 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
    }
    .tier-pill {
        display: inline-block;
        padding: 0.35rem 0.85rem;
        border-radius: 999px;
        font-size: 0.75rem;
        font-weight: 600;
        letter-spacing: 0.04em;
        text-transform: uppercase;
    }
    .tier-a { background: #e8f5e9; color: #1b5e20; }
    .tier-b { background: #fff8e1; color: #f57f17; }
    .tier-c { background: #fce4ec; color: #880e4f; }
    .analyst-pill {
        display: inline-block;
        padding: 0.35rem 0.75rem;
        border-radius: 8px;
        font-size: 0.8rem;
        font-weight: 600;
    }
    .pill-buy { background: #1b5e20; color: #fff; }
    .pill-sell { background: #b71c1c; color: #fff; }
    .pill-hold { background: #e65100; color: #fff; }
    .roi-panel {
        padding: 1.5rem;
        background: #f0f4fa;
        border-radius: 12px;
        border-left: 4px solid #1565c0;
    }
    .section-label {
        font-size: 0.7rem;
        font-weight: 600;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        color: #5c6370;
        margin-bottom: 0.35rem;
    }
    div[data-testid="stExpander"] details {
        border: 1px solid #e8eaef;
        border-radius: 8px;
    }
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
    return "HOLD", "pill-hold"


def _safe_float(val: Any, default: float = 0.0) -> float:
    try:
        if val is None:
            return default
        return float(val)
    except (TypeError, ValueError):
        return default


def calculate_fit_score(info: dict[str, Any]) -> tuple[int, str, str]:
    """
    Heuristic account-strategic fit for edge/ML infrastructure selling.
    Returns (score 0-99, tier label, tier css class).
    """
    score = 52
    sector = (info.get("sector") or "").strip()
    industry = (info.get("industry") or "").lower()

    if sector in ("Technology", "Industrials"):
        score += 14
    if sector == "Consumer Cyclical":
        score += 6
    if any(
        k in industry
        for k in ("semiconductor", "machinery", "electrical", "auto", "aerospace")
    ):
        score += 10

    mc = _safe_float(info.get("marketCap"), 0)
    if mc > 50e9:
        score += 8
    elif mc > 10e9:
        score += 5

    beta = _safe_float(info.get("beta"), 1.0)
    if 0.7 <= beta <= 1.3:
        score += 4

    employees = int(_safe_float(info.get("fullTimeEmployees"), 0))
    if employees > 50000:
        score += 6
    elif employees > 5000:
        score += 3

    score = max(18, min(score, 97))

    if score >= 78:
        return score, "Tier A — prioritize", "tier-a"
    if score >= 58:
        return score, "Tier B — nurture", "tier-b"
    return score, "Tier C — qualify", "tier-c"


def fetch_price_history(ticker: str, period: str = "1y") -> pd.DataFrame:
    t = yf.Ticker(ticker)
    hist = t.history(period=period, auto_adjust=True)
    if hist.empty:
        return pd.DataFrame()
    return hist


def build_price_chart(df: pd.DataFrame, name: str) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=df.index,
            y=df["Close"],
            mode="lines",
            line=dict(color="#1565c0", width=2),
            fill="tozeroy",
            fillcolor="rgba(21, 101, 192, 0.08)",
            name="Close",
        )
    )
    fig.update_layout(
        title=dict(text=f"{name} — share price", font=dict(size=14)),
        margin=dict(l=0, r=0, t=40, b=0),
        height=320,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(showgrid=False, zeroline=False),
        yaxis=dict(showgrid=True, gridcolor="#eef0f4"),
        showlegend=False,
        hovermode="x unified",
    )
    return fig


def fetch_company_news(company_query: str, ticker: str) -> pd.DataFrame:
    if not NEWS_API_KEY:
        return pd.DataFrame()
    q = f'"{company_query}" OR {ticker}'
    url = "https://newsapi.org/v2/everything"
    params = {
        "q": q,
        "sortBy": "publishedAt",
        "language": "en",
        "pageSize": 20,
        "apiKey": NEWS_API_KEY,
    }
    try:
        r = requests.get(url, params=params, timeout=12)
        r.raise_for_status()
        data = r.json()
        articles = data.get("articles") or []
        rows = []
        for a in articles:
            rows.append(
                {
                    "Published": a.get("publishedAt", "")[:16].replace("T", " "),
                    "Title": a.get("title") or "",
                    "Source": (a.get("source") or {}).get("name") or "",
                    "URL": a.get("url") or "",
                }
            )
        return pd.DataFrame(rows)
    except Exception:
        return pd.DataFrame()


def concierge_system_prompt(name: str, ticker: str, persona: str, sector: str) -> str:
    return f"""You are a senior enterprise sales strategist helping a rep selling edge AI /
ML infrastructure and developer tooling. Be concise, confident, and actionable.
Account: {name} ({ticker}). Sector: {sector}. Target persona: {persona}.
Prefer bullets. Suggest next steps, risks, and proof points. Do not invent private facts;
if unknown, say what to verify on a call."""


def run_gemini_chat(user_text: str, context: str) -> str:
    if not GEMINI_API_KEY:
        return "Set GEMINI_API_KEY in `.env` or Streamlit secrets to enable AI answers."
    model = genai.GenerativeModel(
        GEMINI_MODEL,
        system_instruction=context,
    )
    res = model.generate_content(user_text)
    return (res.text or "").strip() or "(No response text.)"


def format_usd_compact(n: float) -> str:
    if n >= 1e12:
        return f"${n/1e12:.2f}T"
    if n >= 1e9:
        return f"${n/1e9:.2f}B"
    if n >= 1e6:
        return f"${n/1e6:.2f}M"
    return f"${n:,.0f}"


# --- SIDEBAR ---
with st.sidebar:
    st.markdown("### Sales Intelligence")
    st.caption("Account research · Pipeline · ROI · Outreach")
    logo_path = os.path.join(os.path.dirname(__file__), "logo.png")
    if os.path.isfile(logo_path):
        st.image(logo_path, use_container_width=True)
    st.divider()
    app_mode = st.radio(
        "Workspace",
        [
            "Executive Summary",
            "Weekly News Digest",
            "Account Leaderboard",
            "ROI Calculator",
            "Outreach & Export",
        ],
        label_visibility="collapsed",
    )
    st.divider()
    st.session_state.ticker = st.text_input("Ticker", st.session_state.ticker).upper().strip()
    st.session_state.persona = st.selectbox(
        "Buyer persona",
        ["VP Engineering", "CTO", "Head of Manufacturing", "Director of Innovation"],
        index=0,
    )
    st.caption("News uses NewsAPI when `NEWS_API_KEY` is set.")

# --- MAIN ---
try:
    ticker = st.session_state.ticker or DEFAULT_TICKER
    stock = yf.Ticker(ticker)
    info = stock.info or {}
    if not info or info.get("regularMarketPrice") is None and info.get("currentPrice") is None:
        # yfinance sometimes returns sparse dict; still try name
        pass
    name = info.get("shortName") or info.get("longName") or ticker
    sector = info.get("sector") or "—"
    industry = info.get("industry") or "—"

    price = _safe_float(
        info.get("currentPrice") or info.get("regularMarketPrice"),
        0.0,
    )
    change_pct = _safe_float(info.get("regularMarketChangePercent"), 0.0)

    col_title, col_metric = st.columns([3, 1])
    with col_title:
        st.title(f"{name}")
        st.markdown(
            f'<p class="section-label">Public equity</p>'
            f'<p style="margin-top:0;"><strong>{ticker}</strong> &nbsp;·&nbsp; '
            f"{sector} &nbsp;·&nbsp; {industry}</p>",
            unsafe_allow_html=True,
        )
    with col_metric:
        st.markdown('<div class="metric-shell">', unsafe_allow_html=True)
        st.metric("Last price", f"${price:,.2f}" if price else "—", f"{change_pct:+.2f}%")
        label, pill_cls = get_recommendation_label(info)
        st.markdown(
            f'<span class="analyst-pill {pill_cls}">Consensus: {label}</span>',
            unsafe_allow_html=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)

    st.divider()

    if app_mode == "Executive Summary":
        score, tier_label, tier_cls = calculate_fit_score(info)
        c1, c2, c3 = st.columns([1.6, 1, 1])

        with c1:
            st.subheader("Narrative")
            summary = info.get("longBusinessSummary") or "No business summary available."
            st.write(summary[:1200] + ("…" if len(summary) > 1200 else ""))
            with st.expander("Full company description"):
                st.write(summary)

            hist = fetch_price_history(ticker)
            if not hist.empty:
                st.plotly_chart(
                    build_price_chart(hist, name),
                    use_container_width=True,
                )
            else:
                st.info("Price history unavailable for this symbol.")

        with c2:
            st.markdown('<p class="section-label">Strategic fit</p>', unsafe_allow_html=True)
            st.markdown(
                f'<div class="fit-ring">'
                f'<div class="section-label" style="margin-bottom:0.5rem;">Account score</div>'
                f'<div class="fit-score">{score}</div>'
                f'<div class="tier-pill {tier_cls}">{tier_label}</div>'
                f"<p style='font-size:0.85rem;color:#5c6370;margin-top:1rem;'>"
                f"Heuristic from sector, scale, and volatility — tune for your ICP.</p>"
                f"</div>",
                unsafe_allow_html=True,
            )

        with c3:
            st.markdown('<p class="section-label">Snapshot</p>', unsafe_allow_html=True)
            mc = _safe_float(info.get("marketCap"), 0)
            emp = int(_safe_float(info.get("fullTimeEmployees"), 0))
            web = (info.get("website") or "").strip() or "—"
            emp_html = (
                f"<p><strong>Employees</strong><br>{emp:,}</p>"
                if emp
                else "<p><strong>Employees</strong><br>—</p>"
            )
            if web == "—":
                web_html = "<p><strong>Website</strong><br>—</p>"
            else:
                href = web if web.startswith("http") else f"https://{web}"
                web_html = (
                    f"<p><strong>Website</strong><br>"
                    f"<a href=\"{href}\" target=\"_blank\" rel=\"noopener noreferrer\">{web}</a></p>"
                )
            st.markdown(
                f'<div class="metric-shell">'
                f"<p><strong>Market cap</strong><br>{format_usd_compact(mc) if mc else '—'}</p>"
                f"{emp_html}{web_html}"
                f"</div>",
                unsafe_allow_html=True,
            )

    elif app_mode == "Weekly News Digest":
        st.subheader("Signal from the wire")
        st.caption("Recent articles mentioning the company or ticker (NewsAPI).")
        if not NEWS_API_KEY:
            st.warning(
                "Add `NEWS_API_KEY` to `.env` or secrets to load live headlines. "
                "See https://newsapi.org/register"
            )
        df_news = fetch_company_news(name, ticker)
        if df_news.empty and NEWS_API_KEY:
            st.info("No articles returned — try a different ticker or check API quota.")
        elif not df_news.empty:
            st.dataframe(
                df_news,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "URL": st.column_config.LinkColumn("Article"),
                    "Title": st.column_config.TextColumn("Headline", width="large"),
                },
            )

    elif app_mode == "Account Leaderboard":
        st.subheader("Pipeline leaderboard")
        st.caption("Demo data — replace with CRM export or connect your data source.")
        edited = st.data_editor(
            st.session_state.leaderboard_rows,
            num_rows="dynamic",
            use_container_width=True,
            hide_index=True,
            column_config={
                "Est. ARR ($K)": st.column_config.NumberColumn(format="%d"),
            },
        )
        st.session_state.leaderboard_rows = edited
        csv_bytes = edited.to_csv(index=False).encode("utf-8")
        st.download_button(
            "Download CSV",
            data=csv_bytes,
            file_name=f"leaderboard_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
        )

    elif app_mode == "ROI Calculator":
        st.subheader("Infrastructure efficiency model")
        st.caption(
            "Illustrative annual savings from optimizing edge data pipelines — adjust assumptions."
        )
        c_left, c_right = st.columns([1, 1])
        with c_left:
            devices = st.number_input("Connected devices", min_value=1, value=10_000, step=500)
            mb_per_day = st.slider("Avg. MB / device / day", 1, 500, 20)
            cost_per_gb = st.number_input("Cloud egress $ / GB (blended)", value=0.12, format="%.4f")
            months = st.slider("Months in model", 6, 36, 12)
        with c_right:
            reduction = st.slider("Efficiency gain vs. baseline (%)", 5, 60, 35)
            st.markdown(
                '<p class="section-label">Formula (illustrative)</p>'
                "<p style='font-size:0.9rem;color:#5c6370;'>"
                "Monthly GB ≈ devices × MB/day × 30 / 1024. Savings scale with "
                "egress cost, volume, and realized efficiency.</p>",
                unsafe_allow_html=True,
            )

        monthly_gb = (devices * mb_per_day * 30) / 1024
        baseline_spend = monthly_gb * cost_per_gb * months
        savings = baseline_spend * (reduction / 100.0)

        st.markdown(
            f'<div class="roi-panel">'
            f"<h3 style='margin:0 0 0.5rem 0;'>Modeled savings</h3>"
            f"<p style='font-size:1.75rem;font-weight:700;margin:0;color:#0d47a1;'>${savings:,.0f}</p>"
            f"<p style='margin:0.25rem 0 0 0;color:#5c6370;'>Over {months} months "
            f"at {reduction}% efficiency vs. baseline cloud egress (~${baseline_spend:,.0f} total spend).</p>"
            f"</div>",
            unsafe_allow_html=True,
        )

    elif app_mode == "Outreach & Export":
        st.subheader("Outreach brief")
        goal = st.selectbox(
            "Objective",
            [
                "Executive intro email (150 words)",
                "Follow-up after demo",
                "Multi-threading to CFO",
                "Meeting agenda bullets",
            ],
        )
        extra = st.text_area("Extra context (optional)", placeholder="Pain points, competitor mentions…")
        if st.button("Generate draft", type="primary"):
            if not GEMINI_API_KEY:
                st.error("Configure GEMINI_API_KEY to generate copy.")
            else:
                prompt = f"""{goal} for account {name} ({ticker}), sector {sector}.
Target persona: {st.session_state.persona}.
Extra notes: {extra or 'None'}.
Output: ready-to-send email or bullets only, no preamble."""
                ctx = concierge_system_prompt(
                    name, ticker, st.session_state.persona, sector
                )
                draft = run_gemini_chat(prompt, ctx)
                st.session_state["last_outreach_draft"] = draft
        if st.session_state.get("last_outreach_draft"):
            st.text_area("Draft", st.session_state["last_outreach_draft"], height=240)
            st.download_button(
                "Download .txt",
                st.session_state["last_outreach_draft"].encode("utf-8"),
                file_name=f"outreach_{ticker}_{datetime.now().strftime('%Y%m%d')}.txt",
            )

    # --- CONCIERGE (all modes) ---
    st.divider()
    st.subheader("Account concierge")
    st.caption("Ask positioning questions; answers use Gemini with account context.")

    chat_ctx = concierge_system_prompt(
        name, ticker, st.session_state.persona, sector
    )

    for msg in st.session_state.chat_messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    prompt = st.chat_input("Ask about this account…")
    if prompt:
        st.session_state.chat_messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        with st.chat_message("assistant"):
            if not GEMINI_API_KEY:
                reply = "Set `GEMINI_API_KEY` in your environment or Streamlit secrets."
            else:
                history_text = "\n".join(
                    f'{m["role"]}: {m["content"]}'
                    for m in st.session_state.chat_messages[-8:]
                )
                reply = run_gemini_chat(
                    f"Conversation:\n{history_text}\n\nLatest user message: {prompt}",
                    chat_ctx,
                )
            st.markdown(reply)
        st.session_state.chat_messages.append({"role": "assistant", "content": reply})
        st.rerun()

except Exception as e:
    st.error(f"Could not load market data for `{st.session_state.get('ticker', DEFAULT_TICKER)}`.")
    st.caption(str(e))
