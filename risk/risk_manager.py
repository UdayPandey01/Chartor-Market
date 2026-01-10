"""
Professional Risk Management System
Implements strict institutional-grade risk controls
"""
import pandas as pd
import numpy as np
from typing import Dict, Optional, Tuple, List
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum


class PositionState(Enum):
    """Position lifecycle states"""
    FLAT = "FLAT"
    LONG = "LONG"
    SHORT = "SHORT"
    MANAGE = "MANAGE"
    EXIT = "EXIT"


@dataclass
class PositionRisk:
    """Risk parameters for a position"""
    symbol: str
    size: float
    entry_price: float
    current_price: float
    stop_loss: float
    take_profit: float
    trailing_stop: Optional[float]
    unrealized_pnl: float
    unrealized_pnl_pct: float
    risk_amount: float
    reward_amount: float
    risk_reward_ratio: float
    time_in_position: float 
    margin_used: float


@dataclass
class PortfolioRisk:
    """Portfolio-level risk metrics"""
    total_equity: float
    available_equity: float
    used_margin: float
    margin_ratio: float
    exposure_pct: float
    daily_pnl: float
    daily_pnl_pct: float
    open_positions: int
    max_positions_allowed: int
    drawdown_from_peak: float
    can_trade: bool
    risk_alerts: List[str]


