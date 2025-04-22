# === position_manager.py (Add get_order_status) ===
import json
import time
import config
import state_manager # Used by check_safety_order_fills

def get_current_position(session):
    """Fetches and returns current position details dictionary or None."""
    # (Function remains the same as before)
    if not session: return None
    try:
        pos_resp = session.get_positions(category=config.CATEGORY, symbol=config.SYMBOL)
        if pos_resp.get('retCode') == 0 and pos_resp.get('result', {}).get('list'):
            pos_list = pos_resp['result']['list']
            if pos_list:
                pos = pos_list[0]; pos_size = float(pos.get('size', 0))
                if pos_size > 0:
                    details = {"size": pos_size, "avg_entry_price": float(pos.get('avgPrice', 0)), "side": pos.get('side'), "liq_price": float(pos.get('liqPrice', 0)) if pos.get('liqPrice') else 0.0}
                    print(f"Pos Found: Side={details['side']}, Size={details['size']}, Entry={details['avg_entry_price']}, Liq={details['liq_price'] if details['liq_price'] > 0 else 'N/A'}")
                    return details
                else: return None # Treat size 0 as no position
            else: return None
        else: print(f"Error get_positions: {pos_resp.get('retMsg')}"); return None
    except Exception as e: print(f"Error get_positions: {e}"); return None


def get_order_status(session, order_id):
    """Checks the status of a specific historical order ID."""
    if not session or not order_id:
        return None
    try:
        # Use get_order_history which includes final states reliably
        hist_resp = session.get_order_history(
            category=config.CATEGORY,
            orderId=order_id,
            limit=1 # We only need the status of this specific order
        )
        if hist_resp.get('retCode') == 0:
            order_list = hist_resp.get('result', {}).get('list', [])
            if order_list:
                status = order_list[0].get('orderStatus')
                print(f"   Checked Order {order_id}: Status = {status}")
                return status # e.g., Filled, PartiallyFilled, New, Cancelled, Rejected
            else:
                # Order might be too old for history limit, or ID wrong
                # Could also check get_open_orders as a fallback for 'New' status
                print(f"   Warning: Order ID {order_id} not found in recent history.")
                # Check open orders just in case it's still active
                open_resp = session.get_open_orders(category=config.CATEGORY, orderId=order_id, limit=1)
                if open_resp.get('retCode') == 0 and open_resp.get('result',{}).get('list'):
                    status = open_resp['result']['list'][0].get('orderStatus')
                    print(f"   Checked Open Order {order_id}: Status = {status}")
                    return status
                else:
                    print(f"   Order {order_id} not found in open orders either.")
                    return "NotFound" # Indicate it couldn't be found recently
        else:
            print(f"!!! Error fetching order history for {order_id}: {hist_resp.get('retMsg')}")
            return None
    except Exception as e:
        print(f"!!! Error in get_order_status for {order_id}: {e}")
        return None


def check_safety_order_fills(session, bot_state):
    """Checks status of active SOs, updates state if filled."""
    # (Function remains the same as before - uses get_order_history)
    if not session or not bot_state["active_safety_order_ids"]: return False

    print(f"\nChecking status of {len(bot_state['active_safety_order_ids'])} active SO ID(s): {bot_state['active_safety_order_ids']}")
    fill_occurred = False; orders_to_remove = []; active_set = set(bot_state["active_safety_order_ids"])

    try:
        history_resp = session.get_order_history(category=config.CATEGORY, symbol=config.SYMBOL, limit=50) # Check recent history
        if history_resp.get('retCode') == 0:
            history_list = history_resp.get('result', {}).get('list', [])
            if history_list:
                for order in history_list:
                    order_id = order.get('orderId')
                    if order_id in active_set:
                        status = order.get('orderStatus')
                        print(f"   Checking Active SO ID {order_id}: Status = {status}")
                        if status in ["Filled", "PartiallyFilledCanceled", "Cancelled", "Rejected"]:
                             if status == "Filled":
                                 print(f"   >>> Safety Order Filled! ID: {order_id}")
                                 bot_state["filled_safety_orders_count"] += 1 # Increment FILLED count
                                 fill_occurred = True
                             else: print(f"   Safety Order {status}. ID: {order_id}")
                             orders_to_remove.append(order_id)
                             active_set.remove(order_id)
            # else: print("   Order history list is empty.") # Can be noisy
        else: print(f"!!! Error fetching order history: {history_resp.get('retMsg')}")
    except Exception as e: print(f"!!! Error checking SO fills: {e}")

    if orders_to_remove:
        print(f"   Removing final state SO IDs: {orders_to_remove}")
        bot_state["active_safety_order_ids"] = [oid for oid in bot_state["active_safety_order_ids"] if oid not in orders_to_remove]
        state_manager.save_state(bot_state)

    return fill_occurred