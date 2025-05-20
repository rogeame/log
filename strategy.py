import datetime
import numpy as np
import pandas as pd

def evaluate_coin(df, coin, params=None):
    """
    Coin evaluation function that can identify multiple strategies:
    1. Coins in early uptrends with momentum (potential explosion) - NOW WITH GOLDEN CROSS
    2. Volume spike signals
    3. Breakout patterns
    4. Mean reversion opportunities
    (Dip buying strategy is REMOVED)
    """
    # Check if df is None or has less than 50 rows
    if df is None or len(df) < 50:
        return None

    try:
        # Convert columns to float
        df['close'] = df['close'].astype(float)
        df['volume'] = df['volume'].astype(float)

        current_price = df['close'].iloc[-1]
        previous_price = df['close'].iloc[-16]  # Roughly 2 hours back on 5-minute candles
        price_change = (current_price - previous_price) / previous_price * 100

        # Get 3-day high to check for recent pumps
        three_day_high = df['high'].max()
        three_day_low = df['low'].min()
        three_day_range = (three_day_high - three_day_low) / three_day_low * 100
        
        # Skip if coin has pumped more than 40% in last 3 days
        if three_day_range > 40:
            return None

        # Calculate RSI for oversold/overbought detection
        rsi_values = calculate_rsi(df['close'], 14)
        current_rsi = rsi_values.iloc[-1]
        
        # Get adaptive parameters if provided
        if params:
            rsi_threshold = params.get('rsi_threshold', 40)
            price_drop_threshold = params.get('price_drop_threshold', 2.0)
            bb_distance = params.get('bb_distance', 2.0)
            momentum_score_threshold = params.get('momentum_score_threshold', 3.0)
            volume_multiplier = params.get('volume_multiplier', 3.0)
        else:
            rsi_threshold = 40
            price_drop_threshold = 2.0
            bb_distance = 2.0
            momentum_score_threshold = 3.0
            volume_multiplier = 3.0
        
        # If RSI is extremely high (over 75), skip - likely overbought and will retrace
        if current_rsi > 75:
            return None

        # Calculate momentum indicators (now with Golden Cross)
        df = add_momentum_indicators(df)
        
        # ===== STRATEGY CHECKS =====
        
        # Strategy 1: MOMENTUM BUYING (Enhanced with Golden Cross)
        momentum_result = None
        if check_momentum_signal(df, threshold=momentum_score_threshold):
            momentum_result = {
                'strategy': 'MOMENTUM',
                'momentum_score': df['momentum_score'].iloc[-1],
                'rank_factor': df['momentum_score'].iloc[-1],
                'golden_cross_active': df['post_golden_cross'].iloc[-1] > 0
            }
        
        # Strategy 2: VOLUME SPIKE
        volume_result = check_volume_spike(df, multiplier=volume_multiplier)
        
        # Strategy 3: BREAKOUT
        breakout_result = check_breakout(df)
        
        # Strategy 4: MEAN REVERSION
        mean_reversion_result = check_mean_reversion(df)
        
        # Combine all strategy results (DIP strategy REMOVED)
        all_results = [momentum_result, volume_result, breakout_result, mean_reversion_result]
        valid_results = [r for r in all_results if r is not None]
        
        if not valid_results:
            return None
            
        # Sort by rank factor and pick the highest one
        best_result = sorted(valid_results, key=lambda x: x['rank_factor'], reverse=True)[0]
        
        # Calculate volume metrics (common for all strategies)
        avg_volume = df['volume'].rolling(20).mean().iloc[-1]
        current_volume = df['volume'].iloc[-1]
        vol_ratio = current_volume / avg_volume if avg_volume > 0 else 0
        
        # Create final result with common fields
        result = {
            'symbol': coin,
            'rsi': round(current_rsi, 2),
            'drop': round(price_change, 2),
            'volume_ratio': round(vol_ratio, 2),
            'vol': current_volume,
            'price': current_price,
            'timestamp': datetime.datetime.now(datetime.timezone.utc),
            'strategy': best_result['strategy'],
            'rank_factor': best_result['rank_factor']
        }
        
        # Add strategy-specific fields
        result.update({k: v for k, v in best_result.items() if k not in result})
        
        return result
        
    except Exception as e:
        print(f"[ERROR] Processing {coin}: {e}")
        return None

# === Helper Functions (unchanged except DIP REMOVED) ===

def calculate_rsi(series, period=14):
    """Calculate the Relative Strength Index"""
    try:
        series = series.ffill()  
        delta = series.diff()
        delta = delta.fillna(0)
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        avg_gain = gain.rolling(window=period).mean()
        avg_loss = loss.rolling(window=period).mean()
        avg_loss = avg_loss.replace(0, 0.00001)
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        rsi = rsi.fillna(50)
        return rsi
    except Exception as e:
        print(f"[ERROR] RSI calculation: {e}")
        return pd.Series([100] * len(series))

