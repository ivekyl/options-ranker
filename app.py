import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import time

# --- NEON OPERATOR INTERFACE CONFIG ---
st.set_page_config(layout="wide", page_title="NEON OPERATOR v1.0")

# Neon Title Layout using native markdown header strings
st.markdown("# NEON OPERATOR // OPT-SCAN")
st.markdown("### REAL-TIME MOVEMENT MATRIX • AUTO_REFRESH: ACTIVE")
st.write("---")

# Fixed core constraints
MAX_BUDGET = 1166.0  
watchlist = ["PLTR", "TSLA", "NVDA", "AMD", "AAPL", "MSFT", "UBER", "HOOD", "SOFI", "XOM", "BAC", "F"]

def calculate_rsi(prices, period=14):
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / (loss + 0.00001)
    return 100 - (100 / (1 + rs))

@st.cache_data(ttl=10) 
def run_matrix_sweep(tickers):
    matrix_pool = []
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
            
            direction = "PUT" if current_rsi >= 62 else "CALL"
            expirations = stock.options
            if not expirations: continue
            
            valid_chain = pd.DataFrame()
            chosen_exp = None
            sorted_exps = sorted(expirations, key=lambda x: abs((pd.to_datetime(x) - today).days - 60))
            
            for exp in sorted_exps:
                days = (pd.to_datetime(exp) - today).days
                if days < 20 or days > 180: continue
                
                opt_chain = stock.option_chain(exp)
                chain = opt_chain.puts if direction == "PUT" else opt_chain.calls
                ntm = chain[(chain['strike'] >= current_price * 0.93) & (chain['strike'] <= current_price * 1.07)].copy()
                ntm = ntm[ntm['ask'] * 100 <= MAX_BUDGET]
                
                if not ntm.empty:
                    valid_chain = ntm
                    chosen_exp = exp
                    break
            
            if valid_chain.empty: continue
            
            valid_chain['distance'] = abs(valid_chain['strike'] - current_price)
            best_option = valid_chain.sort_values(by='distance').iloc[0]
            
            cost = best_option['ask'] * 100
            volume = int(best_option['volume']) if not pd.isna(best_option['volume']) else 0
            iv = best_option.get('impliedVolatility', 0) * 100
            
            rank_score = 50
            if volume > 400: rank_score += 25
            if iv < 55: rank_score += 20
            rank_score += int(pct_change * 2) if direction == "CALL" else int(-pct_change * 2)
            
            matrix_pool.append({
                "ticker": t, "price": current_price, "change": pct_change,
                "direction": direction, "strike": best_option['strike'],
                "cost": cost, "volume": volume, "iv": iv, "score": rank_score,
                "exp": chosen_exp
            })
        except:
            continue
            
    return sorted(matrix_pool, key=lambda x: x['score'], reverse=True)

live_rankings = run_matrix_sweep(watchlist)

# Render Live Matrix Cards using Native Containers
if live_rankings:
    cols = st.columns(3)
    for idx, item in enumerate(live_rankings[:3]):
        with cols[idx]:
            with st.container(border=True):
                # Card Header Block
                st.markdown(f"### RANK 0{idx+1} // {item['ticker']}")
                
                # Direction Status Tag
                if item['direction'] == "CALL":
                    st.markdown(f"🟢 **STRATEGY:** ACTION_BUY_{item['direction']}")
                else:
                    st.markdown(f"💗 **STRATEGY:** ACTION_BUY_{item['direction']}")
                
                # Market data values
                move_sign = "+" if item['change'] >= 0 else ""
                st.write(f"STOCK VALUE: ${item['price']:.2f} ({move_sign}{item['change']:.2f}%)")
                
                st.markdown("---")
                st.write(f"🎯 TARGET STRIKE: **${item['strike']:.2f}**")
                st.write(f"💵 ENTRY PREMIUM: **${item['cost']:.2f}**")
                st.write(f"📅 EXPIRATION: `{item['exp']}`")
                
                st.markdown("---")
                st.caption(f"VOL: {item['volume']:,} // IMP_VOL: {item['iv']:.1f}%")
                
                if st.button(f"ENGAGE VECTOR // {item['ticker']}", key=f"btn-{item['ticker']}-{idx}", use_container_width=True):
                    st.toast(f"Vector active for {item['ticker']}.", icon="🚀")
else:
    st.info("SWEEPING SECTORS FOR VALID PREMIUM SIGNALS...")

# --- BACKGROUND AUTOMATIC TICK LOOP ---
time.sleep(10)
st.rerun()
