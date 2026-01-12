"""
Example: Start Institutional Trading System
Simple script to demonstrate system usage
"""
import logging
import sys
from datetime import datetime


def main():
    """Start the institutional trading system"""
    
    # Setup logging with UTF-8 encoding for Windows emoji support
    import io
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')),
            logging.FileHandler(f'trading_{datetime.now().strftime("%Y%m%d")}.log', encoding='utf-8')
        ]
    )
    
    logger = logging.getLogger("InstitutionalTrading")
    
    print("="*60)
    print("INSTITUTIONAL TRADING SYSTEM")
    print("="*60)
    print()
    
    try:
        # Import required components
        logger.info("Importing components...")
        from trading_orchestrator import TradingOrchestrator
        from core.weex_api import WeexClient
        
        # Initialize WEEX client
        logger.info("Initializing WEEX client...")
        client = WeexClient()
        
        # Configuration
        INITIAL_EQUITY = 10000.0  # Starting capital
        
        print(f"Configuration:")
        print(f"  Initial Equity: ${INITIAL_EQUITY:,.2f}")
        print(f"  Leverage: 20x")
        print(f"  Risk per trade: 1.25%")
        print(f"  Max daily loss: 3%")
        print(f"  Max drawdown: 12%")
        print(f"  Cycle interval: 30 seconds")
        print()
        
        # Create orchestrator
        logger.info("Creating trading orchestrator...")
        orchestrator = TradingOrchestrator(
            weex_client=client,
            initial_equity=INITIAL_EQUITY,
            logger=logger
        )
        
        print("✅ System initialized successfully!")
        print()
        print("Enabled symbols:")
        for symbol in orchestrator.ENABLED_SYMBOLS:
            print(f"  • {symbol}")
        print()
        
        # Confirm before starting
        print("⚠️  WARNING: This will start LIVE TRADING with real money!")
        print("⚠️  Make sure you understand the risks and have reviewed the documentation.")
        print()
        
        response = input("Type 'YES' to start trading, or anything else to exit: ")
        
        if response.strip().upper() != "YES":
            print("❌ Trading not started. Exiting safely.")
            return 0
        
        print()
        print("🚀 Starting institutional trading system...")
        print("   Press Ctrl+C to stop")
        print()
        
        # Start continuous trading
        orchestrator.run_continuous()
        
    except KeyboardInterrupt:
        print("\n\n🛑 Shutdown signal received...")
        logger.info("Shutting down gracefully...")
        
        # Orchestrator handles position closure in run_continuous
        print("✅ Shutdown complete")
        return 0
        
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        print(f"\n❌ Error: {e}")
        print("   Check the log file for details")
        return 1


if __name__ == "__main__":
    sys.exit(main())
