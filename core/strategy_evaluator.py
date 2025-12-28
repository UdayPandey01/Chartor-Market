"""
Strategy Evaluator Module
Evaluates active strategies against real-time market data.
"""
import re
from typing import List, Dict, Any, Optional
from core.db_manager import get_db_connection


def evaluate_strategies(market_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Evaluates all active strategies against current market data.
    
    Args:
        market_data: Dictionary containing current market state:
            - price: float
            - rsi: float
            - trend: str (BULLISH/BEARISH/NEUTRAL)
            - ema_20: float
            - volatility: float
            - volume_spike: bool
    
    Returns:
        List of dictionaries with strategy info and triggered action:
        [{"strategy_id": 1, "name": "RSI Oversold", "action": "BUY", "logic": "rsi < 30"}, ...]
    """
    triggered_strategies = []
    
    try:
        conn = get_db_connection()
        if not conn:
            return triggered_strategies
        
        cur = conn.cursor()
        cur.execute("""
            SELECT id, name, logic, action, description
            FROM strategies
            WHERE is_active = TRUE
        """)
        strategies = cur.fetchall()
        cur.close()
        conn.close()
        
        for strat in strategies:
            logic = strat.get('logic', '')
            action = strat.get('action', 'WAIT')
            
            if evaluate_logic(logic, market_data):
                triggered_strategies.append({
                    "strategy_id": strat.get('id'),
                    "name": strat.get('name'),
                    "action": action,
                    "logic": logic,
                    "description": strat.get('description')
                })
        
        return triggered_strategies
    
    except Exception as e:
        print(f"Strategy Evaluation Error: {e}")
        import traceback
        traceback.print_exc()
        return []


def evaluate_logic(logic: str, market_data: Dict[str, Any]) -> bool:
    """
    Safely evaluates a logic string against market data.
    
    Supports:
    - Comparison operators: <, >, <=, >=, ==, !=
    - Logical operators: and, or, not
    - Variables: rsi, price, ema_20, trend, volatility, volume_spike
    
    Example logic strings:
    - "rsi < 30"
    - "price > ema_20 and trend == 'BULLISH'"
    - "volume_spike == True and rsi < 50"
    """
    try:
        logic = logic.strip()
        
        rsi = float(market_data.get('rsi', 50))
        price = float(market_data.get('price', 0))
        ema_20 = float(market_data.get('ema_20', price))
        volatility = float(market_data.get('volatility', 0))
        
        trend = str(market_data.get('trend', 'NEUTRAL'))
        volume_spike = bool(market_data.get('volume_spike', False))
        
        safe_dict = {
            'rsi': rsi,
            'price': price,
            'ema_20': ema_20,
            'volatility': volatility,
            'trend': trend,
            'volume_spike': volume_spike,
            'True': True,
            'False': False,
            'true': True,
            'false': False,
        }
        
        result = eval(logic, {"__builtins__": {}}, safe_dict)
        
        return bool(result)
    
    except Exception as e:
        print(f"Logic Evaluation Error for '{logic}': {e}")
        return False


def get_active_strategies() -> List[Dict[str, Any]]:
    """Helper function to get all active strategies."""
    try:
        conn = get_db_connection()
        if not conn:
            return []
        
        cur = conn.cursor()
        cur.execute("""
            SELECT id, name, logic, action, description, is_active
            FROM strategies
            WHERE is_active = TRUE
        """)
        strategies = cur.fetchall()
        cur.close()
        conn.close()
        
        return [dict(s) for s in strategies]
    except Exception as e:
        print(f"Get Active Strategies Error: {e}")
        return []

