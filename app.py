import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import time

# --- NEON OPERATOR CORE INTERFACE ---
st.set_page_config(layout="wide", page_title="NEON OPERATOR v2.0")

# Initialize persistent session storage memory banks
if "cash" not in st.session_state:
    st.session_state.cash = 10000.0
if "portfolio" not in st.session_state:
    st.session_state.portfolio = []

st.markdown("# NEON OPERATOR // MATRIX TERMINAL")
st.write(f"SYSTEM CASH BALANCE: **${st.session_state.cash:,.2f} USD**")
st.write("---")

# Optimized high-velocity institutional watchlist
watchlist = [
    "NVDA", "AAPL", "MSFT", "AMZN", "GOOGL", "TSLA", "META", "AMD", "PLTR", 
    "NFLX", "UBER", "HOOD", "SOFI", "BAC", "F", "XOM", "JPM", "V", "ORCL", 
    "COST", "BAC", "DIS", "T", "INTC", "CRM"
]

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
    max_budget_per_slot = 1166.0
    
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
            
            # Professional Strategy: RSI boundary reversal indicators
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
                ntm = ntm[ntm['ask'] * 100 <= max_budget_per_slot]
                
                if not ntm.empty:
                    valid_chain = ntm
                    chosen_exp = exp
                    break
            
            if valid_chain.empty: continue
            
            valid_chain['distance'] = abs(valid_chain['strike'] - current_price)
            best_option = valid_chain.sort_values(by='distance').iloc[0]
            
            cost = best_option['ask'] * 100
            volume = int(best_option['volume']) if not pd.isna(best_option['volume']) else 0
            open_int = int(best_option['openInterest']) if not pd.isna(best_option['openInterest']) else 1
            iv = best_option.get('impliedVolatility', 0) * 100
            
            # ADVANCED MATH CALCULUS RANKING
            # Bumps positions based on High Volume, low premium IV markups, and institutional Volume/OI ratios
            rank_score = 50
            if volume > 500: rank_score += 20
            if iv < 50: rank_score += 15
            if open_int > 0 and (volume / open_int) > 1.2: rank_score += 15
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

# Run system sweep
live_rankings = run_matrix_sweep(watchlist)

# --- NAVIGATION TABS ---
tab_scanner, tab_portfolio = st.tabs(["📡 NEON SCANNER", "💼 PORTFOLIO CORE"])

# ================= TAB 1: SCANNER LAYER =================
with tab_scanner:
    if live_rankings:
        cols = st.columns(3)
        for idx, item in enumerate(live_rankings[:3]):
            with cols[idx]:
                with st.container(border=True):
                    st.markdown(f"### RANK 0{idx+1} // {item['ticker']}")
                    
                    if item['direction'] == "CALL":
                        st.markdown(f"🟢 **STRATEGY:** ACTION_BUY_{item['direction']}")
                    else:
                        st.markdown(f"💗 **STRATEGY:** ACTION_BUY_{item['direction']}")
                        
                    move_sign = "+" if item['change'] >= 0 else ""
                    st.write(f"STOCK VALUE: ${item['price']:.2f} ({move_sign}{item['change']:.2f}%)")
                    
                    st.markdown("---")
                    st.write(f"🎯 TARGET STRIKE: **${item['strike']:.2f}**")
                    st.write(f"💵 PREMIUM COST: **${item['cost']:.2f}** / contract")
                    st.write(f"📅 EXPIRATION: `{item['exp']}`")
                    st.caption(f"VOL: {item['volume']:,} // IV: {item['iv']:.1f}%")
                    st.markdown("---")
                    
                    # Contract transaction interface
                    trade_qty = st.number_input(f"Contracts Size", min_value=1, max_value=25, value=1, key=f"qty-{item['ticker']}-{idx}")
                    total_execution_cost = item['cost'] * trade_qty
                    st.write(f"Total Premium: ${total_execution_cost:,.2f}")
                    
                    if st.button(f"EXECUTE POSITION COLLAR // {item['ticker']}", key=f"buy-{item['ticker']}-{idx}", use_container_width=True):
                        if st.session_state.cash >= total_execution_cost:
                            # Deduct from capital vault
                            st.session_state.cash -= total_execution_cost
                            # Append position configuration payload
                            st.session_state.portfolio.append({
                                "ticker": item['ticker'],
                                "direction": item['direction'],
                                "strike": item['strike'],
                                "entry_stock_price": item['price'],
                                "entry_contract_premium": item['cost'],
                                "qty": trade_qty,
                                "exp": item['exp'],
                                "peak_value": item['cost'] * trade_qty,
                                "trailing_active": False
                            })
                            st.toast(f"Order executed: Allocated {trade_qty} contracts of {item['ticker']}.", icon="🚀")
                            st.rerun()
                        else:
                            st.error("INSUFFICIENT SIMULATED MARGIN LIQUIDITY.")
    else:
        st.info("SCANNING NETWORKS FOR TRADE ALIGNMENT MATCHES...")

# ================= TAB 2: PORTFOLIO LAYER =================
with tab_portfolio:
    st.markdown("### ACTIVE RISK TRACKING DECK")
    
    if st.session_state.portfolio:
        # Action to reset sandbox parameters cleanly
        if st.button("LIQUIDATE ENTIRE PORTFOLIO (RESET CASH TO $10K)", type="secondary"):
            st.session_state.cash = 10000.0
            st.session_state.portfolio = []
            st.rerun()
            
        st.write("---")
        
        # Display each asset holding position sequentially
        for idx, pos in enumerate(st.session_state.portfolio):
            try:
                # Pull current live underlying asset calculation references
                live_asset = yf.Ticker(pos['ticker'])
                current_stock = live_asset.history(period="1d")["Close"].iloc[-1]
            except:
                current_stock = pos['entry_stock_price'] # Safety fallback
                
            # GREEKS DELTA PROXIE MECHANIC CALCULUS
            # Simulates realistic options valuation moves instantly
            stock_delta_move = current_stock - pos['entry_stock_price']
            delta_factor = 0.50 if pos['direction'] == "CALL" else -0.50
            
            current_single_premium = max(0.05, pos['entry_contract_premium'] + (stock_delta_move * delta_factor * 100))
            current_total_value = current_single_premium * pos['qty']
            initial_total_cost = pos['entry_contract_premium'] * pos['qty']
            
            # Absolute P&L tracking profiles
            net_pnl = current_total_value - initial_total_cost
            pnl_pct = (net_pnl / initial_total_cost) * 100
            
            # --- CUSTOM TRAILING STOP-LOSS CALCULUS ENGINE ---
            if current_total_value > pos['peak_value']:
                pos['peak_value'] = current_total_value
                
            # Triggers lock switch if trade gains hit over +50% absolute limits
            if (pos['peak_value'] - initial_total_cost) / initial_total_cost >= 0.50:
                pos['trailing_active'] = True
                
            stop_loss_floor = pos['peak_value'] * 0.90  # 10% maximum trailing drop threshold
            
            with st.container(border=True):
                col_a, col_b, col_c = st.columns([1, 2, 1])
                with col_a:
                    st.markdown(f"#### {pos['ticker']} ({pos['qty']} Contracts)")
                    st.caption(f"{pos['direction']} • Strike ${pos['strike']:.2f} • Exp: {pos['exp']}")
                
                with col_b:
                    pnl_color = ":green" if net_pnl >= 0 else ":red"
                    st.markdown(f"Current Value: **${current_total_value:,.2f}**")
                    st.markdown(f"Net Gain/Loss: {pnl_color}[${net_pnl:+,.2f} ({pnl_pct:+.2f}%)]")
                
                with col_c:
                    if pos['trailing_active']:
                        st.markdown(":green[🛡️ TRAILING STOP: ACTIVE]")
                        st.caption(f"Floor Limit: ${stop_loss_floor:,.2f}")
                        if current_total_value <= stop_loss_floor:
                            st.error("🚨 RETRACE BREACHED")
                            if st.button("LIQUIDATE ORDER VIA STOP", key=f"sell-{idx}"):
                                st.session_state.cash += current_total_value
                                st.session_state.portfolio.pop(idx)
                                st.rerun()
                    else:
                        st.markdown(":orange[⏳ TRAILING STOP: DORMANT]")
                        st.caption("Activates at +50% gains")
                        if st.button("MARKET CLOSE POSITION", key=f"close-{idx}", use_container_width=True):
                            st.session_state.cash += current_total_value
                            st.session_state.portfolio.pop(idx)
                            st.toast(f"Closed position for {pos['ticker']}.", icon="💵")
                            st.rerun()
    else:
        st.info("NO ACTIVE VECTOR DEPLOYMENTS FOUND IN PORTFOLIO VAULT.")

# --- BACKGROUND AUTOMATIC HEARTBEAT LOOP ---
time.sleep(10)
st.session_state.run_count = st.session_state.get('run_count', 0) + 1
st.rerun()
