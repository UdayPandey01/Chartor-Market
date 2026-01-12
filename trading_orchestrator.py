"""
Institutional Trading Orchestrator
Main engine that coordinates all components: strategy, regime, risk, execution, rotation
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import logging
import time

from strategy.intraday_engine import IntradayMomentumEngine, SignalResult
from regime.ofras import OFRASRegimeDetector, RegimeType, RegimeState
from risk.risk_manager import RiskManager, PositionState, PortfolioRisk
from execution.execution_engine import ExecutionEngine, OrderResult


@dataclass
class AssetScore:
    """Asset opportunity score for rotation"""
    symbol: str
    score: float
    signal: str
    confidence: float
    regime: str
    metadata: Dict


class TradingOrchestrator:
    """
    Main Trading System Orchestrator
    
    Runs every 30 seconds and:
    1. Scores all enabled assets
    2. Detects market regime
    3. Rotates capital to highest probability opportunity
    4. Manages open positions
    5. Enforces risk limits
    """
    
    ENABLED_SYMBOLS = [
        "cmt_btcusdt", "cmt_ethusdt", "cmt_solusdt", 
        "cmt_dogeusdt", "cmt_xrpusdt", "cmt_adausdt",
        "cmt_bnbusdt", "cmt_ltcusdt"
    ]
    
    CYCLE_INTERVAL = 30  # seconds
    MIN_SIGNAL_STRENGTH = 25.0  # Minimum signal strength to trade (lowered for testing)
    
    def __init__(self,
                 weex_client,
                 initial_equity: float = 10000.0,
                 logger: Optional[logging.Logger] = None):
        """
        Initialize trading orchestrator
        
        Args:
            weex_client: WeexClient instance
            initial_equity: Starting capital
            logger: Optional logger
        """
        self.client = weex_client
        self.logger = logger or logging.getLogger(__name__)
        
        # Initialize components
        self.strategy_engine = IntradayMomentumEngine()
        self.regime_detector = OFRASRegimeDetector()
        self.risk_manager = RiskManager(initial_equity=initial_equity)
        self.execution_engine = ExecutionEngine(weex_client, logger=self.logger)
        
        # State tracking
        self.current_regime: Optional[RegimeState] = None
        self.asset_scores: Dict[str, AssetScore] = {}
        self.last_cycle_time = datetime.now()
        self.cycle_count = 0
        
        # Performance tracking
        self.total_signals_generated = 0
        self.trades_executed = 0
        self.signals_filtered_by_regime = 0
        self.signals_filtered_by_risk = 0
        
        self.logger.info("🚀 Institutional Trading Orchestrator initialized")
        self.logger.info(f"   Enabled symbols: {len(self.ENABLED_SYMBOLS)}")
        self.logger.info(f"   Initial equity: ${initial_equity:,.2f}")
    
    def fetch_market_data(self, symbol: str, limit: int = 100) -> Optional[pd.DataFrame]:
        """Fetch and prepare market data for a symbol"""
        try:
            self.logger.info(f"      📡 Fetching {limit} candles for {symbol}...")
            candles = self.client.fetch_candles(symbol=symbol, limit=limit)
            
            if not candles or len(candles) < 50:
                self.logger.warning(f"Insufficient data for {symbol}: got {len(candles) if candles else 0} candles")
                return None
            
            self.logger.info(f"      ✓ Received {len(candles)} candles")
            
            # Convert to DataFrame
            df = pd.DataFrame(candles, columns=[
                'timestamp', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'quote_volume', 'trades', 'taker_buy_base', 
                'taker_buy_quote', 'ignore'
            ])
            
            # Keep only needed columns
            df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
            
            # Convert to numeric
            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = df[col].astype(float)
            
            # Log first and last candle for verification
            first = df.iloc[0]
            last = df.iloc[-1]
            self.logger.info(f"      First candle: O={first['open']:.2f} H={first['high']:.2f} L={first['low']:.2f} C={first['close']:.2f}")
            self.logger.info(f"      Last candle:  O={last['open']:.2f} H={last['high']:.2f} L={last['low']:.2f} C={last['close']:.2f} Vol={last['volume']:.2f}")
            
            return df
            
        except Exception as e:
            self.logger.error(f"Error fetching data for {symbol}: {e}", exc_info=True)
            return None
    
    def get_funding_rate(self, symbol: str) -> Optional[float]:
        """Get current funding rate (if available from exchange)"""
        try:
            # Placeholder - implement based on WEEX API
            # funding_data = self.client.get_funding_rate(symbol)
            # return funding_data.get("fundingRate", 0.0)
            return None  # Return None if not available
        except Exception as e:
            self.logger.debug(f"Funding rate not available for {symbol}: {e}")
            return None
    
    def get_oi_change(self, symbol: str) -> Optional[float]:
        """Get open interest change (if available)"""
        try:
            # Placeholder - implement based on WEEX API
            return None
        except Exception as e:
            self.logger.debug(f"OI data not available for {symbol}: {e}")
            return None
    
    def score_asset(self, symbol: str) -> Optional[AssetScore]:
        """
        Score an asset for opportunity
        
        Formula:
        Score = 0.30×Trend + 0.25×Momentum + 0.15×Vol + 0.15×FP + 0.10×OBI - 0.05×Risk
        """
        try:
            # Fetch market data
            df = self.fetch_market_data(symbol)
            if df is None or len(df) < 50:
                return None
            
            # Detect regime
            funding_rate = self.get_funding_rate(symbol)
            oi_change = self.get_oi_change(symbol)
            
            regime_state = self.regime_detector.detect_regime(
                df, funding_rate, oi_change
            )
            
            # Generate signal
            signal_result = self.strategy_engine.generate_signal(
                df, funding_rate, oi_change
            )
            
            # Track signal generation
            if signal_result.signal in ["LONG", "SHORT"] and signal_result.strength > 0:
                self.total_signals_generated += 1
            
            # Always log signal details to diagnose issues
            self.logger.info(f"   {symbol}: {signal_result.signal} ({signal_result.signal_type}) | "
                           f"Strength: {signal_result.strength:.1f} | Regime: {regime_state.regime.value}")
            
            # Apply regime filters
            regime_filters = self.regime_detector.get_strategy_filter(regime_state)
            
            # Show allowed strategies
            if signal_result.signal in ["LONG", "SHORT"]:
                self.logger.info(f"      Allowed strategies: {[k for k,v in regime_filters.items() if v]}")
            
            # Check if signal type is enabled in current regime
            signal_allowed = False
            if signal_result.signal in ["LONG", "SHORT"]:
                # Check if the signal_type matches enabled strategies
                signal_allowed = regime_filters.get(signal_result.signal_type, False)
            
            if not signal_allowed:
                if signal_result.signal in ["LONG", "SHORT"] and signal_result.strength > 30:
                    self.logger.info(f"      ❌ FILTERED: {signal_result.signal_type} not allowed in {regime_state.regime.value} mode")
                self.logger.debug(f"{symbol}: FILTERED by regime - {regime_state.regime.value} doesn't allow {signal_result.signal_type} (filters: {regime_filters})")
                self.signals_filtered_by_regime += 1
                signal_result.strength = 0.0  # Filter out
            
            # Composite score using the formula
            score = 0.0
            
            # Trend component (30%)
            trend_factor = signal_result.confidence_factors.get("momentum", 0) / 100
            score += 0.30 * trend_factor * 100
            
            # Momentum component (25%)
            momentum_factor = signal_result.confidence_factors.get("trend_strength", 0) / 100
            score += 0.25 * momentum_factor * 100
            
            # Volatility component (15%)
            vol_factor = signal_result.confidence_factors.get("volatility_compression", 0) / 100
            score += 0.15 * vol_factor * 100
            
            # Funding pressure (15%)
            fp_factor = signal_result.confidence_factors.get("funding_pressure", 0) / 100 if "funding_pressure" in signal_result.confidence_factors else 0
            score += 0.15 * fp_factor * 100
            
            # Orderbook imbalance (10%)
            obi_factor = signal_result.confidence_factors.get("orderbook_imbalance", 0) / 100 if "orderbook_imbalance" in signal_result.confidence_factors else 0
            score += 0.10 * obi_factor * 100
            
            # Risk penalty (5%)
            # Lower score if regime confidence is low
            risk_penalty = (100 - regime_state.confidence) / 100
            score -= 0.05 * risk_penalty * 100
            
            # Combine with signal strength
            final_score = (score * 0.5 + signal_result.strength * 0.5)
            
            return AssetScore(
                symbol=symbol,
                score=final_score,
                signal=signal_result.signal,
                confidence=signal_result.strength,
                regime=regime_state.regime.value,
                metadata={
                    "signal_result": signal_result,
                    "regime_state": regime_state,
                    "filters_applied": regime_filters,
                    "signal_allowed": signal_allowed
                }
            )
            
        except Exception as e:
            self.logger.error(f"Error scoring {symbol}: {e}")
            return None
    
    def select_best_opportunity(self) -> Optional[AssetScore]:
        """
        Select the highest-scoring asset that passes all filters
        
        Enforces:
        - Correlation group constraints
        - Minimum signal strength
        - Risk limits
        """
        # Score all assets
        self.asset_scores.clear()
        
        signals_found = 0
        for symbol in self.ENABLED_SYMBOLS:
            asset_score = self.score_asset(symbol)
            if asset_score and asset_score.score > 0:
                self.asset_scores[symbol] = asset_score
                if asset_score.signal in ["LONG", "SHORT"]:
                    signals_found += 1
        
        self.logger.info(f"   Scanned {len(self.ENABLED_SYMBOLS)} assets, found {signals_found} potential signals")
        
        if not self.asset_scores:
            self.logger.debug("No valid opportunities found")
            return None
        
        # Sort by score
        sorted_assets = sorted(
            self.asset_scores.values(),
            key=lambda x: x.score,
            reverse=True
        )
        
        # Check each asset in order
        for asset in sorted_assets:
            # Check minimum signal strength
            if asset.score < self.MIN_SIGNAL_STRENGTH:
                continue
            
            # Check if signal is actionable
            if asset.signal not in ["LONG", "SHORT"]:
                continue
            
            # Check risk constraints
            can_trade, reasons = self.risk_manager.can_open_position(asset.symbol)
            if not can_trade:
                self.logger.debug(f"Risk filter blocked {asset.symbol}: {reasons}")
                self.signals_filtered_by_risk += 1
                continue
            
            # This is our best opportunity
            self.logger.info(f"✅ Best opportunity: {asset.symbol} - Score: {asset.score:.1f}, "
                           f"Signal: {asset.signal}, Regime: {asset.regime}")
            return asset
        
        self.logger.debug("No opportunities passed all filters")
        return None
    
    def manage_position(self, symbol: str, current_price: float, atr: float):
        """
        Manage open position
        
        Checks:
        - Stop loss / take profit hit
        - Trailing stop update
        - Time stop
        """
        try:
            # Update position metrics
            position_risk = self.risk_manager.update_position(symbol, current_price, atr)
            
            self.logger.debug(f"Position {symbol}: PnL ${position_risk.unrealized_pnl:.2f} "
                            f"({position_risk.unrealized_pnl_pct:.2f}%), "
                            f"Time: {position_risk.time_in_position:.1f}h")
            
            # Check exit conditions
            should_exit, reason = self.risk_manager.should_exit_position(symbol, current_price)
            
            if should_exit:
                self.logger.info(f"🚪 Exit signal for {symbol}: {reason}")
                self.close_position(symbol, current_price, reason)
            
        except Exception as e:
            self.logger.error(f"Error managing position {symbol}: {e}")
    
    def open_position(self, asset_score: AssetScore):
        """Open a new position"""
        try:
            symbol = asset_score.symbol
            signal_result: SignalResult = asset_score.metadata["signal_result"]
            
            # Get market data for position sizing
            df = self.fetch_market_data(symbol)
            if df is None:
                self.logger.error(f"Cannot open position - no data for {symbol}")
                return
            
            last = df.iloc[-1]
            entry_price = last['close']
            atr = signal_result.metadata.get("atr_pct", 1.0) * entry_price / 100
            
            # Use signal's stop loss and take profit
            stop_loss = signal_result.stop_loss
            take_profit = signal_result.take_profit
            
            # Calculate position size
            size, margin, can_trade = self.risk_manager.calculate_position_size(
                entry_price, stop_loss, atr, symbol
            )
            
            if not can_trade or size <= 0:
                self.logger.warning(f"Cannot open position - insufficient capital or risk limits")
                return
            
            # Validate order safety
            direction = "LONG" if asset_score.signal == "LONG" else "SHORT"
            is_safe, warnings = self.execution_engine.validate_order_safety(
                symbol, "buy" if direction == "LONG" else "sell",
                size, entry_price, stop_loss
            )
            
            if not is_safe:
                self.logger.warning(f"Order safety check failed: {warnings}")
                return
            
            # Execute order
            self.logger.info(f"🎯 Opening {direction} position on {symbol}")
            self.logger.info(f"   Entry: ${entry_price:.2f}, Stop: ${stop_loss:.2f}, "
                           f"Target: ${take_profit:.2f}")
            self.logger.info(f"   Size: {size:.4f}, Margin: ${margin:.2f}, "
                           f"R:R = {signal_result.risk_reward:.1f}")
            
            order_result = self.execution_engine.execute_market_order(
                symbol=symbol,
                side="buy" if direction == "LONG" else "sell",
                size=size
            )
            
            if order_result.success:
                # Register position with risk manager
                self.risk_manager.open_position(
                    symbol=symbol,
                    direction=direction,
                    entry_price=order_result.filled_price,
                    size=order_result.filled_size,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    margin_used=margin,
                    atr=atr
                )
                
                self.trades_executed += 1
                self.logger.info(f"✅ Position opened successfully: {order_result.order_id}")
            else:
                self.logger.error(f"❌ Order execution failed: {order_result.error_message}")
            
        except Exception as e:
            self.logger.error(f"Error opening position: {e}")
    
    def close_position(self, symbol: str, exit_price: float, reason: str):
        """Close an open position"""
        try:
            if symbol not in self.risk_manager.positions:
                self.logger.warning(f"No open position for {symbol}")
                return
            
            pos = self.risk_manager.positions[symbol]
            direction = pos["direction"]
            size = pos["size"]
            
            self.logger.info(f"🔚 Closing {direction} position on {symbol}: {reason}")
            
            # Execute close order
            order_result = self.execution_engine.execute_market_order(
                symbol=symbol,
                side="sell" if direction == "LONG" else "buy",
                size=size,
                reduce_only=True
            )
            
            if order_result.success:
                # Close position in risk manager
                trade_record = self.risk_manager.close_position(
                    symbol, order_result.filled_price, reason
                )
                
                self.logger.info(f"✅ Position closed: PnL ${trade_record['realized_pnl']:.2f} "
                               f"({trade_record['realized_pnl_pct']:.2f}%), "
                               f"Hold time: {trade_record['hold_time_hours']:.1f}h")
            else:
                self.logger.error(f"❌ Close order failed: {order_result.error_message}")
            
        except Exception as e:
            self.logger.error(f"Error closing position: {e}")
    
    def run_cycle(self):
        """
        Run one trading cycle
        
        Process:
        1. Update equity from account balance
        2. Manage open positions
        3. If flat, search for new opportunity
        4. Execute highest probability setup
        """
        self.cycle_count += 1
        self.logger.info(f"\n{'='*60}")
        self.logger.info(f"CYCLE #{self.cycle_count} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self.logger.info(f"{'='*60}")
        
        try:
            # Get portfolio status
            portfolio_risk = self.risk_manager.get_portfolio_risk()
            
            self.logger.info(f"💰 Equity: ${portfolio_risk.total_equity:,.2f} | "
                           f"Daily PnL: ${portfolio_risk.daily_pnl:,.2f} ({portfolio_risk.daily_pnl_pct:.2f}%) | "
                           f"Exposure: {portfolio_risk.exposure_pct:.1f}% | "
                           f"Positions: {portfolio_risk.open_positions}/{portfolio_risk.max_positions_allowed}")
            
            if portfolio_risk.risk_alerts:
                for alert in portfolio_risk.risk_alerts:
                    self.logger.warning(f"⚠️ {alert}")
            
            # Manage open positions
            if portfolio_risk.open_positions > 0:
                for symbol in list(self.risk_manager.positions.keys()):
                    df = self.fetch_market_data(symbol)
                    if df is not None:
                        last = df.iloc[-1]
                        current_price = last['close']
                        
                        # Calculate ATR
                        if 'atr' in df.columns:
                            atr = df['atr'].iloc[-1]
                        else:
                            atr = last['close'] * 0.015  # Estimate 1.5% ATR
                        
                        self.manage_position(symbol, current_price, atr)
            
            # If flat and can trade, look for new opportunity
            if portfolio_risk.open_positions == 0 and portfolio_risk.can_trade:
                self.logger.info("🔍 Scanning for opportunities...")
                
                best_opportunity = self.select_best_opportunity()
                
                if best_opportunity:
                    self.open_position(best_opportunity)
                else:
                    self.logger.info("⏸️ No valid opportunities - staying flat")
            
            # Update statistics
            self.logger.info(f"\n📊 Session Stats:")
            self.logger.info(f"   Trades executed: {self.trades_executed}")
            self.logger.info(f"   Signals generated: {self.total_signals_generated}")
            self.logger.info(f"   Filtered by regime: {self.signals_filtered_by_regime}")
            self.logger.info(f"   Filtered by risk: {self.signals_filtered_by_risk}")
            
            exec_stats = self.execution_engine.get_execution_statistics()
            self.logger.info(f"   Execution success rate: {exec_stats['success_rate']:.1f}%")
            
        except Exception as e:
            self.logger.error(f"Error in trading cycle: {e}", exc_info=True)
        
        self.last_cycle_time = datetime.now()
    
    def run_continuous(self):
        """Run continuous trading loop"""
        self.logger.info("🚀 Starting continuous trading loop...")
        self.logger.info(f"   Cycle interval: {self.CYCLE_INTERVAL}s")
        
        try:
            while True:
                self.run_cycle()
                
                # Sleep until next cycle
                time.sleep(self.CYCLE_INTERVAL)
                
        except KeyboardInterrupt:
            self.logger.info("\n🛑 Shutting down gracefully...")
            
            # Close any open positions
            for symbol in list(self.risk_manager.positions.keys()):
                df = self.fetch_market_data(symbol)
                if df is not None:
                    current_price = df['close'].iloc[-1]
                    self.close_position(symbol, current_price, "System shutdown")
            
            self.logger.info("✅ Shutdown complete")
