import time
import datetime
import ccxt
import traceback
import json
import math
from strategy import (
    evaluate_coin, check_volume_spike, check_breakout, check_mean_reversion
)
from utils import (
    fetch_ohlc_data, load_api_keys, place_order, sell_order,
    get_balance, save_trading_history, load_trading_history
)
from adaptive_parameters import AdaptiveParameters
from market_condition import detect_market_condition
from exit_strategies import (
    update_trailing_stops, check_partial_profit_exits,
    check_time_based_exits
)

def print_gain_visual(daily, weekly):
    bar = lambda v: ("+" * int(v // 10) if v > 0 else "-" * int(abs(v) // 10)) if abs(v) >= 10 else ""
    print(f"[PNL] Daily: ${daily:.2f} {bar(daily)}   Weekly: ${weekly:.2f} {bar(weekly)}")

print("==== ADVANCED MULTI-STRATEGY MEME COIN TRADING BOT ====")
print("WARNING: This bot will execute REAL trades with REAL money!")
print("Using 4 STRATEGIES: MOMENTUM + VOLUME SPIKE + BREAKOUT + MEAN REVERSION")
print("Scalping exit system (NO FIXED TP, -10% SL, dynamic trailing stops)")
print("Trailing stops: 1% at 5%, 3% at 12%, 5% at 20%, 8% at 30%, 10% at 40%, 15% at 50%+")
print("Reinvest profits only every Sunday (weekly compounding)")
print("Press Ctrl+C now if you want to stop before trading begins.")
time.sleep(5)

api_key, api_secret = load_api_keys()

exchange = ccxt.kraken({
    'apiKey': api_key,
    'secret': api_secret,
    'enableRateLimit': True
})
print("Loading available markets from Kraken...")
exchange.load_markets()
try:
    balances = get_balance(exchange)
    usd_balance = balances.get('USD', 0)
    print(f"Account USD Balance: ${usd_balance:.2f}")
except Exception as e:
    print(f"[ERROR] Could not get account balance: {e}")

trading_history = load_trading_history()
print(f"Loaded trading history with {len(trading_history['trades'])} previous trades")
cooldown_until = trading_history.get('cooldown_until')
if cooldown_until and datetime.datetime.fromisoformat(cooldown_until) > datetime.datetime.now(datetime.timezone.utc):
    print(f"[NOTICE] Bot is in cooldown until {cooldown_until} due to excessive losses")
    proceed = input("Override cooldown and proceed anyway? (y/n): ")
    if proceed.lower() != 'y':
        print("Respecting cooldown period. Bot shutting down.")
        exit(0)
    else:
        print("Cooldown overridden by user.")
        trading_history['cooldown_until'] = None

params = AdaptiveParameters()
print("Initialized adaptive parameter system")
portfolio = {}
usdc = 'USDC/USD'

# === SCAN ALL KRAKEN USD PAIRS ===
all_symbols = exchange.symbols
usd_pairs = [s for s in all_symbols if s.endswith('/USD') and s != usdc]
valid_coins = [coin for coin in usd_pairs]
print("\nAvailable coins for trading (all Kraken USD pairs):")
for coin in valid_coins:
    print(f"- {coin}")
if not valid_coins:
    print("[ERROR] No USD trading pairs available on Kraken.")
    exit(1)

max_positions = 10
ohlcv_data = {}

# Weekly compounding logic
if "weekly_investment" not in trading_history:
    trading_history["weekly_investment"] = {}
if "last_week_start" not in trading_history:
    now = datetime.datetime.now(datetime.timezone.utc)
    last_sunday = now - datetime.timedelta(days=now.weekday() + 1)
    last_sunday = last_sunday.replace(hour=0, minute=0, second=0, microsecond=0)
    trading_history["last_week_start"] = last_sunday.isoformat()
if "base_position_size" not in trading_history:
    trading_history["base_position_size"] = float(balances.get("USD", 0)) / max_positions

print("\n=== TRADING RULES (SCALPING, WEEKLY REINVEST) ===")
print("1. Entry: Multi-strategy signals")
print("2. Exit: Dynamic trailing stops (NO fixed TP), SL at -10%")
print("3. Only reinvest USD gains every Sunday; during the week, profits stay in USD")
print("4. Position size: invest base_position_size per position until Sunday")
print("5. Visual daily/weekly gain bar shown each cycle")
print("==== LIVE TRADING STARTED ====\n")

def get_base_position_size():
    now = datetime.datetime.now(datetime.timezone.utc)
    last_week = datetime.datetime.fromisoformat(trading_history["last_week_start"])
    if now.weekday() == 6 and (now - last_week).days >= 7:
        try:
            balances = get_balance(exchange)
            usd_balance = balances.get('USD', 0)
        except Exception:
            usd_balance = sum([pos['allocation'] for pos in portfolio.values()])
        new_base = usd_balance / max_positions if usd_balance > 0 else trading_history["base_position_size"]
        trading_history["base_position_size"] = new_base
        trading_history["last_week_start"] = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        print(f"\n[SUNDAY] Reinvesting: new base position size = ${new_base:.2f} per position")
        save_trading_history(trading_history)
    return trading_history["base_position_size"]

def compute_pnl(trades, days=1):
    now = datetime.datetime.now(datetime.timezone.utc)
    cutoff = now - datetime.timedelta(days=days)
    pnl = sum(t.get("profit_usd", 0) for t in trades if "close_time" in t and datetime.datetime.fromisoformat(t["close_time"]) > cutoff)
    return pnl

def get_trailing_stop(pct_gain):
    # Trailing stops: 1% at 5%, 3% at 12%, 5% at 20%, 8% at 30%, 10% at 40%, 15% at 50%+
    # Returns the trailing stop distance (as a positive percent)
    if pct_gain >= 50:
        return 15.0
    elif pct_gain >= 40:
        return 10.0
    elif pct_gain >= 30:
        return 8.0
    elif pct_gain >= 20:
        return 5.0
    elif pct_gain >= 12:
        return 3.0
    elif pct_gain >= 5:
        return 1.0
    else:
        return None  # No trailing stop below 5%

try:
    while True:
        loop_start_time = datetime.datetime.now(datetime.timezone.utc)
        print(f"\n--- Cycle Start --- {loop_start_time.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        try:
            balances = get_balance(exchange)
            usd_balance = balances.get('USD', 0)
            print(f"Current USD Balance: ${usd_balance:.2f}")
        except Exception as e:
            print(f"[ERROR] Could not update account balance: {e}")
            usd_balance = 0

        position_size = get_base_position_size()

        daily_pnl = compute_pnl(trading_history['trades'], days=1)
        weekly_pnl = compute_pnl(trading_history['trades'], days=7)
        print_gain_visual(daily_pnl, weekly_pnl)

        market_info = detect_market_condition(exchange)
        market_condition = market_info['condition']
        market_description = market_info.get('description', '')
        print(f"[MARKET] Detected {market_condition} market condition")
        print(f"[MARKET] {market_description}")
        params.update_statistics(trading_history, market_condition)
        params.print_current_settings()
        if trading_history.get('cooldown_until') and datetime.datetime.fromisoformat(trading_history['cooldown_until']) > loop_start_time:
            cooldown_time = datetime.datetime.fromisoformat(trading_history['cooldown_until'])
            print(f"[COOLDOWN] Bot is in cooldown until {cooldown_time.strftime('%Y-%m-%d %H:%M:%S UTC')}")
            print(f"Cooling down for {(cooldown_time - loop_start_time).total_seconds() / 3600:.1f} more hours")
            print("Will check portfolio but not make new trades")
        open_positions = len(portfolio)
        print(f"Open positions: {open_positions}/{max_positions}")
        # --- Use batch ticker fetching for all open positions ---
        symbols_to_check = list(portfolio.keys())
        if symbols_to_check:
            try:
                tickers = exchange.fetch_tickers(symbols_to_check)
            except Exception as e:
                print(f"[ERROR] Could not fetch batch tickers: {e}")
                tickers = {}
        else:
            tickers = {}
        if open_positions < max_positions and not (trading_history.get('cooldown_until') and datetime.datetime.fromisoformat(trading_history['cooldown_until']) > loop_start_time):
            momentum_candidates = []
            volume_spike_candidates = []
            breakout_candidates = []
            mean_reversion_candidates = []
            for coin in valid_coins:
                if coin == usdc or coin in portfolio:
                    continue
                try:
                    ohlcv = fetch_ohlc_data(exchange, coin)
                    if ohlcv is not None and len(ohlcv) > 0:
                        ohlcv_data[coin] = ohlcv
                        result = evaluate_coin(ohlcv, coin, params.get_parameters())
                        if result:
                            strategy_type = result.get('strategy')
                            if strategy_type == 'MOMENTUM':
                                momentum_candidates.append(result)
                            elif strategy_type == 'VOLUME_SPIKE':
                                volume_spike_candidates.append(result)
                            elif strategy_type == 'BREAKOUT':
                                breakout_candidates.append(result)
                            elif strategy_type == 'MEAN_REVERSION':
                                mean_reversion_candidates.append(result)
                except Exception as e:
                    print(f"[ERROR] {coin}: {e}")
            all_candidates = []
            if momentum_candidates:
                momentum_candidates.sort(key=lambda x: (-x['rank_factor'], -x['vol']))
                print(f"Found {len(momentum_candidates)} MOMENTUM candidates")
                golden_cross_count = sum(1 for c in momentum_candidates if c.get('golden_cross_active', False))
                if golden_cross_count > 0:
                    print(f"  - {golden_cross_count} candidates with active Golden Cross")
                all_candidates.extend(momentum_candidates)
            if volume_spike_candidates:
                volume_spike_candidates.sort(key=lambda x: (-x['rank_factor'], -x['vol']))
                print(f"Found {len(volume_spike_candidates)} VOLUME SPIKE candidates")
                all_candidates.extend(volume_spike_candidates)
            if breakout_candidates:
                breakout_candidates.sort(key=lambda x: (-x['rank_factor'], -x['vol']))
                print(f"Found {len(breakout_candidates)} BREAKOUT candidates")
                all_candidates.extend(breakout_candidates)
            if mean_reversion_candidates:
                mean_reversion_candidates.sort(key=lambda x: (-x['rank_factor'], -x['vol']))
                print(f"Found {len(mean_reversion_candidates)} MEAN REVERSION candidates")
                all_candidates.extend(mean_reversion_candidates)
            if all_candidates:
                all_candidates.sort(key=lambda x: -x['rank_factor'])
                print(f"Found total of {len(all_candidates)} potential buying candidates across all strategies")
                filtered_candidates = []
                for entry in all_candidates:
                    strategy = entry.get('strategy')
                    include = True
                    if market_condition.startswith("VOLATILE"):
                        if strategy not in ['MEAN_REVERSION']:
                            if strategy in ['BREAKOUT', 'MOMENTUM'] and entry['rank_factor'] < 1.5 * params.momentum_score_threshold:
                                include = False
                    elif market_condition.startswith("RANGING"):
                        if strategy == 'MOMENTUM' and entry['rank_factor'] < 1.2 * params.momentum_score_threshold:
                            include = False
                    elif market_condition.startswith("TRENDING_BULLISH"):
                        if strategy in ['MEAN_REVERSION'] and 'z_score' in entry and entry['z_score'] > -3.0:
                            include = False
                    elif market_condition.startswith("TRENDING_BEARISH"):
                        if entry['rank_factor'] < 1.8 * params.momentum_score_threshold:
                            include = False
                    if include:
                        filtered_candidates.append(entry)
                print(f"Filtered to {len(filtered_candidates)} candidates based on {market_condition} market")
                filtered_candidates.sort(key=lambda x: -x['rank_factor'])
                filtered_candidates = filtered_candidates[:max_positions]
                print(f"Selected top {len(filtered_candidates)} candidates based on rank factor")
                for entry in filtered_candidates:
                    if len(portfolio) >= max_positions:
                        break
                    symbol = entry['symbol']
                    allocation = position_size
                    price = entry['price']
                    strategy = entry.get('strategy', 'UNKNOWN')
                    recent_loss = False
                    for trade in trading_history['trades']:
                        if trade['symbol'] == symbol and trade.get('profit_pct', 0) < 0:
                            trade_time = datetime.datetime.fromisoformat(trade['close_time']) if isinstance(trade['close_time'], str) else trade['close_time']
                            if (loop_start_time - trade_time).total_seconds() < 21600:
                                recent_loss = True
                                break
                    if recent_loss:
                        print(f"[SKIP] {symbol} - Recently closed with loss, skipping for 12h cooldown")
                        continue
                    coin_amount = allocation / price
                    try:
                        market = exchange.market(symbol)
                        amount_precision = market.get('precision', {}).get('amount', 8)
                        min_amount = market.get('limits', {}).get('amount', {}).get('min', 0)
                    except Exception:
                        amount_precision = 8
                        min_amount = 0
                    factor = 10 ** amount_precision
                    coin_amount = int(coin_amount * factor) / factor
                    if min_amount and coin_amount < min_amount:
                        coin_amount = min_amount
                    actual_cost = coin_amount * price
                    if actual_cost > allocation * 1.01:
                        coin_amount = int((allocation / price) * factor) / factor
                        actual_cost = coin_amount * price
                    if coin_amount <= 0 or actual_cost > allocation * 1.01:
                        print(f"[SKIP] {symbol}: Coin amount too small or would exceed allocation. Skipping buy.")
                        continue
                    print(f"[DEBUG] Buying {coin_amount} {symbol} at ${price:.2f} (Total: ${actual_cost:.2f}, Allocation: ${allocation:.2f})")
                    order = place_order(exchange, symbol, coin_amount)
                    if order:
                        print(f"[BUY - {strategy}] {symbol} @ {price} | Allocated: ${allocation:.2f} | Amount: {coin_amount:.8f}")
                        portfolio[symbol] = {
                            'entry': price,
                            'allocation': allocation,
                            'amount': coin_amount,
                            'timestamp': loop_start_time,
                            'highest': price,
                            'lowest': price,
                            'strategy': strategy,
                            'order_id': order.get('id', 'unknown'),
                            'trailing_stop': None,
                            'max_price': price
                        }
                    time.sleep(2)
            else:
                print("No candidates found that meet any strategy criteria")
                params.adjust_parameters(0)
        print("\n--- Portfolio Summary ---")
        total_value = 0
        symbols_to_remove = []
        total_cycles_losses = 0
        for symbol, pos in portfolio.items():
            try:
                ticker = tickers.get(symbol)
                if ticker is not None and 'last' in ticker and ticker['last'] is not None:
                    last_price = ticker['last']
                    pos['current_price'] = last_price
                    gain = (last_price - pos['entry']) / pos['entry'] * 100
                    value = pos['allocation'] * (1 + gain / 100)
                    total_value += value
                    if 'high' in ticker and ticker['high'] > pos.get('highest', 0):
                        pos['highest'] = ticker['high']
                    if last_price < pos.get('lowest', float('inf')):
                        pos['lowest'] = last_price
                    entry_time = pos['timestamp'] if isinstance(pos['timestamp'], datetime.datetime) else datetime.datetime.fromisoformat(pos['timestamp'])
                    hours_held = (loop_start_time - entry_time).total_seconds() / 3600
                    time_str = f"{int(hours_held)}h {int(hours_held % 1 * 60)}m"
                    strategy = pos.get('strategy', 'UNKNOWN')
                    print(f"[HOLD - {strategy}] {symbol}: {gain:.2f}% | Value: ${value:.2f} | Entry: ${pos['entry']} | " +
                          f"Current: ${last_price} | Time: {time_str}")
                    print(f"[DEBUG] {symbol}: gain={gain:.2f}%, entry={pos['entry']}, last={last_price}, at {loop_start_time}")
                    
                    # Check if we need to update or set trailing stop
                    trailing_dist = get_trailing_stop(gain)
                    if trailing_dist is not None:
                        # Update max price
                        if last_price > pos.get('max_price', pos['entry']):
                            pos['max_price'] = last_price
                        
                        # Set or update trailing stop
                        if ('trailing_stop' not in pos) or (pos['trailing_stop'] is None):
                            pos['trailing_stop'] = pos['max_price'] * (1 - trailing_dist/100)
                            print(f"[TRAILING] {symbol}: Activated {trailing_dist:.1f}% trailing stop at ${pos['trailing_stop']:.4f}")
                        else:
                            # Only move up the stop (never down)
                            candidate_stop = pos['max_price'] * (1 - trailing_dist/100)
                            if candidate_stop > pos['trailing_stop']:
                                old_stop = pos['trailing_stop']
                                pos['trailing_stop'] = candidate_stop
                                print(f"[TRAILING] {symbol}: Updated stop from ${old_stop:.4f} to ${pos['trailing_stop']:.4f} ({trailing_dist:.1f}%)")
                        print(f"[TRAILING] {symbol}: gain={gain:.2f}% target={trailing_dist:.1f}% stop=${pos['trailing_stop']:.4f} max=${pos['max_price']:.4f}")
                    else:
                        pos['trailing_stop'] = None
                        pos['max_price'] = max(pos.get('max_price', last_price), last_price)
                else:
                    print(f"[WARNING] Could not get ticker for {symbol}")
            except Exception as e:
                print(f"[ERROR] Updating {symbol}: {e}")
        
        if portfolio:
            print("\n--- Applying Exit Logic ---")
            for symbol, pos in portfolio.items():
                if symbol in symbols_to_remove:
                    continue
                last_price = pos.get('current_price')
                if not last_price:
                    continue
                entry_price = pos['entry']
                gain = (last_price / entry_price - 1) * 100
                sell_reason = None
                sell_percentage = 100
                
                # First check for stop loss (now at -10%)
                if gain <= -10:
                    sell_reason = "STOP_LOSS_-10%"
                # Then check for trailing stop hit
                elif pos.get('trailing_stop') and last_price <= pos['trailing_stop']:
                    sell_reason = f"TRAILING_STOP_{gain:.2f}%"
                
                # NO explicit take profit check - trailing stops handle that
                
                if sell_reason:
                    print(f"[DEBUG] Attempting to sell {symbol} at {last_price} (reason: {sell_reason})")
                    order = sell_order(exchange, symbol, pos['amount'], sell_percentage)
                    print(f"[DEBUG] Sell order result: {order}")
                    if order:
                        strategy = pos.get('strategy', 'UNKNOWN')
                        print(f"[SELL - {sell_reason}] {symbol} @ {last_price} | Gain: {gain:.2f}% | " + 
                              f"Strategy: {strategy} | Amount: {pos['amount']:.8f}")
                        entry_time = pos['timestamp'] if isinstance(pos['timestamp'], datetime.datetime) else datetime.datetime.fromisoformat(pos['timestamp'])
                        hours_held = (loop_start_time - entry_time).total_seconds() / 3600
                        trade_record = {
                            'symbol': symbol,
                            'entry_price': entry_price,
                            'exit_price': last_price,
                            'amount': pos['amount'],
                            'profit_usd': (last_price - entry_price) * pos['amount'],
                            'profit_pct': gain,
                            'reason': sell_reason,
                            'strategy': pos.get('strategy', 'UNKNOWN'),
                            'open_time': entry_time.isoformat(),
                            'close_time': loop_start_time.isoformat(),
                            'hours_held': hours_held
                        }
                        trading_history['trades'].append(trade_record)
                        if gain < 0:
                            loss_amount = abs(trade_record['profit_usd'])
                            trading_history['last_24h_losses'] = trading_history.get('last_24h_losses', 0) + loss_amount
                            total_cycles_losses += loss_amount
                        symbols_to_remove.append(symbol)
        
        for symbol in symbols_to_remove:
            if symbol in portfolio:
                del portfolio[symbol]
        
        cutoff_time = loop_start_time - datetime.timedelta(hours=24)
        recent_losses = 0
        for trade in trading_history['trades']:
            if 'close_time' in trade:
                trade_time = datetime.datetime.fromisoformat(trade['close_time']) if isinstance(trade['close_time'], str) else trade['close_time']
                if trade_time > cutoff_time and trade.get('profit_pct', 0) < 0:
                    recent_losses += abs(trade.get('profit_usd', 0))
        trading_history['last_24h_losses'] = recent_losses
        cooldown_threshold = trading_history["base_position_size"] * max_positions * 0.15
        if recent_losses >= cooldown_threshold and not trading_history.get('cooldown_until'):
            cooldown_until = loop_start_time + datetime.timedelta(hours=24)
            trading_history['cooldown_until'] = cooldown_until.isoformat()
            print(f"[ALERT] Excessive losses detected (${recent_losses:.2f} in 24h)!")
            print(f"[COOLDOWN] Entering 24h trading cooldown until {cooldown_until.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        save_trading_history(trading_history)
        print("\n--- Trading Performance By Strategy ---")
        strategies = ['MOMENTUM', 'VOLUME_SPIKE', 'BREAKOUT', 'MEAN_REVERSION']
        for strategy in strategies:
            trades = [t for t in trading_history['trades'] if t.get('strategy') == strategy]
            if trades:
                trades_count = len(trades)
                profit = sum(t.get('profit_usd', 0) for t in trades)
                wins = sum(1 for t in trades if t.get('profit_pct', 0) > 0)
                win_rate = (wins / trades_count) * 100
                print(f"{strategy} Strategy: {trades_count} trades | ${profit:.2f} profit | {win_rate:.1f}% win rate")
        print(f"\n[PORTFOLIO] Value: ${total_value:.2f} | Open Positions: {len(portfolio)}")
        loop_end_time = datetime.datetime.now(datetime.timezone.utc)
        print(f"--- Cycle complete. Loop duration: {(loop_end_time - loop_start_time).total_seconds():.2f}s. Waiting 10 seconds... ---")
        time.sleep(10)
except KeyboardInterrupt:
    print("\n\n=== Bot stopped by user ===")
    print("Final portfolio summary:")
    for symbol, pos in portfolio.items():
        try:
            ticker = exchange.fetch_ticker(symbol)
            if ticker and 'last' in ticker and ticker['last'] is not None:
                last_price = ticker['last']
                gain = (last_price - pos['entry']) / pos['entry'] * 100
                value = pos['allocation'] * (1 + gain / 100)
                strategy = pos.get('strategy', 'UNKNOWN')
                print(f"{symbol} [{strategy}]: {gain:.2f}% | Value: ${value:.2f} | Amount: {pos['amount']:.8f}")
                sell_now = input(f"Do you want to sell {symbol} now? (y/n): ")
                if sell_now.lower() == 'y':
                    order = sell_order(exchange, symbol, pos['amount'], 100)
                    if order:
                        print(f"[SELL] {symbol} sold at market price")
                        trade_record = {
                            'symbol': symbol,
                            'entry_price': pos['entry'],
                            'exit_price': last_price,
                            'amount': pos['amount'],
                            'profit_usd': (last_price - pos['entry']) * pos['amount'],
                            'profit_pct': gain,
                            'reason': "MANUAL EXIT",
                            'strategy': pos.get('strategy', 'UNKNOWN'),
                            'open_time': pos['timestamp'].isoformat() if isinstance(pos['timestamp'], datetime.datetime) else pos['timestamp'],
                            'close_time': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                            'hours_held': (datetime.datetime.now(datetime.timezone.utc) -
                                           (pos['timestamp'] if isinstance(pos['timestamp'], datetime.datetime)
                                            else datetime.datetime.fromisoformat(pos['timestamp']))).total_seconds() / 3600
                        }
                        trading_history['trades'].append(trade_record)
                        save_trading_history(trading_history)
        except Exception as e:
            print(f"{symbol}: Unable to fetch current price - {e}")
    print("\nTrading history summary:")
    total_trades = len(trading_history['trades'])
    winning_trades = sum(1 for t in trading_history['trades'] if t.get('profit_pct', 0) > 0)
    losing_trades = sum(1 for t in trading_history['trades'] if t.get('profit_pct', 0) < 0)
    if total_trades > 0:
        win_rate = winning_trades / total_trades * 100
        total_profit = sum(t.get('profit_usd', 0) for t in trading_history['trades'])
        print(f"Total trades: {total_trades}")
        print(f"Overall win rate: {win_rate:.2f}% ({winning_trades} wins, {losing_trades} losses)")
        print(f"Total profit/loss: ${total_profit:.2f}")
        strategies = ['MOMENTUM', 'VOLUME_SPIKE', 'BREAKOUT', 'MEAN_REVERSION']
        for strategy in strategies:
            trades = [t for t in trading_history['trades'] if t.get('strategy') == strategy]
            if trades:
                trades_count = len(trades)
                profit = sum(t.get('profit_usd', 0) for t in trades)
                wins = sum(1 for t in trades if t.get('profit_pct', 0) > 0)
                win_rate = (wins / trades_count) * 100
                print(f"{strategy} Strategy: {trades_count} trades | ${profit:.2f} profit | {win_rate:.1f}% win rate")
    else:
        print("No completed trades yet")
except Exception as e:
    print(f"\n[CRITICAL ERROR] Unexpected error: {e}")
    traceback.print_exc()
    print("\nEmergency Portfolio Summary:")
    for symbol, pos in portfolio.items():
        strategy = pos.get('strategy', 'UNKNOWN')
        print(f"{symbol} [{strategy}]: Entry ${pos['entry']} | Amount: {pos['amount']:.8f}")
    print("\nBot stopped due to critical error. Please check your positions manually in Kraken.")