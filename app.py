import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

# --- PAGE CONFIGURATION ---
st.set_page_config(layout="wide", page_title="Market Tile Ranker")

st.title("📊 Dynamic Options Leaderboard")
st.caption("Calibrated for real-time sandbox visibility. Rows auto-refresh based on underlying data updates.")

# --- SIDEBAR RISK CONTROLS ---
st.sidebar.header("System Calibration")
total_capital = st.sidebar.number_input("Total Capital Available ($)", value=3500)
max_trades = st.sidebar.slider("Maximum Active Trades", 1, 5, 3)
max_budget = total_capital / max_trades

st.sidebar.write(f"**Max Budget Per Trade:** ${max_budget:,.2f}")

# WATCHLIST (Highly liquid, lower-priced stocks to ensure steady data hits)
watchlist = ["AAPL", "AMD", "PLTR", "UBER", "HOOD", "SOFI", "XOM", "F", "BAC", "MSFT", "INTC", "PFE"]

@st.cache_data(ttl=30) 
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
            
            # Target roughly 6 months out
            target_days = 180
            best_exp = min(expirations, key=lambda x: abs((pd.to_datetime(x) - today).days - target_days))
            opt_chain = stock.option_chain(best_exp)
            
            calls = opt_chain.calls
            if calls.empty: continue
            
            # Straightforward mathematical spacing for sandbox simulation
            calls['approx_prob'] = (current_price / (calls['strike'] + 0.001)) * 0.50
            calls['approx_prob'] = calls['approx_prob'].clip(0.30, 0.95)
            
            # Check price threshold limit
            affordable = calls[calls['ask'] <= (max_budget / 100)]
            if affordable.empty: continue
            
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
            
            if prob >= 0.65 and cost <= max_budget:
                data_payload["score"] = (prob * 100) + pct_change 
                passed_threshold.append(data_payload)
            else:
                data_payload["score"] = (prob * 50) + pct_change
                contenders.append(data_payload)
                
        except:
            continue
            
    passed_sorted = sorted(passed_threshold, key=lambda x: x['score'], reverse=True)
    contenders_sorted = sorted(contenders, key=lambda x: x['score'], reverse=True)
    
    return passed_sorted, contenders_sorted

with st.spinner("Scanning options chains..."):
    winners, contenders = fetch_leaderboard_data(watchlist)

# --- DISPLAY TIER 1: ACTIVE PLAYS ---
st.subheader("🔥 Top Tier: Active Plays (Fits Budget & Targets)")
if winners:
    winner_cols = st.columns(min(len(winners), 3))
    for idx, w in enumerate(winners[:max_trades]):
        with winner_cols[idx % 3]:
            with st.container(border=True):
                st.markdown(f"### {w['ticker']}")
                
                # Format positive vs negative price movement color codes natively
                move_sign = "+" if w['change'] >= 0 else ""
                if w['change'] >= 0:
                    st.write(f"Price: **${w['price']:.2f}** :green[({move_sign}{w['change']:.2f}%) ]")
                else:
                    st.write(f"Price: **${w['price']:.2f}** :red[({move_sign}{w['change']:.2f}%) ]")
                    
                st.write(f"🎯 **Est. Probability:** {w['prob']*100:.1f}%")
                st.write(f"💵 **Contract Cost:** ${w['cost']:.2f}")
                st.write(f"📍 **Strike Target:** ${w['strike']:.2f}")
                
                if st.button(f"Track {w['ticker']}", key=f"win-{w['ticker']}"):
                    st.success(f"Tracking initialized for {w['ticker']}.")
else:
    st.info("No options currently clear the criteria filters at this specific minute.")

# --- DISPLAY TIER 2: WATCHLIST CONTENDERS ---
st.write("---")
st.subheader("⏳ On Deck: Backup Contenders")
if contenders:
    contender_cols = st.columns(4)
    for idx, c in enumerate(contenders[:8]): 
        with contender_cols[idx % 4]:
            with st.container(border=True):
                st.markdown(f"#### {c['ticker']}")
                
                move_sign = "+" if c['change'] >= 0 else ""
                if c['change'] >= 0:
                    st.write(f"Price: ${c['price']:.2f} :green[({move_sign}{c['change']:.2f}%)]")
                else:
                    st.write(f"Price: ${c['price']:.2f} :red[({move_sign}{c['change']:.2f}%)]")
                    
                st.write(f"⚠️ **Est. Prob:** {c['prob']*100:.1f}%")
                st.write(f"Cost: ${c['cost']:.2f}")
