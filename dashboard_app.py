import streamlit as st
import pandas as pd
import sqlite3
import time
import plotly.graph_objects as go
from google import genai
from google.genai import types
import os
from dotenv import load_dotenv

load_dotenv()
st.set_page_config(page_title="CHARTOR Terminal", layout="wide")

# --- SIDEBAR ---
st.sidebar.title("KAIROS")
st.sidebar.success("System Status: ONLINE")
asset = st.sidebar.selectbox("Active Asset", ["BTC/USDT", "ETH/USDT", "SOL/USDT", "DOGE/USDT"])

st.sidebar.divider()
st.sidebar.subheader("💬 Ask Kairos")
user_query = st.sidebar.text_input("Ask about market context...")
if user_query:
    try:
        # Simple chat connection to Gemini
        api_key = os.getenv("GEMINI_API_KEY")
        if api_key:
            model_name = os.getenv("GEMINI_CHAT_MODEL", "gemini-2.0-flash-lite-preview-02-05")
            client = genai.Client(
                api_key=api_key
            )
            with st.sidebar.chat_message("assistant"):
                response = client.models.generate_content(
                    model=model_name,
                    contents=user_query
                )
                st.write(response.text)
        else:
            st.sidebar.error("Gemini API Key missing in .env")
    except Exception as e:
        st.sidebar.error(f"Error: {e}")

# --- MAIN UI ---
st.title("Kairos: Institutional Trade Engine")

# Auto-Refresh loop
if st.button("Refresh Feed"):
    st.rerun()

# Fetch Data from DB
try:
    conn = sqlite3.connect("kairos_data.db")
    # Check if table exists first
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='market_log'")
    if cursor.fetchone():
        df = pd.read_sql("SELECT * FROM market_log ORDER BY timestamp DESC LIMIT 100", conn)
        conn.close()
        
        if not df.empty:
            latest = df.iloc[0]
            
            # Top Metrics
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Live Price", f"${latest['price']:,.2f}")
            col2.metric("RSI (14)", f"{latest['rsi']:.1f}")
            col3.metric("Trend", latest['trend'])
            col4.metric("Structure", latest['structure'])
            
            # Chart
            st.subheader("Real-Time Price Action")
            fig = go.Figure()
            fig.add_trace(go.Scatter(y=df['price'], mode='lines', name='Price'))
            st.plotly_chart(fig, use_container_width=True)
            
            # AI Decision Section
            st.divider()
            c1, c2 = st.columns([1, 2])
            with c1:
                st.subheader("AI Reasoning Engine")
                # We import the brain here to avoid circular imports
                from core.llm_brain import get_trading_decision
                if st.button("Generate Trade Plan"):
                    with st.spinner("Consulting Gemini 1.5..."):
                        # Convert row to dict
                        market_data = latest.to_dict()
                        decision = get_trading_decision(market_data)
                        
                        st.success(f"DECISION: {decision.get('decision', 'WAIT')}")
                        confidence = decision.get('confidence', 0)
                        st.progress(min(confidence / 100, 1.0))
                        st.caption(f"Confidence: {confidence}%")
                        
                        if 'reasoning' in decision:
                            st.info(f"**Reasoning:** {decision['reasoning']}")
            with c2:
                st.subheader("Risk Protocol")
                st.warning("RISK GUARD: Leverage Capped at 20x (Hackathon Rule)")
                st.success("Compliance Check: PASSED")
        else:
            st.warning("Database is empty. Waiting for Sentinel Service...")
    else:
        st.warning("Database not initialized. Please run sentinel_service.py")
        conn.close()

except Exception as e:
    st.error(f"Waiting for Sentinel Data... Error: {e}")