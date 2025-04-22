from decimal import Decimal, ROUND_DOWN, ROUND_UP, InvalidOperation

def get_price_precision(symbol_info):
    """Gets price precision from Bybit instrument info."""
    try:
        price_filter = symbol_info.get('priceFilter', {})
        tick_size_str = price_filter.get('tickSize', '1')
        if '.' in tick_size_str: return len(tick_size_str.split('.')[-1])
        else: return 0
    except Exception: return 2 # Default fallback

def get_qty_precision(symbol_info):
    """Gets quantity precision from Bybit instrument info."""
    try:
        lot_size_filter = symbol_info.get('lotSizeFilter', {})
        qty_step_str = lot_size_filter.get('qtyStep', '1')
        if '.' in qty_step_str: return len(qty_step_str.split('.')[-1])
        else: return 0
    except Exception: return 3 # Default fallback

def format_price(price, precision):
    """Formats price safely."""
    if price is None: return None
    try:
        dec_price = Decimal(str(price))
        round_str = '1e-' + str(precision)
        # Adjust rounding logic if needed, e.g., round towards safety for SL
        rounded = dec_price.quantize(Decimal(round_str), rounding=ROUND_DOWN if precision > 0 else ROUND_UP)
        return f"{rounded:.{precision}f}"
    except (TypeError, ValueError, InvalidOperation) as e:
        print(f"Error formatting price '{price}': {e}")
        return None

def format_qty(qty, precision):
    """Formats quantity safely, always rounding down."""
    if qty is None: return None
    try:
        dec_qty = Decimal(str(qty))
        round_str = '1e-' + str(precision)
        rounded = dec_qty.quantize(Decimal(round_str), rounding=ROUND_DOWN)
        return f"{rounded:.{precision}f}"
    except (TypeError, ValueError, InvalidOperation) as e:
        print(f"Error formatting quantity '{qty}': {e}")
        return None