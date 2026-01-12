from fastapi import FastAPI, HTTPException, BackgroundTasks, Body, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
from pydantic import BaseModel
from google import genai
from google.genai import types
import os
import pandas as pd
import asyncio
import threading
import time
from dotenv import load_dotenv
from core.weex_api import WeexClient
from core.db_manager import get_db_connection

# NEW: Production-ready components
from core.position_manager import initialize_position_manager, get_position_manager
from core.sentiment_live import get_sentiment_feed, get_real_time_sentiment
from core.safety_layer import ExecutionSafetyLayer
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 1. Load Environment Variables
load_dotenv()

# 2. Validate Environment Variables
def validate_env():
    """Validates required environment variables on startup."""
    required_vars = {
        "DATABASE_URL": "PostgreSQL database connection string",
        "GEMINI_API_KEY": "Google Gemini API key for AI decisions",
    }
    
    optional_vars = {
        "WEEX_API_KEY": "WEEX exchange API key (required for live trading)",
        "WEEX_SECRET": "WEEX exchange secret key (required for live trading)",
        "WEEX_PASSPHRASE": "WEEX exchange passphrase (required for live trading)",
    }
    
    missing_required = []
    missing_optional = []
    
    for var, description in required_vars.items():
        if not os.getenv(var):
            missing_required.append(f"{var} - {description}")
    
    for var, description in optional_vars.items():
        if not os.getenv(var):
            missing_optional.append(f"{var} - {description}")
    
    if missing_required:
        print("CRITICAL: Missing required environment variables:")
        for var in missing_required:
            print(f"   - {var}")
        print("\nWARNING: Application may not function correctly without these variables.")
        print("   Please create a .env file with the required variables.\n")
    
    if missing_optional:
        print("WARNING: Missing optional environment variables:")
        for var in missing_optional:
            print(f"   - {var}")
        print("\nWARNING: Live trading will not work without WEEX credentials.\n")
    
    if not missing_required and not missing_optional:
        print("All environment variables validated successfully.\n")
    
    return len(missing_required) == 0

# Validate on import
env_valid = validate_env()

# 2. Initialize App & Clients
app = FastAPI(title="Chartor Trading Engine API")
client = WeexClient()

# NEW: Initialize production components at module level
try:
    position_manager = initialize_position_manager(client, logger)
    safety_layer = ExecutionSafetyLayer(client, initial_equity=10000.0, logger=logger)
    sentiment_feed = get_sentiment_feed()
    logger.info("✅ Production components initialized successfully")
except Exception as init_error:
    logger.warning(f"⚠️ Failed to initialize production components at module level: {init_error}")
    # Set to None - will be initialized in startup_event
    position_manager = None
    safety_layer = None
    sentiment_feed = None

trading_mode_lock = threading.Lock()  # Prevents Sentinel + Institutional conflict

# Background task control
sentinel_running = False
sentinel_thread = None

# Track which mode is active
active_trading_mode = None  # "SENTINEL" or "INSTITUTIONAL" or None

