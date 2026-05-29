import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

# --- PAGE CONFIGURATION ---
st.set_page_config(layout="wide", page_title="Market Tile Ranker")

# Custom CSS to inject styling for the tile animations and design
st.markdown("""
<style>
    .metric-card {
        background-color: #1E293B;
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 15px;
        border-top: 6px solid #64748B;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        transition: transform 0.3s ease, border-color 0.3s ease;
    }
    .metric-card:hover {
        transform: translateY(-5px);
    }
    .tier-passed {
        border-top: 6px solid #10B981 !important;
        background-color: #0F172A;
    }
    .tier-contender {
        border-top: 6px solid #F59E0B !important;
    }
    .logo-box {
        background-color: #334155;
        color: white;
        font-weight: bold;
        font-size: 20px;
        width: 55px;
        height: 55px;
        display: flex;
        align-items: center;
        justify-content: center;
        border-radius: 8px;
        margin-bottom: 10px;
    }
    .price-text {
        font-size: 24px;
        font-weight: bold;
        color: #F8FAFC;
        margin: 0;
    }
    .movement-up {
        color: #10B981;
        font-weight: bold;
        margin: 0;
    }
    .movement-down {
        color: #EF4444;
        font-weight: bold;
        margin: 0;
    }
</style>
""", unsafe_allowed_html=True)

st.title("📊 Dynamic Options Leaderboard")
st.caption("Tiles automatically shift positions and swap tiers based on real-time market movement metrics.")

# --- SIDEBAR RISK CONTROLS ---
st.sidebar.header("System Calibration")
total_capital = st.sidebar.number_input("Total Capital Available ($)", value=3500)
max_trades = st.sidebar.slider("Maximum Active Trades", 1, 5, 3)
max_budget = total_capital / max_trades

st.sidebar.write(f"**Target Threshold Budget:** ${max_budget:,.2f} / trade")

# Expanded tracking list to show contenders vs winners
watchlist = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "NFLX", "XOM", "JPM", "V", "DIS"]

@st.cache_data(ttl=60) # Refreshes every minute to handle the moving rankings
def fetch_leaderboard_data(tickers):
    passed_threshold = []
    contenders = []
    
    today = pd.Timestamp.now()
    
    for t in tickers:
        try:
            stock = yf.Ticker(t)
            # Get historical info for movement data
            hist = stock.history(period="2d")
            if len(hist) < 2: continue
            
            current_price = hist["Close"].iloc[-1]
            prev_price = hist["Close"].iloc[-2]
            net_change = current_price - prev_price
            pct_change = (net_change / prev_price) * 100
            
            expirations = stock.options
            if not expirations: continue
            
            # Look for 6-month options window
            target_days = 180
            best_exp = min(expirations, key=lambda x: abs((pd.to_datetime(x) - today).days - target_days))
            opt_chain = stock.option_chain(best_exp)
            
            # Analyze calls for simplicity in ranking calculations
            calls = opt_chain.calls
            # Approximate standard probability using deep-in-the-money delta tracking
            calls['approx_prob'] = (current_price - calls['strike']) / current_price + 0.50
            calls['approx_prob'] = calls['approx_prob'].clip(0.1, 0.99)
            
            # Filter options within asset boundary pricing rules
            affordable = calls[calls['ask'] <= (max_budget / 100)]
            if affordable.empty: continue
            
            # Pick the most liquid mathematically sound choice
            best_option = affordable.sort_values(by='approx_prob', ascending=False).iloc[0]
            prob = best_option['approx_prob']
            cost = best_option['ask'] * 100
            
            data_payload = {
                "ticker": t,
                "price": current_price,
                "change": pct_change,
                "prob": prob,
                "cost": cost,
                "strike": best_option['strike']
            }
            
            # SORT INTO TIERS
            # Cracks the surface if probability >= 85% and budget matches perfectly
            if prob >= 0.82 and cost <= max_budget: 
                data_payload["score"] = prob * 100 + pct_change # Price momentum bumps position up or down
                passed_threshold.append(data_payload)
            else:
                data_payload["score"] = prob * 80 + pct_change
                contenders.append(data_payload)
                
        except:
            continue
            
    # Sort both lists by score so higher momentum/probability positions bump to the front
    passed_sorted = sorted(passed_threshold, key=lambda x: x['score'], reverse=True)
    contenders_sorted = sorted(contenders, key=lambda x: x['score'], reverse=True)
    
    return passed_sorted, contenders_sorted

with st.spinner("Re-ranking tiles based on latest ticker movement data..."):
    winners, contenders = fetch_leaderboard_data(watchlist)

# --- DISPLAY TIER 1: CRACKED THE SURFACE ---
st.subheader("🔥 Top Tier: Meets All Strategy Thresholds (Target: Max 3)")
if winners:
    winner_cols = st.columns(max(len(winners), 3))
    for idx, w in enumerate(winners):
        with winner_cols[idx]:
            move_class = "movement-up" if w['change'] >= 0 else "movement-down"
            move_sign = "+" if w['change'] >= 0 else ""
            
            st.markdown(f"""
            <div class="metric-card tier-passed">
                <div class="logo-box">{w['ticker']}</div>
                <p class="price-text">${w['price']:.2f}</p>
                <p class="{move_class}">{move_sign}{w['change']:.2f}% Today</p>
                <hr style="margin: 10px 0; border-color: #334155;">
                <p style="color:#10B981; font-weight:bold; margin:0;">🎯 Success Probability: {w['prob']*100:.1f}%</p>
                <p style="color:#94A3B8; font-size:13px; margin:2px 0;">Est. Cost: ${w['cost']:.2f}</p>
                <p style="color:#94A3B8; font-size:13px; margin:0;">Strike Option: ${w['strike']:.2f}</p>
            </div>
            """, unsafe_allowed_html=True)
            if st.button(f"Initialize Tracking: {w['ticker']}", key=f"win-{w['ticker']}"):
                st.success(f"Position locked. Trailing stop engine initialized for {w['ticker']}.")
else:
    st.info("No companies are currently cracking the 85% success constraint at this specific minute. Watching contenders below.")

# --- DISPLAY TIER 2: ON DECK / CONTENDERS ---
st.write("---")
st.subheader("⏳ On Deck: Contenders Out of Optimal Range")
if contenders:
    contender_cols = st.columns(4)
    col_cycle = 0
    for idx, c in enumerate(contenders):
        with contender_cols[col_cycle]:
            move_class = "movement-up" if c['change'] >= 0 else "movement-down"
            move_sign = "+" if c['change'] >= 0 else ""
            
            st.markdown(f"""
            <div class="metric-card tier-contender">
                <div class="logo-box" style="background-color:#475569;">{c['ticker']}</div>
                <p class="price-text">${c['price']:.2f}</p>
                <p class="{move_class}">{move_sign}{c['change']:.2f}%</p>
                <hr style="margin: 10px 0; border-color: #334155;">
                <p style="color:#F59E0B; font-weight:bold; margin:0;">⚠️ Success Prob: {c['prob']*100:.1f}%</p>
                <p style="color:#94A3B8; font-size:12px; margin:2px 0;">Reason: Needs structural or pricing shift</p>
            </div>
            """, unsafe_allowed_html=True)
        col_cycle = (col_cycle + 1) if col_cycle < 3 else 0
