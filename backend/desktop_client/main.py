"""
Pocket Option Desktop Trading Client
=====================================

Main entry point - launches the GUI or command-line bot.

Usage:
    python main.py          # Launch GUI
    python main.py --cli    # Launch command-line bot
    python main.py --help   # Show options
"""

import sys
import os
import logging

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    """Main entry point"""
    # Check for CLI mode
    if '--cli' in sys.argv or '--headless' in sys.argv:
        # Run command-line bot
        from trading_bot import main as run_bot
        run_bot()
    else:
        # Run GUI
        try:
            from gui import TradingBotGUI
            app = TradingBotGUI()
            app.run()
        except ImportError as e:
            print(f"GUI not available: {e}")
            print("Falling back to command-line mode...")
            print("Run with --cli flag for command-line bot")
            from trading_bot import main as run_bot
            run_bot()
        except Exception as e:
            print(f"Error starting GUI: {e}")
            print("Run with --cli flag for command-line bot")


if __name__ == '__main__':
    # Setup basic logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    main()