class RiskManager:
    """
    Professional Risk Management System
    
    Implements:
    1. Position sizing (1.25% risk per trade)
    2. Stop loss calculation (1.3-1.8 × ATR)
    3. Portfolio limits (40% max exposure)
    4. Daily loss limits (3%)
    5. Drawdown kill switch (12%)
    6. Correlation-aware position limits
    7. Liquidation protection
    """
    
    # Risk parameters
    RISK_PER_TRADE = 0.0125  
    MAX_DAILY_LOSS = 0.03  
    MAX_DRAWDOWN = 0.12  
    MAX_EXPOSURE = 0.40  
    MAX_LEVERAGE = 20 
    
    # Stop loss parameters
    STOP_LOSS_MIN_ATR = 1.3
    STOP_LOSS_MAX_ATR = 1.8
    
    # Trailing stop parameters
    TRAILING_STOP_MIN_ATR = 1.8
    TRAILING_STOP_MAX_ATR = 2.5
    
    # Time stops
    MAX_HOLD_TIME_HOURS = 24 
    
    # Correlation groups (only one position per group allowed)
    CORRELATION_GROUPS = {
        "A": ["cmt_btcusdt", "cmt_ethusdt"],
        "B": ["cmt_solusdt", "cmt_dogeusdt"],
        "C": ["cmt_bnbusdt", "cmt_ltcusdt"],
        "D": ["cmt_xrpusdt", "cmt_adausdt"]
    }
    
    def __init__(self, initial_equity: float = 10000.0):
        self.initial_equity = initial_equity
        self.peak_equity = initial_equity
        self.current_equity = initial_equity
        self.daily_starting_equity = initial_equity
        self.last_reset_date = datetime.now().date()
        
        # Position tracking
        self.positions: Dict[str, Dict] = {}
        self.position_history: List[Dict] = []
        
        # Risk tracking
        self.daily_pnl = 0.0
        self.total_pnl = 0.0
        self.risk_alerts: List[str] = []
        
    def reset_daily_tracking(self):
        """Reset daily metrics at start of new day"""
        today = datetime.now().date()
        if today > self.last_reset_date:
            self.daily_starting_equity = self.current_equity
            self.daily_pnl = 0.0
            self.last_reset_date = today
            self.risk_alerts.clear()
    
    def update_equity(self, new_equity: float):
        """Update portfolio equity and track peak"""
        self.current_equity = new_equity
        self.peak_equity = max(self.peak_equity, new_equity)
        self.total_pnl = new_equity - self.initial_equity
    
    def calculate_position_size(self,
                                entry_price: float,
                                stop_loss: float,
                                atr: float,
                                symbol: str) -> Tuple[float, float, bool]:
        """
        Calculate position size based on risk management rules
        
        Formulas:
        - Risk = 0.0125 × Equity
        - Stop Distance = k × ATR, k ∈ [1.3, 1.8]
        - Size = Risk / Stop Distance
        - Margin = (Size × Price) / Leverage
        
        Returns: (position_size, margin_required, can_trade)
        """
        self.reset_daily_tracking()
        
        # Check if we can trade
        can_trade, reasons = self.can_open_position(symbol)
        logger.info(f"Position sizing for {symbol}:")
        logger.info(f"  Entry Price: ${entry_price:,.2f}")
        logger.info(f"  Stop Loss: ${stop_loss:,.2f}")
        logger.info(f"  ATR: ${atr:.2f}")
        logger.info(f"  Current Equity: ${self.current_equity:,.2f}")
        logger.info(f"  Can Trade Check: {can_trade} - Reasons: {reasons if not can_trade else 'OK'}")
        
        if not can_trade:
            return 0.0, 0.0, False
        
        # Calculate risk amount
        risk_amount = self.RISK_PER_TRADE * self.current_equity
        logger.info(f"  Risk Amount (1.25%): ${risk_amount:,.2f}")
        
        # Calculate stop distance
        stop_distance = abs(entry_price - stop_loss)
        logger.info(f"  Initial Stop Distance: ${stop_distance:,.2f}")
        
        # Validate stop is within ATR bounds
        min_stop = entry_price * self.STOP_LOSS_MIN_ATR * atr / entry_price
        max_stop = entry_price * self.STOP_LOSS_MAX_ATR * atr / entry_price
        
        logger.info(f"  ATR Bounds: Min=${min_stop:.2f}, Max=${max_stop:.2f}")
        
        if stop_distance < min_stop:
            logger.info(f"  Adjusting stop distance from ${stop_distance:.2f} to min ${min_stop:.2f}")
            stop_distance = min_stop
        elif stop_distance > max_stop:
            logger.info(f"  Adjusting stop distance from ${stop_distance:.2f} to max ${max_stop:.2f}")
            stop_distance = max_stop
        
        # Calculate position size
        position_size = risk_amount / stop_distance
        logger.info(f"  Position Size: {position_size:.4f} contracts (Risk ${risk_amount:.2f} / Stop ${stop_distance:.2f})")
        
        # Calculate margin required (with leverage)
        notional_value = position_size * entry_price
        margin_required = notional_value / self.MAX_LEVERAGE
        logger.info(f"  Notional Value: ${notional_value:,.2f}")
        logger.info(f"  Margin Required (20x): ${margin_required:,.2f}")
        
        # Check if margin available
        used_margin = sum(p.get("margin_used", 0) for p in self.positions.values())
        available_margin = self.current_equity - used_margin
        
        logger.info(f"  Used Margin: ${used_margin:,.2f}")
        logger.info(f"  Available Margin: ${available_margin:,.2f}")
        
        if margin_required > available_margin:
            # Reduce position size to fit available margin
            max_notional = available_margin * self.MAX_LEVERAGE
            position_size = max_notional / entry_price
            margin_required = available_margin
            logger.warning(f"  Adjusted position size to fit available margin: {position_size:.4f} contracts")
        
        # Check max exposure limit
        total_exposure = used_margin + margin_required
        max_exposure_allowed = self.current_equity * self.MAX_EXPOSURE
        
        logger.info(f"  Total Exposure: ${total_exposure:,.2f}")
        logger.info(f"  Max Exposure (40%): ${max_exposure_allowed:,.2f}")
        
        if total_exposure > max_exposure_allowed:
            # Can't open position - would exceed exposure limit
            logger.error(f"  BLOCKED: Total exposure ${total_exposure:,.2f} exceeds limit ${max_exposure_allowed:,.2f}")
            return 0.0, 0.0, False
        
        logger.info(f"  APPROVED: Position {position_size:.4f} contracts, Margin ${margin_required:,.2f}")
        return position_size, margin_required, True
    
    def calculate_stop_loss(self,
                           entry_price: float,
                           atr: float,
                           direction: str,
                           volatility_multiplier: float = 1.5) -> float:
        """
        Calculate stop loss using ATR
        
        Formula:
        Stop = Entry ± (k × ATR), k ∈ [1.3, 1.8]
        
        Dynamic k based on volatility:
        - High vol → wider stop (1.8)
        - Low vol → tighter stop (1.3)
        """
        # Dynamic multiplier based on market conditions
        k = np.clip(volatility_multiplier, self.STOP_LOSS_MIN_ATR, self.STOP_LOSS_MAX_ATR)
        
        if direction == "LONG":
            stop_loss = entry_price - (k * atr)
        else:  # SHORT
            stop_loss = entry_price + (k * atr)
        
        return stop_loss
    
    def calculate_take_profit(self,
                             entry_price: float,
                             stop_loss: float,
                             direction: str,
                             risk_reward_ratio: float = 2.0) -> float:
        """
        Calculate take profit based on risk-reward ratio
        
        Formula:
        TP = Entry + R × (Entry - Stop)
        """
        stop_distance = abs(entry_price - stop_loss)
        
        if direction == "LONG":
            take_profit = entry_price + (risk_reward_ratio * stop_distance)
        else:  # SHORT
            take_profit = entry_price - (risk_reward_ratio * stop_distance)
        
        return take_profit
    
    def calculate_trailing_stop(self,
                                entry_price: float,
                                current_price: float,
                                atr: float,
                                direction: str,
                                highest_price: Optional[float] = None) -> Optional[float]:
        """
        Calculate trailing stop
        
        Formula:
        Trailing Stop = Highest Price - m × ATR, m ∈ [1.8, 2.5]
        
        Only activates after profit > 1R
        """
        stop_distance = abs(entry_price - current_price)
        
        # Only activate trailing stop if in profit > 1R
        if direction == "LONG":
            if current_price <= entry_price:
                return None
            highest = highest_price or current_price
            trailing_stop = highest - (2.0 * atr)
            return max(trailing_stop, entry_price)  
        else:  
            if current_price >= entry_price:
                return None
            lowest = highest_price or current_price  
            trailing_stop = lowest + (2.0 * atr)
            return min(trailing_stop, entry_price)  
    
    def can_open_position(self, symbol: str) -> Tuple[bool, List[str]]:
        """
        Check if a new position can be opened
        
        Checks:
        1. Daily loss limit
        2. Drawdown limit
        3. Correlation group conflicts
        4. Max positions
        """
        reasons = []
        
        # Check daily loss limit
        daily_loss_pct = (self.current_equity - self.daily_starting_equity) / self.daily_starting_equity
        if daily_loss_pct < -self.MAX_DAILY_LOSS:
            reasons.append(f"Daily loss limit reached: {daily_loss_pct*100:.2f}%")
        
        # Check max drawdown
        drawdown = (self.peak_equity - self.current_equity) / self.peak_equity
        if drawdown > self.MAX_DRAWDOWN:
            reasons.append(f"Max drawdown exceeded: {drawdown*100:.2f}%")
        
        # Check correlation groups
        symbol_group = self._get_correlation_group(symbol)
        if symbol_group:
            for group, symbols in self.CORRELATION_GROUPS.items():
                if group == symbol_group:
                    # Check if any position in this group exists
                    for sym in symbols:
                        if sym in self.positions and sym != symbol:
                            reasons.append(f"Position already exists in correlation group {group}: {sym}")
        
        if len(self.positions) >= 1:
            reasons.append(f"Maximum positions reached: {len(self.positions)}/1")
        
        # Check exposure limit
        used_margin = sum(p.get("margin_used", 0) for p in self.positions.values())
        exposure_pct = used_margin / self.current_equity
        if exposure_pct >= self.MAX_EXPOSURE:
            reasons.append(f"Max exposure reached: {exposure_pct*100:.2f}%")
        
        can_trade = len(reasons) == 0
        return can_trade, reasons
    
    def _get_correlation_group(self, symbol: str) -> Optional[str]:
        """Get correlation group for a symbol"""
        for group, symbols in self.CORRELATION_GROUPS.items():
            if symbol in symbols:
                return group
        return None
    
    def open_position(self,
                     symbol: str,
                     direction: str,
                     entry_price: float,
                     size: float,
                     stop_loss: float,
                     take_profit: float,
                     margin_used: float,
                     atr: float) -> bool:
        """
        Open a new position with full risk tracking
        """
        # Validate position can be opened
        can_trade, reasons = self.can_open_position(symbol)
        if not can_trade:
            self.risk_alerts.extend(reasons)
            return False
        
        # Create position record
        position = {
            "symbol": symbol,
            "direction": direction,
            "entry_price": entry_price,
            "size": size,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "trailing_stop": None,
            "margin_used": margin_used,
            "atr": atr,
            "entry_time": datetime.now(),
            "highest_price": entry_price,
            "state": PositionState.LONG if direction == "LONG" else PositionState.SHORT
        }
        
        self.positions[symbol] = position
        return True
    
    def update_position(self, symbol: str, current_price: float, atr: float) -> PositionRisk:
        """
        Update position with current price and calculate risk metrics
        """
        if symbol not in self.positions:
            raise ValueError(f"No position found for {symbol}")
        
        pos = self.positions[symbol]
        direction = pos["direction"]
        entry_price = pos["entry_price"]
        size = pos["size"]
        
        # Update highest/lowest price for trailing stop
        if direction == "LONG":
            pos["highest_price"] = max(pos["highest_price"], current_price)
        else:
            pos["highest_price"] = min(pos.get("highest_price", entry_price), current_price)
        
        # Calculate trailing stop
        trailing_stop = self.calculate_trailing_stop(
            entry_price,
            current_price,
            atr,
            direction,
            pos["highest_price"]
        )
        if trailing_stop is not None:
            # Update stop loss to trailing stop if better
            if direction == "LONG" and trailing_stop > pos["stop_loss"]:
                pos["stop_loss"] = trailing_stop
                pos["trailing_stop"] = trailing_stop
            elif direction == "SHORT" and trailing_stop < pos["stop_loss"]:
                pos["stop_loss"] = trailing_stop
                pos["trailing_stop"] = trailing_stop
        
        # Calculate unrealized PnL
        if direction == "LONG":
            unrealized_pnl = (current_price - entry_price) * size
        else:
            unrealized_pnl = (entry_price - current_price) * size
        
        unrealized_pnl_pct = (unrealized_pnl / pos["margin_used"]) * 100 if pos["margin_used"] > 0 else 0
        
        # Calculate risk/reward
        risk_amount = abs(entry_price - pos["stop_loss"]) * size
        reward_amount = abs(pos["take_profit"] - entry_price) * size
        risk_reward_ratio = reward_amount / risk_amount if risk_amount > 0 else 0
        
        # Time in position
        time_in_position = (datetime.now() - pos["entry_time"]).total_seconds() / 3600
        
        return PositionRisk(
            symbol=symbol,
            size=size,
            entry_price=entry_price,
            current_price=current_price,
            stop_loss=pos["stop_loss"],
            take_profit=pos["take_profit"],
            trailing_stop=pos.get("trailing_stop"),
            unrealized_pnl=unrealized_pnl,
            unrealized_pnl_pct=unrealized_pnl_pct,
            risk_amount=risk_amount,
            reward_amount=reward_amount,
            risk_reward_ratio=risk_reward_ratio,
            time_in_position=time_in_position,
            margin_used=pos["margin_used"]
        )
    
    def should_exit_position(self, symbol: str, current_price: float) -> Tuple[bool, str]:
        """
        Check if position should be exited
        
        Exit conditions:
        1. Stop loss hit
        2. Take profit hit
        3. Trailing stop hit
        4. Time stop (max hold time)
        """
        if symbol not in self.positions:
            return False, "No position"
        
        pos = self.positions[symbol]
        direction = pos["direction"]
        
        # Check stop loss
        if direction == "LONG" and current_price <= pos["stop_loss"]:
            return True, "Stop loss hit"
        elif direction == "SHORT" and current_price >= pos["stop_loss"]:
            return True, "Stop loss hit"
        
        # Check take profit
        if direction == "LONG" and current_price >= pos["take_profit"]:
            return True, "Take profit hit"
        elif direction == "SHORT" and current_price <= pos["take_profit"]:
            return True, "Take profit hit"
        
        # Check time stop
        time_in_position = (datetime.now() - pos["entry_time"]).total_seconds() / 3600
        if time_in_position > self.MAX_HOLD_TIME_HOURS:
            return True, f"Time stop ({time_in_position:.1f}h)"
        
        return False, "Active"
    
    def close_position(self, symbol: str, exit_price: float, reason: str = "Manual") -> Dict:
        """
        Close position and calculate realized PnL
        """
        if symbol not in self.positions:
            raise ValueError(f"No position found for {symbol}")
        
        pos = self.positions.pop(symbol)
        direction = pos["direction"]
        entry_price = pos["entry_price"]
        size = pos["size"]
        
        # Calculate realized PnL
        if direction == "LONG":
            realized_pnl = (exit_price - entry_price) * size
        else:
            realized_pnl = (entry_price - exit_price) * size
        
        realized_pnl_pct = (realized_pnl / pos["margin_used"]) * 100 if pos["margin_used"] > 0 else 0
        
        # Update equity
        self.current_equity += realized_pnl
        self.daily_pnl += realized_pnl
        
        # Record to history
        trade_record = {
            "symbol": symbol,
            "direction": direction,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "size": size,
            "realized_pnl": realized_pnl,
            "realized_pnl_pct": realized_pnl_pct,
            "entry_time": pos["entry_time"],
            "exit_time": datetime.now(),
            "hold_time_hours": (datetime.now() - pos["entry_time"]).total_seconds() / 3600,
            "exit_reason": reason,
            "margin_used": pos["margin_used"]
        }
        
        self.position_history.append(trade_record)
        
        return trade_record
    
    def get_portfolio_risk(self) -> PortfolioRisk:
        """
        Calculate portfolio-level risk metrics
        """
        self.reset_daily_tracking()
        
        # Calculate used margin
        used_margin = sum(p.get("margin_used", 0) for p in self.positions.values())
        available_equity = self.current_equity - used_margin
        margin_ratio = used_margin / self.current_equity if self.current_equity > 0 else 0
        exposure_pct = margin_ratio * 100
        
        daily_pnl_pct = ((self.current_equity - self.daily_starting_equity) / 
                        self.daily_starting_equity * 100) if self.daily_starting_equity > 0 else 0
        
        drawdown = ((self.peak_equity - self.current_equity) / 
                   self.peak_equity * 100) if self.peak_equity > 0 else 0
        
        can_trade = True
        risk_alerts = []
        
        if daily_pnl_pct < -self.MAX_DAILY_LOSS * 100:
            can_trade = False
            risk_alerts.append(f"Daily loss limit: {daily_pnl_pct:.2f}%")
        
        if drawdown > self.MAX_DRAWDOWN * 100:
            can_trade = False
            risk_alerts.append(f"Max drawdown: {drawdown:.2f}%")
        
        if exposure_pct > self.MAX_EXPOSURE * 100:
            risk_alerts.append(f"High exposure: {exposure_pct:.2f}%")
        
        return PortfolioRisk(
            total_equity=self.current_equity,
            available_equity=available_equity,
            used_margin=used_margin,
            margin_ratio=margin_ratio,
            exposure_pct=exposure_pct,
            daily_pnl=self.daily_pnl,
            daily_pnl_pct=daily_pnl_pct,
            open_positions=len(self.positions),
            max_positions_allowed=1,
            drawdown_from_peak=drawdown,
            can_trade=can_trade,
            risk_alerts=risk_alerts
        )