def sentinel_loop():
    """Background sentinel service that monitors markets and executes trades when auto-trading is enabled."""
    global sentinel_running
    from core.weex_api import WeexClient
    from core.analysis import analyze_market_structure
    from core.llm_brain import get_trading_decision
    from core.db_manager import save_ai_analysis, log_market_state, get_db_connection
    from core.ml_analyst import MLAnalyst
    from core.sentiment import analyze_market_sentiment
    
    client = WeexClient()
    ml_analyst = MLAnalyst()  # Initialize ML model once
    
    while sentinel_running:
        try:
            # Get current settings
            conn = get_db_connection()
            if not conn:
                time.sleep(30)
                continue
            
            cur = conn.cursor()
            cur.execute("SELECT auto_trading, risk_tolerance, current_symbol FROM trade_settings LIMIT 1")
            settings = cur.fetchone()
            cur.close()
            conn.close()
            
            if not settings:
                time.sleep(30)
                continue
            
            auto_trading = settings.get("auto_trading", False)
            risk_tolerance = settings.get("risk_tolerance", 20)
            symbol = settings.get("current_symbol", "cmt_btcusdt")
            
            # Only run if auto-trading is enabled
            if not auto_trading:
                time.sleep(30)
                continue
            
            # Check if Gemini is available (don't spam if quota exceeded)
            from core.llm_brain import quota_exceeded_until
            from datetime import datetime
            if quota_exceeded_until and datetime.now() < quota_exceeded_until:
                # Quota exceeded, wait longer between checks
                logger.warning(f"Sentinel paused: Gemini quota exceeded. Resuming in {int((quota_exceeded_until - datetime.now()).total_seconds()/60)} minutes")
                time.sleep(300)  # Check every 5 minutes instead of 30 seconds
                continue
            
            logger.info(f"\n{'='*60}")
            logger.info(f"Sentinel: {symbol} | Auto-Trade: ON | Risk: {risk_tolerance}%")
            logger.info(f"{'='*60}")
            
            # Fetch market data (get more for ML training)
            candles = client.fetch_candles(symbol=symbol, limit=500)
            
            if candles and len(candles) > 100:
                # STEP 1: Train Local ML Model (instant retraining on latest data)
                ml_trained = ml_analyst.train_model(candles)
                
                # STEP 2: Technical Analysis
                market_state = analyze_market_structure(candles)
                if not market_state:
                    time.sleep(30)
                    continue
                
                logger.info(f"   Technical: Price ${market_state.get('price', 0):.2f} | RSI {market_state.get('rsi', 50):.1f} | Trend {market_state.get('trend', 'Neutral')}")
                
                # STEP 3: Get Local ML Prediction
                ml_direction, ml_confidence = ml_analyst.predict_next_move(market_state)
                ml_prediction = {"direction": ml_direction, "confidence": ml_confidence} if ml_trained else None
                if ml_prediction:
                    logger.info(f"   Local ML: Predicts {ml_direction} ({ml_confidence}% confidence)")
                
                # STEP 4: Get Market Sentiment (REAL-TIME from CryptoPanic or FinBERT)
                symbol_clean = symbol.replace("cmt_", "").replace("usdt", "").upper()
                
                # Use real-time sentiment feed
                global sentiment_feed
                if sentiment_feed:
                    sentiment_result = sentiment_feed.get_market_sentiment(symbol_clean)
                    sent_label = sentiment_result["label"]
                    sent_score = sentiment_result["score"]
                    sentiment = {
                        "label": sent_label,
                        "score": sent_score,
                        "source": sentiment_result["source"],
                        "headline": sentiment_result.get("latest_headline", "")
                    }
                    logger.info(f"   Sentiment ({sentiment_result['source']}): {sent_label} (score: {sent_score:.2f})")
                    logger.info(f"   Headline: {sentiment_result.get('latest_headline', 'N/A')[:60]}...")
                else:
                    # Fallback to legacy sentiment
                    from core.sentiment import analyze_market_sentiment
                    sent_label, sent_score = analyze_market_sentiment(symbol_clean)
                    sentiment = {"label": sent_label, "score": sent_score}
                    logger.info(f"   FinBERT Sentiment: {sent_label} (score: {sent_score})")
                
                # STEP 5: Evaluate Active Strategies
                from core.strategy_evaluator import evaluate_strategies
                triggered_strategies = evaluate_strategies(market_state)
                
                strategy_decision = None
                strategy_name = None
                if triggered_strategies:
                    # Use the first triggered strategy (can be enhanced to handle multiple)
                    strategy_decision = triggered_strategies[0].get('action')
                    strategy_name = triggered_strategies[0].get('name')
                    logger.info(f"   Strategy Triggered: {strategy_name} -> {strategy_decision}")
                
                # STEP 6: Hybrid Decision - Send summary to Gemini (if no strategy triggered)
                if not strategy_decision or strategy_decision == "WAIT":
                    logger.info("   Consulting Gemini for final approval...")
                    ai_result = get_trading_decision(
                        market_state, 
                        symbol=symbol,
                        use_cache=False,  # Disable cache for sentinel loop to get fresh results
                        ml_prediction=ml_prediction,
                        sentiment=sentiment
                    )
                    
                    # ============================================================
                    # CRITICAL: Check Gemini status - abort on persistent errors
                    # ============================================================
                    ai_status = ai_result.get("status", "UNKNOWN")
                    ai_source = ai_result.get("source", "UNKNOWN")
                    
                    if ai_status == "ERROR":
                        logger.error(f"Gemini API error - skipping cycle")
                        logger.error(f"   Gemini API error - using fallback decision")
                    elif ai_status == "FALLBACK":
                        logger.warning(f"Using fallback decision engine (Gemini unavailable)")
                        logger.warning(f"   Using Fallback Engine (Gemini unavailable)")
                    
                    decision = ai_result.get("decision", "WAIT")
                    confidence = ai_result.get("confidence", 0)
                    reason = ai_result.get("reasoning", "No reason provided")
                    
                    logger.info(f"   {ai_source} Final Decision: {decision} ({confidence}% confidence)")
                    
                    # Save analysis
                    save_ai_analysis(symbol, decision, confidence, reason, market_state)
                    log_market_state(decision, confidence, reason, market_state)
                else:
                    # Use strategy decision
                    decision = strategy_decision
                    confidence = 85  # Strategy-based trades get high confidence
                    reason = f"Strategy '{strategy_name}' triggered: {triggered_strategies[0].get('logic')}"
                    
                    # Save analysis with strategy info
                    save_ai_analysis(symbol, decision, confidence, reason, market_state)
                    log_market_state(decision, confidence, reason, market_state)
                
                # Execute if conditions are met
                if decision in ["BUY", "SELL"]:
                    confidence_threshold = 90 - risk_tolerance
                    
                    if confidence >= confidence_threshold:
                        # Risk check
                        is_safe = True
                        if decision == "BUY" and market_state.get('rsi', 50) > 70:
                            logger.warning("   RISK BLOCK: RSI too high for Buy")
                            is_safe = False
                        if decision == "SELL" and market_state.get('rsi', 50) < 30:
                            logger.warning("   RISK BLOCK: RSI too low for Sell")
                            is_safe = False
                        
                        if is_safe:
                            should_execute = True
                            ml_agrees = False
                            
                            if strategy_name:
                                logger.info(f"   STRATEGY TRADE: Executing based on user-defined strategy '{strategy_name}'")
                            else:
                                if ml_prediction:
                                    ml_dir = ml_prediction.get('direction', 'UNKNOWN')
                                    ml_agrees = (decision == "BUY" and ml_dir == "UP") or (decision == "SELL" and ml_dir == "DOWN")
                                
                                if ml_prediction and not ml_agrees:
                                    logger.warning(f"   CONFLICT: Gemini says {decision}, but ML predicts {ml_prediction.get('direction')}. Being conservative - waiting.")
                                    log_message = f"Confluence check failed: Gemini {decision} vs ML {ml_prediction.get('direction')}. Waiting for alignment."
                                    should_execute = False
                                    
                                    try:
                                        conn = get_db_connection()
                                        if conn:
                                            cur = conn.cursor()
                                            cur.execute("""
                                                INSERT INTO market_log (trend, structure, price, rsi, decision, confidence, reason)
                                                VALUES (%s, %s, %s, %s, %s, %s, %s)
                                            """, (
                                                str(market_state.get('trend', 'Neutral')),
                                                'Confluence-Check',
                                                float(market_state.get('price', 0)),
                                                float(market_state.get('rsi', 50)),
                                                f"WAIT-CONFLICT",
                                                int(confidence),
                                                log_message
                                            ))
                                            conn.commit()
                                            cur.close()
                                            conn.close()
                                    except Exception as log_err:
                                        logger.error(f"Log error: {log_err}")
                                else:
                                    if ml_agrees:
                                        logger.info(f"   CONFLUENCE DETECTED! ML and Gemini agree on {decision}")
                            
                            if should_execute:
                                try:
                                    balance_data = client.get_balance()
                                    available_usdt = 0
                                    
                                    if balance_data:
                                        if isinstance(balance_data, list):
                                            for asset in balance_data:
                                                if asset.get('coinName') == 'USDT':
                                                    available_usdt = float(asset.get('available', 0))
                                                    break
                                        elif isinstance(balance_data, dict):
                                            if balance_data.get('coinName') == 'USDT':
                                                available_usdt = float(balance_data.get('available', 0))
                                    
                                    position_size_usdt = min(max(available_usdt * 0.03, 5), 30)
                                    
                                    current_price = float(market_state.get('price', 0))
                                    if current_price > 0:
                                        contract_size = position_size_usdt / current_price
                                        contract_size = max(round(contract_size, 4), 0.001)
                                        size = str(contract_size)
                                    else:
                                        size = "0.001"  
                                    
                                    logger.info(f"   Balance: {available_usdt:.2f} USDT | Position Size: {size} contracts (~{position_size_usdt:.2f} USDT)")
                                    
                                    if available_usdt < 1:
                                        logger.error(f"   INSUFFICIENT BALANCE: Only {available_usdt:.2f} USDT available. Skipping trade.")
                                        log_message = f"INSUFFICIENT BALANCE: {available_usdt:.2f} USDT available. Need at least 1 USDT."
                                        try:
                                            conn = get_db_connection()
                                            if conn:
                                                cur = conn.cursor()
                                                cur.execute("""
                                                    INSERT INTO market_log (trend, structure, price, rsi, decision, confidence, reason)
                                                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                                                """, (
                                                    str(market_state.get('trend', 'Neutral')),
                                                    'Balance-Check',
                                                    float(market_state.get('price', 0)),
                                                    float(market_state.get('rsi', 50)),
                                                    "WAIT-INSUFFICIENT-BALANCE",
                                                    0,
                                                    log_message
                                                ))
                                                conn.commit()
                                                cur.close()
                                                conn.close()
                                        except:
                                            pass
                                        time.sleep(30)
                                        continue
                                    
                                except Exception as balance_err:
                                    logger.error(f"Balance check error: {balance_err}", exc_info=True)
                                    logger.error(f"   Balance check error: {balance_err}. Using default size.")
                                    size = "0.01"  
                                
                                # ============================================================
                                # CRITICAL SAFETY INTEGRATION (Production Upgrade)
                                # ============================================================
                                
                                # STEP 1: Calculate ATR-based Stop Loss & Take Profit
                                atr = market_state.get('volatility') or market_state.get('atr', current_price * 0.015)
                                if decision == "BUY":
                                    stop_loss = current_price - (atr * 1.5)  # 1.5R risk
                                    take_profit = current_price + (atr * 2.0)  # 2.0R reward (1.33:1 R:R)
                                    direction = "LONG"
                                else:  # SELL
                                    stop_loss = current_price + (atr * 1.5)
                                    take_profit = current_price - (atr * 2.0)
                                    direction = "SHORT"
                                
                                logger.info(f"   SL/TP calculated: Entry ${current_price:.2f}, SL ${stop_loss:.2f}, TP ${take_profit:.2f}, ATR ${atr:.4f}")
                                
                                # STEP 2: Check for duplicate positions (prevent stacking)
                                if position_manager:
                                    existing_pos = position_manager.get_position(symbol)
                                    if existing_pos:
                                        logger.warning(f"   ⚠️ Position already open for {symbol} - skipping to prevent duplicate")
                                        logger.warning(f"   Position already open for {symbol} - skipping trade")
                                        time.sleep(30)
                                        continue
                                
                                # STEP 3: Validate trade through Safety Layer
                                if safety_layer:
                                    try:
                                        # Calculate margin required
                                        leverage = 20  # Default leverage
                                        position_value = float(size) * current_price
                                        margin_required = position_value / leverage
                                        
                                        # Get current positions for safety checks
                                        current_positions = []
                                        if position_manager:
                                            current_positions = [
                                                {
                                                    "symbol": p.symbol,
                                                    "margin_used": p.margin_used,
                                                    "direction": p.direction
                                                }
                                                for p in position_manager.get_all_positions()
                                            ]
                                        
                                        # Run all 10 safety checks
                                        can_execute, safety_results = safety_layer.validate_trade(
                                            symbol=symbol,
                                            direction=direction,
                                            size=float(size),
                                            entry_price=current_price,
                                            stop_loss=stop_loss,
                                            take_profit=take_profit,
                                            leverage=leverage,
                                            margin_required=margin_required,
                                            current_positions=current_positions
                                        )
                                        
                                        if not can_execute:
                                            logger.warning(f"   🚫 Trade REJECTED by Safety Layer")
                                            failed_checks = [r.check_name for r in safety_results if not r.passed and r.severity == "CRITICAL"]
                                            logger.error(f"   Safety checks failed: {', '.join(failed_checks)}")
                                            time.sleep(30)
                                            continue
                                        else:
                                            logger.info(f"   ✅ Trade APPROVED by Safety Layer")
                                    except Exception as safety_err:
                                        logger.error(f"Safety layer validation failed: {safety_err}", exc_info=True)
                                        logger.error(f"   Safety validation error - aborting trade for safety")
                                        time.sleep(30)
                                        continue
                                
                                # STEP 4: Execute order on WEEX
                                logger.info(f"   AUTO-EXECUTING {decision} ORDER...")
                                side = "buy" if decision == "BUY" else "sell"
                                order_res = client.place_order(side=side, size=size, symbol=symbol)
                                
                                if order_res and (order_res.get("code") == "00000" or order_res.get("order_id")):
                                    logger.info(f"   Trade Executed Successfully!")
                                    # Extract order_id from response (can be in data.orderId or directly as order_id)
                                    if isinstance(order_res.get("data"), dict) and order_res.get("data", {}).get("orderId"):
                                        order_id = str(order_res.get("data", {}).get("orderId"))
                                    elif order_res.get("order_id"):
                                        order_id = str(order_res.get("order_id"))
                                    else:
                                        order_id = "unknown"
                                    
                                    # Upload AI log to WEEX for compliance
                                    try:
                                        # Use 'reason' variable which is defined in the scope
                                        reasoning_text = reason if 'reason' in locals() else f"Strategy '{strategy_name}' triggered" if strategy_name else "Auto-trade decision"
                                        
                                        ai_log_input = {
                                            "market_data": {
                                                "symbol": symbol,
                                                "price": float(market_state.get('price', 0)),
                                                "rsi": float(market_state.get('rsi', 50)),
                                                "trend": str(market_state.get('trend', 'Neutral')),
                                                "volume": market_state.get('volume', 0)
                                            },
                                            "ml_prediction": ml_prediction if ml_prediction else {},
                                            "sentiment": sentiment if sentiment else {},
                                            "prompt": f"Analyze {symbol} market data and provide trading decision"
                                        }
                                        
                                        ai_log_output = {
                                            "decision": decision,
                                            "confidence": confidence,
                                            "reasoning": reasoning_text[:500] if reasoning_text else "",
                                            "ml_agrees": ml_agrees,
                                            "strategy": strategy_name or "Hybrid Auto-Trade"
                                        }
                                        
                                        explanation = f"AI analyzed {symbol} with RSI {market_state.get('rsi', 50):.1f}, trend {market_state.get('trend', 'Neutral')}. Decision: {decision} with {confidence}% confidence. ML model {('agreed' if ml_agrees else 'disagreed')}. Reasoning: {reasoning_text[:400] if reasoning_text else 'N/A'}"
                                        
                                        client.upload_ai_log(
                                            order_id=order_id,
                                            stage="Decision Making",
                                            model="Gemini-2.0-Flash-Thinking",
                                            input_data=ai_log_input,
                                            output_data=ai_log_output,
                                            explanation=explanation
                                        )
                                        logger.info(f"   AI Log uploaded for order {order_id}")
                                    except Exception as ai_log_err:
                                        logger.error(f"   AI Log upload failed: {ai_log_err}")
                                        import traceback
                                        traceback.print_exc()
                                    current_price = float(market_state.get('price', 0))
                                    confluence_note = " [CONFLUENCE]" if ml_agrees else ""
                                    log_message = f"AUTO-EXECUTED {decision} on {symbol}{confluence_note} | Confidence: {confidence}% | ML: {ml_prediction.get('direction') if ml_prediction else 'N/A'} | Sentiment: {sentiment.get('label')} | Order ID: {order_id}"
                                    
                                    from core.db_manager import save_trade, update_or_create_position, get_trade_history
                                    
                                    notes_parts = []
                                    if strategy_name:
                                        notes_parts.append(f"Strategy: {strategy_name}")
                                    else:
                                        notes_parts.append(f"Hybrid Auto-trade: {decision} at {confidence}%")
                                    notes_parts.append(f"ML: {ml_prediction.get('direction') if ml_prediction else 'N/A'}")
                                    notes_parts.append(f"Sentiment: {sentiment.get('label')}")
                                    
                                    # Calculate position value in USDT for tracking
                                    position_value_usdt = float(size) * current_price
                                    
                                    save_trade({
                                        "symbol": symbol,
                                        "side": side,
                                        "size": float(size),
                                        "price": current_price,
                                        "order_id": order_id,
                                        "order_type": "market",
                                        "status": "filled",
                                        "notes": " | ".join(notes_parts) + f" | Position Value: ${position_value_usdt:.2f}"
                                    })
                                    
                                    # Check profitable trades count
                                    try:
                                        all_trades = get_trade_history(limit=1000)
                                        profitable_trades = [t for t in all_trades if t.get('pnl') and float(t.get('pnl', 0)) > 0]
                                        profitable_count = len(profitable_trades)
                                        logger.info(f"   Profitable Trades: {profitable_count}/15 required")
                                    except Exception as profitable_err:
                                        logger.error(f"Failed to count profitable trades: {profitable_err}", exc_info=True)
                                    
                                    update_or_create_position({
                                        "symbol": symbol,
                                        "side": side,
                                        "size": float(size),
                                        "entry_price": current_price,
                                        "current_price": current_price,
                                        "unrealized_pnl": 0,
                                        "leverage": leverage,
                                        "order_id": order_id
                                    })
                                    
                                    # ============================================================
                                    # CRITICAL: Register position with Position Manager
                                    # ============================================================
                                    if position_manager:
                                        try:
                                            success = position_manager.open_position(
                                                symbol=symbol,
                                                side=side,
                                                direction=direction,
                                                size=float(size),
                                                entry_price=current_price,
                                                stop_loss=stop_loss,
                                                take_profit=take_profit,
                                                leverage=leverage,
                                                margin_used=margin_required,
                                                atr=atr,
                                                order_id=order_id,
                                                source="SENTINEL",
                                                metadata={
                                                    "ml_prediction": ml_prediction,
                                                    "sentiment": sentiment,
                                                    "confidence": confidence,
                                                    "strategy": strategy_name
                                                }
                                            )
                                            if success:
                                                logger.info(f"   ✅ Position registered with Position Manager - automatic SL/TP monitoring active")
                                            else:
                                                logger.error(f"   ❌ Failed to register position with Position Manager")
                                        except Exception as pm_err:
                                            logger.error(f"Position Manager registration failed: {pm_err}", exc_info=True)
                                    else:
                                        logger.warning(f"   ⚠️ Position Manager not available - no automatic SL/TP monitoring")
                                else:
                                    logger.error(f"   Trade Failed: {order_res.get('msg', 'Unknown error')}")
                                    log_message = f"AUTO-TRADE FAILED: {decision} on {symbol} | Error: {order_res.get('msg', 'Unknown')}"
                                
                                # Log the trade attempt
                                try:
                                    conn = get_db_connection()
                                    if conn:
                                        cur = conn.cursor()
                                        cur.execute("""
                                            INSERT INTO market_log (trend, structure, price, rsi, decision, confidence, reason)
                                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                                        """, (
                                            str(market_state.get('trend', 'Neutral')),
                                            'Auto-Trade',
                                            float(market_state.get('price', 0)),
                                            float(market_state.get('rsi', 50)),
                                            f"AUTO-{decision}",
                                            int(confidence),
                                            log_message
                                        ))
                                        conn.commit()
                                        cur.close()
                                        conn.close()
                                except Exception as log_err:
                                    logger.error(f"Log error: {log_err}")
                    else:
                        if confidence < confidence_threshold:
                            logger.info(f"   Confidence {confidence}% below threshold {confidence_threshold}%")
                        else:
                            logger.info("   Market Indecisive - No Action")
        except Exception as e:
            logger.error(f"Sentinel Loop Error: {e}", exc_info=True)
        
        time.sleep(30)  # Wait 30 seconds before next scan

