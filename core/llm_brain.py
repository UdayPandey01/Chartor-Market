import os
import json
import re
import time
from datetime import datetime, timedelta
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    print("ERROR: GEMINI_API_KEY is missing in .env")

model_name = os.getenv("GEMINI_DECISION_MODEL", os.getenv("GEMINI_CHAT_MODEL", "gemini-flash-latest"))
client = genai.Client(
    api_key=api_key
) if api_key else None

last_api_call = None
api_call_count = 0
quota_exceeded_until = None
cache = {} 
CACHE_DURATION = 60  
MAX_DAILY_CALLS = 15  
COOLDOWN_AFTER_QUOTA = 3600  

def get_fallback_decision(market_data):
    """
    Fallback decision engine using technical analysis when Gemini is unavailable.
    Based on RSI, trend, and price action.
    """
    price = market_data.get('price', 0)
    rsi = market_data.get('rsi', 50)
    trend = market_data.get('trend', 'NEUTRAL')
    volatility = market_data.get('volatility', 0)
    volume_spike = market_data.get('volume_spike', False)
    
    decision = "WAIT"
    confidence = 0
    reasoning = ""
    
    if trend == "BULLISH" and rsi < 70 and rsi > 30:
        if rsi < 50:  
            decision = "BUY"
            confidence = min(75, 50 + (50 - rsi))
            reasoning = f"Bullish trend with RSI pullback ({rsi:.1f}). H1/H2 setup potential."
        elif volume_spike:
            decision = "BUY"
            confidence = 70
            reasoning = f"Bullish trend with volume confirmation. RSI: {rsi:.1f}"
        else:
            decision = "WAIT"
            confidence = 40
            reasoning = f"Bullish trend but waiting for better entry. RSI: {rsi:.1f}"
    
    elif trend == "BEARISH" and rsi > 30 and rsi < 70:
        if rsi > 50:  
            decision = "SELL"
            confidence = min(75, 50 + (rsi - 50))
            reasoning = f"Bearish trend with RSI bounce ({rsi:.1f}). Short setup potential."
        elif volume_spike:
            decision = "SELL"
            confidence = 70
            reasoning = f"Bearish trend with volume confirmation. RSI: {rsi:.1f}"
        else:
            decision = "WAIT"
            confidence = 40
            reasoning = f"Bearish trend but waiting for better entry. RSI: {rsi:.1f}"
    
    elif rsi > 75:
        decision = "SELL"
        confidence = 65
        reasoning = f"RSI overbought ({rsi:.1f}). Potential reversal."
    elif rsi < 25:
        decision = "BUY"
        confidence = 65
        reasoning = f"RSI oversold ({rsi:.1f}). Potential bounce."
    
    else:
        decision = "WAIT"
        confidence = 30
        reasoning = f"Market in {trend.lower()} consolidation. RSI: {rsi:.1f}. Waiting for clear setup."
    
    # ============================================================
    # CRITICAL: Return status to distinguish from Gemini decisions
    # ============================================================
    return {
        "decision": decision,
        "confidence": int(confidence),
        "reasoning": reasoning + " [Fallback Engine]",
        "status": "FALLBACK",
        "source": "FALLBACK_ENGINE"
    }

