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
    
    logger.info("="*60)
    logger.info("INSTITUTIONAL TRADING SYSTEM")
    logger.info("="*60)
    
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
        
        logger.info(f"Configuration:")
        logger.info(f"  Initial Equity: ${INITIAL_EQUITY:,.2f}")
        logger.info(f"  Leverage: 20x")
        logger.info(f"  Risk per trade: 1.25%")
        logger.info(f"  Max daily loss: 3%")
        logger.info(f"  Max drawdown: 12%")
        logger.info(f"  Cycle interval: 30 seconds")
        
        # Create orchestrator
        logger.info("Creating trading orchestrator...")
        orchestrator = TradingOrchestrator(
            weex_client=client,
            initial_equity=INITIAL_EQUITY,
            logger=logger
        )
        
        logger.info("✅ System initialized successfully!")
        logger.info("Enabled symbols:")
        for symbol in orchestrator.ENABLED_SYMBOLS:
            logger.info(f"  • {symbol}")
        
        # Confirm before starting
        logger.warning("⚠️  WARNING: This will start LIVE TRADING with real money!")
        logger.warning("⚠️  Make sure you understand the risks and have reviewed the documentation.")
        
        response = input("Type 'YES' to start trading, or anything else to exit: ")
        
        if response.strip().upper() != "YES":
            logger.info("❌ Trading not started. Exiting safely.")
            return 0
        
        logger.info("🚀 Starting institutional trading system...")
        logger.info("   Press Ctrl+C to stop")
        
        # Start continuous trading
        orchestrator.run_continuous()
        
    except KeyboardInterrupt:
        print("\n\n🛑 Shutdown signal received...")
        logger.info("Shutting down gracefully...")
        
        # Orchestrator handles position closure in run_continuous
        logger.info("✅ Shutdown complete")
        return 0
        
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        logger.error(f"\n❌ Error: {e}")
        logger.error("   Check the log file for details")
        return 1


if __name__ == "__main__":
    sys.exit(main())
