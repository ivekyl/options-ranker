import streamlit as st
import pandas as pd
import numpy as np
import requests
import json
import os
import time

# --- HIGH DENSITY ARCADE GRID CONFIG ---
st.set_page_config(layout="wide", page_title="MATRIX GRID")

PORTFOLIO_FILE = "portfolio_storage.json"

def load_saved_portfolio():
    if os.path.exists(PORTFOLIO_FILE):
        try:
            with open(PORTFOLIO_FILE, "r") as f:
                data = json.load(f)
                return data.get("positions", [])
        except:
            pass
    return []

def save_portfolio_to_disk(positions):
    with open(PORTFOLIO_FILE, "w") as f:
        json.dump({"cash": st.session_state.get("cash", 10000.0), "positions": positions}, f)

if "portfolio" not in st.session_state:
    st.session_state.portfolio = load_saved_portfolio()

# --- HIGH-VELOCITY REACTION WATCHLIST ---
watchlist = [
    "NVDA", "TSLA", "PLTR", "AAPL", "AMD", "MSFT", "AMZN", "META", 
    "HOOD", "SOFI", "F", "BAC", "UBER", "MARA", "RIOT", "NIO", "DKNG", "BABA"
]

@st.cache_data(ttl=10)
def generate_arcade_matrix(tickers):
    sweep_pool = []
    for t in tickers:
        try:
            # Multi-tiered pricing arrays to feed mock variations
            base_prices = {"PLTR": 156.20, "TSLA": 436.14, "NVDA": 216.79, "HOOD": 92.92, "SOFI": 18.34, "F": 17.60, "MARA": 22.40, "RIOT": 11.15}
            current_price = base_prices.get(t, 45.00 + np.random.uniform(-4, 4))
            
            # Massive market moves multiplier (+/- 12% max swings)
            pct_change = np.random.uniform(-12, 12) 
            
            put_vol = np.random.randint(500, 15000)
            call_vol = np.random.randint(500, 15000)
            pcr = put_vol / (call_vol + 1)
            
            # Reversal calculation: Extreme positive moves find Puts; extreme drops find Calls
            direction = "CALL" if pct_change < -4 else "PUT" if pct_change > 4 else "CALL"
            strike = round(current_price)
            cost = max(10.00, current_price * 0.06 * 100)
            
            # Score Matrix (0 - 100 Range)
            score = 50
            if abs(pct_change) > 6.0: score += 25  # Oversold / Overbought spike match
            if pcr < 0.55 or pcr > 1.45: score += 20 # Institutional imbalance
            score += np.random.randint(-5, 5) # Chaos fluctuation factor
            score = max(0, min(100, score))
            
            sweep_pool.append({
                "ticker": t, "price": current_price, "change": pct_change,
                "direction": direction, "strike": strike, "cost": cost,
                "pcr": pcr, "score": score, "exp": "2026-09-18"
            })
        except:
            continue
    return sweep_pool

raw_data = generate_arcade_matrix(watchlist)

# ================= 1. THE TOP MOVERS TICKER RIBBON =================
if raw_data:
    sorted_movers = sorted(raw_data, key=lambda x: x['change'], reverse=True)
    top_gainer = sorted_movers[0]
    top_loser = sorted_movers[-1]
    
    ticker_string = (
        f"🔥 **LIVE TICKER** // "
        f"🚀 TOP GAINER: **{top_gainer['ticker']}** :green[{top_gainer['change']:+.2f}%] (${top_gainer['price']:.2f})  |  "
        f"💥 TOP LOSER: **{top_loser['ticker']}** :red[{top_loser['change']:.2f}%] (${top_loser['price']:.2f})  |  "
        f"⚡ REFRESH ACTIVE: 10s INTERVALS"
    )
    st.markdown(ticker_string)
    st.write("---")

# Navigation Tabs
tab_grid, tab_vault = st.tabs(["🎮 SCAN MATRIX", "💿 SAVED POSITIONS"])

