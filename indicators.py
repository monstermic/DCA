# === indicators.py (Simplified Bias Logic) ===
import pandas as pd
import pandas_ta as ta # Requires: pip install pandas_ta
import config

def get_trend_and_rsi(session, symbol_info): # Pass symbol_info if needed by future indicators
    """
    Determines market bias based purely on SMA alignment (Fast vs Slow).
    Returns 'Buy' (Bullish Bias), 'Sell' (Bearish Bias), or 'Neutral'.
    RSI is calculated for logging/informational purposes only.
    """
    if not session:
        print("Error: Session not provided to get_trend_and_rsi")
        return "Neutral"

    print(f"\nFetching kline ({config.TREND_INTERVAL}) for bias...")
    # Ensure enough data for the longest period + warmup
    limit = max(config.SLOW_SMA_PERIOD, config.RSI_PERIOD) + 5 # Still need data for longest indicator calc if RSI is logged
    try:
        kline_resp = session.get_kline(
            category=config.CATEGORY,
            symbol=config.SYMBOL,
            interval=config.TREND_INTERVAL,
            limit=limit
        )
        if kline_resp.get('retCode') == 0 and kline_resp.get('result', {}).get('list'):
            kline_list = kline_resp['result']['list']
            # Need enough data points for the longest calculation period AFTER potential NaNs
            if len(kline_list) < max(config.SLOW_SMA_PERIOD, config.RSI_PERIOD) + 1:
                print("Insufficient kline data received for calculation."); return "Neutral"

            df = pd.DataFrame(kline_list, columns=['ts', 'o', 'h', 'l', 'c', 'v', 'to'])
            df['c'] = pd.to_numeric(df['c'])
            df = df.iloc[::-1] # Reverse to chronological order for calculations

            # Calculate Indicators
            df['sma_fast'] = df['c'].rolling(window=config.FAST_SMA_PERIOD).mean()
            df['sma_slow'] = df['c'].rolling(window=config.SLOW_SMA_PERIOD).mean()
            rsi_col_name = f"RSI_{config.RSI_PERIOD}"
            df[rsi_col_name] = ta.rsi(close=df['c'], length=config.RSI_PERIOD)

            # Check if latest calculations are valid (not NaN)
            # Check SMA slow as it requires the most data
            if df['sma_slow'].isnull().iloc[-1] or df['sma_fast'].isnull().iloc[-1]:
                 print("SMA calculation resulted in NaN (insufficient data points).")
                 return "Neutral"
            # Check RSI separately in case it needs more/less data and failed
            rsi_valid = not df[rsi_col_name].isnull().iloc[-1]


            # Get latest values
            last_fast = df['sma_fast'].iloc[-1]
            last_slow = df['sma_slow'].iloc[-1]
            last_rsi = df[rsi_col_name].iloc[-1] if rsi_valid else None # Get RSI if valid

            # Log the calculated values
            rsi_log = f"{last_rsi:.2f}" if last_rsi is not None else "N/A"
            print(f"SMAs: F={last_fast:.2f}, S={last_slow:.2f} | RSI={rsi_log}")

            # --- SIMPLIFIED BIAS Logic: SMA Alignment Only ---
            bias = "Neutral"
            if last_fast > last_slow:
                print("Bias Signal: Bullish (Fast > Slow)")
                bias = "Buy"
            elif last_fast < last_slow:
                print("Bias Signal: Bearish (Fast < Slow)")
                bias = "Sell"
            else:
                 print("Bias Signal: Neutral (SMAs Equal)") # Very rare

            return bias
        else:
            print(f"Kline fetch error or empty list: {kline_resp.get('retMsg')}"); return "Neutral"
    except Exception as e:
        print(f"Bias calculation error: {e}"); return "Neutral"