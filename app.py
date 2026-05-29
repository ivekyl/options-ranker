import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import time

# --- 80s SYNTHWAVE TERMINAL INTERFACE ---
st.set_page_config(layout="wide", page_title="NEON OPERATOR v1.0")

# Custom CSS for the glowing 80s retro terminal and animated card movements
st.markdown("""
<style>
    /* Global Styles */
    @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700&family=Share+Tech+Mono&display=swap');
    
    html, body, [data-testid="stAppViewContainer"] {
        background-color: #0b0114 !important;
        font-family: 'Share Tech Mono', monospace !important;
        color: #00ffcc !important;
    }
    
    h1, h2, h3, h4 {
        font-family: 'Orbitron', sans-serif !important;
        text-transform: uppercase;
        letter-spacing: 2px;
    }
    
    /* Hide default Streamlit sidebar and header noise */
    [data-testid="stSidebar"] {display: none !important;}
    [data-testid="stHeader"] {background: transparent !important;}
    div.block-container {padding-top: 2rem !important;}

    /* Neon Container Grid with Slide Transition Logic */
    [data-testid="stHorizontalBlock"] {
        gap: 1.5rem !important;
    }

    /* 80s Retro Glowing Cards */
    .synth-card {
        background: linear-gradient(145deg, #18032b, #0d011a);
        border: 2px solid #ff007f;
        border-radius: 8px;
        padding: 20px;
        box-shadow: 0 0 15px #ff007f, inset 0 0 10px #18032b;
        transition: all 0.6s cubic-bezier(0.25, 0.8, 0.25, 1);
        position: relative;
        overflow: hidden;
    }
    
    .synth-card:hover {
        transform: translateY(-8px) scale(1.02);
        box-shadow: 0 0 25px #00ffcc, inset 0 0 5px #00ffcc;
        border-color: #00ffcc;
    }
    
    /* Deal Tier Accents */
    .card-optimal { border: 2px solid #00ffcc !important; box-shadow: 0 0 15px #00ffcc; }
    .card-stable { border: 2px solid #ffaa00 !important; box-shadow: 0 0 15px #ffaa00; }
    
    /* Neon Text Accents */
    .ticker-header { font-size: 28px; font-weight: 700; color: #ffffff; text-shadow: 0 0 10px #ff007f; margin: 0; }
    .price-sub { font-size: 18px; color: #9d4edd; margin-bottom: 12px; }
    .action-badge { font-size: 16px; font-weight: bold; padding: 4px 8px; border-radius: 4px; display: inline-block; margin-bottom: 15px; text-transform: uppercase;}
    .badge-call { background-color: rgba(0, 255, 204, 0.15); color: #00ffcc; border: 1px solid #00ffcc; }
    .badge-put { background-color: rgba(255, 0, 127, 0.15); color: #ff007f; border: 1px solid #ff007f; }
    
    .metric-line { font-size: 15px; margin: 6px 0; color: #e0aaff; }
    .highlight-value { color: #ffffff; font-weight: bold; }
</style>
""", unsafe_allowed_html=True)

# Neon Header
st.markdown("<h1 style='text-align: center; color: #ff007f; text-shadow: 0 0 20px #ff007f; margin-bottom: 0;'>NEON OPERATOR // OPT-SCAN</h1>", unsafe_allowed_html=True)
st.markdown("<p style='text-align: center; color: #00ffcc; font-size: 14px; letter-spacing: 4px; margin-bottom: 30px;'>REAL-TIME MOVEMENT MATRIX • AUTO_REFRESH: ACTIVE</p>", unsafe_allowed_html=True)

# Fixed constraints directly inside code (no sidebar clutter)
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
            
            # Auto-hop expiration loops to target best-fit options matching position cap
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
            open_int = int(best_option['openInterest']) if not pd.isna(best_option['openInterest']) else 1
            iv = best_option.get('impliedVolatility', 0) * 100
            
            # Synth ranking math: Higher volume & lower premium volatility bumps position order up
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

# Run the real-time matrix processing engine
live_rankings = run_matrix_sweep(watchlist)

# Render Top 3 Animated Leaderboard Grid
if live_rankings:
    cols = st.columns(3)
    for idx, item in enumerate(live_rankings[:3]):
        with cols[idx]:
            # CSS Class assignment for glow effects based on internal scores
            tier_class = "card-optimal" if item['score'] >= 75 else "card-stable" if item['score'] >= 55 else ""
            badge_class = "badge-call" if item['direction'] == "CALL" else "badge-put"
            move_color = "#00ffcc" if item['change'] >= 0 else "#ff007f"
            move_sign = "+" if item['change'] >= 0 else ""
            
            # Interactive Terminal Block
            st.markdown(f"""
            <div class="synth-card {tier_class}">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <p class="ticker-header">RANK 0{idx+1} // {item['ticker']}</p>
                    <span class="action-badge {badge_class}">{item['direction']}</span>
                </div>
                <p class="price-sub">STOCK DATA: ${item['price']:.2f} (<span style="color: {move_color}; font-weight: bold;">{move_sign}{item['change']:.2f}%</span>)</p>
                <hr style="border-color: #3d1466; margin: 12px 0;">
                <p class="metric-line">TARGET STRIKE: <span class="highlight-value">${item['strike']:.2f}</span></p>
                <p class="metric-line">ENTRY PREMIUM: <span class="highlight-value">${item['cost']:.2f}</span></p>
                <p class="metric-line">EXPIRATION WINDOW: <span class="highlight-value">{item['exp']}</span></p>
                <hr style="border-color: #3d1466; margin: 12px 0;">
                <p class="metric-line" style="font-size:
