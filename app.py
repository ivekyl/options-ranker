import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import requests
import base64
import json
import os
import time

# --- HIGH DENSITY ARCADE GRID CONFIG ---
st.set_page_config(layout="wide", page_title="BORED MATRIX ARCADE")

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
        json.dump({"positions": positions}, f)

if "portfolio" not in st.session_state:
    st.session_state.portfolio = load_saved_portfolio()
if "schwab_connected" not in st.session_state:
    st.session_state.schwab_connected = False
if "last_processed_code" not in st.session_state:
    st.session_state.last_processed_code = ""

# High-liquidity volume watchlist
watchlist = ["PLTR", "TSLA", "NVDA", "AMD", "AAPL", "AMZN", "HOOD", "SOFI", "MARA", "DKNG"]

@st.cache_data(ttl=15)
def fetch_live_market_matrix(tickers):
    sweep_pool = []
    for t in tickers:
        try:
            stock = yf.Ticker(t)
            hist = stock.history(period="2d")
            if hist.empty: continue
            
            current_price = hist["Close"].iloc[-1]
            prev_close = hist["Close"].iloc[-2]
            pct_change = ((current_price - prev_close) / prev_close) * 100
            
            expirations = stock.options
            if not expirations: continue
            
            today = pd.Timestamp.now()
            best_exp = min(expirations, key=lambda x: abs((pd.to_datetime(x) - today).days - 45))
            direction = "CALL" if pct_change < 0 else "PUT"
            
            opt_chain = stock.option_chain(best_exp)
            chain = opt_chain.puts if direction == "PUT" else opt_chain.calls
            
            chain['distance'] = abs(chain['strike'] - current_price)
            valid_contracts = chain[(chain['ask'] * 100 <= 1166.0)]
            if valid_contracts.empty: valid_contracts = chain
                
            best_option = valid_contracts.sort_values(by='distance').iloc[0]
            cost = best_option['ask'] * 100
            vol = int(best_option['volume']) if not pd.isna(best_option['volume']) else 0
            
            score = 50
            if vol > 300: score += 20
            if abs(pct_change) > 3.5: score += 20
            score = max(10, min(100, score))
            
            sweep_pool.append({
                "ticker": t, "price": current_price, "change": pct_change,
                "direction": direction, "strike": best_option['strike'],
                "cost": cost, "volume": vol, "score": score, "exp": best_exp
            })
        except:
            continue
    return sweep_pool

live_data = fetch_live_market_matrix(watchlist)

# ================= 1. BORED.COM STYLE TRIVIA & MOVERS RIBBON =================
# Uses standard notification styles to build high-contrast accent blocks
if live_data:
    sorted_movers = sorted(live_data, key=lambda x: x['change'], reverse=True)
    gainer = sorted_movers[0]
    loser = sorted_movers[-1]
    
    st.warning(
        f"⭐ **BORED MINI ARCADE TRIVIA:** THE FIRST REGISTERED STOCK OPTION CONTRACT WAS TRADED ON OLIVE PRESSES IN ANCIENT GREECE!  ||  "
        f"🚀 HIGH VELOCITY: {gainer['ticker']} (+{gainer['change']:.1f}%)  ||  "
        f"💥 SHARP DROP: {loser['ticker']} ({loser['change']:.1f}%)"
    )

# Tab Bar Layout
tab_matrix, tab_saved, tab_schwab_link = st.tabs(["🕹️ BORED OPTION GRID", "💾 PORTFOLIO INVENTORY", "🔑 ACCESS KEY LOG"])

# ================= 2. LIVE DENSE DIRECTORY GRID (TAB 1) =================
with tab_matrix:
    if live_data:
        sorted_matrix = sorted(live_data, key=lambda x: x['score'], reverse=True)
        grid_cols = st.columns(5)
        
        for idx, item in enumerate(sorted_matrix):
            with grid_cols[idx % 5]:
                # Dynamic grading markers based on algorithm scores
                if item['score'] >= 75:
                    tag = "🏆 [PRIME CHOICE]"
                elif item['score'] >= 55:
                    tag = "✅ [STABLE MOVE]"
                else:
                    tag = "👀 [SPECULATIVE]"
                
                with st.container(border=True):
                    st.write(f"### {item['ticker']}")
                    st.caption(tag)
                    
                    sign = "+" if item['change'] >= 0 else ""
                    color = "green" if item['change'] >= 0 else "red"
                    st.write(f"Stock: **${item['price']:.2f}** (:{color}[{sign}{item['change']:.2f}%])")
                    
                    st.write(f"🎮 **{item['direction']} AT ${item['strike']:.2f}**")
                    st.write(f"Premium: **${item['cost']:.2f}**")
                    st.caption(f"Contract Volume: {item['volume']:,}")
                    
                    if st.button("LOCK IN GAME", key=f"lock-{item['ticker']}-{idx}", use_container_width=True):
                        st.session_state.portfolio.append({
                            "ticker": item['ticker'], "direction": item['direction'], "strike": item['strike'],
                            "entry_stock": item['price'], "entry_premium": item['cost'], "qty": 1, "exp": item['exp']
                        })
                        save_portfolio_to_disk(st.session_state.portfolio)
                        st.toast(f"Position compiled into file disk logic!", icon="💾")
                        st.rerun()
    else:
        st.info("LOADING MATRIX GRID NODES...")

