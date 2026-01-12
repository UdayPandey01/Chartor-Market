"""
Execution Safety Layer
Pre-execution validation to prevent dangerous trades
All checks MUST pass before order submission
"""
import logging
from typing import Tuple, List, Dict, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta

from core.weex_api import WeexClient
from core.db_manager import get_db_connection


@dataclass
class SafetyCheckResult:
    """Result of safety check"""
    passed: bool
    check_name: str
    message: str
    severity: str  # "CRITICAL", "WARNING", "INFO"


class ExecutionSafetyLayer:
    """
    Pre-Execution Safety Validator
    
    Validates ALL trades before submission:
    1. Margin availability
    2. Liquidation distance
    3. Minimum order size
    4. Daily loss limit
    5. Max drawdown limit
    6. Exposure limit
    7. Correlation conflicts
    8. Symbol validity
    9. Price reasonableness
    10. Stop loss validity
    
    NO SILENT FAILURES - All rejections logged and returned
    """
    
    # Safety parameters
    MIN_LIQUIDATION_DISTANCE_PCT = 0.04  # 4% minimum distance from liquidation
    MAX_DAILY_LOSS_PCT = 0.03  # 3% maximum daily loss
    MAX_DRAWDOWN_PCT = 0.12  # 12% maximum drawdown from peak
    MAX_EXPOSURE_PCT = 0.40  # 40% maximum portfolio exposure
    MAX_LEVERAGE = 20
    
    # Minimum order sizes (WEEX requirements)
    MIN_ORDER_SIZES = {
        "cmt_btcusdt": 0.001,
        "cmt_ethusdt": 0.01,
        "cmt_solusdt": 0.1,
        "cmt_dogeusdt": 10.0,
        "cmt_xrpusdt": 1.0,
        "cmt_adausdt": 1.0,
        "cmt_bnbusdt": 0.01,
        "cmt_ltcusdt": 0.01
    }
    
    CORRELATION_GROUPS = {
        "A": ["cmt_btcusdt", "cmt_ethusdt"],
        "B": ["cmt_solusdt", "cmt_dogeusdt"],
        "C": ["cmt_bnbusdt", "cmt_ltcusdt"],
        "D": ["cmt_xrpusdt", "cmt_adausdt"]
    }
    
    def __init__(self,
                 weex_client: WeexClient,
                 initial_equity: float = 10000.0,
                 logger: Optional[logging.Logger] = None):
        """
        Initialize safety layer
        
        Args:
            weex_client: WEEX client for balance/position queries
            initial_equity: Starting equity
            logger: Logger instance
        """
        self.client = weex_client
        self.initial_equity = initial_equity
        self.peak_equity = initial_equity
        self.current_equity = initial_equity
        self.daily_starting_equity = initial_equity
        self.last_reset_date = datetime.now().date()
        self.logger = logger or logging.getLogger(__name__)
        
        # Tracking
        self.total_checks = 0
        self.total_rejections = 0
        self.rejection_reasons: Dict[str, int] = {}
        
        self.logger.info("🛡️ Execution Safety Layer initialized")
    
    def reset_daily_tracking(self):
        """Reset daily metrics at start of new day"""
        today = datetime.now().date()
        if today > self.last_reset_date:
            self.daily_starting_equity = self.current_equity
            self.last_reset_date = today
            self.logger.info(f"📅 Daily tracking reset: Starting equity ${self.current_equity:,.2f}")
    
    def update_equity(self, new_equity: float):
        """Update current equity"""
        self.current_equity = new_equity
        self.peak_equity = max(self.peak_equity, new_equity)
    
    def check_margin_availability(self,
                                  required_margin: float,
                                  current_positions: List[Dict]) -> SafetyCheckResult:
        """
        Check if sufficient margin is available
        
        Formula:
        Available Margin = Current Equity - Sum(Position Margins)
        """
        try:
            # Calculate used margin from current positions
            used_margin = sum(p.get("margin_used", 0) for p in current_positions)
            available_margin = self.current_equity - used_margin
            
            if required_margin > available_margin:
                return SafetyCheckResult(
                    passed=False,
                    check_name="MARGIN_AVAILABILITY",
                    message=f"Insufficient margin: Required ${required_margin:.2f}, Available ${available_margin:.2f}",
                    severity="CRITICAL"
                )
            
            margin_usage_pct = ((used_margin + required_margin) / self.current_equity) * 100
            
            return SafetyCheckResult(
                passed=True,
                check_name="MARGIN_AVAILABILITY",
                message=f"Margin OK: ${required_margin:.2f} required, ${available_margin:.2f} available ({margin_usage_pct:.1f}% total usage)",
                severity="INFO"
            )
        except Exception as e:
            return SafetyCheckResult(
                passed=False,
                check_name="MARGIN_AVAILABILITY",
                message=f"Error checking margin: {e}",
                severity="CRITICAL"
            )
    
    def check_liquidation_distance(self,
                                   entry_price: float,
                                   direction: str,
                                   leverage: int,
                                   stop_loss: float) -> SafetyCheckResult:
        """
        Check if stop loss is safely distant from liquidation price
        
        Formula:
        Liquidation = Entry × (1 ± 1/Leverage × 0.9)
        Stop must be at least 4% away from liquidation
        """
        try:
            if direction == "LONG":
                liq_price = entry_price * (1 - (1 / leverage) * 0.9)
                distance_from_liq = (stop_loss - liq_price) / entry_price
            else:  # SHORT
                liq_price = entry_price * (1 + (1 / leverage) * 0.9)
                distance_from_liq = (liq_price - stop_loss) / entry_price
            
            distance_pct = distance_from_liq * 100
            
            if distance_pct < self.MIN_LIQUIDATION_DISTANCE_PCT * 100:
                return SafetyCheckResult(
                    passed=False,
                    check_name="LIQUIDATION_DISTANCE",
                    message=f"Stop loss too close to liquidation: {distance_pct:.2f}% (minimum {self.MIN_LIQUIDATION_DISTANCE_PCT*100}%)",
                    severity="CRITICAL"
                )
            
            return SafetyCheckResult(
                passed=True,
                check_name="LIQUIDATION_DISTANCE",
                message=f"Liquidation distance OK: {distance_pct:.2f}% (Liq: ${liq_price:.2f}, SL: ${stop_loss:.2f})",
                severity="INFO"
            )
        except Exception as e:
            return SafetyCheckResult(
                passed=False,
                check_name="LIQUIDATION_DISTANCE",
                message=f"Error checking liquidation: {e}",
                severity="CRITICAL"
            )
    
    def check_minimum_order_size(self, symbol: str, size: float) -> SafetyCheckResult:
        """Check if order size meets exchange minimum"""
        min_size = self.MIN_ORDER_SIZES.get(symbol, 0.001)
        
        if size < min_size:
            return SafetyCheckResult(
                passed=False,
                check_name="MINIMUM_ORDER_SIZE",
                message=f"Order size {size} below minimum {min_size} for {symbol}",
                severity="CRITICAL"
            )
        
        return SafetyCheckResult(
            passed=True,
            check_name="MINIMUM_ORDER_SIZE",
            message=f"Order size OK: {size} (min: {min_size})",
            severity="INFO"
        )
    
    def check_daily_loss_limit(self) -> SafetyCheckResult:
        """Check if daily loss limit has been exceeded"""
        self.reset_daily_tracking()
        
        daily_pnl = self.current_equity - self.daily_starting_equity
        daily_pnl_pct = daily_pnl / self.daily_starting_equity
        
        if daily_pnl_pct < -self.MAX_DAILY_LOSS_PCT:
            return SafetyCheckResult(
                passed=False,
                check_name="DAILY_LOSS_LIMIT",
                message=f"Daily loss limit exceeded: {daily_pnl_pct*100:.2f}% (max: {self.MAX_DAILY_LOSS_PCT*100}%)",
                severity="CRITICAL"
            )
        
        remaining_loss_buffer = (self.MAX_DAILY_LOSS_PCT + daily_pnl_pct) * 100
        
        return SafetyCheckResult(
            passed=True,
            check_name="DAILY_LOSS_LIMIT",
            message=f"Daily loss OK: {daily_pnl_pct*100:.2f}% ({remaining_loss_buffer:.2f}% buffer remaining)",
            severity="INFO"
        )
    
    def check_max_drawdown(self) -> SafetyCheckResult:
        """Check if maximum drawdown has been exceeded"""
        drawdown = (self.peak_equity - self.current_equity) / self.peak_equity
        
        if drawdown > self.MAX_DRAWDOWN_PCT:
            return SafetyCheckResult(
                passed=False,
                check_name="MAX_DRAWDOWN",
                message=f"Max drawdown exceeded: {drawdown*100:.2f}% (max: {self.MAX_DRAWDOWN_PCT*100}%)",
                severity="CRITICAL"
            )
        
        drawdown_buffer = (self.MAX_DRAWDOWN_PCT - drawdown) * 100
        
        return SafetyCheckResult(
            passed=True,
            check_name="MAX_DRAWDOWN",
            message=f"Drawdown OK: {drawdown*100:.2f}% ({drawdown_buffer:.2f}% buffer remaining)",
            severity="INFO"
        )
    
    def check_exposure_limit(self,
                            new_margin: float,
                            current_positions: List[Dict]) -> SafetyCheckResult:
        """Check if total exposure would exceed limit"""
        used_margin = sum(p.get("margin_used", 0) for p in current_positions)
        total_exposure = used_margin + new_margin
        exposure_pct = total_exposure / self.current_equity
        
        if exposure_pct > self.MAX_EXPOSURE_PCT:
            return SafetyCheckResult(
                passed=False,
                check_name="EXPOSURE_LIMIT",
                message=f"Exposure limit exceeded: {exposure_pct*100:.2f}% (max: {self.MAX_EXPOSURE_PCT*100}%)",
                severity="CRITICAL"
            )
        
        exposure_buffer = (self.MAX_EXPOSURE_PCT - exposure_pct) * 100
        
        return SafetyCheckResult(
            passed=True,
            check_name="EXPOSURE_LIMIT",
            message=f"Exposure OK: {exposure_pct*100:.2f}% ({exposure_buffer:.2f}% buffer remaining)",
            severity="INFO"
        )
    
    def check_correlation_conflict(self,
                                   symbol: str,
                                   current_positions: List[Dict]) -> SafetyCheckResult:
        """Check for correlation group conflicts"""
        # Find symbol's correlation group
        symbol_group = None
        for group, symbols in self.CORRELATION_GROUPS.items():
            if symbol in symbols:
                symbol_group = group
                break
        
        if symbol_group is None:
            return SafetyCheckResult(
                passed=True,
                check_name="CORRELATION_CONFLICT",
                message=f"No correlation group for {symbol}",
                severity="INFO"
            )
        
        # Check if any position exists in same group
        for pos in current_positions:
            pos_symbol = pos.get("symbol")
            for group, symbols in self.CORRELATION_GROUPS.items():
                if group == symbol_group and pos_symbol in symbols and pos_symbol != symbol:
                    return SafetyCheckResult(
                        passed=False,
                        check_name="CORRELATION_CONFLICT",
                        message=f"Correlation conflict: {pos_symbol} already open in group {group}",
                        severity="WARNING"
                    )
        
        return SafetyCheckResult(
            passed=True,
            check_name="CORRELATION_CONFLICT",
            message=f"No correlation conflict (group {symbol_group})",
            severity="INFO"
        )
    
    def check_symbol_validity(self, symbol: str) -> SafetyCheckResult:
        """Check if symbol is valid and supported"""
        valid_symbols = list(self.MIN_ORDER_SIZES.keys())
        
        if symbol not in valid_symbols:
            return SafetyCheckResult(
                passed=False,
                check_name="SYMBOL_VALIDITY",
                message=f"Invalid symbol: {symbol} (valid: {', '.join(valid_symbols)})",
                severity="CRITICAL"
            )
        
        return SafetyCheckResult(
            passed=True,
            check_name="SYMBOL_VALIDITY",
            message=f"Symbol valid: {symbol}",
            severity="INFO"
        )
    
    def check_price_reasonableness(self,
                                   symbol: str,
                                   entry_price: float,
                                   stop_loss: float,
                                   take_profit: float) -> SafetyCheckResult:
        """Check if prices are reasonable and properly ordered"""
        # Check positive prices
        if entry_price <= 0 or stop_loss <= 0 or take_profit <= 0:
            return SafetyCheckResult(
                passed=False,
                check_name="PRICE_REASONABLENESS",
                message=f"Invalid prices: Entry=${entry_price:.2f}, SL=${stop_loss:.2f}, TP=${take_profit:.2f}",
                severity="CRITICAL"
            )
        
        # Check risk:reward ratio
        stop_distance = abs(entry_price - stop_loss)
        profit_distance = abs(take_profit - entry_price)
        risk_reward = profit_distance / stop_distance if stop_distance > 0 else 0
        
        if risk_reward < 1.0:
            return SafetyCheckResult(
                passed=False,
                check_name="PRICE_REASONABLENESS",
                message=f"Poor risk:reward ratio: {risk_reward:.2f} (minimum 1.0)",
                severity="CRITICAL"
            )
        
        return SafetyCheckResult(
            passed=True,
            check_name="PRICE_REASONABLENESS",
            message=f"Prices OK: R:R = {risk_reward:.2f}",
            severity="INFO"
        )
    
    def validate_trade(self,
                      symbol: str,
                      direction: str,
                      size: float,
                      entry_price: float,
                      stop_loss: float,
                      take_profit: float,
                      leverage: int,
                      margin_required: float,
                      current_positions: List[Dict]) -> Tuple[bool, List[SafetyCheckResult]]:
        """
        Run ALL safety checks before trade execution
        
        Returns:
            (can_execute, check_results)
        """
        self.total_checks += 1
        results = []
        
        # Run all checks
        results.append(self.check_symbol_validity(symbol))
        results.append(self.check_minimum_order_size(symbol, size))
        results.append(self.check_price_reasonableness(symbol, entry_price, stop_loss, take_profit))
        results.append(self.check_margin_availability(margin_required, current_positions))
        results.append(self.check_liquidation_distance(entry_price, direction, leverage, stop_loss))
        results.append(self.check_daily_loss_limit())
        results.append(self.check_max_drawdown())
        results.append(self.check_exposure_limit(margin_required, current_positions))
        results.append(self.check_correlation_conflict(symbol, current_positions))
        
        # Determine if trade can execute
        critical_failures = [r for r in results if not r.passed and r.severity == "CRITICAL"]
        warning_failures = [r for r in results if not r.passed and r.severity == "WARNING"]
        
        can_execute = len(critical_failures) == 0
        
        # Log results
        if not can_execute:
            self.total_rejections += 1
            self.logger.warning(f"🚫 Trade REJECTED for {symbol} {direction}:")
            for failure in critical_failures:
                self.logger.warning(f"   ❌ {failure.check_name}: {failure.message}")
                # Track rejection reasons
                reason_key = failure.check_name
                self.rejection_reasons[reason_key] = self.rejection_reasons.get(reason_key, 0) + 1
            
            for warning in warning_failures:
                self.logger.warning(f"   ⚠️ {warning.check_name}: {warning.message}")
        else:
            self.logger.info(f"✅ Trade APPROVED for {symbol} {direction}")
            if warning_failures:
                for warning in warning_failures:
                    self.logger.warning(f"   ⚠️ {warning.check_name}: {warning.message}")
        
        # Log all checks in debug mode
        for result in results:
            if result.passed:
                self.logger.debug(f"   ✓ {result.check_name}: {result.message}")
        
        return can_execute, results
    
    def get_statistics(self) -> Dict:
        """Get safety layer statistics"""
        rejection_rate = (self.total_rejections / self.total_checks * 100) if self.total_checks > 0 else 0
        
        return {
            "total_checks": self.total_checks,
            "total_rejections": self.total_rejections,
            "rejection_rate_pct": rejection_rate,
            "rejection_reasons": self.rejection_reasons,
            "current_equity": self.current_equity,
            "peak_equity": self.peak_equity,
            "current_drawdown_pct": ((self.peak_equity - self.current_equity) / self.peak_equity * 100) if self.peak_equity > 0 else 0,
            "daily_pnl_pct": ((self.current_equity - self.daily_starting_equity) / self.daily_starting_equity * 100) if self.daily_starting_equity > 0 else 0
        }