def add_momentum_indicators(df):
    """Add momentum indicators to the dataframe, with Golden Cross"""
    ema_12 = df['close'].ewm(span=12, adjust=False).mean()
    ema_26 = df['close'].ewm(span=26, adjust=False).mean()
    df['macd'] = ema_12 - ema_26
    df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
    df['macd_hist'] = df['macd'] - df['macd_signal']
    df['roc_5'] = df['close'].pct_change(periods=5) * 100
    df['sma_10'] = df['close'].rolling(window=10).mean()
    df['sma_20'] = df['close'].rolling(window=20).mean()
    df['sma_50'] = df['close'].rolling(window=50).mean()
    df['sma_200'] = df['close'].rolling(window=200).mean()
    df['golden_cross'] = 0.0
    df['death_cross'] = 0.0
    if len(df) > 201:
        for i in range(-20, 0):
            if i+1 < 0:
                if (df['sma_50'].iloc[i-1] <= df['sma_200'].iloc[i-1] and 
                    df['sma_50'].iloc[i] > df['sma_200'].iloc[i]):
                    df.loc[df.index[i], 'golden_cross'] = 1.0
                elif (df['sma_50'].iloc[i-1] >= df['sma_200'].iloc[i-1] and 
                      df['sma_50'].iloc[i] < df['sma_200'].iloc[i]):
                    df.loc[df.index[i], 'death_cross'] = 1.0
        df['post_golden_cross'] = (df['sma_50'] > df['sma_200']).astype(float)
        df['golden_cross_age'] = 0
        last_golden_cross_idx = None
        for i in range(len(df)-1, max(0, len(df)-100), -1):
            if df['golden_cross'].iloc[i] == 1.0:
                last_golden_cross_idx = i
                break
        if last_golden_cross_idx is not None:
            for i in range(last_golden_cross_idx, len(df)):
                df.loc[df.index[i], 'golden_cross_age'] = i - last_golden_cross_idx
    else:
        df['post_golden_cross'] = 0
        df['golden_cross_age'] = 99
    window = 20
    sma = df['close'].rolling(window=window).mean()
    std = df['close'].rolling(window=window).std()
    df['upper_band'] = sma + 2 * std
    df['lower_band'] = sma - 2 * std
    df['bb_position'] = (df['close'] - df['lower_band']) / (df['upper_band'] - df['lower_band'])
    df['volume_trend'] = df['volume'] / df['volume'].rolling(window=5).mean()
    if len(df) > 2:
        df['macd_crossover'] = ((df['macd'].shift(1) <= df['macd_signal'].shift(1)) & 
                              (df['macd'] > df['macd_signal'])).astype(float)
        df['macd_hist_growing'] = ((df['macd_hist'] > 0) & 
                                (df['macd_hist'] > df['macd_hist'].shift(1))).astype(float)
        df['sma_crossover'] = ((df['sma_10'].shift(1) <= df['sma_20'].shift(1)) & 
                            (df['sma_10'] > df['sma_20'])).astype(float)
        df['golden_cross_factor'] = np.where(
            df['golden_cross_age'] <= 0, 0,
            np.where(
                df['golden_cross_age'] <= 5, 5.0,
                np.where(
                    df['golden_cross_age'] <= 15, 3.0,
                    np.where(
                        df['golden_cross_age'] <= 30, 1.5,
                        np.where(
                            df['golden_cross_age'] <= 50, 0.5,
                            0.2
                        )
                    )
                )
            )
        )
        df['momentum_score'] = (
            df['macd_crossover'] * 2.0 +
            df['macd_hist_growing'] * 1.5 +
            df['sma_crossover'] * 2.0 +
            df['roc_5'] * 0.3 +
            df['volume_trend'] * 1.0 +
            df['golden_cross'] * 6.0 +
            df['golden_cross_factor'] +
            df['post_golden_cross'] * 1.5
        )
        df['momentum_score'] = df['momentum_score'] - (df['death_cross'] * 4.0)
    else:
        df['momentum_score'] = 0.0
    return df