# ================= 3. SAVED INVENTORY MANAGEMENT (TAB 2) =================
with tab_saved:
    if st.session_state.portfolio:
        if st.button("WIPE LOCAL INVENTORY STORAGE FILE"):
            st.session_state.portfolio = []
            save_portfolio_to_disk([])
            st.rerun()
        st.write("---")
        for p_idx, pos in enumerate(st.session_state.portfolio):
            try:
                current_stock_valuation = yf.Ticker(pos['ticker']).history(period="1d")["Close"].iloc[-1]
            except:
                current_stock_valuation = pos['entry_stock']
                
            stock_move_spread = current_stock_valuation - pos['entry_stock']
            factor = 0.50 if pos['direction'] == "CALL" else -0.50
            calc_premium = max(5.00, pos['entry_premium'] + (stock_move_spread * factor * 100))
            net_pnl = (calc_premium - pos['entry_premium']) * pos['qty']
            pnl_color = "green" if net_pnl >= 0 else "red"
            
            with st.container(border=True):
                c1, c2, c3 = st.columns([2, 2, 1])
                with c1:
                    st.markdown(f"#### 🎰 {pos['ticker']} Long {pos['direction']}")
                    st.caption(f"Strike Match: ${pos['strike']:.2f} | Basis: ${pos['entry_premium']:.2f}")
                with c2:
                    st.write(f"Asset Net Worth: **${calc_premium * pos['qty']:,.2f}**")
                    st.markdown(f"Realized Performance P&L: :{pnl_color}[${net_pnl:+,.2f}]")
                with c3:
                    st.write("") 
                    if st.button("RELEASE BLOCK", key=f"rel-{pos['ticker']}-{p_idx}", use_container_width=True):
                        st.session_state.portfolio.pop(p_idx)
                        save_portfolio_to_disk(st.session_state.portfolio)
                        st.rerun()
    else:
        st.info("NO CURRENT TRADING BLOCKS STORED IN FILE DIRECTORY.")

# ================= 4. SCHWAB INTEGRATION CHANNEL (TAB 3) =================
with tab_schwab_link:
    st.markdown("### 🔑 SCHWAB ACCESS CHANNEL CONFIGURATION")
    app_key = st.secrets["schwab"]["app_key"].strip()
    app_secret = st.secrets["schwab"]["app_secret"].strip()
    
    if st.session_state.schwab_connected:
        st.success("🛰️ CORE PIPELINE LOGGED AS ACTIVE ON LOCAL DATA CHANNEL")
        if st.button("Disconnect Live Integration"):
            st.session_state.schwab_connected = False
            st.session_state.last_processed_code = ""
            st.rerun()
    else:
        auth_url = f"https://api.schwabapi.com/v1/oauth/authorize?client_id={app_key}&redirect_uri=https://127.0.0.1"
        st.markdown(f"👉 **[CLICK HERE TO LOG INTO SCHWAB DEVELOPER ROUTE]({auth_url})**")
        
        returned_url = st.text_input("Paste Redirect Link Here to Synchronize Data Streams:", key="auth_url_input")
        if returned_url and returned_url != st.session_state.last_processed_code:
            try:
                if "code=" in returned_url:
                    clean_code = returned_url.split("code=")[1].split("&")[0]
                else:
                    clean_code = returned_url.strip()
                clean_code = clean_code.replace("%40", "@")
                st.session_state.last_processed_code = returned_url
                
                raw_cred_string = f"{app_key}:{app_secret}"
                base64_encoded_creds = base64.b64encode(raw_cred_string.encode("utf-8")).decode("utf-8")
                
                token_url = "https://api.schwabapi.com/v1/oauth/token"
                headers = {"Authorization": f"Basic {base64_encoded_creds}", "Content-Type": "application/x-www-form-urlencoded"}
                payload = {"grant_type": "authorization_code", "code": clean_code, "redirect_uri": "https://127.0.0.1", "client_id": app_key}
                
                response = requests.post(token_url, headers=headers, data=payload, timeout=7)
                if response.status_code == 200:
                    st.session_state.schwab_connected = True
                    st.toast("Handshake approved. System online.", icon="⚙️")
                    st.rerun()
                else:
                    st.error("Authentication expired. Request a new login code string.")
            except Exception as e:
                st.error(f"Execution error: {e}")

# --- BACKGROUND AUTOMATIC HEARTBEAT REFRESHEER ---
time.sleep(10)
st.rerun()
