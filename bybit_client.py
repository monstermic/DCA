import pybit
from pybit.unified_trading import HTTP
import config  # Import your configuration
import utils   # Import your utility functions (for precision getters)

_session = None # Cache session

def initialize_session_and_config():
    """
    Initializes session, sets leverage, fetches symbol info.
    Returns True and symbol_info dict on success, False and None on failure.
    Includes detailed error printing.
    """
    global _session # Needed to modify the global _session variable

    if not config.API_KEY or not config.API_SECRET:
        print("CRITICAL ERROR: API Keys not found in config.")
        return False, None

    # --- Step 1: Initialize Session ---
    try:
        # Always try to initialize - ensures session object exists if called multiple times
        print("Attempting to initialize Bybit HTTP session...")
        _session = HTTP(
            testnet=True,
            api_key=config.API_KEY,
            api_secret=config.API_SECRET
        )
        # Test connection with a simple call that requires auth but little permission
        ping_response = _session.get_api_key_information()
        if ping_response.get('retCode') != 0:
             # Throw specific error if API keys themselves are invalid (e.g., 10003, 10004)
             raise ConnectionError(f"API Key Test Failed: {ping_response.get('retMsg')} (Code: {ping_response.get('retCode')})")
        print("Bybit session initialized and API keys seem valid.")

    except Exception as e:
        print(f"CRITICAL ERROR: Failed to initialize Bybit session or validate keys: {e}")
        _session = None # Ensure session is None on failure
        return False, None # Cannot proceed

    # --- Step 2: Set Leverage ---
    try:
        print(f"Attempting to set leverage for {config.SYMBOL} to {config.LEVERAGE}x...")
        lev_resp = _session.set_leverage(
            category=config.CATEGORY,
            symbol=config.SYMBOL,
            buyLeverage=config.LEVERAGE,
            sellLeverage=config.LEVERAGE
        )
        if lev_resp.get('retCode') == 0: print(f"Leverage set to {config.LEVERAGE}x.")
        elif lev_resp.get('retCode') == 110043: print(f"Leverage already set to {config.LEVERAGE}x (Code: 110043).")
        else: print(f"Warning: Leverage setting returned - {lev_resp.get('retMsg')} (Code: {lev_resp.get('retCode')})")
    except Exception as e:
        # Log warning but don't necessarily fail initialization just for leverage setting error
        print(f"Warning: Error during leverage setting: {e}")

    # --- Step 3: Fetch Symbol Info ---
    symbol_info_dict = None
    try:
        print("Fetching Instrument Info...")
        info_resp = _session.get_instruments_info(category=config.CATEGORY, symbol=config.SYMBOL)
        if info_resp.get('retCode') == 0 and info_resp.get('result', {}).get('list'):
            symbol_data = info_resp['result']['list'][0]
            symbol_info_dict = {
                'pricePrecision': utils.get_price_precision(symbol_data),
                'qtyPrecision': utils.get_qty_precision(symbol_data),
                'minOrderQty': float(symbol_data['lotSizeFilter'].get('minOrderQty', '0.001')),
                'maxOrderQty': float(symbol_data['lotSizeFilter'].get('maxOrderQty', '100')),
                'qtyStep': float(symbol_data['lotSizeFilter'].get('qtyStep', '0.001'))
            }
            print(f"Symbol Info OK: PPrec={symbol_info_dict['pricePrecision']}, QPrec={symbol_info_dict['qtyPrecision']}, MinQ={symbol_info_dict['minOrderQty']}, MaxQ={symbol_info_dict['maxOrderQty']}, Step={symbol_info_dict['qtyStep']}")
            return True, symbol_info_dict # SUCCESS
        else:
            print(f"CRITICAL ERROR: Could not fetch instrument info. Err: {info_resp.get('retMsg')}")
            return False, None
    except Exception as e:
        print(f"CRITICAL ERROR: Error fetching instrument info: {e}.")
        return False, None

# Keep the get_session() function as is
def get_session():
    """Returns the initialized Bybit HTTP session."""
    global _session
    # The warning is now less relevant as init should be called first, but keep it
    if not _session:
        print("Warning: get_session() called before successful initialization.")
    return _session