def check_momentum_signal(df, threshold=3.0):
    """Check if there's a momentum signal based on indicators, with enhanced Golden Cross detection"""
    try:
        check_golden_cross = len(df) >= 200
        latest_idx = -1
        macd_signal = (df['macd'].iloc[latest_idx] > df['macd_signal'].iloc[latest_idx] and
                      df['macd'].iloc[latest_idx-1] <= df['macd_signal'].iloc[latest_idx-1])
        sma_signal = (df['sma_10'].iloc[latest_idx] > df['sma_20'].iloc[latest_idx] and
                     df['sma_10'].iloc[latest_idx-1] <= df['sma_20'].iloc[latest_idx-1])
        volume_signal = df['volume_trend'].iloc[latest_idx] > 1.2
        roc_signal = df['roc_5'].iloc[latest_idx] > 2.0
        fresh_golden_cross = False
        golden_cross_age = 99
        if check_golden_cross:
            if df['golden_cross'].iloc[latest_idx] == 1.0:
                fresh_golden_cross = True
                golden_cross_age = 0
            else:
                for i in range(-20, 0):
                    if df['golden_cross'].iloc[i] == 1.0:
                        fresh_golden_cross = True
                        golden_cross_age = abs(i)
                        break
            post_golden_cross = df['post_golden_cross'].iloc[latest_idx] == 1.0
        else:
            post_golden_cross = False
        momentum_score = df['momentum_score'].iloc[latest_idx]
        high_momentum = momentum_score > threshold
        if fresh_golden_cross:
            return high_momentum or (macd_signal and (volume_signal or roc_signal))
        elif post_golden_cross:
            return high_momentum or (macd_signal and sma_signal and volume_signal)
        else:
            return high_momentum or (macd_signal and sma_signal and volume_signal and roc_signal)
    except Exception as e:
        print(f"[ERROR] Momentum check: {e}")
        return False

def check_volume_spike(df, multiplier=3, lookback=20, price_confirmation=True):
    """Detect unusual volume spikes that may indicate impending price movements"""
    try:
        current_volume = df['volume'].iloc[-1]
        avg_volume = df['volume'].iloc[-lookback:-1].mean()
        volume_ratio = current_volume / avg_volume if avg_volume > 0 else 0
        price_rising = df['close'].iloc[-1] > df['open'].iloc[-1]
        prev_candles_falling = df['close'].iloc[-4:-1].mean() < df['open'].iloc[-4:-1].mean()
        volume_spike = volume_ratio >= multiplier
        reversal_potential = prev_candles_falling and price_rising
        valid_signal = volume_spike and (not price_confirmation or price_rising)
        if valid_signal:
            return {
                'strategy': 'VOLUME_SPIKE',
                'volume_ratio': volume_ratio,
                'price_rising': price_rising,
                'reversal_potential': reversal_potential,
                'rank_factor': volume_ratio * (1.5 if reversal_potential else 1.0)
            }
        return None
    except Exception as e:
        print(f"[ERROR] Volume spike check: {e}")
        return None

def check_breakout(df, lookback_periods=48, confirmation_periods=3, volume_req=1.5):
    """Detect breakouts above recent resistance levels"""
    try:
        resistance = df['high'].iloc[-lookback_periods:-confirmation_periods].max()
        current_price = df['close'].iloc[-1]
        prev_close = df['close'].iloc[-2]
        current_volume = df['volume'].iloc[-1]
        avg_volume = df['volume'].iloc[-10:].mean()
        volume_increase = current_volume / avg_volume if avg_volume > 0 else 0
        breakout_percent = (current_price / resistance - 1) * 100
        price_above_resistance = current_price > resistance
        recent_break = prev_close < resistance and current_price > resistance
        volume_confirmed = volume_increase >= volume_req
        is_breakout = price_above_resistance and (recent_break or breakout_percent > 1.0) and volume_confirmed
        if is_breakout:
            rank_factor = breakout_percent * volume_increase
            return {
                'strategy': 'BREAKOUT',
                'breakout_percent': breakout_percent,
                'resistance_level': resistance,
                'volume_increase': volume_increase,
                'fresh_breakout': recent_break,
                'rank_factor': rank_factor
            }
        return None
    except Exception as e:
        print(f"[ERROR] Breakout check: {e}")
        return None

def check_mean_reversion(df, ma_periods=20, deviation_threshold=2.5, trend_filter=True):
    """Detect mean reversion opportunities when price deviates from moving average"""
    try:
        ma = df['close'].rolling(ma_periods).mean()
        std = df['close'].rolling(ma_periods).std()
        current_price = df['close'].iloc[-1]
        current_ma = ma.iloc[-1]
        current_std = std.iloc[-1]
        if current_std > 0:
            z_score = (current_price - current_ma) / current_std
        else:
            z_score = 0
        ma_trend_up = ma.iloc[-1] > ma.iloc[-5]
        oversold_signal = (z_score <= -deviation_threshold and 
                          df['close'].iloc[-1] > df['close'].iloc[-2] and
                          (not trend_filter or ma_trend_up))
        if oversold_signal:
            signal_strength = abs(z_score) * (df['volume'].iloc[-1] / df['volume'].iloc[-5:].mean())
            return {
                'strategy': 'MEAN_REVERSION',
                'z_score': z_score,
                'ma_price': current_ma,
                'signal_type': 'oversold',
                'trend_direction': 'bullish' if ma_trend_up else 'bearish',
                'rank_factor': signal_strength
            }
        return None
    except Exception as e:
        print(f"[ERROR] Mean reversion check: {e}")
        return None