def get_trading_decision(market_data, symbol="cmt_btcusdt", use_cache=True, ml_prediction=None, sentiment=None):
    global last_api_call, api_call_count, quota_exceeded_until, cache
    
    if quota_exceeded_until and datetime.now() < quota_exceeded_until:
        time_remaining = (quota_exceeded_until - datetime.now()).total_seconds()
        print(f"Gemini quota exceeded. Cooldown: {int(time_remaining/60)} minutes remaining")
        return get_fallback_decision(market_data)
    
    if use_cache and symbol in cache:
        cached = cache[symbol]
        if datetime.now() - cached['timestamp'] < timedelta(seconds=CACHE_DURATION):
            print("Using cached analysis result")
            return cached['result']
    
    if api_call_count >= MAX_DAILY_CALLS:
        print(f"Daily API limit reached ({MAX_DAILY_CALLS} calls). Using fallback engine.")
        return get_fallback_decision(market_data)
    
    if last_api_call:
        time_since_last = time.time() - last_api_call
        if time_since_last < 2:
            time.sleep(2 - time_since_last)
    
    if not client or not api_key:
        print("Gemini client not available. Using fallback engine.")
        return get_fallback_decision(market_data)
    
    prompt_parts = [
        "You are CHARTOR, an institutional AI Trading Agent specializing in Al Brooks Price Action.",
        "",
        "MARKET CONTEXT:",
        f"- Asset: {symbol}",
        f"- Price: {market_data.get('price', 0)}",
        f"- Trend: {market_data.get('trend', 'Neutral')}",
        f"- RSI (14): {market_data.get('rsi', 50)}",
        f"- EMA 20: {market_data.get('ema_20', market_data.get('price', 0))}",
        f"- Volatility (ATR): {market_data.get('volatility', 0)}",
        f"- Volume Spike: {market_data.get('volume_spike', False)}"
    ]
    
    if ml_prediction:
        ml_dir = ml_prediction.get('direction', 'UNKNOWN')
        ml_conf = ml_prediction.get('confidence', 0)
        prompt_parts.append(f"- Local ML Prediction: {ml_dir} ({ml_conf}% confidence)")
    
    if sentiment:
        sent_label = sentiment.get('label', 'NEUTRAL')
        sent_score = sentiment.get('score', 0)
        prompt_parts.append(f"- Market Sentiment: {sent_label} (score: {sent_score})")
    
    prompt_parts.extend([
        "",
        "YOUR TASK:",
        "Synthesize all inputs (Technical Analysis + ML Prediction + Sentiment) to make the final decision.",
        "If ML and Technicals align, increase confidence. If they conflict, be more conservative.",
        "If sentiment is strongly negative/positive, factor it into risk assessment.",
        "",
        "OUTPUT FORMAT (JSON ONLY):",
        "{",
        '    "decision": "BUY", "SELL" or "WAIT",',
        '    "confidence": <integer between 0-100>,',
        '    "reasoning": "<short, concise explanation incorporating all signals>"',
        "}"
    ])
    
    prompt = "\n".join(prompt_parts)
    
    try:
        last_api_call = time.time()
        api_call_count += 1
        
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.7,
                response_mime_type="application/json"
            )
        )
        
        response_text = response.text.strip()
        
        if response_text.startswith("```"):
            response_text = re.sub(r'^```(?:json)?\s*', '', response_text)
            response_text = re.sub(r'\s*```$', '', response_text)
        
        result = json.loads(response_text)
        
        if 'confidence' not in result or not isinstance(result['confidence'], (int, float)):
            print(f"Warning: Invalid confidence in Gemini response. Defaulting to 50%")
            result['confidence'] = 50
        
        result['confidence'] = max(0, min(100, int(result['confidence'])))
        
        if 'decision' not in result or result['decision'] not in ['BUY', 'SELL', 'WAIT']:
            print(f"Warning: Invalid decision in Gemini response. Defaulting to WAIT")
            result['decision'] = 'WAIT'
        
        if use_cache:
            cache[symbol] = {
                'result': result,
                'timestamp': datetime.now()
            }
        
        quota_exceeded_until = None
        
        # ============================================================
        # CRITICAL: Add status to distinguish successful Gemini calls
        # ============================================================
        result['status'] = 'SUCCESS'
        result['source'] = 'GEMINI'
        
        return result
        
    except Exception as e:
        error_str = str(e)
        print(f"Gemini Error: {error_str[:200]}")
        
        if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str or "quota" in error_str.lower():
            quota_exceeded_until = datetime.now() + timedelta(seconds=COOLDOWN_AFTER_QUOTA)
            print(f"Gemini quota exceeded. Using fallback engine for next {COOLDOWN_AFTER_QUOTA/60:.0f} minutes.")
        
        result = get_fallback_decision(market_data)
        result['status'] = 'ERROR'  # Override fallback status to indicate error occurred
        result['error_message'] = error_str[:200]
        result['source'] = 'FALLBACK'  # Ensure source is set
        
        if use_cache:
            cache[symbol] = {
                'result': result,
                'timestamp': datetime.now()
            }
        
        return result