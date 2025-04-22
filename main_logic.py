# === main_logic.py (v20 - TSL to BE After Last SO + Profit Threshold) ===
import time
import math
from decimal import Decimal
import config
import state_manager
import bybit_client
import indicators
import order_manager
import position_manager
import journal

def run_bot_cycle(session, bot_state, symbol_info):
    """Main logic cycle - v20 TSL Activation Includes Profit Check"""
    if not session or not symbol_info: print("Error: Session/symbol_info missing."); return bot_state
    print(f"\n----- {time.strftime('%Y-%m-%d %H:%M:%S')} Running Check -----")

    bot_state = state_manager.load_state()
    print(f"State: InTrade={bot_state.get('is_in_trade')}, PendingEntry={bot_state.get('pending_entry_order_id')}, PlacedTime={bot_state.get('pending_order_placed_timestamp')}, FilledSOs={bot_state.get('filled_safety_orders_count')}, BaseQty={bot_state.get('calculated_base_qty_this_cycle')}, ActiveSOs={len(bot_state.get('active_safety_order_ids'))}, TSLActive={bot_state.get('tsl_activated_this_trade')}")

    was_in_trade = bot_state.get('is_in_trade', False)
    fill_detected_this_cycle = False

    # --- Check Status of Pending Entry Order FIRST ---
    pending_entry_id = bot_state.get('pending_entry_order_id')
    if pending_entry_id:
        # (Pending entry check logic remains same as v19, including timeout)
        print(f"Checking status of pending entry order: {pending_entry_id}")
        order_status = position_manager.get_order_status(session, pending_entry_id)
        print(f"DEBUG Main: Status returned for {pending_entry_id}: '{order_status}'")
        if order_status == "Filled":
            # ... (Handle fill: set state, calc/set initial TP/SL - same as v19) ...
            print(f"   >>> Base Order {pending_entry_id} Filled! Entering trade state.")
            bot_state['pending_entry_order_id'] = None; bot_state['pending_order_placed_timestamp'] = 0; bot_state['is_in_trade'] = True; bot_state['current_trade_entry_timestamp'] = int(time.time()*1000); bot_state['filled_safety_orders_count'] = 0; bot_state['active_safety_order_ids'] = []; bot_state['tsl_activated_this_trade'] = False
            try:
                entry_pos_details = position_manager.get_current_position(session)
                if entry_pos_details:
                    entry_p = entry_pos_details['avg_entry_price']; entry_side = entry_pos_details['side']
                    bot_state['current_trade_side'] = entry_side; bot_state['current_trade_avg_price'] = entry_p
                    print(f"   DEBUG Main: Pos fetched. AvgP={entry_p}, Side={entry_side}. Calc TP/SL...")
                    effective_tp_percent = config.TAKE_PROFIT_PERCENT + config.ESTIMATED_TOTAL_FEE_PERCENT
                    tp_mult=(1+effective_tp_percent/100.0) if entry_side=="Buy" else (1-effective_tp_percent/100.0); tp_p_exec=entry_p*tp_mult
                    sl_mult=(1-config.STOP_LOSS_PERCENT_FOR_SIZING/100.0) if entry_side=="Buy" else (1+config.STOP_LOSS_PERCENT_FOR_SIZING/100.0); sl_p_exec=entry_p*sl_mult
                    print(f"   DEBUG Main: Calc TP={tp_p_exec:.{symbol_info['pricePrecision']}f}, SL={sl_p_exec:.{symbol_info['pricePrecision']}f}. Setting...")
                    if order_manager.set_position_tp_sl(session, symbol_info, take_profit_price=tp_p_exec, stop_loss_price=sl_p_exec): print("   DEBUG Main: TP/SL set OK.")
                    else: print("   !!! Warn: Failed set initial TP/SL post-fill.")
                    state_manager.save_state(bot_state); print(f"   DEBUG Main: State saved.")
                else: print("   !!! Err: Pos not found after fill!"); bot_state['pending_entry_order_id'] = None; bot_state['is_in_trade'] = False; state_manager.save_state(bot_state)
            except Exception as e: print(f"   !!! Err setting TP/SL: {e}"); bot_state['pending_entry_order_id'] = None; bot_state['is_in_trade'] = False; state_manager.save_state(bot_state)
            return bot_state
        elif order_status in ["Cancelled", "Rejected", "NotFound"]:
             # ... (Handle cancel/reject - same as v19) ...
            print(f"DEBUG Main: Status '{order_status}'. Clearing pending state."); print(f"   Base Order {pending_entry_id} is {order_status}. Clearing pending state.")
            bot_state['pending_entry_order_id'] = None; bot_state['calculated_base_qty_this_cycle'] = 0.0; bot_state['pending_order_placed_timestamp'] = 0; bot_state['tsl_activated_this_trade'] = False
            state_manager.save_state(bot_state); return bot_state
        elif order_status in ["New", "PartiallyFilled"]:
             # Check Timeout
             placed_time = bot_state.get('pending_order_placed_timestamp', 0)
             if placed_time > 0:
                 elapsed_time = int(time.time()) - placed_time; print(f"   Base order {pending_entry_id} still {order_status}. Elapsed: {elapsed_time}s / Timeout: {config.PENDING_ORDER_TIMEOUT_SECONDS}s")
                 if elapsed_time > config.PENDING_ORDER_TIMEOUT_SECONDS:
                     print(f"   !!! Pending order TIMEOUT exceeded. Cancelling {pending_entry_id}...")
                     if order_manager.cancel_order(session, pending_entry_id): print(f"   Successfully cancelled or confirmed inactive.")
                     else: print(f"   Warn: Failed cancel order {pending_entry_id}.")
                     bot_state['pending_entry_order_id'] = None; bot_state['calculated_base_qty_this_cycle'] = 0.0; bot_state['pending_order_placed_timestamp'] = 0; bot_state['tsl_activated_this_trade'] = False
                     state_manager.save_state(bot_state); print("   Pending state cleared due to timeout."); return bot_state
                 else: return bot_state # Not timed out, wait
             else: print("   Warn: Pending timestamp missing."); return bot_state
        else: print(f"DEBUG Main: Unknown status ('{order_status}'). Waiting."); return bot_state


    # --- Check for SO Fills if NOT checking pending entry ---
    if bot_state.get('is_in_trade'):
        fill_detected_this_cycle = position_manager.check_safety_order_fills(session, bot_state)
        if fill_detected_this_cycle: bot_state = state_manager.load_state()

    # --- Get Current Position Info AGAIN ---
    position_details = position_manager.get_current_position(session)
    current_pos_size = position_details['size'] if position_details else 0
    current_avg_price = position_details['avg_entry_price'] if position_details else 0.0
    current_side = position_details['side'] if position_details else None
    current_liq_price = position_details['liq_price'] if position_details else 0.0

    # --- Detect Trade Exit & Log ---
    if bot_state.get('is_in_trade') and current_pos_size == 0:
        print("\n--- Position Closed! Logging Journal Entry & Resetting State ---")
        # (Logging logic remains same...)
        try:
            pnl_resp = session.get_closed_pnl(category=config.CATEGORY, symbol=config.SYMBOL, limit=1)
            if pnl_resp.get('retCode') == 0 and pnl_resp['result'].get('list'):
                trade_log_entry = journal.format_trade_data(bot_state, pnl_resp['result']['list'][0])
                if trade_log_entry: journal.log_trade_to_csv(trade_log_entry)
            else: print(f"Warn: Could not fetch closed PNL: {pnl_resp.get('retMsg')}")
        except Exception as e: print(f"Err logging trade: {e}")
        finally:
            bot_state = config.INITIAL_STATE.copy(); state_manager.save_state(bot_state); print("   Trade state reset.")
        return bot_state

    # --- TP/SL Adjustment & TSL Activation on SO Fill ---
    if fill_detected_this_cycle and current_pos_size > 0 :
        print("\n--- SO Fill Detected This Cycle! Adjusting TP/SL & Checking TSL ---")
        entry_p = current_avg_price; side = current_side # Use latest fetched data
        if entry_p > 0 and side:
            bot_state['current_trade_avg_price'] = entry_p; # Update state avg price first

            # Recalculate Standard TP/SL
            effective_tp_percent = config.TAKE_PROFIT_PERCENT + config.ESTIMATED_TOTAL_FEE_PERCENT
            tp_mult=(1+effective_tp_percent/100.0) if side=="Buy" else (1-effective_tp_percent/100.0); new_tp = entry_p*tp_mult
            sl_mult=(1-config.STOP_LOSS_PERCENT_FOR_SIZING/100.0) if side=="Buy" else (1+config.STOP_LOSS_PERCENT_FOR_SIZING/100.0); new_sl = entry_p*sl_mult
            print(f"   New Avg Entry: {entry_p:.{symbol_info['pricePrecision']}f}"); print(f"   Recalc TP ({effective_tp_percent}%): {new_tp:.{symbol_info['pricePrecision']}f}"); print(f"   Recalc SL ({config.STOP_LOSS_PERCENT_FOR_SIZING}%): {new_sl:.{symbol_info['pricePrecision']}f}")
            tp_sl_set_ok = order_manager.set_position_tp_sl(session, symbol_info, take_profit_price=new_tp, stop_loss_price=new_sl)
            if not tp_sl_set_ok: print("   !!! Warning: Failed update standard TP/SL after SO fill.")

            # --- Check for TSL Activation (Move to Breakeven IF Profit Met) ---
            current_filled_so_count = bot_state.get('filled_safety_orders_count', 0)
            tsl_already_active = bot_state.get('tsl_activated_this_trade', False)

            if current_filled_so_count == config.MAX_SAFETY_ORDERS and not tsl_already_active:
                print(f"--- Last SO ({config.MAX_SAFETY_ORDERS}) Filled. Checking TSL profit condition ---")
                mark_p = 0.0; current_pnl_percent = -1 # Default to prevent activation if price fetch fails
                try: # Fetch current price for PnL check
                    tick_resp = session.get_tickers(category=config.CATEGORY, symbol=config.SYMBOL)
                    if tick_resp.get('retCode') == 0 and tick_resp['result'].get('list'):
                         mark_p = float(tick_resp['result']['list'][0].get('markPrice', 0))
                except Exception as e: print(f"   Warn: Could not fetch ticker for TSL PnL check: {e}")

                if mark_p > 0 and entry_p > 0:
                     if side == "Buy": current_pnl_percent = ((mark_p - entry_p) / entry_p) * 100.0
                     elif side == "Sell": current_pnl_percent = ((entry_p - mark_p) / entry_p) * 100.0
                     print(f"   Current PnL %: {current_pnl_percent:.4f}%, Required TSL Threshold: {config.TSL_PROFIT_THRESHOLD_PERCENT}%")

                     if current_pnl_percent >= config.TSL_PROFIT_THRESHOLD_PERCENT:
                        print(f"   >>> Profit threshold met! Activating TSL (Moving SL to Breakeven) <<<")
                        breakeven_price = entry_p # Final average price
                        print(f"   Moving SL to final breakeven price: {breakeven_price:.{symbol_info['pricePrecision']}f}")
                        # Set ONLY SL, pass None for TP to keep existing TP
                        if order_manager.set_position_tp_sl(session, symbol_info, stop_loss_price=breakeven_price, take_profit_price=None):
                             print("   >>> Breakeven SL set successfully.")
                             bot_state['tsl_activated_this_trade'] = True # Set flag
                        else: print("   !!! Warning: Failed to set breakeven SL.")
                     else: print("   Profit threshold not yet met for TSL activation.")
                else: print("   Could not calculate PnL% for TSL check (missing prices).")
            # --- End TSL Activation Check ---

            state_manager.save_state(bot_state) # Save state after all updates
        else: print("   !!! No valid avgPrice/side after fill. TP/SL not adjusted.")


    # --- Logic if NO position is open AND NO pending entry ---
    # ( Entry Logic remains same as v19 )
    if current_pos_size == 0 and not bot_state.get('pending_entry_order_id'):
        print("No active position or pending entry. Checking trend & sizing...")
        trend = indicators.get_trend_and_rsi(session, symbol_info)
        if trend != "Neutral":
            order_side = trend; print(f"Bias: {order_side}. Calculating size & checking margin...")
            try:
                bal_resp=session.get_wallet_balance(accountType="UNIFIED"); tick_resp=session.get_tickers(category=config.CATEGORY,symbol=config.SYMBOL)
                if bal_resp.get('retCode')==0 and tick_resp.get('retCode')==0:
                    equity=0.0; mark_p=0.0
                    if bal_resp['result'].get('list'):
                        for c in bal_resp['result']['list'][0].get('coin',[]):
                             if c['coin']=='USDT': equity=float(c.get('equity',0)); break
                    if tick_resp['result'].get('list'): mark_p=float(tick_resp['result']['list'][0].get('markPrice',0))
                    if equity > 0 and mark_p > 0:
                        risk_amt=equity*(config.RISK_PER_TRADE_PERCENT/100.0); sl_mult_sz=(1-config.STOP_LOSS_PERCENT_FOR_SIZING/100.0) if order_side=="Buy" else (1+config.STOP_LOSS_PERCENT_FOR_SIZING/100.0); sl_p_sz=mark_p*sl_mult_sz; sl_dist=abs(mark_p-sl_p_sz)
                        if sl_dist > 0:
                            qty_raw=risk_amt/sl_dist; print(f"Equity:{equity:.4f}, Mark:{mark_p}, Risk:${risk_amt:.4f}, SLDist:${sl_dist:.{symbol_info['pricePrecision']}f}, RawQty:{qty_raw:.6f}")
                            min_qty = symbol_info['minOrderQty']; step_d = Decimal(str(symbol_info['qtyStep'])); target_qty = max(qty_raw, min_qty); target_qty_d = Decimal(str(target_qty));
                            if step_d > 0: target_qty_d = (target_qty_d // step_d) * step_d
                            final_target_qty = float(target_qty_d)
                            if final_target_qty < min_qty: print(f"Final qty {final_target_qty} < min {min_qty}. Aborting."); return bot_state
                            print(f"Target Qty: {final_target_qty:.{symbol_info['qtyPrecision']}f}")
                            proceed_with_order = False; current_config_leverage = float(config.LEVERAGE); max_allowed_leverage = float(symbol_info.get('leverageFilter',{}).get('maxLeverage', '100')); margin_buffer = 0.95
                            position_value = final_target_qty * mark_p; required_margin_current_lev = position_value / current_config_leverage if current_config_leverage > 0 else float('inf')
                            print(f"   Est Val:${position_value:.2f} | Need Margin({current_config_leverage}x):${required_margin_current_lev:.4f} | Avail:${equity*margin_buffer:.4f}")
                            if required_margin_current_lev <= equity * margin_buffer: print("   Sufficient margin."); proceed_with_order = True
                            else:
                                print("   Insufficient margin. Calc req lev..."); min_lev_needed = position_value/(equity*margin_buffer); req_lev = max(1.0, math.ceil(min_lev_needed)); print(f"   Min Lev Needed: {req_lev:.0f}x")
                                if req_lev > max_allowed_leverage: print(f"   !!! Req lev {req_lev:.0f}x > max {max_allowed_leverage}x."); proceed_with_order = False
                                else:
                                    print(f"   >>> Adjusting lev to {req_lev:.0f}x...");
                                    try:
                                        set_lev_resp=session.set_leverage(category=config.CATEGORY, symbol=config.SYMBOL, buyLeverage=str(int(req_lev)), sellLeverage=str(int(req_lev)))
                                        if set_lev_resp.get('retCode')==0 or set_lev_resp.get('retCode')==110043: print(f"   Lev set/confirmed @ {req_lev:.0f}x."); proceed_with_order=True; time.sleep(1)
                                        else: print(f"   !!! Failed adjust lev: {set_lev_resp.get('retMsg')}({set_lev_resp.get('retCode')})"); proceed_with_order=False
                                    except Exception as e: print(f"   !!! Err setting lev: {e}"); proceed_with_order=False
                            if proceed_with_order:
                                print(f"Placing LIMIT base order @ price: {mark_p}")
                                order_id, actual_base_qty = order_manager.place_base_order(session, symbol_info, order_side, final_target_qty, limit_price=mark_p)
                                if order_id and actual_base_qty > 0:
                                    bot_state['pending_entry_order_id'] = order_id; bot_state['calculated_base_qty_this_cycle'] = actual_base_qty; bot_state['current_trade_side'] = order_side; bot_state['pending_order_placed_timestamp'] = int(time.time())
                                    bot_state['is_in_trade'] = False; bot_state['current_trade_entry_timestamp'] = 0; bot_state['current_trade_avg_price'] = 0.0; bot_state['filled_safety_orders_count'] = 0; bot_state['active_safety_order_ids'] = []; bot_state['tsl_activated_this_trade'] = False
                                    state_manager.save_state(bot_state); print(f"   Base limit order {order_id} placed. State set to pending...")
                                else: print("Base limit order placement failed.")
                            else: print("Cannot proceed: Margin/Leverage issue or other check failed.")
                        else: print("SL dist zero.")
                    else: print("Could not get equity/price.")
                else: print(f"API Err fetch bal/tick: Bal={bal_resp.get('retCode')}, Tick={tick_resp.get('retCode')}")
            except Exception as e: print(f"Error sizing/entry: {e}")
        else: print("Trend Neutral.")


    # --- Logic if a position IS open AND confirmed (not pending) ---
    # (SO check logic remains same as v18)
    elif current_pos_size > 0 and not bot_state.get('pending_entry_order_id'):
        entry_p = current_avg_price; side = current_side; liq_p = current_liq_price
        print(f"\nPosition found (Side: {side}). Checking for safety order...")
        if abs(entry_p - bot_state.get('current_trade_avg_price', 0.0)) > 1e-9:
             bot_state['current_trade_avg_price'] = entry_p
        try:
            tick_resp = session.get_tickers(category=config.CATEGORY, symbol=config.SYMBOL)
            if tick_resp.get('retCode') == 0 and tick_resp['result'].get('list'):
                mark_p = float(tick_resp['result']['list'][0].get('markPrice', 0))
                print(f"Mark Price: {mark_p}")
                if mark_p > 0 and liq_p > 0:
                    current_filled_so_count = bot_state.get('filled_safety_orders_count', 0)
                    if current_filled_so_count < config.MAX_SAFETY_ORDERS:
                        current_step_pct = config.SAFETY_ORDER_STEP_PERCENT * (config.SAFETY_ORDER_STEP_SCALE ** current_filled_so_count)
                        print(f"   Checking for SO #{current_filled_so_count + 1} using Step: {current_step_pct:.2f}%")
                        dev_mult = (1 - current_step_pct / 100.0) if side == "Buy" else (1 + current_step_pct / 100.0)
                        so_trig_p = entry_p * dev_mult
                        print(f"   Calculated SO Trigger Price: {so_trig_p:.{symbol_info['pricePrecision']}f}")
                        trigger_hit = (side == "Buy" and mark_p <= so_trig_p) or \
                                      (side == "Sell" and mark_p >= so_trig_p)
                        if trigger_hit:
                            print(f"\n!!! SO TRIGGERED !!! (Filled Count: {current_filled_so_count})")
                            so_base_qty = bot_state.get('calculated_base_qty_this_cycle', 0.0)
                            if so_base_qty <= 0: print("Warn: Base Qty missing."); so_base_qty = symbol_info['minOrderQty']
                            so_qty = so_base_qty * (config.SAFETY_ORDER_VOLUME_SCALE ** current_filled_so_count)
                            new_so_id = order_manager.place_safety_order(session, symbol_info, side, so_qty, so_trig_p, liq_p)
                            if new_so_id:
                                if new_so_id not in bot_state.get('active_safety_order_ids', []):
                                    bot_state['active_safety_order_ids'].append(new_so_id)
                                    state_manager.save_state(bot_state)
                                    print(f"   Added {new_so_id} to active SO list.")
                                else: print(f"   Warn: SO ID {new_so_id} already active?")
                        else: print("Price not at SO trigger level.")
                    else: print(f"Max safety orders ({config.MAX_SAFETY_ORDERS}) already filled.")
                else: print("Mark/Liq price zero for SO check.")
            else: print(f"Ticker fetch err: {tick_resp.get('retMsg')}")
        except Exception as e: print(f"Error during SO check: {e}")
    # else: Covers other cases

    print(f"----- Check Cycle Complete -----")
    return bot_state # Return potentially modified state