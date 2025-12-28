import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

def get_db_connection():
    """Establishes a connection to Neon PostgreSQL."""
    try:
        url = os.getenv("DATABASE_URL")
        if not url:
            print("Error: DATABASE_URL not found in .env")
            return None
            
        conn = psycopg2.connect(
            url,
            cursor_factory=RealDictCursor  
        )
        return conn
    except Exception as e:
        print(f"Database Connection Failed: {e}")
        return None

def init_db():
    """Creates the necessary tables in PostgreSQL if they don't exist."""
    conn = get_db_connection()
    if not conn:
        return

    try:
        cur = conn.cursor()
        
        cur.execute("""
            CREATE TABLE IF NOT EXISTS market_log (
                id SERIAL PRIMARY KEY,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                trend TEXT,
                structure TEXT,
                price DECIMAL,
                rsi DECIMAL,
                decision TEXT,
                confidence INTEGER,
                reason TEXT
            );
        """)
        
        cur.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            );
        """)
        
        cur.execute("INSERT INTO settings (key, value) VALUES ('auto_pilot', 'OFF') ON CONFLICT (key) DO NOTHING;")
        
        cur.execute("""
            CREATE TABLE IF NOT EXISTS trade_settings (
                id SERIAL PRIMARY KEY,
                auto_trading BOOLEAN DEFAULT FALSE,
                risk_tolerance INTEGER DEFAULT 20,
                current_symbol TEXT DEFAULT 'cmt_btcusdt',
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        cur.execute("""
            INSERT INTO trade_settings (auto_trading, risk_tolerance, current_symbol) 
            SELECT FALSE, 20, 'cmt_btcusdt' 
            WHERE NOT EXISTS (SELECT 1 FROM trade_settings LIMIT 1);
        """)
        
        cur.execute("""
            CREATE TABLE IF NOT EXISTS ai_analysis (
                id SERIAL PRIMARY KEY,
                symbol TEXT,
                decision TEXT,
                confidence INTEGER,
                reasoning TEXT,
                price DECIMAL,
                rsi DECIMAL,
                trend TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        cur.execute("""
            CREATE TABLE IF NOT EXISTS trade_history (
                id SERIAL PRIMARY KEY,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                size DECIMAL NOT NULL,
                price DECIMAL,
                order_id TEXT,
                order_type TEXT DEFAULT 'market',
                status TEXT DEFAULT 'filled',
                execution_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                pnl DECIMAL,
                fees DECIMAL,
                notes TEXT
            );
        """)
        
        cur.execute("""
            CREATE TABLE IF NOT EXISTS open_positions (
                id SERIAL PRIMARY KEY,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                size DECIMAL NOT NULL,
                entry_price DECIMAL NOT NULL,
                current_price DECIMAL,
                unrealized_pnl DECIMAL,
                leverage INTEGER DEFAULT 1,
                opened_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                order_id TEXT,
                UNIQUE(symbol, side)
            );
        """)
        
        cur.execute("""
            CREATE TABLE IF NOT EXISTS strategies (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                logic TEXT NOT NULL,
                action TEXT NOT NULL,
                raw_prompt TEXT,
                logic_json TEXT,
                is_active BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        try:
            cur.execute("ALTER TABLE strategies ADD COLUMN IF NOT EXISTS raw_prompt TEXT;")
            cur.execute("ALTER TABLE strategies ADD COLUMN IF NOT EXISTS logic_json TEXT;")
        except:
            pass  
        
        cur.execute("SELECT COUNT(*) FROM strategies")
        if cur.fetchone()['count'] == 0:
            default_strategies = [
                ("RSI Oversold Buy", "Buy when RSI drops below 30", "rsi < 30", "BUY"),
                ("RSI Overbought Sell", "Sell when RSI exceeds 70", "rsi > 70", "SELL"),
                ("Bullish Trend Buy", "Buy when price is above EMA 20 and trend is bullish", "price > ema_20 and trend == 'BULLISH'", "BUY"),
                ("Bearish Trend Sell", "Sell when price is below EMA 20 and trend is bearish", "price < ema_20 and trend == 'BEARISH'", "SELL"),
                ("Volume Spike Buy", "Buy on high volume with bullish trend", "volume_spike == True and trend == 'BULLISH'", "BUY"),
            ]
            for name, desc, logic, action in default_strategies:
                cur.execute("""
                    INSERT INTO strategies (name, description, logic, action, is_active)
                    VALUES (%s, %s, %s, %s, FALSE)
                """, (name, desc, logic, action))
        
        cur.execute("CREATE INDEX IF NOT EXISTS idx_trade_history_symbol ON trade_history(symbol);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_trade_history_time ON trade_history(execution_time);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_open_positions_symbol ON open_positions(symbol);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_strategies_active ON strategies(is_active);")
        
        conn.commit()
        cur.close()
        conn.close()
        print("Neon PostgreSQL Initialized Successfully.")
        
    except Exception as e:
        print(f"Init DB Error: {e}")

def log_market_state(decision, confidence, reason, market_data):
    """Saves a Sentinel Decision to the database."""
    conn = get_db_connection()
    if not conn:
        return

    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO market_log (trend, structure, price, rsi, decision, confidence, reason)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            str(market_data.get('trend', 'Neutral')),
            str(market_data.get('structure', 'Scanning')),
            float(market_data.get('price', 0)),
            float(market_data.get('rsi', 50)),
            str(decision),
            int(confidence),
            str(reason)
        ))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Log Error: {e}")

def save_ai_analysis(symbol, decision, confidence, reasoning, market_data):
    """Saves the latest AI analysis result for display in frontend."""
    conn = get_db_connection()
    if not conn:
        return

    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM ai_analysis WHERE symbol = %s", (str(symbol),))
        
        cur.execute("""
            INSERT INTO ai_analysis (symbol, decision, confidence, reasoning, price, rsi, trend)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            str(symbol),
            str(decision),
            int(confidence),
            str(reasoning),
            float(market_data.get('price', 0)),
            float(market_data.get('rsi', 50)),
            str(market_data.get('trend', 'Neutral'))
        ))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Save AI Analysis Error: {e}")

def save_trade(trade_data):
    """Saves a trade to the trade history table."""
    conn = get_db_connection()
    if not conn:
        return None
    
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO trade_history (symbol, side, size, price, order_id, order_type, status, pnl, fees, notes)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            str(trade_data.get('symbol', '')),
            str(trade_data.get('side', '')),
            float(trade_data.get('size', 0)),
            float(trade_data.get('price', 0)) if trade_data.get('price') else None,
            str(trade_data.get('order_id', '')) if trade_data.get('order_id') else None,
            str(trade_data.get('order_type', 'market')),
            str(trade_data.get('status', 'filled')),
            float(trade_data.get('pnl', 0)) if trade_data.get('pnl') is not None else None,
            float(trade_data.get('fees', 0)) if trade_data.get('fees') is not None else None,
            str(trade_data.get('notes', '')) if trade_data.get('notes') else None
        ))
        trade_id = cur.fetchone()['id']
        conn.commit()
        cur.close()
        conn.close()
        return trade_id
    except Exception as e:
        print(f"Save Trade Error: {e}")
        return None

def update_or_create_position(position_data):
    """Updates existing position or creates new one."""
    conn = get_db_connection()
    if not conn:
        return None
    
    try:
        cur = conn.cursor()
        # Check if position exists
        cur.execute("""
            SELECT id FROM open_positions 
            WHERE symbol = %s AND side = %s
        """, (str(position_data.get('symbol', '')), str(position_data.get('side', ''))))
        
        existing = cur.fetchone()
        
        if existing:
            # Update existing position
            cur.execute("""
                UPDATE open_positions 
                SET size = %s, current_price = %s, unrealized_pnl = %s, updated_at = CURRENT_TIMESTAMP
                WHERE symbol = %s AND side = %s
            """, (
                float(position_data.get('size', 0)),
                float(position_data.get('current_price', 0)) if position_data.get('current_price') else None,
                float(position_data.get('unrealized_pnl', 0)) if position_data.get('unrealized_pnl') is not None else None,
                str(position_data.get('symbol', '')),
                str(position_data.get('side', ''))
            ))
        else:
            # Create new position
            cur.execute("""
                INSERT INTO open_positions (symbol, side, size, entry_price, current_price, unrealized_pnl, leverage, order_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                str(position_data.get('symbol', '')),
                str(position_data.get('side', '')),
                float(position_data.get('size', 0)),
                float(position_data.get('entry_price', 0)),
                float(position_data.get('current_price', 0)) if position_data.get('current_price') else None,
                float(position_data.get('unrealized_pnl', 0)) if position_data.get('unrealized_pnl') is not None else None,
                int(position_data.get('leverage', 1)),
                str(position_data.get('order_id', '')) if position_data.get('order_id') else None
            ))
        
        conn.commit()
        cur.close()
        conn.close()
        return True
    except Exception as e:
        print(f"Update Position Error: {e}")
        return None

def close_position(symbol, side):
    """Closes a position by removing it from open_positions."""
    conn = get_db_connection()
    if not conn:
        return False
    
    try:
        cur = conn.cursor()
        cur.execute("""
            DELETE FROM open_positions 
            WHERE symbol = %s AND side = %s
        """, (str(symbol), str(side)))
        conn.commit()
        cur.close()
        conn.close()
        return True
    except Exception as e:
        print(f"Close Position Error: {e}")
        return False

def get_open_positions():
    """Returns all open positions."""
    conn = get_db_connection()
    if not conn:
        return []
    
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM open_positions ORDER BY opened_at DESC")
        positions = cur.fetchall()
        cur.close()
        conn.close()
        return [dict(pos) for pos in positions]
    except Exception as e:
        print(f"Get Positions Error: {e}")
        return []

def get_trade_history(limit=100, symbol=None):
    """Returns trade history, optionally filtered by symbol."""
    conn = get_db_connection()
    if not conn:
        return []
    
    try:
        cur = conn.cursor()
        if symbol:
            cur.execute("""
                SELECT * FROM trade_history 
                WHERE symbol = %s 
                ORDER BY execution_time DESC 
                LIMIT %s
            """, (str(symbol), limit))
        else:
            cur.execute("""
                SELECT * FROM trade_history 
                ORDER BY execution_time DESC 
                LIMIT %s
            """, (limit,))
        
        trades = cur.fetchall()
        cur.close()
        conn.close()
        return [dict(trade) for trade in trades]
    except Exception as e:
        print(f"Get Trade History Error: {e}")
        return []