# Chartor AI - Intelligent Trading Bot

Chartor AI is an advanced automated trading system that combines machine learning, sentiment analysis, and AI-powered decision-making to execute trades on the WEEX exchange. The platform features a Strategy Marketplace where users can create, manage, and activate custom trading strategies in plain English.

## 🚀 Features

### Core Features
- **Hybrid AI Trading Engine**: Combines local ML models (RandomForest) with Gemini AI for intelligent trading decisions
- **Strategy Marketplace**: Create and manage custom trading strategies in plain English
- **Auto-Trading**: Automated trade execution based on active strategies or AI analysis
- **Real-Time Market Analysis**: Technical indicators (RSI, EMA, ATR) with ML predictions
- **Sentiment Analysis**: FinBERT-based market sentiment analysis
- **Risk Management**: Configurable risk tolerance and position management
- **Live Trading Dashboard**: Modern React-based UI with real-time charts and logs

### Strategy Marketplace
- **Create Strategies**: Describe trading logic in plain English (e.g., "Buy when RSI is under 30")
- **AI Translation**: Gemini AI converts natural language to executable trading logic
- **Toggle Activation**: Enable/disable strategies with a single click
- **Auto-Execution**: Active strategies automatically execute trades when conditions are met

### Technical Analysis
- **500 Candle History**: Extended historical data for better ML training
- **Multiple Timeframes**: Scalping (1m), Intraday (15m), Swing (4h)
- **Technical Indicators**: RSI, EMA, ATR, Volume Analysis
- **Market Structure Analysis**: Trend detection, support/resistance levels

## 📋 Prerequisites

- Python 3.8+
- Node.js 16+ (for frontend)
- PostgreSQL database (Neon recommended)
- WEEX API credentials
- Google Gemini API key

## 🛠️ Installation

### Backend Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/HoomanBuilds/Chartor-Market.git
   cd Chartor-Market
   ```

2. **Install Python dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment variables**
   Create a `.env` file in the root directory:
   ```env
   # Database (Neon PostgreSQL)
   DATABASE_URL=postgresql://user:password@host/database

   # WEEX Exchange API
   WEEX_API_KEY=your_weex_api_key
   WEEX_SECRET=your_weex_secret
   WEEX_PASSPHRASE=your_weex_passphrase

   # Google Gemini API
   GEMINI_API_KEY=your_gemini_api_key
   GEMINI_CHAT_MODEL=gemini-flash-latest
   GEMINI_DECISION_MODEL=gemini-flash-latest
   ```

4. **Initialize the database**
   The database tables will be created automatically on first run.

5. **Start the backend server**
   ```bash
   python api_server.py
   ```
   The server will run on `http://localhost:8000`

### Frontend Setup

1. **Navigate to frontend directory**
   ```bash
   cd kairos-trading-hub-main
   ```

2. **Install dependencies**
   ```bash
   npm install
   # or
   bun install
   ```

3. **Start the development server**
   ```bash
   npm run dev
   # or
   bun dev
   ```
   The frontend will run on `http://localhost:5173` (or port 8080)

## 📖 Usage

### Starting Auto-Trading

1. **Enable Auto-Trading**
   - Open the Sentinel tab in the right panel
   - Toggle "Auto-Trading" switch to ON
   - The sentinel service will start monitoring the market

2. **Select Trading Asset**
   - Click on an asset in the left sidebar (BTC, ETH, etc.)
   - The system will automatically update to monitor that asset

3. **Configure Risk Settings**
   - Adjust risk tolerance slider (0-50%)
   - Lower values = more conservative trading

### Creating Strategies

1. **Open Strategies Tab**
   - Click on the "Strategies" tab in the right panel

2. **Create New Strategy**
   - Click "Create" button
   - Enter strategy name (e.g., "RSI Oversold Buy")
   - Describe your strategy in plain English:
     - "Buy when RSI is under 30 and price is above EMA 20"
     - "Sell when RSI exceeds 70"
     - "Buy on high volume with bullish trend"
   - Click "Generate & Save Strategy"
   - Gemini AI will translate your description into executable logic

3. **Activate Strategy**
   - Toggle the switch next to any strategy to activate it
   - When activated, auto-trading is automatically enabled
   - The strategy will execute trades when conditions are met

### Monitoring Trades

- **Trades History Tab**: View all executed trades
- **Positions Tab**: Monitor open positions and P&L
- **Risk Metrics Tab**: Track performance metrics (win rate, Sharpe ratio, drawdown)
- **Terminal Logs**: Real-time system logs and analysis results

## 🏗️ Architecture

### Backend Components

- **`api_server.py`**: FastAPI server with all endpoints
- **`core/llm_brain.py`**: Gemini AI integration for trading decisions
- **`core/ml_analyst.py`**: RandomForest ML model for price prediction
- **`core/sentiment.py`**: FinBERT sentiment analysis
- **`core/strategy_evaluator.py`**: Dynamic strategy evaluation engine
- **`core/weex_api.py`**: WEEX exchange API client
- **`core/db_manager.py`**: PostgreSQL database management
- **`core/analysis.py`**: Technical analysis and market structure

