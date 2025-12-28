import pandas as pd
import pandas_ta as ta

def analyze_market_structure(candles):
    """
    Takes raw candles (list) and returns a DataFrame with Technical Indicators.
    """
    try:
        df = pd.DataFrame(candles, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 
                                           'close_time', 'quote_volume', 'trades', 'taker_buy_base', 'taker_buy_quote', 'ignore'])
        
        df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
        
        cols = ['open', 'high', 'low', 'close', 'volume']
        df[cols] = df[cols].astype(float)
        
        df['ema_20'] = ta.ema(df['close'], length=20)
        df['ema_50'] = ta.ema(df['close'], length=50)
        
        df['rsi'] = ta.rsi(df['close'], length=14)
        
        df['atr'] = ta.atr(df['high'], df['low'], df['close'], length=14)
        
        last_row = df.iloc[-1]
        trend = "NEUTRAL"
        
        if last_row['close'] > last_row['ema_20'] > last_row['ema_50']:
            trend = "BULLISH"
        elif last_row['close'] < last_row['ema_20'] < last_row['ema_50']:
            trend = "BEARISH"
            
        return {
            "price": last_row['close'],
            "rsi": round(last_row['rsi'], 2),
            "trend": trend,
            "ema_20": round(last_row['ema_20'], 2),
            "volatility": round(last_row['atr'], 2),
            "volume_spike": last_row['volume'] > (df['volume'].mean() * 1.5) 
        }
        
    except Exception as e:
        print(f"Analysis Error: {e}")
        return None