def start_sentinel():
    """Start the background sentinel service."""
    global sentinel_running, sentinel_thread, active_trading_mode, position_manager
    
    with trading_mode_lock:
        # Check for conflicts
        if active_trading_mode == "INSTITUTIONAL":
            logger.error("❌ Cannot start Sentinel: Institutional trading is active")
            raise Exception("Trading conflict: Institutional system is already running. Stop it first.")
        
        if not sentinel_running:
            sentinel_running = True
            active_trading_mode = "SENTINEL"
            
            # ============================================================
            # CRITICAL: Start Position Manager monitoring
            # ============================================================
            if position_manager and not position_manager.monitor_running:
                try:
                    position_manager.start_monitoring()
                    logger.info("✅ Position Manager monitoring started - automatic SL/TP active")
                except Exception as pm_err:
                    logger.error(f"Failed to start Position Manager monitoring: {pm_err}", exc_info=True)
            
            sentinel_thread = threading.Thread(target=sentinel_loop, daemon=True)
            sentinel_thread.start()
            logger.info("✅ Sentinel service started")

def stop_sentinel():
    """Stop the background sentinel service."""
    global sentinel_running, active_trading_mode
    
    with trading_mode_lock:
        sentinel_running = False
        if active_trading_mode == "SENTINEL":
            active_trading_mode = None
        logger.info("🛑 Sentinel service stopped")

# 3. CORS Configuration (CRITICAL for React Connection)
# This allows your frontend (localhost:8080 or 5173) to talk to this backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://chartor-market.vercel.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Data Models (Pydantic) ---
class ChatRequest(BaseModel):
    message: str

class AnalysisRequest(BaseModel):
    symbol: str

# --- API ENDPOINTS ---

@app.get("/")
def health_check():
    return {"status": "online", "system": "Chartor v2.4.1"}

@app.get("/api/ai-status")
def get_ai_status():
    """
    Returns the status of the AI service (Gemini availability, quota status, etc.)
    """
    from core.llm_brain import quota_exceeded_until, api_call_count, MAX_DAILY_CALLS
    from datetime import datetime
    
    status = {
        "available": True,
        "using_fallback": False,
        "quota_exceeded": False,
        "calls_remaining": max(0, MAX_DAILY_CALLS - api_call_count),
        "cooldown_until": None
    }
    
    if quota_exceeded_until:
        if datetime.now() < quota_exceeded_until:
            status["available"] = False
            status["using_fallback"] = True
            status["quota_exceeded"] = True
            status["cooldown_until"] = quota_exceeded_until.isoformat()
        else:
            # Cooldown expired
            status["available"] = True
    
    if api_call_count >= MAX_DAILY_CALLS:
        status["available"] = False
        status["using_fallback"] = True
        status["quota_exceeded"] = True
    
    return status

@app.get("/api/watchlist")
def get_watchlist():
    """
    Fetches LIVE real-time prices + 24h data for the sidebar assets from Binance.
    """
    import requests
    
    # Official Futures Symbols on Weex
    symbols = [
        "cmt_btcusdt", "cmt_ethusdt", "cmt_solusdt", 
        "cmt_dogeusdt", "cmt_xrpusdt", "cmt_bnbusdt", 
        "cmt_adausdt", "cmt_ltcusdt"
    ]
    
    watchlist = []
    
    try:
        # Fetch 24h ticker data from Binance (includes price, change, high, low, volume)
        for sym in symbols:
            binance_symbol = sym.upper().replace("CMT_", "").replace("USDT", "USDT")
            
            try:
                # Binance 24h Ticker endpoint
                response = requests.get(
                    f"https://api.binance.com/api/v3/ticker/24hr?symbol={binance_symbol}",
                    timeout=3
                )
                ticker = response.json()
                
                if "lastPrice" in ticker:
                    watchlist.append({
                        "symbol": sym.upper().replace("CMT_", "").replace("USDT", "/USDT"),
                        "raw_symbol": sym,
                        "price": float(ticker["lastPrice"]),
                        "change": round(float(ticker["priceChangePercent"]), 2),
                        "volume24h": float(ticker["quoteVolume"]),
                        "high24h": float(ticker["highPrice"]),
                        "low24h": float(ticker["lowPrice"])
                    })
            except:
                # Fallback: use candle data if ticker fails
                raw = client.fetch_candles(sym, limit=1)
                if raw and len(raw) > 0:
                    current_price = float(raw[-1][4])
                    open_price = float(raw[-1][1])
                    change_pct = ((current_price - open_price) / open_price) * 100
                    
                    watchlist.append({
                        "symbol": sym.upper().replace("CMT_", "").replace("USDT", "/USDT"),
                        "raw_symbol": sym,
                        "price": current_price,
                        "change": round(change_pct, 2),
                        "volume24h": 0,
                        "high24h": 0,
                        "low24h": 0
                    })
        
        return watchlist
    except Exception as e:
        print(f"Watchlist Error: {e}")
        return []