# ================= 2. THE HIGH-DENSITY GRID (TAB 1) =================
with tab_grid:
    if raw_data:
        # Sort cards dynamically by score so the top deals shift positions to the front
        sorted_matrix = sorted(raw_data, key=lambda x: x['score'], reverse=True)
        
        # 5-Column layout creates a dense arcade grid style
        grid_cols = st.columns(5)
        
        for idx, item in enumerate(sorted_matrix[:15]): # Renders top 15 blocks
            with grid_cols[idx % 5]:
                # Assign tier shades based on mathematical quality evaluations
                if item['score'] >= 75:
                    grade_label = "💎 :green[ULTRA DEAL]"
                elif item['score'] >= 55:
                    grade_label = "✳️ :green[GOOD PLAY]"
                elif item['score'] >= 40:
                    grade_label = "⚠️ :orange[STABLE]"
                else:
                    grade_label = "🛑 :red[RISK / RAW]"
                
                # Render dense block element
                with st.container(border=True):
                    st.markdown(f"### {item['ticker']}")
                    st.write(grade_label)
                    
                    sign = "+" if item['change'] >= 0 else ""
                    color = "green" if item['change'] >= 0 else "red"
                    st.write(f"Stock: **${item['price']:.2f}** (:{color}[{sign}{item['change']:.2f}%])")
                    
                    st.write(f"👉 **{item['direction']} ${item['strike']}**")
                    st.write(f"Cost: **${item['cost']:.1f}** | PCR: `{item['pcr']:.2f}`")
                    
                    # High-density interactive parameters
                    contract_qty = st.number_input("Contracts", min_value=1, max_value=10, value=1, key=f"qty-{item['ticker']}-{idx}", label_visibility="collapsed")
                    
                    if st.button("LOCK PLAY", key=f"btn-{item['ticker']}-{idx}", use_container_width=True):
                        st.session_state.portfolio.append({
                            "ticker": item['ticker'], "direction": item['direction'],
                            "strike": item['strike'], "entry_stock": item['price'],
                            "entry_premium": item['cost'], "qty": contract_qty, "exp": item['exp']
                        })
                        save_portfolio_to_disk(st.session_state.portfolio)
                        st.toast(f"Saved {item['ticker']} to disk inventory!", icon="💿")
                        st.rerun()
    else:
        st.info("LOADING DATA STREAM NODE...")

# ================= 3. SAVED POSITIONS DECK (TAB 2) =================
with tab_vault:
    if st.session_state.portfolio:
        if st.button("WIPE MEMORY FILE (RESET)"):
            st.session_state.portfolio = []
            save_portfolio_to_disk([])
            st.rerun()
            
        st.write("---")
        
        # Display saved holdings cleanly in a high-density vertical deck
        for p_idx, pos in enumerate(st.session_state.portfolio):
            try:
                # Mock live asset price checks for the tracker panel
                current_stock_val = pos['entry_stock'] + np.random.uniform(-1.5, 1.5)
            except:
                current_stock_val = pos['entry_stock']
                
            delta_move = current_stock_val - pos['entry_stock']
            factor = 0.50 if pos['direction'] == "CALL" else -0.50
            
            calc_premium = max(5.00, pos['entry_premium'] + (delta_move * factor * 100))
            current_total = calc_premium * pos['qty']
            initial_total = pos['entry_premium'] * pos['qty']
            
            net_gain = current_total - initial_total
            gain_pct = (net_gain / initial_total) * 100
            pnl_color = "green" if net_gain >= 0 else "red"
            
            with st.container(border=True):
                col1, col2, col3 = st.columns([2, 2, 1])
                with col1:
                    st.markdown(f"#### 📦 {pos['ticker']} (x{pos['qty']})")
                    st.caption(f"{pos['direction']} strike ${pos['strike']} • Entry: ${pos['entry_premium']:.1f}")
                with col2:
                    st.write(f"Position Value: **${current_total:,.2f}**")
                    st.markdown(f"P&L: :{pnl_color}[${net_gain:+,.2f} ({gain_pct:+.1f}%)]")
                with col3:
                    st.write("") # Formatting offset spacer
                    if st.button("RELEASE", key=f"rel-{pos['ticker']}-{p_idx}", use_container_width=True):
                        st.session_state.portfolio.pop(p_idx)
                        save_portfolio_to_disk(st.session_state.portfolio)
                        st.toast(f"Released position block for {pos['ticker']}.", icon="🗑️")
                        st.rerun()
    else:
        st.info("DISK STORAGE REPORT: NO OPEN INVENTORY DETECTED.")

# --- BACKGROUND AUTOMATIC HEARTBEAT LOOP ---
time.sleep(10)
st.rerun()
