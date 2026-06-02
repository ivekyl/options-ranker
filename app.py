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

# --- watchlists (STRICT SEPARATION) ---
megacaps = ["NVDA", "TSLA", "AAPL", "AMZN", "MSFT", "META", "AMD"]
lowcaps = ["PLTR", "HOOD", "SOFI", "MARA", "RIOT", "DKNG", "AMC", "GME", "CLSK"]
full_watchlist = megacaps + lowcaps

# ================= HOURLY EXTREMES TICKER ENGINE =================
@st.cache_data(ttl=3600)
def fetch_hourly_extremes(tickers):
    extremes = []
    for t in tickers:
        try:
            stock = yf.Ticker(t)
            hist = stock.history(period="2d")
            if hist.empty or len(hist) < 2: continue
            current_price = hist["Close"].iloc[-1]
            prev_close = hist["Close"].iloc[-2]
            pct_change = ((current_price - prev_close) / prev_close) * 100
            extremes.append({"ticker": t, "change": pct_change, "price": current_price})
        except:
            continue
    if extremes:
        sorted_ext = sorted(extremes, key=lambda x: x['change'])
        return sorted_ext[-1], sorted_ext[0]
    return None, None

top_gainer, top_loser = fetch_hourly_extremes(full_watchlist)

# ================= CLEAN EXTREMES RIBBON =================
if top_gainer and top_loser:
    st.warning(
        f"🚨 MARKET EXTREMES // "
        f"🚀 GAIN: {top_gainer['ticker']} ({top_gainer['change']:+.2f}%) at ${top_gainer['price']:.2f} | "
        f"💥 DROP: {top_loser['ticker']} ({top_loser['change']:.2f}%) at ${top_loser['price']:.2f}"
    )

# Navigation Menu Tabs
tab_matrix, tab_saved, tab_calculus, tab_schwab = st.tabs([
    "🕹️ OPTION GRID", "💾 PORTFOLIO", "🎯 SCORING CALCULUS", "🔑 SCHWAB AUTH"
])

# ================= TAB: SCORING CALCULUS CONFIG =================
with tab_calculus:
    st.markdown("##### 🛠️ SCANNING PARAMETERS PRIORITY LOGIC")
    special_sauce = st.toggle("ENGAGE DEFAULTS", value=True)
    
    if special_sauce:
        w_momentum = 35
        w_pcr = 25
        w_vol = 25
        w_iv = 15
        st.caption("Priority order: 1. Price Velocity | 2. Put/Call Skew | 3. Contract Vol | 4. Implied Volatility")
    else:
        w_momentum = st.slider("1. Price Momentum Weight", 0, 50, 25)
        w_pcr = st.slider("2. Put/Call Ratio Weight", 0, 50, 25)
        w_vol = st.slider("3. Options Volume Weight", 0, 50, 25)
        w_iv = st.slider("4. Implied Volatility Weight", 0, 50, 25)

# ================= OPTIONS DATA HARVESTER CORE =================
@st.cache_data(ttl=15)
def fetch_live_market_matrix(tickers, w_mom, w_p, w_v, w_i):
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
            iv = best_option['impliedVolatility'] * 100
            pcr_mock = np.random.uniform(0.35, 1.65)
            
            score = 10
            if abs(pct_change) > 3.0: score += w_mom
            if pcr_mock < 0.60 or pcr_mock > 1.35: score += w_p
            if vol > 400: score += w_v
            if iv < 60: score += w_i
            score = max(5, min(100, int(score)))
            
            sweep_pool.append({
                "ticker": t, "price": current_price, "change": pct_change,
                "direction": direction, "strike": best_option['strike'],
                "cost": cost, "volume": vol, "iv": iv, "pcr": pcr_mock, "score": score, "exp": best_exp
            })
        except:
            continue
    return sweep_pool

mega_data = fetch_live_market_matrix(megacaps, w_momentum, w_pcr, w_vol, w_iv)
low_data = fetch_live_market_matrix(lowcaps, w_momentum, w_pcr, w_vol, w_iv)

