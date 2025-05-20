import datetime

class AdaptiveParameters:
    def __init__(self):
        # Default parameters
        self.rsi_threshold = 60
        self.price_drop_threshold = 2.0
        self.bb_distance = 2.0
        self.momentum_score_threshold = 3.0
        self.volume_multiplier = 3.0
        self.breakout_confirmation_periods = 3
        
        # Tracking variables
        self.cycles_without_trades = 0
        self.consecutive_losses = 0
        self.recent_win_rate = 0.5  # Starting assumption
        self.market_volatility = "NORMAL"
        self.last_adjustment_time = datetime.datetime.now(datetime.timezone.utc)
        
        # Parameter boundaries
        self.min_rsi = 40
        self.max_rsi = 70
        self.min_price_drop = 0.5
        self.max_price_drop = 3.0
        self.min_bb_distance = 1.0
        self.max_bb_distance = 5.0
        self.min_momentum_score = 1.5
        self.max_momentum_score = 5.0
    
    def update_statistics(self, trading_history, market_condition):
        """Update internal statistics based on recent performance"""
        now = datetime.datetime.now(datetime.timezone.utc)
        
        # Only update statistics every hour to avoid overreacting
        if (now - self.last_adjustment_time).total_seconds() < 3600:
            return
            
        # Get recent trades (last 24 hours)
        recent_trades = []
        cutoff_time = now - datetime.timedelta(hours=24)
        
        for trade in trading_history.get('trades', []):
            if 'close_time' in trade:
                close_time = datetime.datetime.fromisoformat(trade['close_time']) if isinstance(trade['close_time'], str) else trade['close_time']
                if close_time > cutoff_time:
                    recent_trades.append(trade)
        
        # Calculate recent win rate
        if recent_trades:
            winning_trades = sum(1 for t in recent_trades if t.get('profit_pct', 0) > 0)
            self.recent_win_rate = winning_trades / len(recent_trades)
            
            # Track consecutive losses
            sorted_trades = sorted(recent_trades, key=lambda t: t['close_time'] if isinstance(t['close_time'], str) else t['close_time'].isoformat())
            self.consecutive_losses = 0
            for trade in sorted_trades:
                if trade.get('profit_pct', 0) < 0:
                    self.consecutive_losses += 1
                else:
                    self.consecutive_losses = 0
        
        # Store market volatility
        self.market_volatility = market_condition
        self.last_adjustment_time = now
    
    def adjust_parameters(self, trades_found=0):
        """Adjust parameters based on recent performance and market conditions"""
        if trades_found > 0:
            self.cycles_without_trades = 0
            return
            
        self.cycles_without_trades += 1
        
        # Only adjust parameters after several cycles without trades
        if self.cycles_without_trades < 5:
            return
            
        # Adjust parameters based on win rate, market condition, and lack of trades
        if self.cycles_without_trades >= 10:
            # Significant adjustments after 10 cycles with no trades
            self._aggressive_adjustment()
            print("[ADAPTIVE] Aggressive parameter adjustment due to lack of trades")
        else:
            # Moderate adjustments
            self._moderate_adjustment()
            print("[ADAPTIVE] Moderate parameter adjustment")
            
        # Reset counter periodically to avoid over-adjustment
        if self.cycles_without_trades >= 20:
            self.cycles_without_trades = 0
    
    def _aggressive_adjustment(self):
        """Make larger parameter adjustments when no trades are found for extended periods"""
        # Loosen RSI requirement significantly
        self.rsi_threshold = min(self.max_rsi, self.rsi_threshold + 5)
        
        # Reduce required price drop
        self.price_drop_threshold = max(self.min_price_drop, self.price_drop_threshold - 0.5)
        
        # Increase BB distance allowance
        self.bb_distance = min(self.max_bb_distance, self.bb_distance + 1.0)
        
        # Lower momentum score threshold
        self.momentum_score_threshold = max(self.min_momentum_score, self.momentum_score_threshold - 0.5)
        
        # Adjust based on market volatility
        if self.market_volatility == "VOLATILE":
            # In volatile markets, be more conservative with entries
            self.rsi_threshold = max(self.min_rsi, self.rsi_threshold - 3)
            self.momentum_score_threshold = min(self.max_momentum_score, self.momentum_score_threshold + 0.3)
        elif self.market_volatility == "RANGING":
            # In ranging markets, look for smaller moves
            self.price_drop_threshold = max(self.min_price_drop, self.price_drop_threshold - 0.2)
            self.bb_distance = min(self.max_bb_distance, self.bb_distance + 0.5)
    
    def _moderate_adjustment(self):
        """Make smaller parameter adjustments"""
        # Moderately loosen RSI requirement
        self.rsi_threshold = min(self.max_rsi, self.rsi_threshold + 2)
        
        # Slightly reduce required price drop
        self.price_drop_threshold = max(self.min_price_drop, self.price_drop_threshold - 0.2)
        
        # Slightly increase BB distance allowance
        self.bb_distance = min(self.max_bb_distance, self.bb_distance + 0.3)
        
        # Slightly lower momentum score threshold
        self.momentum_score_threshold = max(self.min_momentum_score, self.momentum_score_threshold - 0.2)
    
    def get_parameters(self):
        """Return current parameter set"""
        return {
            'rsi_threshold': self.rsi_threshold,
            'price_drop_threshold': self.price_drop_threshold,
            'bb_distance': self.bb_distance,
            'momentum_score_threshold': self.momentum_score_threshold,
            'volume_multiplier': self.volume_multiplier,
            'breakout_confirmation_periods': self.breakout_confirmation_periods
        }
        
    def print_current_settings(self):
        """Print current parameter settings"""
        print("\n--- Adaptive Parameters ---")
        print(f"RSI Threshold: < {self.rsi_threshold:.1f}")
        print(f"Price Drop Threshold: {self.price_drop_threshold:.2f}%")
        print(f"Bollinger Band Distance: {self.bb_distance:.2f}%")
        print(f"Momentum Score Threshold: {self.momentum_score_threshold:.2f}")
        print(f"Volume Spike Multiplier: {self.volume_multiplier:.1f}x")
        print(f"Market Condition: {self.market_volatility}")
