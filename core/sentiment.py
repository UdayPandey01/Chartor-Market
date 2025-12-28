from transformers import pipeline
import warnings

# Suppress warnings to keep terminal clean
warnings.filterwarnings("ignore")

# Global pipeline - loaded once
_sentiment_pipeline = None

def get_sentiment_pipeline():
    """Lazy load the sentiment pipeline to avoid loading on import."""
    global _sentiment_pipeline
    if _sentiment_pipeline is None:
        try:
            print("Loading Local FinBERT Model... (This runs offline)")
            # FinBERT is specialized for Financial Sentiment
            # The pipeline handles tokenization and model inference automatically
            _sentiment_pipeline = pipeline("sentiment-analysis", model="ProsusAI/finbert")
            print("FinBERT model loaded successfully")
        except Exception as e:
            print(f"Failed to load FinBERT model: {e}")
            print("Sentiment analysis will return NEUTRAL")
            _sentiment_pipeline = None
    return _sentiment_pipeline

def get_sentiment(text_input):
    """
    Analyzes text locally. Returns 'POSITIVE', 'NEGATIVE', or 'NEUTRAL' and score.
    
    Args:
        text_input: String text to analyze
        
    Returns:
        tuple: (label, score) where label is 'POSITIVE', 'NEGATIVE', or 'NEUTRAL'
               and score is between -1.0 and 1.0
    """
    if not text_input or len(text_input) < 5:
        return "NEUTRAL", 0.0

    try:
        pipeline = get_sentiment_pipeline()
        if pipeline is None:
            return "NEUTRAL", 0.0
        
        # Run inference locally
        result = pipeline(text_input)[0]
        label = result['label'] 
        score = result['score'] 
        
        # Convert to a simple -1 to 1 scale
        final_score = 0.0
        if label == 'positive':
            final_score = score
        elif label == 'negative':
            final_score = -score
        
        return label.upper(), round(final_score, 2)
    except Exception as e:
        print(f"Sentiment Error: {e}")
        return "NEUTRAL", 0.0

def analyze_market_sentiment(symbol="BTC"):
    """
    Analyzes market sentiment based on symbol.
    In production, this would scrape news/reddit/twitter.
    For now, returns a mock analysis based on symbol.
    """
    mock_headlines = {
        "BTC": "Bitcoin shows strong institutional adoption as major corporations add to reserves.",
        "ETH": "Ethereum network activity increases as DeFi protocols see record volumes.",
        "SOL": "Solana ecosystem expands with new partnerships and developer interest.",
        "DOGE": "Dogecoin community remains active as meme coin sector gains traction."
    }
    
    headline = mock_headlines.get(symbol.upper(), "Crypto markets showing resilience as volume increases.")
    return get_sentiment(headline)

# TEST IT
if __name__ == "__main__":
    print(get_sentiment("Bitcoin hits all time high as institutions buy aggressively."))
    print(get_sentiment("Market crashes due to regulatory crackdown."))
    print(analyze_market_sentiment("BTC"))

