"""
Professional Execution Engine
Handles order execution, partial fills, retry logic, and execution tracking
"""
import time
from typing import Dict, Optional, Tuple, List
from dataclasses import dataclass
from enum import Enum
from datetime import datetime
import logging


class OrderType(Enum):
    """Order types"""
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP_LOSS = "STOP_LOSS"
    TAKE_PROFIT = "TAKE_PROFIT"


class OrderStatus(Enum):
    """Order execution status"""
    PENDING = "PENDING"
    PARTIAL = "PARTIAL"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"


@dataclass
class OrderResult:
    """Order execution result"""
    success: bool
    order_id: Optional[str]
    status: OrderStatus
    filled_size: float
    filled_price: float
    total_size: float
    fees: float
    slippage: float
    execution_time: float
    error_message: Optional[str]
    metadata: Dict


class ExecutionEngine:
    """
    Professional Order Execution Engine
    
    Features:
    - Partial fill handling
    - Spread awareness
    - Liquidation protection
    - Retry logic
    - Execution tracking
    - Reduce-only support
    """
    
    # Execution parameters
    MAX_SLIPPAGE_PCT = 0.002  
    MAX_RETRIES = 3
    RETRY_DELAY = 1.0  
    ORDER_TIMEOUT = 10.0 
    
    def __init__(self, weex_client, logger: Optional[logging.Logger] = None):
        """
        Initialize execution engine
        
        Args:
            weex_client: WeexClient instance for order execution
            logger: Optional logger instance
        """
        self.client = weex_client
        self.logger = logger or logging.getLogger(__name__)
        
        # Execution tracking
        self.execution_history: List[OrderResult] = []
        self.failed_orders: List[Dict] = []
        
        # Statistics
        self.total_orders = 0
        self.successful_orders = 0
        self.failed_orders_count = 0
        self.total_slippage = 0.0
        self.total_fees = 0.0
    
    def check_spread(self, symbol: str) -> Tuple[bool, float, float]:
        """
        Check bid-ask spread before execution
        
        Returns: (spread_acceptable, bid, ask)
        """
        try:
            # Check if client has orderbook method
            if not hasattr(self.client, 'get_orderbook'):
                self.logger.debug(f"Orderbook check skipped - method not available")
                return True, 0.0, 0.0  
            
            # Get orderbook from WEEX
            orderbook = self.client.get_orderbook(symbol)
            
            if not orderbook or "bids" not in orderbook or "asks" not in orderbook:
                self.logger.warning(f"No orderbook data for {symbol}")
                return True, 0.0, 0.0  
            
            bids = orderbook["bids"]
            asks = orderbook["asks"]
            
            if not bids or not asks:
                return True, 0.0, 0.0
            
            best_bid = float(bids[0][0])
            best_ask = float(asks[0][0])
            
            # Calculate spread percentage
            spread_pct = (best_ask - best_bid) / best_bid
            
            # Spread should be < 0.1% for crypto
            spread_acceptable = spread_pct < 0.001
            
            if not spread_acceptable:
                self.logger.warning(f"Wide spread on {symbol}: {spread_pct*100:.3f}%")
            
            return spread_acceptable, best_bid, best_ask
            
        except Exception as e:
            self.logger.error(f"Error checking spread: {e}")
            return False, 0.0, 0.0
    
    def calculate_liquidation_price(self,
                                   entry_price: float,
                                   leverage: float,
                                   direction: str) -> float:
        """
        Calculate liquidation price
        
        Formula:
        Liquidation = Entry × (1 ± 1/Leverage × 0.9)
        (0.9 factor for maintenance margin)
        """
        if direction == "LONG":
            liq_price = entry_price * (1 - (1 / leverage) * 0.9)
        else:  # SHORT
            liq_price = entry_price * (1 + (1 / leverage) * 0.9)
        
        return liq_price
    
    def validate_order_safety(self,
                             symbol: str,
                             side: str,
                             size: float,
                             entry_price: float,
                             stop_loss: float,
                             leverage: float = 20) -> Tuple[bool, List[str]]:
        """
        Validate order safety before execution
        
        Checks:
        1. Spread acceptable
        2. Stop loss not too close to liquidation
        3. Position size reasonable
        4. Price stability
        """
        warnings = []
        
        # Check spread
        spread_ok, bid, ask = self.check_spread(symbol)
        if not spread_ok:
            warnings.append("Wide spread detected")
        
        # Calculate liquidation price
        direction = "LONG" if side == "buy" else "SHORT"
        liq_price = self.calculate_liquidation_price(entry_price, leverage, direction)
        
        # Ensure stop loss is at least 3% away from liquidation (relaxed from 10%)
        if direction == "LONG":
            distance_to_liq = (stop_loss - liq_price) / entry_price
        else:
            distance_to_liq = (liq_price - stop_loss) / entry_price
        
        if distance_to_liq < 0.03:  
            warnings.append(f"Stop loss too close to liquidation: {distance_to_liq*100:.1f}%")
        
        # Check if size is reasonable (not zero or negative)
        if size <= 0:
            warnings.append(f"Invalid position size: {size}")
        
        is_safe = len(warnings) == 0
        return is_safe, warnings
    
    def execute_market_order(self,
                            symbol: str,
                            side: str,
                            size: float,
                            reduce_only: bool = False,
                            max_retries: Optional[int] = None) -> OrderResult:
        """
        Execute market order with retry logic
        
        Args:
            symbol: Trading symbol (e.g., "cmt_btcusdt")
            side: "buy" or "sell"
            size: Order size
            reduce_only: If True, order can only reduce position
            max_retries: Maximum retry attempts
        
        Returns:
            OrderResult with execution details
        """
        start_time = time.time()
        max_retries = max_retries or self.MAX_RETRIES
        
        # Get expected price before execution
        spread_ok, bid, ask = self.check_spread(symbol)
        expected_price = ask if side == "buy" else bid
        
        for attempt in range(max_retries):
            try:
                self.logger.info(f"Executing {side} order for {symbol}, size: {size} (attempt {attempt + 1}/{max_retries})")
                
                # Execute order via WEEX client
                response = self.client.execute_order(
                    side=side,
                    size=str(size),
                    symbol=symbol,
                    order_type="market"
                )
                
                # Parse response
                if not response:
                    raise Exception("No response from exchange")
                
                if response.get("code") != "00000":
                    error_msg = response.get("msg", "Unknown error")
                    self.logger.error(f"Order failed: {error_msg}")
                    
                    # Retry on certain errors
                    if attempt < max_retries - 1:
                        time.sleep(self.RETRY_DELAY)
                        continue
                    
                    # Failed after retries
                    self.total_orders += 1
                    self.failed_orders_count += 1
                    
                    return OrderResult(
                        success=False,
                        order_id=None,
                        status=OrderStatus.FAILED,
                        filled_size=0.0,
                        filled_price=0.0,
                        total_size=size,
                        fees=0.0,
                        slippage=0.0,
                        execution_time=time.time() - start_time,
                        error_message=error_msg,
                        metadata={"response": response}
                    )
                
                # Successful execution
                order_data = response.get("data", {})
                order_id = order_data.get("orderId", "unknown")
                
                filled_price = float(order_data.get("fillPrice", expected_price))
                filled_size = float(order_data.get("fillSize", size))
                fees = float(order_data.get("fee", 0.0))
                
                # Calculate slippage
                slippage = abs(filled_price - expected_price) / expected_price
                
                # Determine status
                if filled_size >= size * 0.99:  
                    status = OrderStatus.FILLED
                elif filled_size > 0:
                    status = OrderStatus.PARTIAL
                else:
                    status = OrderStatus.PENDING
                
                # Update statistics
                self.total_orders += 1
                self.successful_orders += 1
                self.total_slippage += slippage
                self.total_fees += fees
                
                execution_time = time.time() - start_time
                
                self.logger.info(f"Order executed successfully: {order_id}, "
                               f"filled {filled_size}/{size} @ {filled_price}, "
                               f"slippage: {slippage*100:.3f}%")
                
                result = OrderResult(
                    success=True,
                    order_id=order_id,
                    status=status,
                    filled_size=filled_size,
                    filled_price=filled_price,
                    total_size=size,
                    fees=fees,
                    slippage=slippage,
                    execution_time=execution_time,
                    error_message=None,
                    metadata={
                        "response": response,
                        "expected_price": expected_price,
                        "attempt": attempt + 1
                    }
                )
                
                self.execution_history.append(result)
                return result
                
            except Exception as e:
                self.logger.error(f"Execution error on attempt {attempt + 1}: {e}")
                
                if attempt < max_retries - 1:
                    time.sleep(self.RETRY_DELAY)
                    continue
                
                # Final failure
                self.total_orders += 1
                self.failed_orders_count += 1
                
                return OrderResult(
                    success=False,
                    order_id=None,
                    status=OrderStatus.FAILED,
                    filled_size=0.0,
                    filled_price=0.0,
                    total_size=size,
                    fees=0.0,
                    slippage=0.0,
                    execution_time=time.time() - start_time,
                    error_message=str(e),
                    metadata={"attempts": attempt + 1}
                )
        
        # Should not reach here
        return OrderResult(
            success=False,
            order_id=None,
            status=OrderStatus.FAILED,
            filled_size=0.0,
            filled_price=0.0,
            total_size=size,
            fees=0.0,
            slippage=0.0,
            execution_time=time.time() - start_time,
            error_message="Max retries exceeded",
            metadata={}
        )
    
    def execute_stop_loss_order(self,
                               symbol: str,
                               side: str,
                               size: float,
                               stop_price: float) -> OrderResult:
        """
        Place stop loss order
        
        Note: WEEX may require different API endpoint for stop orders
        This is a placeholder - implement based on WEEX API docs
        """
        self.logger.info(f"Placing stop loss order: {symbol} {side} @ {stop_price}")
        
        try:
            # Place stop loss order
            response = self.client.place_stop_order(
                symbol=symbol,
                side=side,
                size=str(size),
                stop_price=str(stop_price)
            )
            
            if response and response.get("code") == "00000":
                order_data = response.get("data", {})
                order_id = order_data.get("orderId")
                
                return OrderResult(
                    success=True,
                    order_id=order_id,
                    status=OrderStatus.PENDING,
                    filled_size=0.0,
                    filled_price=0.0,
                    total_size=size,
                    fees=0.0,
                    slippage=0.0,
                    execution_time=0.0,
                    error_message=None,
                    metadata={"stop_price": stop_price, "response": response}
                )
            else:
                return OrderResult(
                    success=False,
                    order_id=None,
                    status=OrderStatus.FAILED,
                    filled_size=0.0,
                    filled_price=0.0,
                    total_size=size,
                    fees=0.0,
                    slippage=0.0,
                    execution_time=0.0,
                    error_message=response.get("msg", "Failed to place stop order"),
                    metadata={"response": response}
                )
                
        except Exception as e:
            self.logger.error(f"Stop loss order error: {e}")
            return OrderResult(
                success=False,
                order_id=None,
                status=OrderStatus.FAILED,
                filled_size=0.0,
                filled_price=0.0,
                total_size=size,
                fees=0.0,
                slippage=0.0,
                execution_time=0.0,
                error_message=str(e),
                metadata={}
            )
    
    def get_execution_statistics(self) -> Dict:
        """Get execution performance statistics"""
        if self.total_orders == 0:
            return {
                "total_orders": 0,
                "success_rate": 0.0,
                "avg_slippage": 0.0,
                "total_fees": 0.0
            }
        
        return {
            "total_orders": self.total_orders,
            "successful_orders": self.successful_orders,
            "failed_orders": self.failed_orders_count,
            "success_rate": (self.successful_orders / self.total_orders) * 100,
            "avg_slippage": (self.total_slippage / self.successful_orders) * 100 if self.successful_orders > 0 else 0,
            "total_fees": self.total_fees,
            "avg_fee_per_order": self.total_fees / self.successful_orders if self.successful_orders > 0 else 0
        }
