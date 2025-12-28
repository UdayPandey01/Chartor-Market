import time
from core.weex_api import WeexClient
from core.analysis import analyze_market_structure
from core.llm_brain import get_trading_decision
from core.db_manager import init_db, log_market_state, save_ai_analysis, get_db_connection

# 1. Setup
init_db()
client = WeexClient()

print(f"⚡ KAIROS SENTINEL ONLINE: AI-Powered Trading Assistant...")
print("⚠️ MODE: Controlled Trading (User Authorization Required)")

def get_trade_settings():
    """Fetch current trade settings from database."""
    try:
        conn = get_db_connection()
        if conn:
            cur = conn.cursor()
            cur.execute("SELECT auto_trading, risk_tolerance, current_symbol FROM trade_settings LIMIT 1")
            result = cur.fetchone()
            cur.close()
            conn.close()
            
            if result:
                return {
                    "auto_trading": result["auto_trading"],
                    "risk_tolerance": result["risk_tolerance"],
                    "current_symbol": result["current_symbol"]
                }
    except Exception as e:
        print(f"Error fetching settings: {e}")
    
    # Fallback to defaults
    return {"auto_trading": False, "risk_tolerance": 20, "current_symbol": "cmt_btcusdt"}

while True:
    try:
        # Get current settings
        settings = get_trade_settings()
        TRADING_SYMBOL = settings["current_symbol"]
        auto_trading = settings["auto_trading"]
        risk_tolerance = settings["risk_tolerance"]
        
        print(f"\n{'='*60}")
        print(f"📊 Symbol: {TRADING_SYMBOL} | Auto-Trade: {'ON' if auto_trading else 'OFF'} | Risk: {risk_tolerance}%")
        print(f"{'='*60}")
        
        # STEP 1: Fetch Data (From Binance for stability)
        print("1️⃣ Fetching Market Data...")
        candles = client.fetch_candles(symbol=TRADING_SYMBOL, limit=100)
        
        if len(candles) > 20:
            # STEP 2: Technical Analysis (RSI, EMA)
            market_state = analyze_market_structure(candles)
            print(f"   Price: ${market_state['price']} | RSI: {market_state['rsi']} | Trend: {market_state['trend']}")
            
            # STEP 3: The AI Brain (Gemini)
            print("2️⃣ Asking Gemini AI...")
            ai_result = get_trading_decision(market_state)
            decision = ai_result.get("decision", "WAIT")
            confidence = ai_result.get("confidence", 0)
            reason = ai_result.get("reasoning", "No reason provided")
            
            print(f"   🤖 AI Says: {decision} (Confidence: {confidence}%)")
            print(f"   📝 Reason: {reason}")
            
            # Save AI analysis for frontend display
            save_ai_analysis(TRADING_SYMBOL, decision, confidence, reason, market_state)
            
            # Log for historical tracking
            log_market_state(decision, confidence, reason, market_state)

            # STEP 4: Execution Logic - Only if AUTO TRADING is enabled
            if auto_trading and decision in ["BUY", "SELL"]:
                # Adjust confidence threshold based on risk tolerance
                # Higher risk tolerance = lower confidence needed
                confidence_threshold = 90 - risk_tolerance  # 20% risk = 70% confidence, 30% risk = 60% confidence
                
                if confidence >= confidence_threshold:
                    print(f"3️⃣ High Confidence Setup Detected (>{confidence_threshold}%). Checking Risk...")
                    
                    # Risk Check: Don't trade if RSI is extreme (Overbought/Oversold)
                    is_safe = True
                    if decision == "BUY" and market_state['rsi'] > 70: 
                        print("   ❌ RISK BLOCK: RSI too high for Buy.")
                        is_safe = False
                    if decision == "SELL" and market_state['rsi'] < 30:
                        print("   ❌ RISK BLOCK: RSI too low for Sell.")
                        is_safe = False
                        
                    if is_safe:
                        print(f"   🚀 AUTO-EXECUTING {decision} ORDER ON WEEX...")
                        side_param = "buy" if decision == "BUY" else "sell"
                        order_res = client.execute_order(side=side_param, size="10", symbol=TRADING_SYMBOL)
                        
                        # Check if order was successful
                        if order_res and order_res.get("code") == "00000":
                            print(f"   ✅ Trade Executed Successfully!")
                            print(f"   📊 Order ID: {order_res.get('data', {})}")
                        else:
                            print(f"   ❌ Trade Failed: {order_res.get('msg', 'Unknown error')}")
                else:
                    print(f"   ⏸️ Confidence {confidence}% below threshold {confidence_threshold}%. Waiting...")
            elif decision in ["BUY", "SELL"]:
                print(f"   💡 AI Recommendation Ready: {decision} at {confidence}% confidence")
                print(f"   👤 Awaiting user authorization from frontend...")
            else:
                print("   ⏸️ Market Indecisive - No Action Recommended")
                
        else:
            print("⚠️ Not enough data from Binance.")

    except Exception as e:
        print(f"❌ Loop Error: {e}")

    # Wait 30 seconds before next scan
    time.sleep(30)