@app.get("/api/candles")
def get_candles(symbol: str = "cmt_btcusdt", interval: str = "15m"):
    """
    Fetches OHLC data for the TradingView Chart.
    """
    try:
        # Fetch 500 candles (15m timeframe default)
        raw_data = client.fetch_candles(symbol=symbol, limit=500, interval=interval)
        
        formatted_data = []
        if raw_data:
            # Sort Oldest -> Newest
            raw_data.sort(key=lambda x: x[0])
            
            for c in raw_data:
                formatted_data.append({
                    "time": int(c[0] / 1000), # Unix Timestamp
                    "open": float(c[1]),
                    "high": float(c[2]),
                    "low": float(c[3]),
                    "close": float(c[4])
                })
        return formatted_data
    except Exception as e:
        print(f"Candle Error: {e}")
        return []

@app.post("/api/chat")
def chat_with_chartor(request: ChatRequest):
    """
    Enhanced chat with Chartor AI - includes real-time market data context.
    """
    try:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            return {"response": "Error: GEMINI_API_KEY not found in .env"}

        model_name = os.getenv("GEMINI_CHAT_MODEL", "gemini-flash-latest")
        client = genai.Client(api_key=api_key)
        
        # Extract symbol from user message if mentioned, otherwise use default
        user_message = request.message.lower()
        symbol_to_analyze = "cmt_btcusdt"  # Default
        
        # Try to detect symbol in message
        symbol_map = {
            "btc": "cmt_btcusdt", "bitcoin": "cmt_btcusdt",
            "eth": "cmt_ethusdt", "ethereum": "cmt_ethusdt",
            "sol": "cmt_solusdt", "solana": "cmt_solusdt",
            "doge": "cmt_dogeusdt", "dogecoin": "cmt_dogeusdt",
            "xrp": "cmt_xrpusdt", "ripple": "cmt_xrpusdt",
            "bnb": "cmt_bnbusdt", "binance": "cmt_bnbusdt",
            "ada": "cmt_adausdt", "cardano": "cmt_adausdt",
            "ltc": "cmt_ltcusdt", "litecoin": "cmt_ltcusdt"
        }
        
        for key, val in symbol_map.items():
            if key in user_message:
                symbol_to_analyze = val
                break
        
        # Fetch real-time market data
        from core.weex_api import WeexClient
        from core.analysis import analyze_market_structure
        from core.ml_analyst import MLAnalyst
        from core.sentiment import analyze_market_sentiment
        
        market_context = ""
        try:
            weex_client = WeexClient()
            candles = weex_client.fetch_candles(symbol=symbol_to_analyze, limit=500)
            
            if candles and len(candles) >= 100:
                # Technical Analysis
                market_state = analyze_market_structure(candles)
                
                # ML Prediction
                ml_analyst = MLAnalyst()
                ml_trained = ml_analyst.train_model(candles)
                ml_direction, ml_confidence = ml_analyst.predict_next_move(market_state) if ml_trained else ("UNKNOWN", 0)
                
                # Sentiment
                symbol_clean = symbol_to_analyze.replace("cmt_", "").replace("usdt", "").upper()
                sent_label, sent_score = analyze_market_sentiment(symbol_clean)
                
                # Build comprehensive market context
                price = market_state.get('price', 0)
                trend = market_state.get('trend', 'Neutral')
                rsi = market_state.get('rsi', 50)
                ema_20 = market_state.get('ema_20', price)
                volatility = market_state.get('volatility', 0)
                volume_spike = market_state.get('volume_spike', False)
                
                market_context = f"""
CURRENT MARKET DATA ({symbol_clean}):
- Current Price: ${price:,.2f}
- Trend: {trend}
- RSI (14): {rsi:.1f}
- EMA 20: ${ema_20:,.2f}
- Volatility (ATR): ${volatility:,.2f}
- Volume Spike: {volume_spike}
- ML Prediction: {ml_direction} ({ml_confidence}% confidence)
- Market Sentiment: {sent_label} (score: {sent_score:.2f})
- Price vs EMA: {"Above" if price > ema_20 else "Below"} EMA (${abs(price - ema_20):,.2f} difference)
"""
        except Exception as e:
            print(f"Error fetching market data for chat: {e}")
            market_context = "\nNote: Real-time market data unavailable. Providing general analysis.\n"
        
        # Enhanced system prompt
        system_prompt = """You are Chartor, an elite institutional crypto trading AI with deep expertise in:
- Al Brooks Price Action methodology
- Technical analysis (RSI, EMA, ATR, Volume Profile)
- Machine Learning price predictions
- Market sentiment analysis
- Risk management and position sizing

YOUR COMMUNICATION STYLE:
- Be precise, technical, and data-driven
- Use specific numbers, percentages, and price levels
- Reference actual market conditions when provided
- Explain your reasoning clearly
- Highlight key support/resistance levels
- Mention risk factors and trade setups
- Use professional trading terminology
- Format important data points clearly

When market data is provided, ALWAYS reference the actual numbers (price, RSI, etc.) in your response.
Be specific about entry/exit levels, stop losses, and take profit targets when discussing trades.
If the user asks about a specific asset, use the provided market data to give accurate, real-time analysis.

Keep responses concise but comprehensive - aim for 3-5 sentences for simple questions, up to 2 paragraphs for complex analysis."""
        
        full_prompt = f"""{system_prompt}

{market_context}

USER QUESTION: {request.message}

Provide a detailed, accurate response using the market data above. If specific numbers are provided, use them in your answer."""
        
        response = client.models.generate_content(model=model_name, contents=full_prompt)
        return {"response": response.text}
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"response": f"AI Error: {str(e)}"}

@app.post("/api/trigger-analysis")
def trigger_analysis(
    request: Optional[AnalysisRequest] = Body(None),
    symbol: Optional[str] = Query(None)
):
    """
    Triggers on-demand AI analysis for a specific symbol.
    Accepts symbol from request body (JSON) or query parameter.
    """
    try:
        from core.weex_api import WeexClient
        from core.analysis import analyze_market_structure
        from core.llm_brain import get_trading_decision
        from core.db_manager import save_ai_analysis, log_market_state
        
        # Get symbol from request body or query param
        if request and hasattr(request, 'symbol') and request.symbol:
            symbol = request.symbol
        elif not symbol:
            # Try to get from current settings
            conn = get_db_connection()
            if conn:
                cur = conn.cursor()
                cur.execute("SELECT current_symbol FROM trade_settings LIMIT 1")
                settings = cur.fetchone()
                cur.close()
                conn.close()
                symbol = settings["current_symbol"] if settings else "cmt_btcusdt"
            else:
                symbol = "cmt_btcusdt"
        
        if not symbol:
            return {"status": "error", "msg": "Symbol is required"}
        
        print(f"Triggering hybrid ML analysis for {symbol}...")
        
        # Fetch market data (get more for ML training)
        client = WeexClient()
        candles = client.fetch_candles(symbol=symbol, limit=500)
        
        if not candles or len(candles) < 100:
            return {"status": "error", "msg": "Not enough market data for ML analysis"}
        
        # STEP 1: Train Local ML Model
        from core.ml_analyst import MLAnalyst
        from core.sentiment import analyze_market_sentiment
        
        ml_analyst = MLAnalyst()
        ml_trained = ml_analyst.train_model(candles)
        
        # STEP 2: Technical Analysis
        market_state = analyze_market_structure(candles)
        if not market_state:
            return {"status": "error", "msg": "Analysis failed"}
        
        # STEP 3: Get Local ML Prediction
        ml_direction, ml_confidence = ml_analyst.predict_next_move(market_state)
        ml_prediction = {"direction": ml_direction, "confidence": ml_confidence} if ml_trained else None
        
        # STEP 4: Get Market Sentiment
        symbol_clean = symbol.replace("cmt_", "").replace("usdt", "").upper()
        sent_label, sent_score = analyze_market_sentiment(symbol_clean)
        sentiment = {"label": sent_label, "score": sent_score}
        
        # STEP 5: Hybrid Decision - Get AI decision with all inputs
        ai_result = get_trading_decision(
            market_state, 
            symbol=symbol,
            ml_prediction=ml_prediction,
            sentiment=sentiment
        )
        decision = ai_result.get("decision", "WAIT")
        confidence = ai_result.get("confidence", 0)
        reasoning = ai_result.get("reasoning", "No analysis available")
        
        # Save to database
        save_ai_analysis(symbol, decision, confidence, reasoning, market_state)
        log_market_state(decision, confidence, reasoning, market_state)
        
        # Check if auto-trading is enabled and execute if conditions are met
        auto_execute = False
        try:
            conn = get_db_connection()
            if conn:
                cur = conn.cursor()
                cur.execute("SELECT auto_trading, risk_tolerance FROM trade_settings LIMIT 1")
                settings = cur.fetchone()
                cur.close()
                conn.close()
                
                if settings and settings.get("auto_trading"):
                    risk_tolerance = settings.get("risk_tolerance", 20)
                    confidence_threshold = 90 - risk_tolerance
                    
                    if decision in ["BUY", "SELL"] and confidence >= confidence_threshold:
                        # Risk check
                        is_safe = True
                        if decision == "BUY" and market_state.get('rsi', 50) > 70:
                            is_safe = False
                        if decision == "SELL" and market_state.get('rsi', 50) < 30:
                            is_safe = False
                        
                        if is_safe:
                            auto_execute = True
                            side = "buy" if decision == "BUY" else "sell"
                            trade_result = client.place_order(side=side, size="10", symbol=symbol)
                            if trade_result and trade_result.get("code") == "00000":
                                log_message = f"AUTO-EXECUTED {decision} on {symbol} | Confidence: {confidence}% | Order ID: {trade_result.get('data', 'N/A')}"
                            else:
                                log_message = f"AUTO-TRADE FAILED: {decision} on {symbol} | Error: {trade_result.get('msg', 'Unknown')}"
                            
                            # Log the auto-trade
                            try:
                                conn = get_db_connection()
                                if conn:
                                    cur = conn.cursor()
                                    cur.execute("""
                                        INSERT INTO market_log (trend, structure, price, rsi, decision, confidence, reason)
                                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                                    """, (
                                        str(market_state.get('trend', 'Neutral')),
                                        'Auto-Trade',
                                        float(market_state.get('price', 0)),
                                        float(market_state.get('rsi', 50)),
                                        f"AUTO-{decision}",
                                        int(confidence),
                                        log_message
                                    ))
                                    conn.commit()
                                    cur.close()
                                    conn.close()
                            except Exception as log_err:
                                print(f"Log error: {log_err}")
        except Exception as auto_err:
            print(f"Auto-trade check error: {auto_err}")
        
        # Return the analysis
        return {
            "status": "success",
            "symbol": symbol,
            "decision": decision,
            "confidence": confidence,
            "reasoning": reasoning,
            "price": float(market_state.get('price', 0)),
            "rsi": float(market_state.get('rsi', 50)),
            "trend": str(market_state.get('trend', 'Neutral')),
            "auto_executed": auto_execute
        }
    except Exception as e:
        print(f"Trigger Analysis Error: {e}")
        import traceback
        traceback.print_exc()
        return {"status": "error", "msg": str(e)}