### Frontend Components

- **React + TypeScript**: Modern UI framework
- **TradingView Charts**: Real-time candlestick charts
- **Shadcn UI**: Component library
- **Real-time Updates**: WebSocket-like polling for live data

### Data Flow

1. **Market Data**: Fetched from Binance (public API) for reliability
2. **ML Training**: RandomForest trains on 500 candles
3. **Sentiment**: FinBERT analyzes market sentiment
4. **Strategy Evaluation**: Active strategies checked against market data
5. **AI Decision**: Gemini synthesizes all inputs for final decision
6. **Trade Execution**: Orders placed on WEEX exchange

## 🔌 API Endpoints

### Trading
- `POST /api/trade` - Execute manual trade
- `POST /api/trade-settings` - Update auto-trading settings
- `GET /api/trade-settings` - Get current settings
- `GET /api/trade-history` - Get trade history
- `GET /api/positions` - Get open positions
- `GET /api/risk-metrics` - Get risk metrics

### Analysis
- `POST /api/trigger-analysis` - Trigger on-demand analysis
- `GET /api/ai-analysis` - Get latest AI analysis
- `GET /api/candles` - Get candlestick data
- `GET /api/logs` - Get system logs

### Strategies
- `GET /api/strategies` - Get all strategies
- `POST /api/strategies/{id}/toggle` - Toggle strategy activation
- `POST /api/create-strategy` - Create new strategy

### Chat
- `POST /api/chat` - Chat with Chartor AI

## ⚙️ Configuration

### Trading Modes
- **Scalping**: 1-minute candles, fast execution
- **Intraday**: 15-minute candles, balanced approach
- **Swing**: 4-hour candles, longer-term positions

### Risk Management
- **Risk Tolerance**: 0-50% (affects confidence threshold)
- **Confidence Threshold**: `90 - risk_tolerance` (minimum confidence to execute)
- **Position Sizing**: Fixed at 10 units (configurable in code)

### Strategy Logic Variables
Available variables for strategy logic:
- `rsi`: Relative Strength Index (0-100)
- `price`: Current price (float)
- `ema_20`: 20-period EMA (float)
- `volatility`: ATR volatility (float)
- `trend`: Market trend ('BULLISH', 'BEARISH', 'NEUTRAL')
- `volume_spike`: Boolean indicating high volume

### Example Strategy Logic
```
rsi < 30                                    # RSI oversold
price > ema_20 and trend == 'BULLISH'      # Bullish trend with price above EMA
volume_spike == True and rsi < 50          # High volume with moderate RSI
rsi > 70 or price < ema_20                  # Overbought or price below EMA
```

## 🔒 Security

- **API Keys**: Stored in `.env` file (never commit to git)
- **Database**: Uses parameterized queries to prevent SQL injection
- **Strategy Evaluation**: Safe `eval()` with restricted context
- **Rate Limiting**: Built-in rate limiting for Gemini API

## 📊 Database Schema

### Tables
- `trade_settings`: Auto-trading configuration
- `strategies`: User-defined trading strategies
- `market_log`: Market analysis logs
- `ai_analysis`: AI decision history
- `trade_history`: Executed trades
- `open_positions`: Current positions

## 🐛 Troubleshooting

### Common Issues

1. **"Database connection failed"**
   - Check `DATABASE_URL` in `.env`
   - Ensure Neon database is accessible

2. **"WEEX API Error"**
   - Verify API credentials in `.env`
   - Check network connectivity
   - Ensure API keys have trading permissions

3. **"Gemini quota exceeded"**
   - System automatically uses fallback engine
   - Wait for cooldown period (1 hour)
   - Consider upgrading Gemini API plan

4. **Strategies not executing**
   - Ensure auto-trading is enabled
   - Check that strategies are activated (toggle ON)
   - Verify strategy logic syntax

5. **Frontend not connecting**
   - Check backend is running on port 8000
   - Verify CORS settings in `api_server.py`
   - Check browser console for errors


### Code Structure
```
Chartor-Market/
├── api_server.py          # Main FastAPI server
├── core/                   # Core modules
│   ├── analysis.py        # Technical analysis
│   ├── db_manager.py      # Database operations
│   ├── llm_brain.py       # Gemini AI integration
│   ├── ml_analyst.py      # ML model
│   ├── sentiment.py       # Sentiment analysis
│   ├── strategy_evaluator.py  # Strategy evaluation
│   └── weex_api.py        # WEEX API client
├── kairos-trading-hub-main/  # Frontend React app
│   ├── src/
│   │   ├── components/    # React components
│   │   ├── pages/         # Page components
│   │   └── types/         # TypeScript types
│   └── package.json
├── requirements.txt       # Python dependencies
└── README.md             # This file
```

---

**⚠️ Disclaimer**: Trading cryptocurrencies involves substantial risk. This software is provided as-is without warranty. Use at your own risk. Past performance does not guarantee future results.

