"""
Intraday Liquidity & Momentum Engine
Detects volatility compression → breakout, momentum continuation, liquidation snapbacks
"""
import pandas as pd
import numpy as np
import pandas_ta as ta
from typing import Dict, Optional, Tuple
from dataclasses import dataclass


@dataclass
class SignalResult:
    """Trading signal with strength and metadata"""
    signal: str  # "LONG", "SHORT", "NEUTRAL"
    signal_type: str  # "breakout", "trend_following", "mean_reversion", "liquidation_snapback"
    strength: float  # 0-100
    entry_price: float
    stop_loss: float
    take_profit: float
    risk_reward: float
    confidence_factors: Dict[str, float]
    metadata: Dict


class IntradayMomentumEngine:
    """
    High-probability intraday trading engine combining:
    - Volatility compression detection
    - Momentum confirmation
    - Liquidity analysis
    - Liquidation snapback detection
    """
    
    def __init__(self, 
                 atr_period: int = 14,
                 rsi_period: int = 14,
                 adx_period: int = 14,
                 bb_period: int = 20,
                 bb_std: float = 2.0,
                 volume_lookback: int = 20):
        self.atr_period = atr_period
        self.rsi_period = rsi_period
        self.adx_period = adx_period
        self.bb_period = bb_period
        self.bb_std = bb_std
        self.volume_lookback = volume_lookback
    
    def _manual_atr(self, df: pd.DataFrame) -> pd.Series:
        """Calculate ATR manually as fallback"""
        high_low = df['high'] - df['low']
        high_close = abs(df['high'] - df['close'].shift())
        low_close = abs(df['low'] - df['close'].shift())
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = ranges.max(axis=1)
        return true_range.ewm(span=self.atr_period, adjust=False).mean()
        
    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate all technical indicators needed for signal generation
        
        Mathematical Formulas:
        - Returns: r_t = ln(P_t / P_{t-1})
        - ATR: EMA of True Range
        - RSI: 100 - 100/(1 + RS)
        - BB Width: (Upper - Lower) / Middle
        - Volume Z-Score: (V - μ) / σ
        """
        df = df.copy()
        
        df['returns'] = np.log(df['close'] / df['close'].shift(1))
        
        # ATR - Average True Range
        try:
            atr_result = ta.atr(high=df['high'], low=df['low'], close=df['close'], length=self.atr_period)
            df['atr'] = atr_result if atr_result is not None else self._manual_atr(df)
        except:
            df['atr'] = self._manual_atr(df)
        
        # Normalized ATR (percentage of price)
        df['atr_pct'] = (df['atr'] / df['close']) * 100
        
        # RSI - Relative Strength Index
        try:
            rsi_result = ta.rsi(close=df['close'], length=self.rsi_period)
            df['rsi'] = rsi_result if rsi_result is not None else 50
        except:
            df['rsi'] = 50
        
        # ADX - Average Directional Index (trend strength)
        try:
            adx_df = ta.adx(high=df['high'], low=df['low'], close=df['close'], length=self.adx_period)
            if adx_df is not None and not adx_df.empty:
                # Try multiple column name patterns
                adx_col = next((c for c in adx_df.columns if 'ADX' in c.upper()), None)
                dmp_col = next((c for c in adx_df.columns if 'DMP' in c.upper() or 'DI+' in c.upper()), None)
                dmn_col = next((c for c in adx_df.columns if 'DMN' in c.upper() or 'DI-' in c.upper()), None)
                
                df['adx'] = adx_df[adx_col] if adx_col else 0
                df['di_plus'] = adx_df[dmp_col] if dmp_col else 0
                df['di_minus'] = adx_df[dmn_col] if dmn_col else 0
            else:
                df['adx'] = 0
                df['di_plus'] = 0
                df['di_minus'] = 0
        except:
            df['adx'] = 0
            df['di_plus'] = 0
            df['di_minus'] = 0
        
        # Bollinger Bands
        try:
            bbands = ta.bbands(close=df['close'], length=self.bb_period, std=self.bb_std)
            if bbands is not None and not bbands.empty:
                # pandas_ta may return different column formats, try multiple patterns
                possible_upper = [f'BBU_{self.bb_period}_{self.bb_std}', f'BBU_{self.bb_period}_{int(self.bb_std)}', 'BBU_20_2']
                possible_middle = [f'BBM_{self.bb_period}_{self.bb_std}', f'BBM_{self.bb_period}_{int(self.bb_std)}', 'BBM_20_2']
                possible_lower = [f'BBL_{self.bb_period}_{self.bb_std}', f'BBL_{self.bb_period}_{int(self.bb_std)}', 'BBL_20_2']
                
                # Find the actual column names
                bb_upper_col = next((col for col in possible_upper if col in bbands.columns), None)
                bb_middle_col = next((col for col in possible_middle if col in bbands.columns), None)
                bb_lower_col = next((col for col in possible_lower if col in bbands.columns), None)
                
                if bb_upper_col and bb_middle_col and bb_lower_col:
                    df['bb_upper'] = bbands[bb_upper_col]
                    df['bb_middle'] = bbands[bb_middle_col]
                    df['bb_lower'] = bbands[bb_lower_col]
                    df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['bb_middle']
                else:
                    # Fallback to manual calculation
                    sma = df['close'].rolling(window=self.bb_period).mean()
                    std = df['close'].rolling(window=self.bb_period).std()
                    df['bb_middle'] = sma
                    df['bb_upper'] = sma + (self.bb_std * std)
                    df['bb_lower'] = sma - (self.bb_std * std)
                    df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['bb_middle']
            else:
                # Manual calculation fallback
                sma = df['close'].rolling(window=self.bb_period).mean()
                std = df['close'].rolling(window=self.bb_period).std()
                df['bb_middle'] = sma
                df['bb_upper'] = sma + (self.bb_std * std)
                df['bb_lower'] = sma - (self.bb_std * std)
                df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['bb_middle']
        except:
            # Manual calculation fallback
            sma = df['close'].rolling(window=self.bb_period).mean()
            std = df['close'].rolling(window=self.bb_period).std()
            df['bb_middle'] = sma
            df['bb_upper'] = sma + (self.bb_std * std)
            df['bb_lower'] = sma - (self.bb_std * std)
            df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['bb_middle']
        
        # Bollinger Band %B (position within bands)
        df['bb_pct'] = (df['close'] - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'])
        
        # EMA for trend
        try:
            ema_9_result = ta.ema(close=df['close'], length=9)
            ema_21_result = ta.ema(close=df['close'], length=21)
            ema_50_result = ta.ema(close=df['close'], length=50)
            df['ema_9'] = ema_9_result if ema_9_result is not None else df['close'].ewm(span=9, adjust=False).mean()
            df['ema_21'] = ema_21_result if ema_21_result is not None else df['close'].ewm(span=21, adjust=False).mean()
            df['ema_50'] = ema_50_result if ema_50_result is not None else df['close'].ewm(span=50, adjust=False).mean()
        except:
            df['ema_9'] = df['close'].ewm(span=9, adjust=False).mean()
            df['ema_21'] = df['close'].ewm(span=21, adjust=False).mean()
            df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean()
        
        # EMA slope (momentum)
        df['ema_21_slope'] = df['ema_21'].pct_change(5) * 100
        
        # Volume Analysis
        df['volume_sma'] = df['volume'].rolling(window=self.volume_lookback).mean()
        df['volume_std'] = df['volume'].rolling(window=self.volume_lookback).std()
        df['volume_zscore'] = (df['volume'] - df['volume_sma']) / df['volume_std']
        
        # Volume spike detection
        df['volume_spike'] = df['volume_zscore'] > 2.0
        
        # MACD for momentum confirmation
        try:
            macd = ta.macd(close=df['close'], fast=12, slow=26, signal=9)
            if macd is not None and not macd.empty:
                # Try multiple column name patterns
                macd_cols = [c for c in macd.columns if 'MACD' in c.upper()]
                if len(macd_cols) >= 3:
                    df['macd'] = macd[macd_cols[0]]
                    df['macd_signal'] = macd[macd_cols[1]]
                    df['macd_hist'] = macd[macd_cols[2]]
                else:
                    df['macd'] = 0
                    df['macd_signal'] = 0
                    df['macd_hist'] = 0
            else:
                df['macd'] = 0
                df['macd_signal'] = 0
                df['macd_hist'] = 0
        except:
            df['macd'] = 0
            df['macd_signal'] = 0
            df['macd_hist'] = 0
        
        return df
    
    def detect_volatility_compression(self, df: pd.DataFrame) -> Tuple[bool, float]:
        """
        Detect volatility compression (BB squeeze)
        Returns: (is_compressed, compression_score)
        
        Formula: BBW = (Upper - Lower) / Middle
        Compression when BBW is in lowest 20th percentile
        """
        if len(df) < self.bb_period + 20:
            return False, 0.0
        
        current_bb_width = df['bb_width'].iloc[-1]
        bb_width_percentile = (df['bb_width'].iloc[-20:] < current_bb_width).sum() / 20
        
        # Compression if in lowest 20% of recent width
        is_compressed = bb_width_percentile < 0.20
        compression_score = (1 - bb_width_percentile) * 100
        
        return is_compressed, compression_score
    
    def detect_momentum(self, df: pd.DataFrame) -> Tuple[str, float]:
        """
        Detect momentum direction and strength
        Returns: (direction, momentum_score)
        
        Uses:
        - EMA alignment and slope
        - MACD histogram
        - ADX for trend strength
        """
        last = df.iloc[-1]
        
        # EMA alignment
        ema_bullish = (last['ema_9'] > last['ema_21'] > last['ema_50'])
        ema_bearish = (last['ema_9'] < last['ema_21'] < last['ema_50'])
        
        # EMA slope strength
        slope_strength = abs(last['ema_21_slope'])
        
        # MACD confirmation
        macd_bullish = last['macd'] > last['macd_signal'] and last['macd_hist'] > 0
        macd_bearish = last['macd'] < last['macd_signal'] and last['macd_hist'] < 0
        
        # ADX trend strength (above 25 = strong trend)
        adx_score = min(last['adx'] / 25, 1.0) * 100 if last['adx'] > 0 else 0
        
        # Calculate momentum score
        momentum_score = 0
        direction = "NEUTRAL"
        
        # Relaxed logic: EMA OR MACD confirmation (not both required)
        if ema_bullish or macd_bullish:
            direction = "BULLISH"
            # Base score + bonuses
            momentum_score = 40  # Base score
            if ema_bullish: momentum_score += 20
            if macd_bullish: momentum_score += 20
            momentum_score += slope_strength * 1.5 + adx_score * 0.3
        elif ema_bearish or macd_bearish:
            direction = "BEARISH"
            momentum_score = 40  # Base score
            if ema_bearish: momentum_score += 20
            if macd_bearish: momentum_score += 20
            momentum_score += slope_strength * 1.5 + adx_score * 0.3
        
        momentum_score = min(momentum_score, 100)
        
        return direction, momentum_score
    
    def detect_breakout(self, df: pd.DataFrame) -> Tuple[Optional[str], float]:
        """
        Detect breakout from consolidation
        Returns: (breakout_direction, breakout_score)
        """
        if len(df) < 5:
            return None, 0.0
        
        last = df.iloc[-1]
        prev = df.iloc[-2]
        
        # Price action relative to BB
        bb_breakout_up = (prev['close'] <= prev['bb_upper'] and 
                          last['close'] > last['bb_upper'])
        bb_breakout_down = (prev['close'] >= prev['bb_lower'] and 
                           last['close'] < last['bb_lower'])
        
        # Volume confirmation (bonus, not required)
        volume_confirmed = last['volume_zscore'] > 1.5
        volume_bonus = min(last['volume_zscore'] * 10, 30) if last['volume_zscore'] > 0 else 0
        
        # ADX increasing (trend developing)
        adx_increasing = last['adx'] > df['adx'].iloc[-3:].mean()
        
        breakout_score = 0
        direction = None
        
        # Relaxed: Allow breakouts without strict volume requirement
        if bb_breakout_up:
            direction = "LONG"
            breakout_score = 50 + volume_bonus + (20 if adx_increasing else 0)
        elif bb_breakout_down:
            direction = "SHORT"
            breakout_score = 50 + volume_bonus + (20 if adx_increasing else 0)
        
        breakout_score = min(breakout_score, 100)
        
        return direction, breakout_score
    
    def detect_liquidation_snapback(self, df: pd.DataFrame) -> Tuple[Optional[str], float]:
        """
        Detect potential liquidation cascade reversal (V-shape recovery)
        Returns: (direction, snapback_score)
        """
        if len(df) < 10:
            return None, 0.0
        
        last = df.iloc[-1]
        
        # Look for sharp move followed by immediate reversal
        recent_returns = df['returns'].iloc[-5:].values
        
        # Detect sharp drop then recovery
        sharp_drop = any(r < -0.02 for r in recent_returns[:3])  # 2%+ drop
        quick_recovery = recent_returns[-1] > 0.01  # 1%+ recovery
        
        # RSI oversold/overbought reversal
        rsi_oversold_reversal = last['rsi'] > 30 and df['rsi'].iloc[-3:].min() < 30
        rsi_overbought_reversal = last['rsi'] < 70 and df['rsi'].iloc[-3:].max() > 70
        
        # Volume spike on reversal
        volume_spike = last['volume_zscore'] > 2.0
        
        snapback_score = 0
        direction = None
        
        if sharp_drop and quick_recovery and rsi_oversold_reversal:
            direction = "LONG"
            snapback_score = 50 + (20 if volume_spike else 0) + (last['rsi'] - 30) * 0.5
        elif rsi_overbought_reversal and volume_spike:
            direction = "SHORT"
            snapback_score = 50 + (20 if volume_spike else 0) + (70 - last['rsi']) * 0.5
        
        snapback_score = min(snapback_score, 100)
        
        return direction, snapback_score
    
    def calculate_stop_and_target(self, 
                                   entry: float, 
                                   direction: str, 
                                   atr: float,
                                   risk_reward: float = 2.0) -> Tuple[float, float]:
        """
        Calculate stop loss and take profit using ATR
        
        Formulas:
        - Stop = k * ATR, k ∈ [1.3, 1.8]
        - TP = Entry + R * Stop
        """
        # Dynamic stop multiplier based on volatility
        stop_multiplier = 1.5  # Conservative for intraday
        
        if direction == "LONG":
            stop_loss = entry - (stop_multiplier * atr)
            take_profit = entry + (risk_reward * stop_multiplier * atr)
        else:  # SHORT
            stop_loss = entry + (stop_multiplier * atr)
            take_profit = entry - (risk_reward * stop_multiplier * atr)
        
        return stop_loss, take_profit
    
    def generate_signal(self, 
                       df: pd.DataFrame,
                       funding_rate: Optional[float] = None,
                       oi_change: Optional[float] = None,
                       orderbook_imbalance: Optional[float] = None) -> SignalResult:
        """
        Generate comprehensive trading signal
        
        Combines:
        1. Volatility compression
        2. Momentum
        3. Breakout detection
        4. Liquidation snapback
        5. Optional: funding rate, OI, orderbook
        """
        # Calculate all indicators
        df = self.calculate_indicators(df)
        
        if len(df) < 50:
            return SignalResult(
                signal="NEUTRAL",
                signal_type="none",
                strength=0.0,
                entry_price=df['close'].iloc[-1],
                stop_loss=0.0,
                take_profit=0.0,
                risk_reward=0.0,
                confidence_factors={},
                metadata={"reason": "Insufficient data"}
            )
        
        last = df.iloc[-1]
        
        # Run all detection algorithms
        is_compressed, compression_score = self.detect_volatility_compression(df)
        momentum_dir, momentum_score = self.detect_momentum(df)
        breakout_dir, breakout_score = self.detect_breakout(df)
        snapback_dir, snapback_score = self.detect_liquidation_snapback(df)
        
        # Confidence factors
        confidence_factors = {
            "volatility_compression": compression_score,
            "momentum": momentum_score,
            "breakout": breakout_score,
            "liquidation_snapback": snapback_score,
            "volume_confirmation": min(last['volume_zscore'] * 20, 100) if last['volume_zscore'] > 0 else 0,
            "trend_strength": min(last['adx'] * 2, 100) if last['adx'] > 0 else 0
        }
        
        # Add optional factors
        if funding_rate is not None:
            # Negative funding = longs paying shorts (bearish sentiment)
            funding_factor = abs(funding_rate) * 10000  # Scale to 0-100
            confidence_factors["funding_pressure"] = min(funding_factor, 100)
        
        if oi_change is not None:
            # Positive OI change + price up = bullish
            oi_factor = abs(oi_change) * 100
            confidence_factors["oi_momentum"] = min(oi_factor, 100)
        
        if orderbook_imbalance is not None:
            # Positive = more bids (bullish)
            ob_factor = abs(orderbook_imbalance) * 100
            confidence_factors["orderbook_imbalance"] = min(ob_factor, 100)
        
        # Log detection scores for debugging (INFO level to see in output)
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"      Scores - Breakout: {breakout_score:.0f} ({breakout_dir}), "
                    f"Momentum: {momentum_score:.0f} ({momentum_dir}), "
                    f"Snapback: {snapback_score:.0f} ({snapback_dir}), "
                    f"Compression: {compression_score:.0f}")
        
        # Signal aggregation logic
        signal = "NEUTRAL"
        signal_type = "none"
        strength = 0.0
        
        # Priority 1: Strong breakout with compression (relaxed thresholds)
        if breakout_dir and breakout_score > 50:  # Lowered from 60, removed strict compression requirement
            signal = breakout_dir
            signal_type = "breakout"
            # Bonus for compression
            compression_bonus = compression_score * 0.2 if is_compressed else 0
            strength = (breakout_score * 0.5 + momentum_score * 0.3 + compression_bonus)
        
        # Priority 2: Momentum continuation (relaxed threshold)
        elif momentum_dir != "NEUTRAL" and momentum_score > 50:  # Lowered from 60
            signal = "LONG" if momentum_dir == "BULLISH" else "SHORT"
            signal_type = "trend_following"
            strength = (momentum_score * 0.5 + 
                       confidence_factors["trend_strength"] * 0.3 +
                       confidence_factors["volume_confirmation"] * 0.2)
        
        # Priority 3: Liquidation snapback (relaxed threshold)
        elif snapback_dir and snapback_score > 50:  # Lowered from 60
            signal = snapback_dir
            signal_type = "liquidation_snapback"
            strength = snapback_score
        
        # Calculate stops and targets
        entry_price = last['close']
        atr = last['atr']
        
        if signal != "NEUTRAL":
            stop_loss, take_profit = self.calculate_stop_and_target(
                entry_price, signal, atr, risk_reward=2.0
            )
            risk_reward = 2.0
        else:
            stop_loss = 0.0
            take_profit = 0.0
            risk_reward = 0.0
        
        # Metadata
        metadata = {
            "rsi": last['rsi'],
            "adx": last['adx'],
            "atr_pct": last['atr_pct'],
            "bb_width": last['bb_width'],
            "volume_zscore": last['volume_zscore'],
            "compression_detected": is_compressed,
            "momentum_direction": momentum_dir,
            "breakout_detected": breakout_dir is not None,
            "snapback_detected": snapback_dir is not None
        }
        
        return SignalResult(
            signal=signal,
            signal_type=signal_type,
            strength=min(strength, 100),
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            risk_reward=risk_reward,
            confidence_factors=confidence_factors,
            metadata=metadata
        )