@app.post("/api/trade")
def execute_trade(action: str = None, symbol: str = None):
    """
    Executes a REAL trade on Weex when the user authorizes it.
    Now supports dynamic symbol selection with comprehensive logging.
    """
    from core.db_manager import save_trade, update_or_create_position, log_market_state
    
    try:
        # Get action and symbol from query params or body
        if not action:
            return {"status": "error", "msg": "Action parameter is required (buy/sell/long/short)"}
        
        # Get current symbol from settings if not provided
        if not symbol:
            conn = get_db_connection()
            if conn:
                cur = conn.cursor()
                cur.execute("SELECT current_symbol FROM trade_settings LIMIT 1")
                settings = cur.fetchone()
                cur.close()
                conn.close()
                symbol = settings["current_symbol"] if settings else "cmt_btcusdt"
            else:
                symbol = "cmt_btcusdt"
        
        print(f"RECEIVED TRADE SIGNAL: {action.upper()} on {symbol}")
        
        # Call the Real Weex Client
        # Note: 'action' comes in as 'buy' or 'sell' (or 'long'/'short')
        side = "buy" if action.lower() in ["buy", "long"] else "sell"
        size = "10"  # Safe default size
        
        # Execute trade
        result = client.place_order(side=side, size=size, symbol=symbol)
        
        # Log the trade attempt
        log_message = f"Trade Execution: {action.upper()} {size} {symbol}"
        
        if result and result.get("code") == "00000":
            # Trade successful - save to history and update position
            order_id = str(result.get("data", {}).get("orderId", "unknown")) if isinstance(result.get("data"), dict) else str(result.get("data", "unknown"))
            
            # Get current price for logging
            try:
                candles = client.fetch_candles(symbol=symbol, limit=1)
                current_price = float(candles[0][4]) if candles and len(candles) > 0 else 0
            except:
                current_price = 0
            
            # Save trade to history
            trade_id = save_trade({
                "symbol": symbol,
                "side": side,
                "size": float(size),
                "price": current_price,
                "order_id": order_id,
                "order_type": "market",
                "status": "filled",
                "notes": f"Manual trade execution: {action.upper()}"
            })
            
            # Update or create position
            update_or_create_position({
                "symbol": symbol,
                "side": side,
                "size": float(size),
                "entry_price": current_price,
                "current_price": current_price,
                "unrealized_pnl": 0,
                "leverage": 1,
                "order_id": order_id
            })
            
            # Upload AI log to WEEX for compliance
            try:
                ai_log_input = {
                    "market_data": {
                        "symbol": symbol,
                        "price": current_price,
                        "action": action.upper()
                    },
                    "prompt": f"Execute manual {action.upper()} trade on {symbol}"
                }
                
                ai_log_output = {
                    "decision": action.upper(),
                    "execution_type": "manual",
                    "order_id": order_id,
                    "price": current_price
                }
                
                explanation = f"Manual trade execution: {action.upper()} {size} units of {symbol} at ${current_price:.2f}. Order placed via user interface with AI system oversight."
                
                client.upload_ai_log(
                    order_id=order_id,
                    stage="Strategy Execution",
                    model="Gemini-2.0-Flash-Thinking",
                    input_data=ai_log_input,
                    output_data=ai_log_output,
                    explanation=explanation
                )
                print(f"AI Log uploaded for manual trade order {order_id}")
            except Exception as ai_log_err:
                print(f"AI Log upload failed: {ai_log_err}")
            
            # Log success
            log_market_state(
                f"TRADE-{action.upper()}",
                100,
                f"Trade executed successfully: {action.upper()} {size} {symbol} @ ${current_price:.2f} | Order ID: {order_id}",
                {"price": current_price, "trend": "TRADE", "rsi": 0}
            )
            
            return {
                "status": "success",
                "msg": f"Order Placed: {order_id}",
                "order_id": order_id,
                "trade_id": trade_id,
                "price": current_price
            }
        else:
            # Trade failed
            error_msg = result.get('msg', 'Unknown error') if result else 'No response from WEEX'
            log_market_state(
                f"TRADE-FAILED",
                0,
                f"Trade failed: {action.upper()} {symbol} | Error: {error_msg}",
                {"price": 0, "trend": "ERROR", "rsi": 0}
            )
            return {"status": "error", "msg": error_msg}
            
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Trade Execution Error: {error_details}")
        
        # Log error
        try:
            log_market_state(
                "TRADE-ERROR",
                0,
                f"Trade execution exception: {str(e)}",
                {"price": 0, "trend": "ERROR", "rsi": 0}
            )
        except:
            pass
        
        return {"status": "error", "msg": str(e)}

@app.get("/api/trade-settings")
def get_trade_settings():
    """
    Fetches current trade settings (auto-trading mode, risk tolerance, current symbol).
    """
    try:
        conn = get_db_connection()
        if not conn:
            return {"auto_trading": False, "risk_tolerance": 20, "current_symbol": "cmt_btcusdt"}
        
        cur = conn.cursor()
        cur.execute("SELECT * FROM trade_settings ORDER BY id DESC LIMIT 1")
        settings = cur.fetchone()
        cur.close()
        conn.close()
        
        if settings:
            return {
                "auto_trading": settings["auto_trading"],
                "risk_tolerance": settings["risk_tolerance"],
                "current_symbol": settings["current_symbol"]
            }
        return {"auto_trading": False, "risk_tolerance": 20, "current_symbol": "cmt_btcusdt"}
    except Exception as e:
        print(f"Get Settings Error: {e}")
        return {"auto_trading": False, "risk_tolerance": 20, "current_symbol": "cmt_btcusdt"}

@app.post("/api/trade-settings")
def update_trade_settings(auto_trading: bool = None, risk_tolerance: int = None, current_symbol: str = None):
    """
    Updates trade settings (auto-trading mode, risk tolerance, current symbol).
    Automatically starts/stops sentinel service based on auto-trading setting.
    """
    try:
        conn = get_db_connection()
        if not conn:
            return {"status": "error", "msg": "Database connection failed"}
        
        cur = conn.cursor()
        
        # Build dynamic update query based on provided parameters
        updates = []
        params = []
        
        if auto_trading is not None:
            updates.append("auto_trading = %s")
            params.append(auto_trading)
        if risk_tolerance is not None:
            updates.append("risk_tolerance = %s")
            params.append(risk_tolerance)
        if current_symbol is not None:
            updates.append("current_symbol = %s")
            params.append(current_symbol)
        
        if updates:
            updates.append("updated_at = CURRENT_TIMESTAMP")
            query = f"UPDATE trade_settings SET {', '.join(updates)}"
            cur.execute(query, tuple(params))
            conn.commit()
            
            # Start/stop sentinel based on auto_trading
            if auto_trading is not None:
                if auto_trading:
                    start_sentinel()
                else:
                    stop_sentinel()
        
        cur.close()
        conn.close()
        return {"status": "success", "msg": "Settings updated"}
    except Exception as e:
        print(f"Update Settings Error: {e}")
        return {"status": "error", "msg": str(e)}

@app.get("/api/ai-analysis")
def get_ai_analysis(symbol: str = None):
    """
    Fetches the latest AI analysis for a specific symbol (or current symbol).
    """
    try:
        if not symbol:
            conn = get_db_connection()
            if not conn:
                return None
            cur = conn.cursor()
            cur.execute("SELECT current_symbol FROM trade_settings LIMIT 1")
            settings = cur.fetchone()
            symbol = settings["current_symbol"] if settings else "cmt_btcusdt"
            cur.close()
            conn.close()
        
        conn = get_db_connection()
        if not conn:
            return None
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM ai_analysis WHERE symbol = %s ORDER BY timestamp DESC LIMIT 1", 
            (symbol,)
        )
        analysis = cur.fetchone()
        cur.close()
        conn.close()
        
        if analysis:
            return {
                "symbol": analysis["symbol"],
                "decision": analysis["decision"],
                "confidence": analysis["confidence"],
                "reasoning": analysis["reasoning"],
                "price": float(analysis["price"]),
                "rsi": float(analysis["rsi"]),
                "trend": analysis["trend"],
                "timestamp": str(analysis["timestamp"])
            }
        return None
    except Exception as e:
        print(f"Get AI Analysis Error: {e}")
        return None

@app.get("/api/logs")
def get_logs(limit: int = 20):
    """
    Fetches the latest AI decision logs for the bottom terminal.
    """
    try:
        conn = get_db_connection()
        if not conn:
            return []
        
        cur = conn.cursor()
        cur.execute("SELECT * FROM market_log ORDER BY timestamp DESC LIMIT %s", (limit,))
        logs = cur.fetchall()
        cur.close()
        conn.close()
        
        formatted_logs = []
        for row in logs:
            # Determine log type based on decision
            log_type = "sentinel"
            if "AUTO-" in str(row.get('decision', '')) or "TRADE-" in str(row.get('decision', '')):
                log_type = "trade"
            elif row.get('decision') in ["BUY", "SELL"]:
                log_type = "sentinel"
            elif "RISK" in str(row.get('reason', '')) or "ERROR" in str(row.get('reason', '')):
                log_type = "risk"
            else:
                log_type = "system"
            
            # Format message
            message = str(row.get('reason', ''))
            if not message or message == "None":
                message = f"Trend: {row.get('trend', 'N/A')} | RSI: {row.get('rsi', 0):.1f} | Decision: {row.get('decision', 'WAIT')} | Confidence: {row.get('confidence', 0)}%"
            
            formatted_logs.append({
                "id": str(row["id"]),
                "timestamp": str(row["timestamp"]),
                "type": log_type,
                "message": message
            })
        
        return formatted_logs
    except Exception as e:
        print(f"Get Logs Error: {e}")
        import traceback
        traceback.print_exc()
        return []

