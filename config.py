# === config.py (Added TSL Profit Threshold) ===

import os
from dotenv import load_dotenv

load_dotenv()

# --- API Keys ---
API_KEY = os.getenv("BYBIT_TEST_API_KEY")
API_SECRET = os.getenv("BYBIT_TEST_API_SECRET")

# --- Fee Estimation ---
ESTIMATED_TAKER_FEE_PERCENT = 0.055
ESTIMATED_TOTAL_FEE_PERCENT = ESTIMATED_TAKER_FEE_PERCENT * 2
print(f"INFO: Using estimated total fee buffer for TP: {ESTIMATED_TOTAL_FEE_PERCENT:.4f}%")

# --- Bot Parameters (3-MINUTE SCALPING EXAMPLE) ---
SYMBOL = "BTCUSDT"
CATEGORY = "linear"
LEVERAGE = "10" # Preferred leverage

# --- Risk & Sizing Parameters ---
RISK_PER_TRADE_PERCENT = 0.5
STOP_LOSS_PERCENT_FOR_SIZING = 0.4 # Used for both sizing and execution SL %

# --- Safety Order Parameters ---
SAFETY_ORDER_STEP_PERCENT = 0.15
SAFETY_ORDER_STEP_SCALE = 1.1
SAFETY_ORDER_VOLUME_SCALE = 1.1
MAX_SAFETY_ORDERS = 3
SAFETY_ORDER_LIQ_BUFFER_PERCENT = 1.0

# --- Take Profit / Stop Loss Parameters (Execution) ---
TAKE_PROFIT_PERCENT = 0.7
# SL execution % uses STOP_LOSS_PERCENT_FOR_SIZING

# --- Trailing Stop Loss Activation ---
# Activate TSL (move SL to BE) after last SO fills ONLY IF profit meets threshold
TSL_PROFIT_THRESHOLD_PERCENT = 0.1 # NEW: e.g., require 0.1% profit before moving SL to BE

# --- Order Management ---
PENDING_ORDER_TIMEOUT_SECONDS = 180 # Cancel pending entry after 3 mins

# --- Trend Parameters ---
TREND_INTERVAL = "3"
FAST_SMA_PERIOD = 8
SLOW_SMA_PERIOD = 13
RSI_PERIOD = 9
RSI_OVERBOUGHT = 75 # Used only for logging now
RSI_OVERSOLD = 25  # Used only for logging now

# --- State File ---
STATE_FILE = "bot_state_3m.json" # Or your current state file name

# --- Initial State Structure ---
INITIAL_STATE = {
    "filled_safety_orders_count": 0,
    "calculated_base_qty_this_cycle": 0.0,
    "active_safety_order_ids": [],
    "is_in_trade": False,
    "current_trade_entry_timestamp": 0,
    "current_trade_side": None,
    "current_trade_avg_price": 0.0,
    "pending_entry_order_id": None,
    "pending_order_placed_timestamp": 0,
    "tsl_activated_this_trade": False # TSL Flag (Move to BE after last SO + Profit)
}

# Basic check for keys
if not API_KEY or not API_SECRET:
    print("CRITICAL ERROR: API Keys not found.")
    # Raise error or exit