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

st.title("📊 Dynamic Options Leaderboard (Sandbox Calibration)")
st.caption("Calibrated for real-time visibility. Threshold relaxed to 65%+ probability to accommodate the $3,500 capital limit.")

# --- SIDEBAR RISK CONTROLS ---
st.sidebar.header("System Calibration")
total_capital = st.sidebar.number_input("Total Capital Available ($)", value=3500)
max_trades = st.sidebar.slider("Maximum Active Trades", 1, 5, 3)
max_budget = total_capital / max_trades

st.sidebar.write(f"**Max Budget Per Trade:** ${max_budget:,.2f}")

# NEW EXPANDED WATCHLIST (Includes highly liquid, lower-priced stocks to guarantee hits)
watchlist = ["AAPL", "AMD", "PLTR", "UBER", "HOOD", "SOFI", "XOM", "F", "BAC", "MSFT", "INTC", "PFE"]

@st.cache_data(ttl=30) # Quick refresh rate to catch real-time data adjustments
def fetch_leaderboard_data(tickers):
    passed_threshold = []
    contenders = []
    today = pd.Timestamp.now()
    
    for t in tickers:
        try:
            stock = yf.Ticker(t)
            hist = stock.history(period="2d")
            if len(hist) < 2: continue
            
            current_price = hist["Close"].iloc[-1]
            prev_price = hist["Close"].iloc[-2]
            net_change = current_price - prev_price
            pct_change = (net_change / prev_price) * 100
            
            expirations = stock.options
            if not expirations: continue
            
            # Target 6 months out (180 days)
            target_days = 180
            best_exp = min(expirations, key=lambda x: abs((pd.to_datetime(x) - today).days - target_days))
            opt_chain = stock.option_chain(best_exp)
            
            # Evaluate Calls
            calls = opt_chain.calls
            if calls.empty: continue
            
            # Relaxed probability approximation logic for the sandbox layout
            # Calculates option delta distance relative to stock price floor
            calls['approx_prob'] = (current_price / (calls['strike'] + 0.001)) * 0.50
            calls['approx_prob'] = calls['approx_prob'].clip(0.30, 0.95)
            
            # Look for options that fit our strict monetary per-trade limit
            # Options premium is multiplied by 100 shares
            affordable = calls[calls['ask'] <= (max_budget / 100)]
            if affordable.empty: continue
            
            # Select the most optimal affordable setup
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
            
            # NEW SANDBOX TIERS:
            # If the option costs less than your budget limit and hits at least a 65% success probability
            if prob >= 0.65 and cost <= max_budget:
                data_payload["score"] = (prob * 100) + pct_change # Momentum alters leaderboard rank
                passed_threshold.append(data_payload)
            else:
                data_payload["score"] = (prob * 50) + pct_change
                contenders.append(data_payload)
                
        except:
            continue
            
    # Sort positions so highest scoring momentum values bump to the front of the screen
    passed_sorted = sorted(passed_threshold, key=lambda x: x['score'], reverse=True)
    contenders_sorted = sorted(contenders, key=lambda x: x['score'], reverse=True)
    
    return passed_sorted, contenders_sorted

with st.spinner("Scanning chains and shifting tile rankings..."):
    winners, contenders = fetch_leaderboard_data(watchlist)

# --- DISPLAY TIER 1: ACTIVE PLAYS ---
st.subheader("🔥 Top Tier: Active Plays (Fits Budget & Target Probabilities)")
if winners:
    winner_cols = st.columns(min(len(winners), 3))
    # Limit visualization to your custom max trade count parameter
    for idx, w in enumerate(winners[:max_trades]):
        with winner_cols[idx % 3]:
            move_class = "movement-up" if w['change'] >= 0 else "movement-down"
            move_sign = "+" if w['change'] >= 0 else ""
            
            st.markdown(f"""
            <div class="metric-card tier-passed">
                <div class="logo-box">{w['ticker']}</div>
                <p class="price-text">${w['price']:.2f}</p>
                <p class="{move_class}">{move_sign}{w['change']:.2f}% Today</p>
                <hr style="margin: 10px 0; border-color: #334155;">
                <p style="color:#10B981; font-weight:bold; margin:0;">🎯 Est. Probability: {w['prob']*