@app.post("/api/force-close")
def force_close_all():
    """
    Emergency function to close all open positions.
    """
    from core.db_manager import close_position, get_open_positions, save_trade, log_market_state
    
    try:
        print("FORCE CLOSE ALL POSITIONS REQUESTED")
        
        # Get all open positions from database
        positions = get_open_positions()
        
        if not positions:
            return {"status": "success", "msg": "No open positions to close", "closed": 0}
        
        closed_count = 0
        errors = []
        
        for pos in positions:
            try:
                symbol = pos.get('symbol')
                side = pos.get('side')
                size = pos.get('size')
                
                # Determine close side (opposite of position side)
                close_side = "sell" if side == "buy" else "buy"
                
                # Close position on WEEX
                result = client.close_position(symbol, close_side, str(size))
                
                if result and result.get("code") == "00000":
                    # Remove from open positions
                    close_position(symbol, side)
                    
                    # Log the close trade
                    save_trade({
                        "symbol": symbol,
                        "side": close_side,
                        "size": float(size),
                        "price": pos.get('current_price', 0) or pos.get('entry_price', 0),
                        "order_id": result.get('data', {}).get('orderId', 'force-close') if isinstance(result.get('data'), dict) else 'force-close',
                        "order_type": "market",
                        "status": "filled",
                        "pnl": pos.get('unrealized_pnl', 0),
                        "notes": "Force close - emergency liquidation"
                    })
                    
                    closed_count += 1
                    print(f"Closed position: {side} {size} {symbol}")
                else:
                    error_msg = result.get('msg', 'Unknown error') if result else 'No response'
                    errors.append(f"{symbol} {side}: {error_msg}")
                    print(f"Failed to close {symbol} {side}: {error_msg}")
            except Exception as e:
                errors.append(f"{pos.get('symbol', 'unknown')}: {str(e)}")
                print(f"Error closing position: {e}")
        
        # Log the force close action
        log_market_state(
            "FORCE-CLOSE",
            100,
            f"Force close executed: {closed_count} positions closed",
            {"price": 0, "trend": "EMERGENCY", "rsi": 0}
        )
        
        return {
            "status": "success",
            "msg": f"Force close completed: {closed_count} positions closed",
            "closed": closed_count,
            "total": len(positions),
            "errors": errors if errors else None
        }
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Force Close Error: {error_details}")
        return {"status": "error", "msg": str(e)}

@app.get("/api/trade-history")
def get_trade_history_endpoint(limit: int = 100, symbol: str = None):
    """
    Fetches trade history from WEEX API using /capi/v2/order/history
    This returns completed/filled orders, not pending ones.
    """
    try:
        # Calculate time range (last 90 days max as per WEEX API)
        import time
        end_time = int(time.time() * 1000)  # Current time in milliseconds
        start_time = end_time - (89 * 24 * 60 * 60 * 1000)  # 89 days ago
        
        # Call WEEX API to get history orders (completed trades)
        weex_history = client.get_history_orders(
            symbol=symbol, 
            page_size=min(limit, 100),
            create_date=start_time,
            end_create_date=end_time
        )
        
        if not weex_history:
            return {"status": "success", "trades": [], "count": 0}
        
        # Handle response format
        orders_data = []
        if isinstance(weex_history, dict):
            if weex_history.get("code") == "00000" and weex_history.get("data"):
                data = weex_history.get("data", {})
                # Handle both list and paginated responses
                if isinstance(data, list):
                    orders_data = data
                elif isinstance(data, dict):
                    orders_data = data.get("orderList", []) or data.get("list", []) or []
            else:
                print(f"WEEX History API Response: {weex_history}")
        elif isinstance(weex_history, list):
            orders_data = weex_history
        
        formatted_trades = []
        for order in orders_data:
            try:
                order_id = str(order.get("orderId", "") or order.get("order_id", ""))
                symbol_order = order.get("symbol", "")
                order_type = str(order.get("type", ""))
                
                # Convert order type to side
                # type: 1=open_long(buy), 2=open_short(sell), 3=close_long(sell), 4=close_short(buy)
                side = "buy"
                if order_type in ["2", "3"] or "short" in order_type.lower() or "sell" in order_type.lower():
                    side = "sell"
                elif order_type in ["1", "4"] or "long" in order_type.lower() or "buy" in order_type.lower():
                    side = "buy"
                
                size = float(order.get("size", 0) or 0)
                
                # Use priceAvg for filled orders
                price_avg = order.get("priceAvg") or order.get("price_avg")
                price = order.get("price")
                execution_price = float(price_avg) if price_avg and float(price_avg) > 0 else (float(price) if price else None)
                
                status = order.get("status", "filled")
                fee = float(order.get("fee", 0) or 0)
                
                # Get PnL from various possible fields
                pnl = order.get("totalProfits") or order.get("pnl") or order.get("profit")
                pnl_value = float(pnl) if pnl and str(pnl) not in ["", "null", "None"] else None
                
                # Get timestamps
                create_time = order.get("cTime") or order.get("createTime") or order.get("created_at")
                execution_time = ""
                if create_time:
                    from datetime import datetime
                    try:
                        # Convert milliseconds timestamp to ISO string
                        timestamp_ms = int(create_time)
                        execution_time = datetime.fromtimestamp(timestamp_ms / 1000).isoformat()
                    except:
                        execution_time = str(create_time)
                
                # Generate a numeric ID
                numeric_id = 0
                try:
                    if order_id and order_id.isdigit():
                        numeric_id = int(order_id)
                    else:
                        numeric_id = abs(hash(order_id)) % (10 ** 9)
                except:
                    numeric_id = abs(hash(str(order))) % (10 ** 9)
                
                formatted_trades.append({
                    "id": numeric_id,
                    "symbol": symbol_order,
                    "side": side,
                    "size": size,
                    "price": execution_price,
                    "order_id": order_id,
                    "status": status,
                    "pnl": pnl_value,
                    "fees": fee if fee > 0 else None,
                    "execution_time": execution_time,
                    "notes": f"Order type: {order_type}"
                })
            except Exception as e:
                print(f"Error formatting order: {e}")
                import traceback
                traceback.print_exc()
                continue
        
        return {"status": "success", "trades": formatted_trades, "count": len(formatted_trades)}
    except Exception as e:
        print(f"Get Trade History Error: {e}")
        import traceback
        traceback.print_exc()
        return {"status": "error", "msg": str(e), "trades": []}

@app.get("/api/positions")
def get_positions():
    """
    Fetches all open positions from WEEX API using /capi/v2/account/position/allPosition
    """
    try:
        # Call WEEX API to get all positions
        weex_positions = client.get_all_positions()
        
        if not weex_positions:
            return {"status": "success", "positions": [], "count": 0}
        
        # Handle different response formats
        positions_data = []
        if isinstance(weex_positions, list):
            positions_data = weex_positions
        elif isinstance(weex_positions, dict):
            if weex_positions.get("code") == "00000" and weex_positions.get("data"):
                positions_data = weex_positions.get("data", [])
            elif isinstance(weex_positions.get("data"), list):
                positions_data = weex_positions.get("data", [])
        
        formatted_positions = []
        for pos in positions_data:
            try:
                symbol = pos.get("symbol", "")
                side_raw = pos.get("side", "LONG")
                # Convert LONG/SHORT to buy/sell for frontend
                side = "buy" if side_raw.upper() == "LONG" else "sell"
                size = float(pos.get("size", 0))
                leverage = float(pos.get("leverage", 1))
                unrealized_pnl = float(pos.get("unrealizePnl", 0)) if pos.get("unrealizePnl") else 0
                open_value = float(pos.get("open_value", 0)) if pos.get("open_value") else 0
                
                # Calculate entry price from open_value and size
                entry_price = (open_value / size) if size > 0 else 0
                
                # Get current price from candles for display
                current_price = None
                try:
                    candles = client.fetch_candles(symbol=symbol, limit=1)
                    if candles and len(candles) > 0:
                        current_price = float(candles[0][4])  # Close price
                except:
                    pass
                
                # If we can't calculate entry_price from open_value, use a fallback
                if entry_price == 0 and current_price:
                    entry_price = current_price
                
                created_time = pos.get("created_time")
                if created_time:
                    from datetime import datetime
                    try:
                        opened_at = datetime.fromtimestamp(int(created_time) / 1000).isoformat()
                    except:
                        opened_at = str(created_time)
                else:
                    opened_at = ""
                
                formatted_positions.append({
                    "id": pos.get("id") or pos.get("position_id", 0),
                    "symbol": symbol,
                    "side": side,
                    "size": size,
                    "entry_price": entry_price,
                    "current_price": current_price,
                    "unrealized_pnl": unrealized_pnl,
                    "leverage": int(leverage),
                    "opened_at": opened_at,
                    "updated_at": str(pos.get("updated_time", "")) if pos.get("updated_time") else opened_at
                })
            except Exception as e:
                print(f"Error formatting position: {e}")
                import traceback
                traceback.print_exc()
                continue
        
        return {"status": "success", "positions": formatted_positions, "count": len(formatted_positions)}
    except Exception as e:
        print(f"Get Positions Error: {e}")
        import traceback
        traceback.print_exc()
        return {"status": "error", "msg": str(e), "positions": []}

