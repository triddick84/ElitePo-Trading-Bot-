"""
Pocket Option Desktop Client - GUI
===================================

Tkinter-based GUI for configuring and running the trading bot.
Based on VitalySvyatyuk's visual interface approach.
"""

import sys
import os
import json
import asyncio
import threading
import logging
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from trading_bot import PocketOptionTradingBot

logger = logging.getLogger(__name__)

SETTINGS_FILE = 'bot_settings.json'


class TradingBotGUI:
    """
    Tkinter GUI for the Pocket Option Trading Bot
    """
    
    def __init__(self):
        self.window = None
        self.bot = None
        self.bot_thread = None
        self.settings = {}
        self.is_running = False
        
        # Log widget
        self.log_text = None
        
        self._init_window()
    
    def _init_window(self):
        """Initialize the main window"""
        self.window = tk.Tk()
        self.window.title('GPT Signal Bot - Desktop Client v2.0')
        self.window.geometry('700x550')
        self.window.resizable(True, True)
        
        # Load settings
        self.load_settings()
        
        # Create UI
        self._create_ui()
        
        # Setup logging to GUI
        self._setup_logging()
        
        # Handle window close
        self.window.protocol("WM_DELETE_WINDOW", self._on_close)
    
    def _create_ui(self):
        """Create the user interface"""
        # Main frame
        main_frame = tk.Frame(self.window, padx=10, pady=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # === TOP SECTION: Account Settings ===
        account_frame = tk.LabelFrame(main_frame, text="Account Settings", padx=10, pady=5)
        account_frame.pack(fill=tk.X, pady=5)
        
        # Account type
        tk.Label(account_frame, text="Account Type:").grid(row=0, column=0, sticky=tk.W)
        self.account_type = tk.StringVar(value=self.settings.get('account_type', 'demo'))
        ttk.Radiobutton(account_frame, text="Demo", variable=self.account_type, value='demo').grid(row=0, column=1)
        ttk.Radiobutton(account_frame, text="Live", variable=self.account_type, value='live').grid(row=0, column=2)
        
        # Trade amount
        tk.Label(account_frame, text="Trade Amount ($):").grid(row=1, column=0, sticky=tk.W)
        self.trade_amount = tk.IntVar(value=self.settings.get('trade_amount', 1))
        tk.Entry(account_frame, textvariable=self.trade_amount, width=10).grid(row=1, column=1)
        
        # Min payout
        tk.Label(account_frame, text="Min Payout (%):").grid(row=1, column=2, sticky=tk.W, padx=(20,0))
        self.min_payout = tk.IntVar(value=self.settings.get('min_payout', 80))
        tk.Entry(account_frame, textvariable=self.min_payout, width=10).grid(row=1, column=3)
        
        # === STRATEGY SECTION ===
        strategy_frame = tk.LabelFrame(main_frame, text="Strategies", padx=10, pady=5)
        strategy_frame.pack(fill=tk.X, pady=5)
        
        # Moving Averages
        self.use_ma = tk.IntVar(value=self.settings.get('use_ma_crossover', 1))
        tk.Checkbutton(strategy_frame, text="MA Crossover", variable=self.use_ma).grid(row=0, column=0, sticky=tk.W)
        
        tk.Label(strategy_frame, text="Fast MA:").grid(row=0, column=1)
        self.fast_ma = tk.IntVar(value=self.settings.get('fast_ma', 3))
        tk.Entry(strategy_frame, textvariable=self.fast_ma, width=5).grid(row=0, column=2)
        
        tk.Label(strategy_frame, text="Slow MA:").grid(row=0, column=3)
        self.slow_ma = tk.IntVar(value=self.settings.get('slow_ma', 8))
        tk.Entry(strategy_frame, textvariable=self.slow_ma, width=5).grid(row=0, column=4)
        
        # RSI
        self.use_rsi = tk.IntVar(value=self.settings.get('use_rsi', 1))
        tk.Checkbutton(strategy_frame, text="RSI Strategy", variable=self.use_rsi).grid(row=1, column=0, sticky=tk.W)
        
        tk.Label(strategy_frame, text="RSI Period:").grid(row=1, column=1)
        self.rsi_period = tk.IntVar(value=self.settings.get('rsi_period', 14))
        tk.Entry(strategy_frame, textvariable=self.rsi_period, width=5).grid(row=1, column=2)
        
        # Enhanced Divergence
        self.use_enhanced = tk.IntVar(value=self.settings.get('use_enhanced_divergence', 1))
        tk.Checkbutton(strategy_frame, text="Enhanced Divergence (Advanced)", variable=self.use_enhanced).grid(row=2, column=0, columnspan=2, sticky=tk.W)
        
        # Professional Scalping
        self.use_scalping = tk.IntVar(value=self.settings.get('use_professional_scalping', 0))
        tk.Checkbutton(strategy_frame, text="Professional Scalping (Advanced)", variable=self.use_scalping).grid(row=2, column=2, columnspan=2, sticky=tk.W)
        
        # Min confidence
        tk.Label(strategy_frame, text="Min Confidence (%):").grid(row=3, column=0, sticky=tk.W)
        self.min_confidence = tk.IntVar(value=self.settings.get('min_confidence', 65))
        tk.Entry(strategy_frame, textvariable=self.min_confidence, width=5).grid(row=3, column=1)
        
        # Min strategy votes
        tk.Label(strategy_frame, text="Min Strategy Votes:").grid(row=3, column=2, sticky=tk.W)
        self.min_votes = tk.IntVar(value=self.settings.get('min_strategy_votes', 2))
        tk.Entry(strategy_frame, textvariable=self.min_votes, width=5).grid(row=3, column=3)
        
        # === RISK MANAGEMENT ===
        risk_frame = tk.LabelFrame(main_frame, text="Risk Management", padx=10, pady=5)
        risk_frame.pack(fill=tk.X, pady=5)
        
        # Martingale
        self.martingale_enabled = tk.IntVar(value=self.settings.get('martingale_enabled', 0))
        tk.Checkbutton(risk_frame, text="Enable Martingale", variable=self.martingale_enabled).grid(row=0, column=0, sticky=tk.W)
        
        tk.Label(risk_frame, text="Martingale List:").grid(row=0, column=1)
        self.martingale_list = tk.StringVar(value=self.settings.get('martingale_list_str', '1, 3, 7, 15, 32, 67'))
        tk.Entry(risk_frame, textvariable=self.martingale_list, width=25).grid(row=0, column=2, columnspan=2)
        
        # Take Profit
        self.take_profit_enabled = tk.IntVar(value=self.settings.get('take_profit_enabled', 0))
        tk.Checkbutton(risk_frame, text="Take Profit ($):", variable=self.take_profit_enabled).grid(row=1, column=0, sticky=tk.W)
        self.take_profit = tk.IntVar(value=self.settings.get('take_profit', 100))
        tk.Entry(risk_frame, textvariable=self.take_profit, width=10).grid(row=1, column=1)
        
        # Stop Loss
        self.stop_loss_enabled = tk.IntVar(value=self.settings.get('stop_loss_enabled', 0))
        tk.Checkbutton(risk_frame, text="Stop Loss ($):", variable=self.stop_loss_enabled).grid(row=1, column=2, sticky=tk.W)
        self.stop_loss = tk.IntVar(value=self.settings.get('stop_loss', 50))
        tk.Entry(risk_frame, textvariable=self.stop_loss, width=10).grid(row=1, column=3)
        
        # Vice Versa
        self.vice_versa = tk.IntVar(value=self.settings.get('vice_versa', 0))
        tk.Checkbutton(risk_frame, text="Vice Versa (Invert Signals)", variable=self.vice_versa).grid(row=2, column=0, columnspan=2, sticky=tk.W)
        
        # Max trades per hour
        tk.Label(risk_frame, text="Max Trades/Hour:").grid(row=2, column=2, sticky=tk.W)
        self.max_trades = tk.IntVar(value=self.settings.get('max_trades_per_hour', 30))
        tk.Entry(risk_frame, textvariable=self.max_trades, width=10).grid(row=2, column=3)
        
        # === LOG SECTION ===
        log_frame = tk.LabelFrame(main_frame, text="Activity Log", padx=10, pady=5)
        log_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Log text with scrollbar
        self.log_text = tk.Text(log_frame, height=10, state=DISABLED, wrap=tk.WORD)
        scrollbar = tk.Scrollbar(log_frame, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=Y)
        
        # === BUTTON SECTION ===
        button_frame = tk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)
        
        self.start_button = tk.Button(
            button_frame, 
            text="🚀 Start Trading", 
            command=self._start_bot,
            bg='#4CAF50',
            fg='white',
            font=('Arial', 12, 'bold'),
            width=20
        )
        self.start_button.pack(side=tk.LEFT, padx=5)
        
        self.stop_button = tk.Button(
            button_frame,
            text="🛑 Stop",
            command=self._stop_bot,
            bg='#f44336',
            fg='white',
            font=('Arial', 12, 'bold'),
            width=15,
            state=DISABLED
        )
        self.stop_button.pack(side=tk.LEFT, padx=5)
        
        # Status label
        self.status_var = tk.StringVar(value="Status: Ready")
        self.status_label = tk.Label(button_frame, textvariable=self.status_var, font=('Arial', 10))
        self.status_label.pack(side=tk.RIGHT, padx=10)
    
    def _setup_logging(self):
        """Setup logging to display in GUI"""
        class GUILogHandler(logging.Handler):
            def __init__(self, text_widget):
                super().__init__()
                self.text_widget = text_widget
            
            def emit(self, record):
                msg = self.format(record)
                def append():
                    self.text_widget.configure(state=tk.NORMAL)
                    self.text_widget.insert(END, msg + '\n')
                    self.text_widget.see(END)
                    self.text_widget.configure(state=tk.DISABLED)
                self.text_widget.after(0, append)
        
        # Setup logging
        log_handler = GUILogHandler(self.log_text)
        log_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s', datefmt='%H:%M:%S'))
        
        # Add handler to root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)
        root_logger.addHandler(log_handler)
    
    def _get_config(self) -> dict:
        """Get configuration from GUI fields"""
        # Parse martingale list
        try:
            mart_list = [int(x.strip()) for x in self.martingale_list.get().split(',')]
        except:
            mart_list = [1, 3, 7, 15, 32, 67]
        
        return {
            'account_type': self.account_type.get(),
            'trade_amount': self.trade_amount.get(),
            'min_payout': self.min_payout.get(),
            'use_ma_crossover': bool(self.use_ma.get()),
            'use_rsi': bool(self.use_rsi.get()),
            'use_enhanced_divergence': bool(self.use_enhanced.get()),
            'use_professional_scalping': bool(self.use_scalping.get()),
            'fast_ma': self.fast_ma.get(),
            'slow_ma': self.slow_ma.get(),
            'rsi_period': self.rsi_period.get(),
            'min_confidence': self.min_confidence.get(),
            'min_strategy_votes': self.min_votes.get(),
            'martingale_enabled': bool(self.martingale_enabled.get()),
            'martingale_list': mart_list,
            'martingale_list_str': self.martingale_list.get(),
            'take_profit_enabled': bool(self.take_profit_enabled.get()),
            'take_profit': self.take_profit.get(),
            'stop_loss_enabled': bool(self.stop_loss_enabled.get()),
            'stop_loss': self.stop_loss.get(),
            'vice_versa': bool(self.vice_versa.get()),
            'max_trades_per_hour': self.max_trades.get(),
            'headless': False
        }
    
    def _validate_config(self) -> bool:
        """Validate configuration before starting"""
        errors = []
        
        if self.fast_ma.get() >= self.slow_ma.get():
            errors.append("Fast MA must be less than Slow MA")
        
        if self.min_payout.get() < 50 or self.min_payout.get() > 100:
            errors.append("Min Payout must be between 50-100%")
        
        if self.trade_amount.get() < 1:
            errors.append("Trade amount must be at least $1")
        
        if self.min_confidence.get() < 50 or self.min_confidence.get() > 100:
            errors.append("Min Confidence must be between 50-100%")
        
        if errors:
            messagebox.showerror("Configuration Error", "\n".join(errors))
            return False
        
        return True
    
    def _start_bot(self):
        """Start the trading bot"""
        if not self._validate_config():
            return
        
        config = self._get_config()
        self.save_settings(config)
        
        self.log_message("🚀 Starting bot...")
        self.status_var.set("Status: Starting...")
        
        # Disable start button, enable stop
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        
        # Create and start bot in separate thread
        self.bot = PocketOptionTradingBot(config)
        self.is_running = True
        
        def run_bot():
            try:
                self.bot.run()
            except Exception as e:
                self.log_message(f"❌ Bot error: {e}")
            finally:
                self.window.after(0, self._on_bot_stopped)
        
        self.bot_thread = threading.Thread(target=run_bot, daemon=True)
        self.bot_thread.start()
        
        self.status_var.set("Status: Running")
    
    def _stop_bot(self):
        """Stop the trading bot"""
        self.log_message("🛑 Stopping bot...")
        self.status_var.set("Status: Stopping...")
        
        if self.bot:
            self.bot.stop()
        
        self.is_running = False
    
    def _on_bot_stopped(self):
        """Called when bot stops"""
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.status_var.set("Status: Stopped")
        self.log_message("🛑 Bot stopped")
    
    def log_message(self, message: str):
        """Add message to log"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.insert(END, f"{timestamp} - {message}\n")
        self.log_text.see(END)
        self.log_text.configure(state=tk.DISABLED)
    
    def save_settings(self, settings: dict = None):
        """Save settings to file"""
        if settings is None:
            settings = self._get_config()
        
        self.settings = settings
        
        try:
            with open(SETTINGS_FILE, 'w') as f:
                json.dump(settings, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save settings: {e}")
    
    def load_settings(self):
        """Load settings from file"""
        try:
            if os.path.exists(SETTINGS_FILE):
                with open(SETTINGS_FILE, 'r') as f:
                    self.settings = json.load(f)
        except Exception as e:
            logger.error(f"Failed to load settings: {e}")
            self.settings = {}
    
    def _on_close(self):
        """Handle window close"""
        if self.is_running:
            if messagebox.askokcancel("Quit", "Bot is running. Are you sure you want to quit?"):
                self._stop_bot()
                self.window.after(1000, self.window.destroy)
        else:
            self.save_settings(self._get_config())
            self.window.destroy()
    
    def run(self):
        """Start the GUI"""
        self.log_message("👋 Welcome to GPT Signal Bot Desktop Client")
        self.log_message("📝 Configure settings and click 'Start Trading'")
        self.log_message("⚠️ Make sure you're logged into Pocket Option in Chrome")
        self.window.mainloop()


def main():
    """Entry point"""
    app = TradingBotGUI()
    app.run()


if __name__ == '__main__':
    main()
