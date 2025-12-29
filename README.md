

# Chartor Market

**Where strategies trade.**

Chartor Market is an AI-native automated trading platform with a built-in **Strategy Marketplace**, enabling users to create, activate, and execute algorithmic trading strategies using plain English. It bridges the gap between human intent and machine-executable trading logic, making systematic trading accessible without compromising sophistication.

---

## 1. Problem Statement

Algorithmic trading today suffers from three fundamental problems:

### 1. Strategy Creation Is Inaccessible

Building trading strategies typically requires:

* Strong programming skills
* Deep familiarity with trading frameworks
* Complex rule encoding and testing

This excludes a large class of traders, analysts, and domain experts who understand markets but not code.

### 2. Execution Is Fragmented

Most platforms separate:

* Strategy ideation
* Backtesting
* Execution
* Risk management

This fragmentation introduces latency, inconsistency, and operational risk.

### 3. Decision-Making Lacks Context

Purely rule-based bots ignore:

* Market sentiment
* Regime shifts
* Probabilistic confidence

While purely AI-driven systems lack transparency and user control.

---

## 2. Example

A trader wants to express the following logic:

> “Buy BTC when RSI is below 30, price is above the 20 EMA, and market sentiment is positive. Exit when RSI crosses above 70 or trend turns bearish.”

In most systems, this requires:

* Writing indicator code
* Wiring conditions manually
* Handling execution edge cases

In Chartor Market, this strategy is written **exactly as above**, saved, toggled on, and executed automatically.

---

## 3. Solution

Chartor Market introduces a **Strategy-as-Language** paradigm.

### Core Idea

Plain-English trading intent → AI translation → Safe executable logic → Automated execution.

### How It Works

1. **Natural Language Input**
   Users describe strategies in plain English.

2. **AI Translation Layer**
   Gemini AI converts descriptions into deterministic, executable strategy logic.

3. **Hybrid Decision Engine**
   Decisions are synthesized using:

   * Technical indicators (RSI, EMA, ATR)
   * Machine learning predictions (RandomForest)
   * Market sentiment (FinBERT)
   * User-defined strategy rules

4. **Automated Execution**
   Validated decisions are executed in real time on the WEEX exchange with built-in risk controls.

---

## 4. Key Features

### Strategy Marketplace

* Create strategies using natural language
* AI-translated into executable logic
* One-click activation and deactivation
* Multiple strategies can run concurrently

### Hybrid AI Trading Engine

* Local ML models for price behavior
* LLM-based reasoning for contextual decisions
* Deterministic confidence thresholds for execution

### Real-Time Market Intelligence

* Multi-timeframe analysis (1m, 15m, 4h)
* 500-candle historical context
* Trend and market structure detection
* Volume and volatility awareness

### Risk & Execution Controls

* Configurable risk tolerance
* Confidence-based trade filtering
* Position tracking and P&L monitoring

### Live Trading Dashboard

* Real-time charts and logs
* Strategy status visibility
* Trade history and open positions

---

## 5. System Architecture

### Backend

* **FastAPI** for low-latency APIs
* **RandomForest ML** for predictive signals
* **FinBERT** for sentiment analysis
* **Gemini AI** for strategy translation and decision synthesis
* **PostgreSQL (Neon)** for persistence
* **WEEX API** for live trade execution

### Frontend

* **React + TypeScript**
* TradingView-based charting
* Real-time system telemetry
* Strategy and risk management UI

### Data Flow

1. Market data ingestion (Binance public API)
2. Feature extraction & ML inference
3. Sentiment analysis
4. Strategy condition evaluation
5. AI decision synthesis
6. Trade execution on WEEX
7. Logging and metrics persistence

---

## 6. Impact

### For Traders

* No-code algorithmic trading
* Faster experimentation and iteration
* Transparent, controllable automation

### For the Ecosystem

* Democratizes systematic trading
* Creates a marketplace for strategy logic
* Bridges discretionary thinking with machine execution

### For the Future

Chartor Market is designed to evolve into:

* A tradable strategy economy
* A foundation for agent-to-agent trading
* A composable financial automation layer

---

## 7. Installation & Setup

### Prerequisites

* Python 3.8+
* Node.js 16+
* PostgreSQL (Neon recommended)
* WEEX API credentials
* Google Gemini API key

### Backend

```bash
git clone https://github.com/HoomanBuilds/Chartor-Market.git
cd Chartor-Market
pip install -r requirements.txt
python api_server.py
```

### Frontend

```bash
cd kairos-trading-hub-main
npm install
npm run dev
```

---

## 8. API Overview

### Trading

* `POST /api/trade`
* `GET /api/trade-history`
* `GET /api/positions`
* `GET /api/risk-metrics`

### Strategies

* `POST /api/create-strategy`
* `GET /api/strategies`
* `POST /api/strategies/{id}/toggle`

### Analysis

* `POST /api/trigger-analysis`
* `GET /api/ai-analysis`
* `GET /api/candles`

---

## 9. Security & Safety

* Secrets managed via environment variables
* Parameterized database queries
* Restricted strategy execution context
* AI rate limiting and fallback logic

---

## 10. Disclaimer

This project is a hackathon prototype intended for experimentation and research. Cryptocurrency trading involves significant risk. Use at your own discretion.

---

**Chartor Market is not just a trading bot.
It is an interface between human strategy and machine execution.**