@app.post("/api/close-position")
def close_single_position(request: dict = Body(...)):
    """
    Closes a single position.
    """
    from core.db_manager import get_open_positions, close_position, save_trade
    
    try:
        symbol = request.get('symbol')
        side = request.get('side')
        
        if not symbol or not side:
            return {"status": "error", "msg": "Symbol and side are required"}
        
        # Get the position
        positions = get_open_positions()
        position = next((p for p in positions if p.get('symbol') == symbol and p.get('side') == side), None)
        
        if not position:
            return {"status": "error", "msg": "Position not found"}
        
        size = str(position.get('size', 0))
        close_side = "sell" if side == "buy" else "buy"
        
        # Close position on WEEX
        result = client.close_position(symbol, close_side, size)
        
        if result and result.get("code") == "00000":
            # Get current price
            try:
                candles = client.fetch_candles(symbol=symbol, limit=1)
                current_price = float(candles[0][4]) if candles and len(candles) > 0 else position.get('entry_price', 0)
            except:
                current_price = position.get('entry_price', 0)
            
            # Calculate realized P&L
            entry_price = float(position.get('entry_price', 0))
            size_float = float(size)
            if side == "buy":
                realized_pnl = (current_price - entry_price) * size_float
            else:
                realized_pnl = (entry_price - current_price) * size_float
            
            # Save close trade
            order_id = result.get('data', {}).get('orderId', 'close-' + str(int(time.time()))) if isinstance(result.get('data'), dict) else 'close-' + str(int(time.time()))
            save_trade({
                "symbol": symbol,
                "side": close_side,
                "size": size_float,
                "price": current_price,
                "order_id": str(order_id),
                "order_type": "market",
                "status": "filled",
                "pnl": realized_pnl,
                "notes": f"Manual close: {side} position"
            })
            
            # Remove from open positions
            close_position(symbol, side)
            
            return {
                "status": "success",
                "msg": f"Position closed successfully",
                "pnl": realized_pnl,
                "order_id": str(order_id)
            }
        else:
            return {"status": "error", "msg": result.get('msg', 'Unknown error') if result else 'No response from WEEX'}
            
    except Exception as e:
        print(f"Close Position Error: {e}")
        import traceback
        traceback.print_exc()
        return {"status": "error", "msg": str(e)}

@app.get("/api/risk-metrics")
def get_risk_metrics():
    """
    Calculates risk metrics: Sharpe ratio, drawdown, win rate, profit factor, etc.
    """
    from core.db_manager import get_trade_history
    import numpy as np
    
    try:
        trades = get_trade_history(limit=1000)
        
        if len(trades) < 5:
            return {
                "status": "error",
                "msg": "Need at least 5 trades to calculate metrics",
                "metrics": None
            }
        
        # Filter trades with P&L
        trades_with_pnl = [t for t in trades if t.get('pnl') is not None]
        
        if len(trades_with_pnl) < 5:
            return {
                "status": "error",
                "msg": "Need at least 5 trades with P&L data",
                "metrics": None
            }
        
        pnls = [float(t.get('pnl', 0)) for t in trades_with_pnl]
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p < 0]
        
        # Basic stats
        total_trades = len(trades)
        total_pnl = sum(pnls)
        win_rate = (len(wins) / len(trades_with_pnl)) * 100 if trades_with_pnl else 0
        avg_trade = total_pnl / len(trades_with_pnl) if trades_with_pnl else 0
        best_trade = max(pnls) if pnls else 0
        worst_trade = min(pnls) if pnls else 0
        
        # Profit Factor
        total_wins = sum(wins) if wins else 0
        total_losses = abs(sum(losses)) if losses else 0
        profit_factor = total_wins / total_losses if total_losses > 0 else (total_wins if total_wins > 0 else 0)
        
        # Sharpe Ratio (simplified - using returns)
        if len(pnls) > 1:
            returns = np.array(pnls)
            mean_return = np.mean(returns)
            std_return = np.std(returns)
            sharpe_ratio = (mean_return / std_return) * np.sqrt(252) if std_return > 0 else 0  # Annualized
        else:
            sharpe_ratio = 0
        
        # Max Drawdown
        cumulative = []
        running_sum = 0
        peak = 0
        max_drawdown = 0
        
        for pnl in pnls:
            running_sum += pnl
            cumulative.append(running_sum)
            if running_sum > peak:
                peak = running_sum
            drawdown = ((running_sum - peak) / peak * 100) if peak > 0 else 0
            if drawdown < max_drawdown:
                max_drawdown = drawdown
        
        metrics = {
            "totalTrades": total_trades,
            "winRate": round(win_rate, 1),
            "totalPnL": round(total_pnl, 2),
            "sharpeRatio": round(sharpe_ratio, 2),
            "maxDrawdown": round(max_drawdown, 2),
            "profitFactor": round(profit_factor, 2),
            "avgTrade": round(avg_trade, 2),
            "bestTrade": round(best_trade, 2),
            "worstTrade": round(worst_trade, 2)
        }
        
        return {"status": "success", "metrics": metrics}
        
    except Exception as e:
        print(f"Get Risk Metrics Error: {e}")
        import traceback
        traceback.print_exc()
        return {"status": "error", "msg": str(e), "metrics": None}

@app.on_event("startup")
async def startup_event():
    """Initialize database and production-ready trading systems on startup."""
    global position_manager, safety_layer, sentiment_feed
    
    from core.db_manager import init_db
    
    try:
        logger.info("="*60)
        logger.info("CHARTOR TRADING ENGINE - STARTUP")
        logger.info("="*60)
        
        # Initialize database tables
        logger.info("Initializing database...")
        init_db()
        
        # Initialize production components (if not already initialized)
        if position_manager is None:
            logger.info("Initializing Position Manager...")
            position_manager = initialize_position_manager(client, logger)
        else:
            logger.info("Position Manager already initialized")
        
        if safety_layer is None:
            logger.info("Initializing Safety Layer...")
            safety_layer = ExecutionSafetyLayer(client, initial_equity=10000.0, logger=logger)
        else:
            logger.info("Safety Layer already initialized")
        
        if sentiment_feed is None:
            logger.info("Initializing Sentiment Feed...")
            sentiment_feed = get_sentiment_feed()
        else:
            logger.info("Sentiment Feed already initialized")
        
        # Check if auto-trading is enabled
        conn = get_db_connection()
        if conn:
            cur = conn.cursor()
            cur.execute("SELECT auto_trading FROM trade_settings LIMIT 1")
            settings = cur.fetchone()
            cur.close()
            conn.close()
            
            if settings and settings.get("auto_trading"):
                logger.info("Auto-trading enabled, starting Sentinel service...")
                start_sentinel()
            else:
                logger.info("Auto-trading disabled")
        
        logger.info("="*60)
        logger.info("STARTUP COMPLETE ✅")
        logger.info("="*60)
    except Exception as e:
        logger.error(f"Startup error: {e}", exc_info=True)

@app.on_event("shutdown")
async def shutdown_event():
    """Stop all trading systems and close positions on shutdown."""
    global position_manager
    
    logger.info("="*60)
    logger.info("SHUTDOWN INITIATED")
    logger.info("="*60)
    
    # Stop sentinel
    stop_sentinel()
    
    # Stop institutional trading
    global orchestrator_instance
    if orchestrator_instance:
        logger.info("Stopping institutional trading...")
        orchestrator_instance = None
    
    # Shutdown position manager (closes all positions)
    if position_manager:
        position_manager.shutdown()
    
    logger.info("="*60)
    logger.info("SHUTDOWN COMPLETE ✅")
    logger.info("="*60)

# --- Strategy Marketplace Endpoints ---
@app.get("/api/strategies")
def get_strategies():
    """Fetch all strategies with their current status."""
    from core.db_manager import get_db_connection
    
    try:
        conn = get_db_connection()
        if not conn:
            return {"status": "error", "msg": "Database connection failed", "strategies": []}
        
        cur = conn.cursor()
        cur.execute("""
            SELECT id, name, description, logic, action, is_active, created_at, updated_at
            FROM strategies
            ORDER BY created_at DESC
        """)
        strategies = cur.fetchall()
        cur.close()
        conn.close()
        
        formatted_strategies = []
        for strat in strategies:
            formatted_strategies.append({
                "id": strat.get("id"),
                "name": strat.get("name"),
                "description": strat.get("description"),
                "logic": strat.get("logic"),
                "action": strat.get("action"),
                "is_active": bool(strat.get("is_active", False)),
                "created_at": str(strat.get("created_at")),
                "updated_at": str(strat.get("updated_at"))
            })
        
        return {"status": "success", "strategies": formatted_strategies, "count": len(formatted_strategies)}
    except Exception as e:
        print(f"Get Strategies Error: {e}")
        import traceback
        traceback.print_exc()
        return {"status": "error", "msg": str(e), "strategies": []}

class ToggleStrategyRequest(BaseModel):
    is_active: bool

@app.post("/api/strategies/{strategy_id}/toggle")
def toggle_strategy(strategy_id: int, request: ToggleStrategyRequest):
    """Toggle a strategy's active status. Automatically enables auto-trading when any strategy is activated."""
    from core.db_manager import get_db_connection
    
    try:
        conn = get_db_connection()
        if not conn:
            return {"status": "error", "msg": "Database connection failed"}
        
        cur = conn.cursor()
        
        # Update strategy status
        cur.execute("""
            UPDATE strategies
            SET is_active = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
            RETURNING id, name, is_active
        """, (request.is_active, strategy_id))
        
        result = cur.fetchone()
        
        if not result:
            cur.close()
            conn.close()
            return {"status": "error", "msg": "Strategy not found"}
        
        # If strategy is being activated, automatically enable auto-trading
        if request.is_active:
            # Enable auto-trading in settings
            cur.execute("""
                UPDATE trade_settings 
                SET auto_trading = TRUE, updated_at = CURRENT_TIMESTAMP
                WHERE id = (SELECT id FROM trade_settings LIMIT 1)
            """)
            conn.commit()
            
            # Start sentinel if not already running
            start_sentinel()
            print(f"Auto-trading automatically enabled because strategy '{result['name']}' was activated")
        
        # Note: We don't disable auto-trading when strategies are deactivated
        # because the user might still want Gemini AI trading to work
        
        conn.commit()
        cur.close()
        conn.close()
        
        return {
            "status": "success",
            "msg": f"Strategy '{result['name']}' {'activated' if request.is_active else 'deactivated'}" + 
                   (". Auto-trading enabled." if request.is_active else ""),
            "strategy": {
                "id": result["id"],
                "name": result["name"],
                "is_active": bool(result["is_active"])
            }
        }
    except Exception as e:
        print(f"Toggle Strategy Error: {e}")
        import traceback
        traceback.print_exc()
        return {"status": "error", "msg": str(e)}

