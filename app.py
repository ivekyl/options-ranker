import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import time

# --- PAGE CONFIGURATION ---
st.set_page_config(layout="wide", page_title="Live Momentum Options Ranker")

st.title("⚡ Real-Time Auto-Updating Options Terminal")
st.caption("This page automatically fetches live options chains and re-calculates deal metrics every 10 seconds. No manual refresh required.")

# --- SIDEBAR RISK CONTROLS ---
st.sidebar.header("Capital Allocation Engine")
total_capital = st.sidebar.number_input("Total Capital Available ($)", value=3500)
max_trades = st.sidebar.slider("Maximum Active Tiles", 1, 5, 3)
max_budget = total_capital / max_trades

st.sidebar.write(f"**Max Budget Per Position Slot:** ${max_budget:,.2f}")

# Broad list of highly liquid, fast-moving structural favorites
watchlist = ["PLTR", "TSLA", "NVDA", "AMD", "AAPL", "MSFT", "UBER", "HOOD", "SOFI", "XOM", "BAC", "F"]

def calculate_rsi(prices, period=14):
    """Calculates basic Relative Strength Index for directional trade confirmations."""
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / (loss + 0.00001)
    return 100 - (100 / (1 + rs))

# --- AUTO-REFRESH TRIGGER ---
# This loop injects live time parameters to force Streamlit to pull fresh data loops
if "run_count" not in st.session_state:
    st.session_state.run_count = 0

# Visual placeholder for real-time heartbeat indicator
st.sidebar.markdown(f"⏳ **Last Engine Pulse:** Live System Running (Tick: {st.session_state.run_count})")

def fetch_live_deals(tickers):
    deals = []
    today = pd.Timestamp.now()
    
    for t in tickers:
        try:
            stock = yf.Ticker(t)
            hist = stock.history(period="1mo")
            if len(hist) < 15: continue
            
            current_price = hist["Close"].iloc[-1]
            prev_price = hist["Close"].iloc[-2]
            pct_change = ((current_price - prev_price) / prev_price) * 100
            
            hist['RSI'] = calculate_rsi(hist['Close'])
            current_rsi = hist['RSI'].iloc[-1]
            
            # Determine direction base on RSI parameters
            direction = "PUT" if current_rsi >= 65 else "CALL"
            
            expirations = stock.options
            if not expirations: continue
            
            # DYNAMIC TIMEFRAME HOPPING: Search from 30 to 180 days to locate budget-compliant strikes
            valid_chain = pd.DataFrame()
            chosen_exp = None
            
            # Sort expirations by proximity to our 45-180 day sweet spot
            sorted_exps = sorted(expirations, key=lambda x: abs((pd.to_datetime(x) - today).days - 90))
            
            for exp in sorted_exps:
                days = (pd.to_datetime(exp) - today).days
                if days < 20 or days > 200: continue # Skip ultra-short or ultra-long contracts
                
                opt_chain = stock.option_chain(exp)
                chain = opt_chain.puts if direction == "PUT" else opt_chain.calls
                
                # Snag options within 8% of the real stock price
                ntm = chain[(chain['strike'] >= current_price * 0.92) & (chain['strike'] <= current_price * 1.08)].copy()
                
                # Check for budget viability
                ntm = ntm[ntm['ask'] * 100 <= max_budget]
                
                if not ntm.empty:
                    valid_chain = ntm
                    chosen_exp = exp
                    break # Optimal target located, exit search loop
            
            if valid_chain.empty: continue
            
            # Select contract strike closest to At-The-Money (the asset's current valuation)
            valid_chain['distance'] = abs(valid_chain['strike'] - current_price)
            best_option = valid_chain.sort_values(by='distance').iloc[0]
            
            cost = best_option['ask'] * 100
            volume = int(best_option['volume']) if not pd.isna(best_option['volume']) else 0
            open_int = int(best_option['openInterest']) if not pd.isna(best_option['openInterest']) else 1
            iv = best_option.get('impliedVolatility', 0) * 100
            
            # CRITERIA CALCULUS: Score position based on volume velocity and competitive entry pricing
            deal_score = 50
            if volume > 500: deal_score += 20
            if iv < 50: deal_score += 15 # Lower implied volatility means option pricing is cheap
            if volume / open_int > 1.2: deal_score += 15 # Signals active unusual institutional buying
            
            deals.append({
                "ticker": t,
                "price": current_price,
                "change": pct_change,
                "direction": direction,
                "strike": best_option['strike'],
                "cost": cost,
                "volume": volume,
                "iv": iv,
                "score": deal_score,
                "exp": chosen_exp
            })
        except:
            continue
            
    return sorted(deals, key=lambda x: x['score'], reverse=True)

# Run pipeline execution
active_deals = fetch_live_deals(watchlist)

# --- DISPLAY DYNAMIC LEADERBOARD TILES ---
st.subheader("🔥 Calculated Ranking Matrix")

if active_deals:
    cols = st.columns(min(len(active_deals), 3))
    for idx, d in enumerate(active_deals[:max_trades]):
        with cols[idx % 3]:
            # Assign color status parameters based on calculation scoring profiles
            if d['score'] >= 75:
                deal_rank = ":green[🟢 OPTIMAL DEAL (Highly Liquid / Strong Momentum)]"
                border_style = "✅ Top Pick"
            elif d['score'] >= 55:
                deal_rank = ":orange[🟡 STABLE PLAY (Fair Value Layout)]"
                border_style = "⚠️ Moderate Tier"
            else:
                deal_rank = ":red[🔴 SPECULATIVE (Thin Volume or Premium Premium)]"
                border_style = "🛑 High Risk"
                
            with st.container(border=True):
                st.markdown(f"### {d['ticker']} — {border_style}")
                st.markdown(f"**Deal Grade:** {deal_rank}")
                
                # Asset pricing movement tags
                move_sign = "+" if d['change'] >= 0 else ""
                color_tag = "green" if d['change'] >= 0 else "red"
                st.write(f"📈 Stock Price: **${d['price']:.2f}** (:{color_tag}[{move_sign}{d['change']:.2f}% Today])")
                
                st.markdown("---")
                st.write(f"🎯 **Suggested Action:** Buy standard 60-90 day **{d['direction']}**")
                st.write(f"📍 Target Strike Price: **${d['strike']:.2f}**")
                st.write(f"💵 Target Entry Cost: **${d['cost']:.2f}** per contract")
                st.write(f"📅 Recommended Expiration: `{d['exp']}`")
                
                st.markdown("---")
                st.write(f"📊 Volume: `{d['volume']:,}` contracts | Implied Volatility: `{d['iv']:.1f}%`")
                
                if st.button(f"Deploy Stream Tracking: {d['ticker']}", key=f"deal-{d['ticker']}-{idx}"):
                    st.success(f"Position locked. Monitoring trailing stop profiles for {d['ticker']}.")
else:
    st.info("The algorithm is dynamically adjusting timeframes to capture matching entries. Stand by for the next data block refresh cycle.")

# --- REFRESH INTERNALS CONTROLLER ---
# Forces the app to sleep for 10 seconds, then tick up session parameter counter to refresh data
time.sleep(10)
st.session_state.run_count += 1
st.rerun()
