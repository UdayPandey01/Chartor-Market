import pandas as pd
import pandas_ta as ta
import numpy as np
from sklearn.ensemble import RandomForestClassifier
import warnings

warnings.filterwarnings("ignore")

class MLAnalyst:
    def __init__(self):
        # Initialize a Random Forest Classifier
        self.model = RandomForestClassifier(n_estimators=100, random_state=42, max_depth=10)
        self.is_trained = False
        self.feature_names = ['RSI', 'EMA_20', 'Return', 'Volume_Normalized']

    def prepare_features(self, df):
        """Prepare features from DataFrame."""
        try:
            # Ensure numeric types
            numeric_cols = ['open', 'high', 'low', 'close', 'volume']
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            
            # Add Technical Indicators
            df['RSI'] = ta.rsi(df['close'], length=14)
            df['EMA_20'] = ta.ema(df['close'], length=20)
            df['Return'] = df['close'].pct_change()
            
            # Normalize volume (use rolling mean for normalization)
            if 'volume' in df.columns:
                volume_mean = df['volume'].rolling(window=20).mean()
                df['Volume_Normalized'] = df['volume'] / (volume_mean + 1)  # Avoid division by zero
            else:
                df['Volume_Normalized'] = 1.0
            
            return df
        except Exception as e:
            print(f"Feature preparation error: {e}")
            return df

    def train_model(self, candles):
        """
        Trains the model instantly on the latest candle data.
        
        Args:
            candles: List of candles in format [timestamp, open, high, low, close, volume, ...]
        """
        try:
            if not candles or len(candles) < 50:
                return False
            
            # 1. Prepare Data
            # Handle both list of lists and list of dicts
            if isinstance(candles[0], (list, tuple)):
                df = pd.DataFrame(candles, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'] + 
                                 ['close_time', 'quote_volume', 'trades', 'taker_buy_base', 'taker_buy_quote', 'ignore'][:len(candles[0])-6])
            else:
                df = pd.DataFrame(candles)
            
            # Keep only needed columns
            required_cols = ['open', 'high', 'low', 'close', 'volume']
            available_cols = [col for col in required_cols if col in df.columns]
            if len(available_cols) < 4:  # Need at least open, high, low, close
                return False
            
            # Convert to numeric
            for col in available_cols:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            
            # Drop rows with NaN in essential columns
            df = df.dropna(subset=available_cols)
            
            if len(df) < 30:
                return False
            
            # 2. Prepare Features
            df = self.prepare_features(df)
            
            # 3. Create Target (Did price go UP or DOWN in the next candle?)
            # 1 = Up, 0 = Down
            df['Target'] = (df['close'].shift(-1) > df['close']).astype(int)
            
            # Drop NaN values created by indicators and target
            df = df.dropna(subset=self.feature_names + ['Target'])
            
            if len(df) < 20:
                return False
            
            # 4. Features to train on
            X = df[self.feature_names].values
            y = df['Target'].values
            
            # Train the model
            self.model.fit(X, y)
            self.is_trained = True
            return True
            
        except Exception as e:
            print(f"ML Training Error: {e}")
            import traceback
            traceback.print_exc()
            return False

    def predict_next_move(self, market_state):
        """
        Predicts next price move based on current market state.
        
        Args:
            market_state: Dict with keys like 'rsi', 'ema_20', 'price', 'volume'
            
        Returns:
            tuple: (direction, confidence) where direction is 'UP' or 'DOWN'
                   and confidence is 0-100
        """
        if not self.is_trained:
            return "UNKNOWN", 0.0
        
        try:
            # Extract features from market_state
            rsi = float(market_state.get('rsi', 50))
            ema_20 = float(market_state.get('ema_20', market_state.get('price', 0)))
            price = float(market_state.get('price', 0))
            
            # Calculate return (simplified - use recent price change if available)
            # For now, use a small default return
            price_return = 0.01  # Default 1% return assumption
            if 'price_change' in market_state:
                price_return = float(market_state.get('price_change', 0.01))
            elif 'volatility' in market_state and price > 0:
                # Use volatility as proxy for return expectation
                price_return = float(market_state.get('volatility', 0)) / price if price > 0 else 0.01
            
            # Normalize volume
            volume = float(market_state.get('volume', 1000))
            volume_normalized = 1.0  # Default
            if 'volume_spike' in market_state:
                volume_normalized = 1.5 if market_state.get('volume_spike') else 1.0
            
            # Create feature vector matching training: [RSI, EMA_20, Return, Volume_Normalized]
            current_features = np.array([[rsi, ema_20, price_return, volume_normalized]])
            
            # Predict
            prediction = self.model.predict(current_features)[0]
            probabilities = self.model.predict_proba(current_features)[0]
            
            # Get confidence (probability of predicted class)
            confidence = probabilities[prediction] * 100
            
            direction = "UP" if prediction == 1 else "DOWN"
            return direction, round(confidence, 1)
        except Exception as e:
            print(f"ML Prediction Error: {e}")
            import traceback
            traceback.print_exc()
            return "UNKNOWN", 0.0

    def get_model_status(self):
        """Returns model training status."""
        return {
            "is_trained": self.is_trained,
            "model_type": "RandomForestClassifier",
            "features": self.feature_names
        }