class ToggleStrategyRequest(BaseModel):
    is_active: bool

class CreateStrategyRequest(BaseModel):
    name: str
    prompt: str
    description: Optional[str] = None

@app.post("/api/create-strategy")
def create_strategy(request: CreateStrategyRequest):
    """
    Creates a new strategy by translating plain English to trading logic using Gemini.
    """
    from core.db_manager import get_db_connection
    import json
    import re
    
    try:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            return {"status": "error", "msg": "GEMINI_API_KEY not found in .env"}
        
        model_name = os.getenv("GEMINI_CHAT_MODEL", "gemini-flash-latest")
        client = genai.Client(api_key=api_key)
        
        # System instruction for Gemini
        system_instruction = """You are a trading logic converter. Convert the user's plain English trading strategy into a Python-like boolean expression that can be evaluated against market data.

Available market data variables:
- rsi: Relative Strength Index (0-100)
- price: Current price (float)
- ema_20: 20-period EMA (float)
- volatility: ATR volatility (float)
- trend: Market trend ('BULLISH', 'BEARISH', 'NEUTRAL')
- volume_spike: Boolean indicating high volume

Supported operators: <, >, <=, >=, ==, !=, and, or, not

Examples:
- "Buy when RSI is under 30" → "rsi < 30"
- "Sell when RSI exceeds 70" → "rsi > 70"
- "Buy when price is above EMA 20 and trend is bullish" → "price > ema_20 and trend == 'BULLISH'"
- "Buy on high volume with bullish trend" → "volume_spike == True and trend == 'BULLISH'"
- "Sell when RSI is high or price drops below EMA" → "rsi > 70 or price < ema_20"

Return ONLY the Python expression, nothing else. No explanations, no markdown, just the expression."""
        
        # Send prompt to Gemini
        # Use string concatenation instead of f-string to avoid % formatting issues
        full_prompt = system_instruction + "\n\nUser Strategy: " + request.prompt + "\n\nConvert to Python expression:"
        
        try:
            response = client.models.generate_content(model=model_name, contents=full_prompt)
            logic_text = response.text.strip()
            
            # Clean markdown backticks if present
            logic_text = re.sub(r'```(?:python|json)?\s*', '', logic_text)
            logic_text = re.sub(r'```\s*', '', logic_text)
            logic_text = logic_text.strip()
            
            # Determine action from the prompt (simple heuristic)
            prompt_lower = request.prompt.lower()
            if any(word in prompt_lower for word in ['buy', 'long', 'enter long', 'purchase']):
                action = "BUY"
            elif any(word in prompt_lower for word in ['sell', 'short', 'exit', 'close']):
                action = "SELL"
            else:
                # Try to infer from logic
                if 'rsi <' in logic_text or 'price >' in logic_text:
                    action = "BUY"
                elif 'rsi >' in logic_text or 'price <' in logic_text:
                    action = "SELL"
                else:
                    action = "BUY"  # Default to BUY
            
            # Validate the logic by trying to parse it (basic check)
            # We'll do a simple syntax check
            if not logic_text or len(logic_text) < 3:
                return {"status": "error", "msg": "Invalid logic generated. Please try rephrasing your strategy."}
            
            # Save to database
            conn = get_db_connection()
            if not conn:
                return {"status": "error", "msg": "Database connection failed"}
            
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO strategies (name, description, logic, action, raw_prompt, logic_json, is_active)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id, name, logic, action
            """, (
                request.name,
                request.description or "",
                logic_text,
                action,
                request.prompt,
                json.dumps({"prompt": request.prompt, "logic": logic_text}),  # Store JSON for reference
                True  # Auto-activate new strategies
            ))
            
            result = cur.fetchone()
            conn.commit()
            cur.close()
            conn.close()
            
            return {
                "status": "success",
                "msg": f"Strategy '{request.name}' created and activated",
                "strategy": {
                    "id": result["id"],
                    "name": result["name"],
                    "logic": result["logic"],
                    "action": result["action"],
                    "is_active": True
                }
            }
            
        except Exception as gemini_error:
            print(f"Gemini Translation Error: {gemini_error}")
            import traceback
            traceback.print_exc()
            error_msg = str(gemini_error)
            # Provide more helpful error messages
            if "not all arguments converted" in error_msg or "string formatting" in error_msg:
                return {
                    "status": "error",
                    "msg": "Translation error occurred. Please try rephrasing your strategy in simpler terms."
                }
            return {
                "status": "error",
                "msg": f"Failed to translate strategy. Please try rephrasing: {error_msg}"
            }
            
    except Exception as e:
        print(f"Create Strategy Error: {e}")
        import traceback
        traceback.print_exc()
        return {"status": "error", "msg": str(e)}

# ============================================================================
# INSTITUTIONAL TRADING SYSTEM ENDPOINTS
# ============================================================================

# ============================================================================
# INSTITUTIONAL TRADING SYSTEM ENDPOINTS
# ============================================================================

# Global orchestrator instance
orchestrator_instance = None
orchestrator_thread_inst = None

# Removed duplicate endpoint definitions - see bottom of file for active endpoints

@app.get("/api/institutional/trades")
async def get_institutional_trades():
    """Get trade history from institutional system"""
    global orchestrator_instance
    
    try:
        if orchestrator_instance is None:
            return {"status": "error", "msg": "Institutional trading not running", "trades": []}
        
        trades = []
        for trade in orchestrator_instance.risk_manager.position_history:
            trades.append({
                "symbol": trade["symbol"],
                "direction": trade["direction"],
                "entry_price": trade["entry_price"],
                "exit_price": trade["exit_price"],
                "size": trade["size"],
                "realized_pnl": trade["realized_pnl"],
                "realized_pnl_pct": trade["realized_pnl_pct"],
                "entry_time": trade["entry_time"].isoformat(),
                "exit_time": trade["exit_time"].isoformat(),
                "hold_time_hours": trade["hold_time_hours"],
                "exit_reason": trade["exit_reason"]
            })
        
        return {
            "status": "success",
            "trades": trades,
            "total_trades": len(trades)
        }
        
    except Exception as e:
        return {"status": "error", "msg": str(e), "trades": []}

@app.post("/api/institutional/backtest")
async def run_backtest(background_tasks: BackgroundTasks):
    """Run backtest of institutional system"""
    try:
        from backtest.backtest_engine import BacktestEngine, BacktestConfig
        from strategy.intraday_engine import IntradayMomentumEngine
        from regime.ofras import OFRASRegimeDetector
        
        # This would need historical data - placeholder for now
        return {
            "status": "info",
            "msg": "Backtesting requires historical data feed. Implementation pending."
        }
        
    except Exception as e:
        return {"status": "error", "msg": str(e)}

# === Institutional Trading Control Endpoints ===
institutional_thread = None
institutional_running = False

@app.post("/api/institutional/start", status_code=200)
def start_institutional():
    """Start institutional quant trading system - No body required"""
    global institutional_thread, institutional_running, active_trading_mode, sentinel_running
    
    with trading_mode_lock:
        # Auto-stop Sentinel if running
        if active_trading_mode == "SENTINEL":
            logger.info("🔄 Auto-stopping Sentinel AI to start Institutional mode")
            sentinel_running = False
            active_trading_mode = None
            # Also update trade settings to disable auto_trading
            try:
                import sqlite3
                db_path = "trading_bot.db"
                conn = sqlite3.connect(db_path)
                c = conn.cursor()
                c.execute("UPDATE trade_settings SET auto_trading = 0")
                conn.commit()
                conn.close()
            except Exception as db_err:
                logger.warning(f"Could not update trade_settings DB: {db_err}")
        
        if institutional_running:
            return {"status": "info", "msg": "Institutional trading already running"}
        
        try:
            from run_institutional_trading import main as institutional_main
            
            def run_institutional():
                global institutional_running
                institutional_running = True
                try:
                    institutional_main()
                except Exception as e:
                    logger.error(f"Institutional trading error: {e}", exc_info=True)
                finally:
                    institutional_running = False
            
            institutional_thread = threading.Thread(target=run_institutional, daemon=True)
            institutional_thread.start()
            active_trading_mode = "INSTITUTIONAL"
            
            logger.info("✅ Institutional trading system started")
            return {"status": "success", "msg": "Institutional trading started"}
            
        except Exception as e:
            logger.error(f"Failed to start institutional trading: {e}", exc_info=True)
            return {"status": "error", "msg": str(e)}

@app.post("/api/institutional/stop", status_code=200)
def stop_institutional():
    """Stop institutional quant trading system - No body required"""
    global institutional_running, active_trading_mode
    
    with trading_mode_lock:
        if not institutional_running:
            return {"status": "info", "msg": "Institutional trading not running"}
        
        institutional_running = False
        active_trading_mode = None
        logger.info("⏸️ Institutional trading system stopped")
        return {"status": "success", "msg": "Institutional trading stopped"}

@app.get("/api/institutional/status", status_code=200)
def get_institutional_status():
    """Get institutional trading system status"""
    return {
        "status": "success",
        "running": institutional_running,
        "active_mode": active_trading_mode
    }

if __name__ == "__main__":
    import uvicorn
    # Runs on localhost:8000
    uvicorn.run(app, host="0.0.0.0", port=8000)