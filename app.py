import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import requests
import base64
import json
import os
import time

# --- ARCADE BOARD GRID SYSTEM ---
st.set_page_config(layout="wide", page_title="NEON MATRIX")

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

# High-liquidity tracking cluster
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
            iv = best_option['impliedVolatility'] * 100
            
            score = 50
            if vol > 300: score += 20
            if abs(pct_change) > 3.5: score += 20
            if iv < 65: score += 10
            score = max(10, min(100, score))
            
            sweep_pool.append({
                "ticker": t, "price": current_price, "change": pct_change,
                "direction": direction, "strike": best_option['strike'],
                "cost": cost, "volume": vol, "iv": iv, "score": score, "exp": best_exp
            })
        except:
            continue
    return sweep_pool

live_data = fetch_live_market_matrix(watchlist)

# Ribbon Ticker Component
if live_data:
    sorted_movers = sorted(live_data, key=lambda x: x['change'], reverse=True)
    st.markdown(f"⚡ **LIVE TICKER** // 🚀 MAX GAIN: **{sorted_movers[0]['ticker']}** :green[{sorted_movers[0]['change']:+.2f}%] (${sorted_movers[0]['price']:.2f})  |  💥 MAX DROP: **{sorted_movers[-1]['ticker']}** :red[{sorted_movers[-1]['change']:+.2f}%] (${sorted_movers[-1]['price']:.2f})")
    st.write("---")

tab_matrix, tab_saved, tab_schwab_link = st.tabs(["🎮 SCAN MATRIX", "💿 SAVED POSITIONS", "🔑 SCHWAB AUTH"])

with tab_matrix:
    if live_data:
        sorted_matrix = sorted(live_data, key=lambda x: x['score'], reverse=True)
        grid_cols = st.columns(5)
        for idx, item in enumerate(sorted_matrix):
            with grid_cols[idx % 5]:
                deal_tag = "💎 :green[ULTRA]" if item['score'] >= 75 else "✳️ :green[OPTIMAL]" if item['score'] >= 55 else "⚠️ :orange[NEUTRAL]"
                with st.container(border=True):
                    st.markdown(f"#### {item['ticker']}")
                    st.caption(deal_tag)
                    move_color = "green" if item['change'] >= 0 else "red"
                    st.write(f"Stock: **${item['price']:.2f}** (:{move_color}[{item['change']:+.2f}%])")
                    st.write(f"👉 **{item['direction']} ${item['strike']:.2f}**")
                    st.write(f"Premium: **${item['cost']:.2f}**")
                    if st.button("LOCK PLAY", key=f"lock-{item['ticker']}-{idx}", use_container_width=True):
                        st.session_state.portfolio.append({
                            "ticker": item['ticker'], "direction": item['direction'], "strike": item['strike'],
                            "entry_stock": item['price'], "entry_premium": item['cost'], "qty": 1, "exp": item['exp']
                        })
                        save_portfolio_to_disk(st.session_state.portfolio)
                        st.toast(f"Saved {item['ticker']} to storage.", icon="💿")
                        st.rerun()

with tab_saved:
    if st.session_state.portfolio:
        if st.button("CLEAR DISK MEMORY STORAGE"):
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
                    st.markdown(f"##### 📦 {pos['ticker']} {pos['direction']}")
                    st.caption(f"Strike: ${pos['strike']:.2f} | Entry: ${pos['entry_premium']:.2f}")
                with c2:
                    st.write(f"Current Value: **${calc_premium * pos['qty']:,.2f}**")
                    st.markdown(f"P&L: :{pnl_color}[${net_pnl:+,.2f}]")
                with c3:
                    if st.button("RELEASE", key=f"rel-{pos['ticker']}-{p_idx}", use_container_width=True):
                        st.session_state.portfolio.pop(p_idx)
                        save_portfolio_to_disk(st.session_state.portfolio)
                        st.rerun()

# ================= FIXED PRODUCTION SCHWAB AUTHENTICATION INTERFACE =================
with tab_schwab_link:
    st.markdown("### SCHWAB OAUTH SECURE GATEWAY")
    
    app_key = st.secrets["schwab"]["app_key"]
    app_secret = st.secrets["schwab"]["app_secret"]
    
    auth_url = f"https://api.schwabapi.com/v1/oauth/authorize?client_id={app_key}&redirect_uri=https://127.0.0.1"
    st.markdown(f"🔗 **[STEP 1: CLICK HERE TO LOG INTO SCHWAB]({auth_url})**")
    st.caption("Log into Schwab, approve account tracking access lines, and copy the final link address from the blank browser page.")
    
    returned_url = st.text_input("STEP 2: Paste Returned URL Link String Here:")
    
    if returned_url and "code=" in returned_url:
        try:
            # Automatic URL String Extraction & Decoupling parameters
            raw_code = returned_url.split("code=")[1].split("&")[0]
            clean_code = raw_code.replace("%40", "@") # Converts the hidden symbol bug automatically
            
            # Formulate the HTTP Basic Authentication Header
            raw_cred_string = f"{app_key}:{app_secret}"
            base64_encoded_creds = base64.b64encode(raw_cred_string.encode("utf-8")).decode("utf-8")
            
            token_url = "https://api.schwabapi.com/v1/oauth/token"
            headers = {
                "Authorization": f"Basic {base64_encoded_creds}",
                "Content-Type": "application/x-www-form-urlencoded"
            }
            payload = {
                "grant_type": "authorization_code",
                "code": clean_code,
                "redirect_uri": "https://127.0.0.1"
            }
            
            with st.spinner("Exchanging code for official operational tokens..."):
                response = requests.post(token_url, headers=headers, data=payload, timeout=7)
                
                if response.status_code == 200:
                    tokens = response.json()
                    st.success("🎉 CONNECTOR KEY ACTIVE!")
                    st.json({
                        "access_token": f"{tokens.get('access_token')[:10]}...",
                        "refresh_token": f"{tokens.get('refresh_token')[:10]}...",
                        "expires_in": f"{tokens.get('expires_in')} seconds (30 mins)"
                    })
                else:
                    st.error(f"Schwab Authentication Denied (Status: {response.status_code})")
                    st.write(response.json())
        except Exception as e:
            st.error(f"Parser processing layout initialization disruption: {e}")

time.sleep(10)
st.rerun()