# ================= TAB: ARCADE GRID INTERFACE =================
with tab_matrix:
    # ---------------- TOP ROW: MEGA CAPS ----------------
    st.markdown("##### 🏛️ MEGA-CAP RISK POOLS")
    if mega_data:
        mega_sorted = sorted(mega_data, key=lambda x: x['score'], reverse=True)
        cols = st.columns(6) # 6 Columns makes font sizes smaller automatically
        for idx, item in enumerate(mega_sorted[:6]):
            with cols[idx]:
                with st.container(border=True):
                    st.markdown(f"##### **{item['ticker']}** ({item['score']}/100)")
                    sign = "+" if item['change'] >= 0 else ""
                    color = "green" if item['change'] >= 0 else "red"
                    
                    st.write(f"Stock: ${item['price']:.2f} (:{color}[{sign}{item['change']:.1f}%])")
                    st.write(f"Play: **{item['direction']} ${item['strike']:.1f}**")
                    st.write(f"Entry: **${item['cost']:.1f}**")
                    st.caption(f"V: {item['volume']:,} | IV: {item['iv']:.0f}%")
                    
                    if st.button("LOCK", key=f"l-mega-{item['ticker']}-{idx}", use_container_width=True):
                        st.session_state.portfolio.append({
                            "ticker": item['ticker'], "direction": item['direction'], "strike": item['strike'],
                            "entry_stock": item['price'], "entry_premium": item['cost'], "qty": 1, "exp": item['exp']
                        })
                        save_portfolio_to_disk(st.session_state.portfolio)
                        st.rerun()
                        
    # ---------------- BOTTOM ROW: LOW CAPS ----------------
    st.write("---")
    st.markdown("##### 🎲 LOW-CAP HIGH-VELOCITY RISK POOLS")
    if low_data:
        low_sorted = sorted(low_data, key=lambda x: x['score'], reverse=True)
        cols_low = st.columns(6)
        for idx, item in enumerate(low_sorted[:6]):
            with cols_low[idx]:
                with st.container(border=True):
                    st.markdown(f"##### **{item['ticker']}** ({item['score']}/100)")
                    sign = "+" if item['change'] >= 0 else ""
                    color = "green" if item['change'] >= 0 else "red"
                    
                    st.write(f"Stock: ${item['price']:.2f} (:{color}[{sign}{item['change']:.1f}%])")
                    st.write(f"Play: **{item['direction']} ${item['strike']:.1f}**")
                    st.write(f"Entry: **${item['cost']:.1f}**")
                    st.caption(f"V: {item['volume']:,} | IV: {item['iv']:.0f}%")
                    
                    if st.button("LOCK", key=f"l-low-{item['ticker']}-{idx}", use_container_width=True):
                        st.session_state.portfolio.append({
                            "ticker": item['ticker'], "direction": item['direction'], "strike": item['strike'],
                            "entry_stock": item['price'], "entry_premium": item['cost'], "qty": 1, "exp": item['exp']
                        })
                        save_portfolio_to_disk(st.session_state.portfolio)
                        st.rerun()

# ================= TAB: PORTFOLIO DECK TRACKER =================
with tab_saved:
    if st.session_state.portfolio:
        if st.button("WIPE ALL INVENTORY"):
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
                    st.markdown(f"##### **{pos['ticker']}** Long {pos['direction']}")
                    st.caption(f"Strike: ${pos['strike']:.2f} | Entry: ${pos['entry_premium']:.1f}")
                with c2:
                    st.write(f"Value: **${calc_premium * pos['qty']:,.2f}**")
                    st.markdown(f"P&L: :{pnl_color}[${net_pnl:+,.2f}]")
                with c3:
                    if st.button("RELEASE", key=f"rel-{pos['ticker']}-{p_idx}", use_container_width=True):
                        st.session_state.portfolio.pop(p_idx)
                        save_portfolio_to_disk(st.session_state.portfolio)
                        st.rerun()

# ================= TAB: SCHWAB AUTH NODE =================
with tab_schwab:
    st.markdown("##### 🔑 SECURE OAUTH GATEWAY")
    app_key = st.secrets["schwab"]["app_key"].strip()
    app_secret = st.secrets["schwab"]["app_secret"].strip()
    
    if st.session_state.schwab_connected:
        st.success("🛰️ PIPELINE ACTIVE")
        if st.button("Disconnect Session"):
            st.session_state.schwab_connected = False
            st.session_state.last_processed_code = ""
            st.rerun()
    else:
        auth_url = f"https://api.schwabapi.com/v1/oauth/authorize?client_id={app_key}&redirect_uri=https://127.0.0.1"
        st.markdown(f"👉 **[LOG INTO SCHWAB INTERFACE]({auth_url})**")
        
        returned_url = st.text_input("Paste Redirect Link Here:", key="auth_url_input")
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
                    st.toast("Handshake approved.", icon="⚙️")
                    st.rerun()
                else:
                    st.error("Authentication expired. Try again.")
            except Exception as e:
                st.error(f"Execution error: {e}")

# --- BACKGROUND AUTOMATIC TICK LOOP ---
time.sleep(10)
st.rerun()
