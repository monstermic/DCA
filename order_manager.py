# === order_manager.py (No changes needed from v19) ===
import json
from decimal import Decimal
import config
import utils

# (place_base_order remains same as v15 - uses Limit)
def place_base_order(session, symbol_info, side, qty, limit_price):
    if not session: return None, 0
    print(f"--- Placing BASE Limit Order ---")
    try:
        min_qty = symbol_info['minOrderQty']; max_qty = symbol_info['maxOrderQty']
        qty_step = symbol_info['qtyStep']; qty_prec = symbol_info['qtyPrecision']
        price_prec = symbol_info['pricePrecision']
        qty_d = Decimal(str(qty)); min_d=Decimal(str(min_qty)); max_d=Decimal(str(max_qty)); step_d=Decimal(str(qty_step))
        if qty_d < min_d: qty_d=min_d
        elif qty_d > max_d: qty_d=max_d
        if step_d > 0: qty_d=(qty_d//step_d)*step_d
        final_qty=float(qty_d); fmt_qty=utils.format_qty(final_qty, qty_prec); fmt_price = utils.format_price(limit_price, price_prec)
        if not fmt_qty or final_qty < min_qty or not fmt_price: print(f"   !!! Final Qty {fmt_qty} or Price {fmt_price} invalid."); return None, 0
        print(f"   {config.SYMBOL}, {side}, Qty: {fmt_qty}, Limit Price: {fmt_price}")
        resp = session.place_order(category=config.CATEGORY, symbol=config.SYMBOL, side=side, orderType="Limit", qty=fmt_qty, price=fmt_price, timeInForce="GTC")
        print(f"   API Resp: {json.dumps(resp)}")
        if resp.get('retCode')==0 and resp['result'].get('orderId'): print(f"   >>> Success! Limit Order Placed ID: {resp['result']['orderId']}"); return resp['result']['orderId'], final_qty
        else: print(f"   !!! Failed: {resp.get('retMsg')} ({resp.get('retCode')})"); return None, 0
    except Exception as e: print(f"   !!! Error placing base: {e}"); return None, 0

# (set_position_tp_sl handles None args - same as v19)
def set_position_tp_sl(session, symbol_info, take_profit_price=None, stop_loss_price=None):
    if not session: return False
    if take_profit_price is None and stop_loss_price is None: return False
    print(f"--- Setting/Updating TP/SL ---"); params={"category": config.CATEGORY, "symbol": config.SYMBOL, "tpslMode": "Full"}; log=[]
    price_prec = symbol_info['pricePrecision']
    if take_profit_price is not None:
        fmt_tp=utils.format_price(take_profit_price, price_prec)
        if fmt_tp: params["takeProfit"]=fmt_tp; log.append(f"TP={fmt_tp}")
        else: print("   !!! Invalid TP price.")
    # else: log.append("TP=None") # Optional logging if needed
    if stop_loss_price is not None:
        fmt_sl=utils.format_price(stop_loss_price, price_prec)
        if fmt_sl: params["stopLoss"]=fmt_sl; log.append(f"SL={fmt_sl}")
        else: print("   !!! Invalid SL price."); # If only SL provided and invalid, fail?
              # if take_profit_price is None: return False
    # else: log.append("SL=None") # Optional logging if needed
    if "takeProfit" not in params and "stopLoss" not in params: print("   No valid TP/SL params formatted."); return False
    print(f"   Sending Params: {params}")
    try:
        resp = session.set_trading_stop(**params)
        print(f"   API Resp: {json.dumps(resp)}")
        if resp.get('retCode')==0: print(f"   >>> Success."); return True
        else: print(f"   !!! Failed: {resp.get('retMsg')} ({resp.get('retCode')})"); return False
    except Exception as e: print(f"   !!! Error setting TP/SL: {e}"); return False

# (place_safety_order remains same as v19)
def place_safety_order(session, symbol_info, side, qty, price, current_liq_price):
    if not session: return None
    print(f"--- Placing Safety Order ---")
    try:
        min_qty=symbol_info['minOrderQty']; max_qty=symbol_info['maxOrderQty']; qty_step=symbol_info['qtyStep']; qty_prec=symbol_info['qtyPrecision']; price_prec=symbol_info['pricePrecision']
        if current_liq_price > 0:
             danger_mult = (1+config.SAFETY_ORDER_LIQ_BUFFER_PERCENT/100.0) if side=="Buy" else (1-config.SAFETY_ORDER_LIQ_BUFFER_PERCENT/100.0); danger_p = current_liq_price*danger_mult
             print(f"   Checking SO vs Liq Danger ({config.SAFETY_ORDER_LIQ_BUFFER_PERCENT}%): SO Price={price:.{price_prec}f}, Danger Price={danger_p:.{price_prec}f}")
             is_safe = (side=="Buy" and price>danger_p) or (side=="Sell" and price<danger_p)
             if not is_safe: print("   !!! Safety Check FAILED! SO too close to Liq."); return None
             else: print("   Safety check PASSED.")
        else: print("   Warn: No valid Liq Price for safety check.")
        qty_d = Decimal(str(qty)); min_d=Decimal(str(min_qty)); max_d=Decimal(str(max_qty)); step_d=Decimal(str(qty_step))
        if qty_d < min_d: qty_d=min_d
        elif qty_d > max_d: qty_d=max_d
        if step_d > 0: qty_d=(qty_d//step_d)*step_d
        final_qty=float(qty_d); fmt_qty=utils.format_qty(final_qty, qty_prec); fmt_price=utils.format_price(price, price_prec)
        if not fmt_qty or final_qty < min_qty or not fmt_price: print(f"   !!! Invalid qty/price. Qty={fmt_qty}, Price={fmt_price}"); return None
        print(f"   {config.SYMBOL}, {side}, Qty: {fmt_qty}, Price: {fmt_price}")
        resp = session.place_order(category=config.CATEGORY, symbol=config.SYMBOL, side=side, orderType="Limit", qty=fmt_qty, price=fmt_price, timeInForce="GTC")
        print(f"   API Resp: {json.dumps(resp)}")
        if resp.get('retCode')==0 and resp['result'].get('orderId'): print(f"   >>> Success! SO ID: {resp['result']['orderId']}"); return resp['result']['orderId']
        else: print(f"   !!! Failed: {resp.get('retMsg')} ({resp.get('retCode')})"); return None
    except Exception as e: print(f"   !!! Error placing SO: {e}"); return None

# (cancel_order remains same as v19)
def cancel_order(session, order_id):
    if not session or not order_id: return False
    print(f"--- Attempting to Cancel Order ID: {order_id} ---")
    try:
        resp = session.cancel_order(category=config.CATEGORY, symbol=config.SYMBOL, orderId=order_id)
        print(f"   API Resp: {json.dumps(resp)}")
        if resp.get('retCode') == 0: print(f"   >>> Success! Cancelled order {order_id}."); return True
        else:
            error_msg = resp.get('retMsg', '').lower()
            # Treat "already filled/cancelled/not found" errors as success for our purpose
            if resp.get('retCode') == 10001 and ('order not exists' in error_msg or 'order has been filled' in error_msg or 'has been cancelled' in error_msg):
                 print(f"   Order {order_id} likely already inactive (Code: {resp.get('retCode')}). Treating as success for cancel.")
                 return True
            print(f"   !!! Failed cancel order {order_id}: {resp.get('retMsg')} ({resp.get('retCode')})"); return False
    except Exception as e: print(f"   !!! Error cancelling order {order_id}: {e}"); return False