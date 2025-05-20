import ccxt
import os
import time
import json
import pandas as pd
from dotenv import load_dotenv
from datetime import datetime, timedelta

def load_api_keys():
    """Load API keys from environment variables."""
    # Load .env file
    load_dotenv('.env.txt')
    
    api_key = os.getenv("KRAKEN_API_KEY")
    api_secret = os.getenv("KRAKEN_API_SECRET")
    
    if not api_key or not api_secret:
        raise ValueError("[ERROR] API keys not found in environment variables. Cannot trade without valid keys.")
        
    return api_key, api_secret

def fetch_ohlc_data(exchange, symbol, timeframe='1m', limit=144):  # 144 candles = 12 hours for 5-minute frames
    """
    Fetch OHLCV data for a symbol
    
    Parameters:
    - exchange: CCXT exchange object
    - symbol: Trading pair symbol (e.g. 'BTC/USD')
    - timeframe: Candle timeframe (default '1m')
    - limit: Number of candles to fetch
    
    Returns:
    - Pandas DataFrame with OHLCV data
    """
    try:
        data = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        if data and len(data) > 0:
            df = pd.DataFrame(data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            return df
        else:
            print(f"[WARNING] No OHLCV data for {symbol}")
            return None
    except Exception as e:
        print(f"[ERROR] {symbol}: {e}")
        return None

def get_balance(exchange):
    """Get account balance from exchange"""
    try:
        balance = exchange.fetch_balance()
        return balance['total']
    except Exception as e:
        print(f"[ERROR] Fetching balance failed: {e}")
        return {}

def place_order(exchange, symbol, amount):
    """
    Place a buy order on the exchange
    
    Parameters:
    - exchange: CCXT exchange object
    - symbol: Trading pair symbol (e.g. 'BTC/USD')
    - amount: Amount of asset to buy
    
    Returns:
    - Order object if successful, None otherwise
    """
    try:
        # Make sure markets are loaded
        if not hasattr(exchange, 'markets') or not exchange.markets:
            exchange.load_markets()

        # Get market information
        market = exchange.market(symbol)
        min_amount = market.get('limits', {}).get('amount', {}).get('min', 0)
        
        # Ensure amount is above minimum
        if amount < min_amount:
            print(f"[WARNING] Amount {amount} is below minimum {min_amount} for {symbol}. Increasing to minimum.")
            amount = min_amount
            
        # Apply precision (round to correct number of decimal places)
        precision = market.get('precision', {}).get('amount')
        if precision is not None:
            # Convert precision to int if it's a decimal
            if isinstance(precision, float):
                precision = int(precision)
            amount = float(round(amount, precision))
        
        # Convert to string with proper format if needed by exchange
        if exchange.id == 'kraken':
            # Some exchanges require string amounts
            amount_str = str(amount)
            print(f"[EXECUTING] Buy order for {symbol} | Amount: {amount_str}")
            order = exchange.create_market_buy_order(symbol, amount_str)
        else:
            print(f"[EXECUTING] Buy order for {symbol} | Amount: {amount}")
            order = exchange.create_market_buy_order(symbol, amount)
            
        print(f"[SUCCESS] Market buy executed for {symbol} | Amount: {amount} | Order ID: {order.get('id', 'unknown')}")
        return order
    except Exception as e:
        print(f"[ERROR] Placing order for {symbol}: {e}")
        return None

def sell_order(exchange, symbol, amount, percentage=100):
    """
    Place a sell order on the exchange
    
    Parameters:
    - exchange: CCXT exchange object
    - symbol: Trading pair symbol (e.g. 'BTC/USD')
    - amount: Total amount of asset in position
    - percentage: Percentage of position to sell (default 100%)
    
    Returns:
    - Order object if successful, None otherwise
    """
    try:
        # Make sure markets are loaded
        if not hasattr(exchange, 'markets') or not exchange.markets:
            exchange.load_markets()

        # Get market information
        market = exchange.market(symbol)
        min_amount = market.get('limits', {}).get('amount', {}).get('min', 0)
        
        # Calculate the actual amount to sell based on percentage
        actual_amount = amount * (percentage / 100)
        
        # Ensure amount is above minimum
        if actual_amount < min_amount:
            print(f"[WARNING] Amount {actual_amount} is below minimum {min_amount} for {symbol}. Increasing to minimum.")
            actual_amount = min_amount
            
        # Apply precision (round to correct number of decimal places)
        precision = market.get('precision', {}).get('amount')
        if precision is not None:
            # Convert precision to int if it's a decimal
            if isinstance(precision, float):
                precision = int(precision)
            actual_amount = float(round(actual_amount, precision))
        
        # Convert to string with proper format if needed by exchange
        if exchange.id == 'kraken':
            # Some exchanges require string amounts
            amount_str = str(actual_amount)
            print(f"[EXECUTING] Sell order for {symbol} | Amount: {amount_str} ({percentage}% of position)")
            order = exchange.create_market_sell_order(symbol, amount_str)
        else:
            print(f"[EXECUTING] Sell order for {symbol} | Amount: {actual_amount} ({percentage}% of position)")
            order = exchange.create_market_sell_order(symbol, actual_amount)
            
        print(f"[SUCCESS] Market sell executed for {symbol} | Amount: {actual_amount} | Order ID: {order.get('id', 'unknown')}")
        return order
    except Exception as e:
        print(f"[ERROR] Selling order for {symbol}: {e}")
        return None

def save_trading_history(history):
    """Save trading history to a JSON file"""
    try:
        with open('trading_history.json', 'w') as f:
            json.dump(history, f, default=str)
    except Exception as e:
        print(f"[ERROR] Failed to save trading history: {e}")

def load_trading_history():
    """Load trading history from a JSON file"""
    try:
        with open('trading_history.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {'trades': [], 'last_24h_losses': 0, 'cooldown_until': None}
    except Exception as e:
        print(f"[ERROR] Failed to load trading history: {e}")
        return {'trades': [], 'last_24h_losses': 0, 'cooldown_until': None}

def calculate_atr(df, period=14):
    """Calculate Average True Range for a dataframe"""
    try:
        # True Range calculation
        high_low = df['high'] - df['low']
        high_close = abs(df['high'] - df['close'].shift())
        low_close = abs(df['low'] - df['close'].shift())
        
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = ranges.max(axis=1)
        
        # ATR calculation (simple moving average of true range)
        atr = true_range.rolling(window=period).mean()
        
        return atr
    except Exception as e:
        print(f"[ERROR] ATR calculation: {e}")
        return pd.Series([0] * len(df))