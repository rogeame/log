import pandas as pd
import numpy as np
from utils import fetch_ohlc_data

def calculate_ema(prices, period):
    alpha = 2 / (period + 1)
    ema = [prices[0]]
    for i in range(1, len(prices)):
        ema.append(alpha * prices[i] + (1 - alpha) * ema[i-1])
    return np.array(ema)

def calculate_atr_array(highs, lows, closes, period=14):
    if len(highs) <= period:
        return np.mean(highs - lows)
    tr1 = highs[-period:] - lows[-period:]
    tr2 = np.abs(highs[-period:] - np.roll(closes, 1)[-period:])
    tr3 = np.abs(lows[-period:] - np.roll(closes, 1)[-period:])
    tr = np.vstack([tr1, tr2, tr3]).max(axis=0)
    return np.mean(tr)

def calculate_bb_width_array(prices, period=20, num_std=2):
    if len(prices) < period:
        return 0
    ma = np.mean(prices[-period:])
    std = np.std(prices[-period:])
    if ma == 0:
        return 0
    upper = ma + num_std * std
    lower = ma - num_std * std
    return ((upper - lower) / ma) * 100

def calculate_rsi_array(prices, period=14):
    if len(prices) <= period:
        return 50
    deltas = np.diff(prices)
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)
    avg_gain = np.mean(gains[-period:])
    avg_loss = np.mean(losses[-period:])
    if avg_loss == 0:
        return 100
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def detect_market_condition(
    exchange, 
    timeframes=['5m', '15m', '1h', '4h'],
    reference_symbols=["BTC/USD", "ETH/USD", "SOL/USD"]
):
    try:
        aggregated_metrics = {
            'volatility': 0,
            'trending_strength': 0,
            'bullish_signals': 0,
            'bearish_signals': 0,
            'volume_intensity': 0,
            'total_samples': 0
        }

        bullish_count = 0
        bearish_count = 0
        ranging_count = 0
        volatile_count = 0

        for symbol in reference_symbols:
            for timeframe in timeframes:
                data = fetch_ohlc_data(exchange, symbol, timeframe=timeframe)
                if not isinstance(data, (list, tuple)) or len(data) < 30:
                    continue

                closes = np.array([c[4] for c in data if isinstance(c, (list, tuple)) and len(c) >= 6])
                highs = np.array([c[2] for c in data if isinstance(c, (list, tuple)) and len(c) >= 6])
                lows = np.array([c[3] for c in data if isinstance(c, (list, tuple)) and len(c) >= 6])
                volumes = np.array([c[5] for c in data if isinstance(c, (list, tuple)) and len(c) >= 6])

                if len(closes) < 50 or len(highs) < 50 or len(lows) < 50 or len(volumes) < 20:
                    continue

                # Volatility: Average candle size and ATR%
                candle_sizes = np.mean((highs - lows) / np.where(lows == 0, 1, lows) * 100)
                atr = calculate_atr_array(highs, lows, closes)
                atr_pct = atr / closes[-1] * 100 if closes[-1] != 0 else 0
                bb_width = calculate_bb_width_array(closes)
                
                # Trend: EMA alignment and slopes
                ema9 = calculate_ema(closes, 9)
                ema21 = calculate_ema(closes, 21)
                ema50 = calculate_ema(closes, 50)
                ema200 = calculate_ema(closes, 200) if len(closes) > 200 else np.array([closes[0]] * len(closes))
                ema_alignment = 0
                if len(ema9) > 0 and len(ema21) > 0 and len(ema50) > 0:
                    if ema9[-1] > ema21[-1] > ema50[-1]:
                        ema_alignment = 1
                    elif ema9[-1] < ema21[-1] < ema50[-1]:
                        ema_alignment = -1
                ema9_slope = (ema9[-1] / ema9[-5] - 1) * 100 if len(ema9) > 5 and ema9[-5] != 0 else 0
                ema21_slope = (ema21[-1] / ema21[-5] - 1) * 100 if len(ema21) > 5 and ema21[-5] != 0 else 0
                ema50_slope = (ema50[-1] / ema50[-5] - 1) * 100 if len(ema50) > 5 and ema50[-5] != 0 else 0
                price_change = (closes[-1] / closes[-20] - 1) * 100 if closes[-20] != 0 else 0

                # Volume
                avg_vol_20 = np.mean(volumes[-20:])
                avg_vol_5 = np.mean(volumes[-5:])
                rel_volume = avg_vol_5 / avg_vol_20 if avg_vol_20 != 0 else 1

                # RSI
                rsi = calculate_rsi_array(closes)
                price_vs_50ema = (closes[-1] / ema50[-1] - 1) * 100 if len(ema50) > 0 and ema50[-1] != 0 else 0
                price_vs_200ema = (closes[-1] / ema200[-1] - 1) * 100 if len(ema200) > 0 and ema200[-1] != 0 else 0

                # Golden/Death Cross
                golden_cross = False
                death_cross = False
                if len(ema50) > 10 and len(ema200) > 10:
                    golden_cross = ema50[-1] > ema200[-1] and ema50[-10] < ema200[-10]
                    death_cross = ema50[-1] < ema200[-1] and ema50[-10] > ema200[-10]

                # Heuristic scoring
                trending = ema_alignment != 0 and abs(ema9_slope) > 0.2 and abs(ema21_slope) > 0.15
                volatile = atr_pct > 3.5 or bb_width > 6 or candle_sizes > 2.5
                bullish = trending and ema_alignment == 1 and rsi > 55 and price_vs_50ema > 0.5 and price_vs_200ema > 0.5
                bearish = trending and ema_alignment == -1 and rsi < 45 and price_vs_50ema < -0.5 and price_vs_200ema < -0.5

                # Count signals
                if bullish:
                    bullish_count += 1
                elif bearish:
                    bearish_count += 1
                elif volatile:
                    volatile_count += 1
                else:
                    ranging_count += 1

                aggregated_metrics['volatility'] += float(volatile)
                aggregated_metrics['trending_strength'] += float(trending)
                aggregated_metrics['bullish_signals'] += float(bullish)
                aggregated_metrics['bearish_signals'] += float(bearish)
                aggregated_metrics['volume_intensity'] += float(rel_volume)
                aggregated_metrics['total_samples'] += 1

        # Decision logic
        samples = aggregated_metrics['total_samples']
        if samples == 0:
            return {
                'condition': 'RANGING',
                'description': 'No valid samples for market condition detection.'
            }

        # Aggregate proportions
        bull = bullish_count / samples
        bear = bearish_count / samples
        range_ = ranging_count / samples
        vol = volatile_count / samples

        # Main classification
        if bull > 0.49:
            return {
                'condition': 'TRENDING_BULLISH',
                'description': f"Detected strong bullish market ({bull*100:.0f}% bullish signals, {range_*100:.0f}% ranging)."
            }
        elif bear > 0.49:
            return {
                'condition': 'TRENDING_BEARISH',
                'description': f"Detected strong bearish market ({bear*100:.0f}% bearish signals, {range_*100:.0f}% ranging)."
            }
        elif vol > 0.49:
            return {
                'condition': 'VOLATILE',
                'description': f"Detected high volatility ({vol*100:.0f}% volatile signals)."
            }
        else:
            return {
                'condition': 'RANGING',
                'description': f"Market is mostly ranging ({range_*100:.0f}% ranging, {bull*100:.0f}% bull, {bear*100:.0f}% bear, {vol*100:.0f}% volatile)."
            }

    except Exception as e:
        print(f"[ERROR] Market condition detection: {e}")
        return {
            'condition': 'RANGING',
            'description': 'Fallback due to exception.'
        }
