# === journal.py ===
import csv
import os
import config # To get symbol maybe? Or pass everything needed

JOURNAL_FILE = "trade_journal.csv"
# Define the headers for your journal
CSV_HEADERS = [
    "EntryTimestamp", "ExitTimestamp", "DurationSec", "Side",
    "AvgEntryPrice", "AvgExitPrice", "BaseQty", "FilledSOs",
    "FinalSize", "RealizedPnL_USDT", "ExitType"
    # Add more fields as needed, e.g., InitialSL, InitialTP, Trend Indicators at entry...
]

def log_trade_to_csv(trade_data):
    """Appends a completed trade's data to the CSV journal file."""
    file_exists = os.path.isfile(JOURNAL_FILE)
    try:
        with open(JOURNAL_FILE, 'a', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=CSV_HEADERS)
            if not file_exists:
                writer.writeheader() # Write header only if file is new
            writer.writerow(trade_data)
            print(f"--- Trade Logged to {JOURNAL_FILE} ---")
    except Exception as e:
        print(f"!!! Error writing to journal file: {e}")

def format_trade_data(bot_state_on_close, closed_pnl_data):
    """Formats data from bot state and PNL data into a dictionary for logging."""
    try:
        entry_ts = bot_state_on_close.get('current_trade_entry_timestamp', 0)
        exit_ts = int(closed_pnl_data.get('updatedTime', 0)) # PNL data uses ms
        duration = (exit_ts - entry_ts) / 1000 if entry_ts > 0 and exit_ts > 0 else 0 # Duration in seconds

        trade_log_entry = {
            "EntryTimestamp": entry_ts,
            "ExitTimestamp": exit_ts,
            "DurationSec": f"{duration:.2f}",
            "Side": bot_state_on_close.get('current_trade_side', 'N/A'),
            "AvgEntryPrice": f"{bot_state_on_close.get('current_trade_avg_price', 0.0):.4f}", # Price from state when closed
            "AvgExitPrice": f"{float(closed_pnl_data.get('avgExitPrice', '0')):.4f}",
            "BaseQty": f"{bot_state_on_close.get('calculated_base_qty_this_cycle', 0.0):.6f}", # Base qty from state
            "FilledSOs": bot_state_on_close.get('filled_safety_orders_count', 0),
            "FinalSize": f"{float(closed_pnl_data.get('closedSize', '0')):.6f}", # Should match total size placed
            "RealizedPnL_USDT": f"{float(closed_pnl_data.get('closedPnl', '0')):.6f}",
            "ExitType": closed_pnl_data.get('exitType', 'Unknown') # e.g., TakeProfit, StopLoss, Unknown
            # Add more fields here by extracting from bot_state_on_close or closed_pnl_data
        }
        return trade_log_entry
    except Exception as e:
        print(f"Error formatting trade data: {e}")
        return None