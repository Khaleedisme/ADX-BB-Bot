"""
ADX Volatility Waves Trading Bot v2.1
Converted from Pine Script to Python

Features:
- Paper Trading Engine with realistic fee calculation
- ATR-based Risk Management with Partial TP and Trailing Stop
- Async Multi-Symbol Support (15 cryptocurrencies)
- Telegram Integration (v20+ async) with chart visualization
- Anti-Repaint Signal Logic

Fee Calculation:
- Entry Fee = (Margin × Leverage) × 0.05% = ($5 × 10) × 0.0005 = $0.025
- Exit Fee = (Margin × Leverage) × 0.05% = ($5 × 10) × 0.0005 = $0.025
- Both fees are deducted from balance on trade execution

Timeframe Configuration:
- Change TIMEFRAME variable below to '1m', '5m', '15m', etc.
- Default: '5m'
"""

import asyncio
import ccxt.async_support as ccxt
import pandas as pd
import pandas_ta as ta
import numpy as np
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
import json
import os
from dataclasses import dataclass, asdict
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import mplfinance as mpf
import matplotlib.pyplot as plt
from io import BytesIO

# ============================================================================
# 📊 CONFIGURATION
# ============================================================================

# Timeframe - Change this to '1m', '5m', '15m', etc.
TIMEFRAME = '1m'

# Telegram Configuration
TELEGRAM_BOT_TOKEN = "8597445147:AAGvZZLNigyCEpLol5CvHvQAxc9PVy6JrLM"
TELEGRAM_USER_ID = 368629145

# Target Symbols - Updated list
SYMBOLS = [
    'BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'XRP/USDT',
    'ADA/USDT', 'DOGE/USDT', 'AVAX/USDT', 'LINK/USDT', 'DOT/USDT',
    'LTC/USDT', 'TRX/USDT', 'ATOM/USDT', 'UNI/USDT', 'TAO/USDT',
    'AAVE/USDT', 'ENA/USDT', 'BCH/USDT', 'HYPE/USDT', 'SUI/USDT'
]

# Paper Trading Parameters
INITIAL_BALANCE = 100.0  # $100 USDT
MARGIN_PER_TRADE = 5.0   # $5 margin per trade
LEVERAGE = 10            # 10x leverage
FEE_RATE = 0.0005        # 0.05% taker fee

# Indicator Parameters
BB_LENGTH = 15
BB_MULT = 2
ADX_LENGTH = 14
ADX_SMOOTH = 14
ADX_STRONG = 25
ADX_WEAK = 20
ADX_INFLUENCE = 0.8
ZONE_OFFSET = 1.0
ZONE_EXPANSION = 1.0
SMOOTH_LENGTH = 50
SIGNAL_COOLDOWN = 20  # bars

# Risk Management - Adjusted for 1m scalping with 10x leverage
USE_ATR_FOR_TPSL = False  # Using percentage for precise control
TP_PERCENT = 0.1      # 0.1% = 1% with 10x leverage
SL_PERCENT = 0.08     # 0.08% = 0.8% with 10x leverage
ATR_LENGTH = 14
ATR_TP_MULT = 2.0
ATR_SL_MULT = 1.0
PARTIAL_TP_ATR_MULT = 1.5  # First partial TP at 1.5x ATR
FINAL_TP_ATR_MULT = 3.0    # Final TP at 3x ATR

# Anti-Repaint Mode
USE_ANTI_REPAINT = True

# Check Interval (seconds) - Adjust based on timeframe
CHECK_INTERVAL = 4  # 4 seconds for 1m, use 10 for 5m, 30 for 15m

# ============================================================================
# 📦 DATA CLASSES
# ============================================================================

@dataclass
class Position:
    """Represents an open trading position"""
    symbol: str
    side: str  # 'long' or 'short'
    entry_price: float
    entry_time: datetime
    size: float  # Position size in USDT (margin * leverage)
    margin: float
    leverage: int
    stop_loss: float
    take_profit_1: float  # Partial TP (50% at 1.5x ATR)
    take_profit_2: float  # Final TP (50% at 3x ATR)
    partial_tp_hit: bool = False
    trailing_stop: Optional[float] = None
    highest_price: Optional[float] = None  # For trailing stop
    atr_value: float = 0.0
    
    def to_dict(self):
        return asdict(self)

@dataclass
class Trade:
    """Represents a completed trade"""
    symbol: str
    side: str
    entry_price: float
    exit_price: float
    entry_time: datetime
    exit_time: datetime
    pnl: float
    pnl_percent: float
    exit_reason: str  # 'tp1', 'tp2', 'sl', 'trailing_sl'
    fees_paid: float
    
    def to_dict(self):
        d = asdict(self)
        d['entry_time'] = self.entry_time.isoformat()
        d['exit_time'] = self.exit_time.isoformat()
        return d

# ============================================================================
# 🏦 PAPER TRADING ENGINE
# ============================================================================

class PaperTradingEngine:
    """Manages paper trading positions and balance"""
    
    def __init__(self):
        self.balance = INITIAL_BALANCE
        self.positions: Dict[str, Position] = {}
        self.trade_history: List[Trade] = []
        self.total_fees_paid = 0.0
        self.load_state()
    
    def calculate_fee(self, margin: float, leverage: int) -> float:
        """Calculate trading fee based on leveraged position size"""
        position_size = margin * leverage
        fee = position_size * FEE_RATE
        return fee
    
    def open_position(self, symbol: str, side: str, entry_price: float, 
                     sl: float, tp1: float, tp2: float, atr_value: float) -> bool:
        """Open a new position"""
        if symbol in self.positions:
            print(f"⚠️  Position already open for {symbol}")
            return False
        
        # Calculate entry fee
        entry_fee = self.calculate_fee(MARGIN_PER_TRADE, LEVERAGE)
        
        if self.balance < (MARGIN_PER_TRADE + entry_fee):
            print(f"⚠️  Insufficient balance for {symbol}")
            return False
        
        # Deduct margin and entry fee
        self.balance -= (MARGIN_PER_TRADE + entry_fee)
        self.total_fees_paid += entry_fee
        
        position = Position(
            symbol=symbol,
            side=side,
            entry_price=entry_price,
            entry_time=datetime.now(timezone.utc),
            size=MARGIN_PER_TRADE * LEVERAGE,
            margin=MARGIN_PER_TRADE,
            leverage=LEVERAGE,
            stop_loss=sl,
            take_profit_1=tp1,
            take_profit_2=tp2,
            atr_value=atr_value
        )
        
        self.positions[symbol] = position
        self.save_state()
        
        print(f"✅ Opened {side.upper()} position for {symbol} @ {entry_price:.4f}")
        print(f"   Entry Fee: ${entry_fee:.4f} | Balance: ${self.balance:.2f}")
        
        return True
    
    def close_position(self, symbol: str, exit_price: float, exit_reason: str, 
                      partial: bool = False) -> Optional[Trade]:
        """Close a position (fully or partially)"""
        if symbol not in self.positions:
            return None
        
        position = self.positions[symbol]
        
        # Calculate size to close (50% if partial, 100% otherwise)
        close_percentage = 0.5 if partial else 1.0
        close_size = position.size * close_percentage
        close_margin = position.margin * close_percentage
        
        # Calculate exit fee
        exit_fee = self.calculate_fee(close_margin, LEVERAGE)
        
        # Calculate PnL using CORRECT futures formula
        # PNL_USD = position_notional * (price_change_percent / 100)
        # where position_notional = margin * leverage
        
        # Calculate price change percentage
        if position.side == 'long':
            price_change_percent = ((exit_price - position.entry_price) / position.entry_price) * 100
        else:  # short
            price_change_percent = ((position.entry_price - exit_price) / position.entry_price) * 100
        
        # Calculate notional value (margin * leverage)
        position_notional = close_margin * LEVERAGE
        
        # Calculate PnL in USD (this is the CORRECT formula for futures)
        pnl_amount = position_notional * (price_change_percent / 100)
        
        # PnL percentage for display (leveraged return)
        pnl_percent = price_change_percent
        
        # Deduct exit fee and add PnL to balance
        self.balance += close_margin + pnl_amount - exit_fee
        self.total_fees_paid += exit_fee
        
        # Create trade record
        trade = Trade(
            symbol=symbol,
            side=position.side,
            entry_price=position.entry_price,
            exit_price=exit_price,
            entry_time=position.entry_time,
            exit_time=datetime.now(timezone.utc),
            pnl=pnl_amount,
            pnl_percent=pnl_percent * LEVERAGE,
            exit_reason=exit_reason,
            fees_paid=exit_fee if not partial else entry_fee + exit_fee
        )
        
        self.trade_history.append(trade)
        
        if partial:
            # Reduce position size by 50%
            position.size *= 0.5
            position.margin *= 0.5
            position.partial_tp_hit = True
            # Move SL to breakeven
            position.stop_loss = position.entry_price
            # Activate trailing stop
            position.highest_price = exit_price if position.side == 'long' else position.entry_price
            print(f"📊 Partial close (50%) {symbol} @ {exit_price:.4f} | PnL: ${pnl_amount:.2f} ({pnl_percent*LEVERAGE:.2f}%)")
            print(f"   SL moved to breakeven. Trailing stop activated.")
        else:
            # Full close
            del self.positions[symbol]
            print(f"🔒 Closed {symbol} @ {exit_price:.4f} | Reason: {exit_reason}")
            print(f"   PnL: ${pnl_amount:.2f} ({pnl_percent*LEVERAGE:.2f}%) | Exit Fee: ${exit_fee:.4f}")
        
        print(f"   Balance: ${self.balance:.2f}")
        self.save_state()
        
        return trade
    
    def update_trailing_stop(self, symbol: str, current_price: float):
        """Update trailing stop for a position"""
        if symbol not in self.positions:
            return
        
        position = self.positions[symbol]
        
        if not position.partial_tp_hit or position.highest_price is None:
            return
        
        # Update highest price
        if position.side == 'long':
            if current_price > position.highest_price:
                position.highest_price = current_price
                # Set trailing stop at highest_price - ATR
                position.trailing_stop = position.highest_price - position.atr_value
                print(f"📈 Trailing stop updated for {symbol}: {position.trailing_stop:.4f}")
        else:  # short
            if current_price < position.highest_price:
                position.highest_price = current_price
                # Set trailing stop at highest_price + ATR
                position.trailing_stop = position.highest_price + position.atr_value
                print(f"📉 Trailing stop updated for {symbol}: {position.trailing_stop:.4f}")
    
    def get_stats(self) -> Dict:
        """Get trading statistics"""
        total_trades = len(self.trade_history)
        if total_trades == 0:
            return {
                'balance': self.balance,
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'win_rate': 0.0,
                'total_pnl': 0.0,
                'total_fees': self.total_fees_paid,
                'open_positions': len(self.positions)
            }
        
        winning_trades = sum(1 for t in self.trade_history if t.pnl > 0)
        losing_trades = sum(1 for t in self.trade_history if t.pnl < 0)
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        total_pnl = sum(t.pnl for t in self.trade_history)
        
        return {
            'balance': self.balance,
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'win_rate': win_rate,
            'total_pnl': total_pnl,
            'total_fees': self.total_fees_paid,
            'open_positions': len(self.positions)
        }
    
    def save_state(self):
        """Save trading state to JSON"""
        state = {
            'balance': self.balance,
            'total_fees_paid': self.total_fees_paid,
            'positions': {k: v.to_dict() for k, v in self.positions.items()},
            'trade_history': [t.to_dict() for t in self.trade_history]
        }
        
        with open('trading_state.json', 'w') as f:
            json.dump(state, f, indent=2, default=str)
    
    def load_state(self):
        """Load trading state from JSON"""
        if not os.path.exists('trading_state.json'):
            return
        
        try:
            with open('trading_state.json', 'r') as f:
                state = json.load(f)
            
            self.balance = state.get('balance', INITIAL_BALANCE)
            self.total_fees_paid = state.get('total_fees_paid', 0.0)
            
            # Reconstruct positions (simplified - you may need to handle datetime parsing)
            # For now, starting fresh on each restart is safer
            print("ℹ️  Previous state loaded")
        except Exception as e:
            print(f"⚠️  Failed to load state: {e}")

# ============================================================================
# 📈 TECHNICAL INDICATOR ENGINE
# ============================================================================

class IndicatorEngine:
    """Calculate technical indicators matching Pine Script logic"""
    
    @staticmethod
    def calculate_adx_adjusted_bb(df: pd.DataFrame) -> pd.DataFrame:
        """Calculate ADX-adjusted Bollinger Bands and zones"""
        df = df.copy()
        
        # Calculate ADX and DI
        adx_df = df.ta.adx(length=ADX_LENGTH, lensig=ADX_SMOOTH)
        df['adx'] = adx_df[f'ADX_{ADX_LENGTH}']
        df['di_plus'] = adx_df[f'DMP_{ADX_LENGTH}']
        df['di_minus'] = adx_df[f'DMN_{ADX_LENGTH}']
        
        # Normalize ADX
        df['adx_normalized'] = df['adx'] / 100
        
        # Calculate standard BB
        bb_basis = df['close'].rolling(window=BB_LENGTH).mean()
        bb_dev = df['close'].rolling(window=BB_LENGTH).std()
        
        # ADX multiplier
        adx_multiplier = 1 + (df['adx_normalized'] * ADX_INFLUENCE)
        bb_dev_adjusted = BB_MULT * bb_dev * adx_multiplier
        
        df['bb_upper'] = bb_basis + bb_dev_adjusted
        df['bb_lower'] = bb_basis - bb_dev_adjusted
        df['bb_basis'] = bb_basis
        
        # Smoothed values for zones
        df['bb_upper_smooth'] = df['bb_upper'].rolling(window=SMOOTH_LENGTH).mean()
        df['bb_lower_smooth'] = df['bb_lower'].rolling(window=SMOOTH_LENGTH).mean()
        df['bb_range_smooth'] = df['bb_upper_smooth'] - df['bb_lower_smooth']
        
        # Calculate zones
        offset_distance = df['bb_range_smooth'] * ZONE_OFFSET
        
        # Top Zone (Sell/Overbought)
        df['top_zone_bottom'] = df['bb_upper_smooth'] + offset_distance
        df['top_zone_top'] = df['top_zone_bottom'] + (df['bb_range_smooth'] * ZONE_EXPANSION)
        
        # Bottom Zone (Buy/Oversold)
        df['bottom_zone_top'] = df['bb_lower_smooth'] - offset_distance
        df['bottom_zone_bottom'] = df['bottom_zone_top'] - (df['bb_range_smooth'] * ZONE_EXPANSION)
        
        # Calculate ATR
        df['atr'] = df.ta.atr(length=ATR_LENGTH)
        
        return df
    
    @staticmethod
    def generate_signals(df: pd.DataFrame, last_buy_bar: int, last_sell_bar: int, 
                        current_bar: int) -> Tuple[bool, bool]:
        """Generate buy/sell signals with anti-repaint logic"""
        if len(df) < 3:
            return False, False
        
        # Use previous bar's data for anti-repaint
        if USE_ANTI_REPAINT:
            src_close = df['close'].iloc[-2]
            top_zone_bottom = df['top_zone_bottom'].iloc[-2]
            bottom_zone_top = df['bottom_zone_top'].iloc[-2]
            prev_close = df['close'].iloc[-3]
            prev_top_zone_bottom = df['top_zone_bottom'].iloc[-3]
            prev_bottom_zone_top = df['bottom_zone_top'].iloc[-3]
        else:
            src_close = df['close'].iloc[-1]
            top_zone_bottom = df['top_zone_bottom'].iloc[-1]
            bottom_zone_top = df['bottom_zone_top'].iloc[-1]
            prev_close = df['close'].iloc[-2]
            prev_top_zone_bottom = df['top_zone_bottom'].iloc[-2]
            prev_bottom_zone_top = df['bottom_zone_top'].iloc[-2]
        
        # Zone detection
        price_in_top_zone = src_close > top_zone_bottom
        price_in_bottom_zone = src_close < bottom_zone_top
        prev_in_top_zone = prev_close > prev_top_zone_bottom
        prev_in_bottom_zone = prev_close < prev_bottom_zone_top
        
        # Entry signals (entering zone)
        raw_buy_signal = price_in_bottom_zone and not prev_in_bottom_zone
        raw_sell_signal = price_in_top_zone and not prev_in_top_zone
        
        # Cooldown check
        buy_cooldown_ok = (current_bar - last_buy_bar) >= SIGNAL_COOLDOWN
        sell_cooldown_ok = (current_bar - last_sell_bar) >= SIGNAL_COOLDOWN
        
        # Final signals
        buy_signal = raw_buy_signal and buy_cooldown_ok
        sell_signal = raw_sell_signal and sell_cooldown_ok
        
        return buy_signal, sell_signal
    
    @staticmethod
    def calculate_tpsl(entry_price: float, side: str, atr_value: float) -> Tuple[float, float, float]:
        """Calculate TP and SL levels"""
        if USE_ATR_FOR_TPSL:
            # ATR-based TP/SL
            tp_distance_1 = atr_value * PARTIAL_TP_ATR_MULT
            tp_distance_2 = atr_value * FINAL_TP_ATR_MULT
            sl_distance = atr_value * ATR_SL_MULT
        else:
            # Percentage-based TP/SL for scalping
            tp_distance_1 = entry_price * (TP_PERCENT / 100)       # 0.1%
            tp_distance_2 = entry_price * (TP_PERCENT * 1.5 / 100) # 0.15%
            sl_distance = entry_price * (SL_PERCENT / 100)          # 0.08%
        
        if side == 'long':
            tp1 = entry_price + tp_distance_1
            tp2 = entry_price + tp_distance_2
            sl = entry_price - sl_distance
        else:  # short
            tp1 = entry_price - tp_distance_1
            tp2 = entry_price - tp_distance_2
            sl = entry_price + sl_distance
        
        return sl, tp1, tp2

# ============================================================================
# 📊 CHART GENERATOR
# ============================================================================

class ChartGenerator:
    """Generate mplfinance charts with indicators"""
    
    @staticmethod
    def create_chart(df: pd.DataFrame, symbol: str, timeframe: str, 
                    entry_price: Optional[float] = None,
                    tp1: Optional[float] = None,
                    tp2: Optional[float] = None,
                    sl: Optional[float] = None,
                    side: Optional[str] = None) -> BytesIO:
        """Create a TradingView-style chart with gradient-filled zones"""
        # Prepare data - take last 100 candles
        df_plot = df.tail(100).copy()
        
        # Ensure index is datetime
        if not isinstance(df_plot.index, pd.DatetimeIndex):
            df_plot.index = pd.to_datetime(df_plot.index)
        
        # Prepare OHLCV data
        ohlcv = df_plot[['open', 'high', 'low', 'close', 'volume']].copy()
        
        # Create figure and axes manually for more control
        from matplotlib import patheffects
        import matplotlib.patches as mpatches
        
        fig = plt.figure(figsize=(16, 10), facecolor='#0d1117')
        
        # Create custom gridspec for main chart and volume
        gs = fig.add_gridspec(2, 1, height_ratios=[4, 1], hspace=0.05)
        ax_main = fig.add_subplot(gs[0])
        ax_vol = fig.add_subplot(gs[1], sharex=ax_main)
        
        # Style main axis
        ax_main.set_facecolor('#131722')
        ax_main.grid(True, color='#1e222d', linestyle='--', linewidth=0.5, alpha=0.3)
        ax_main.spines['top'].set_visible(False)
        ax_main.spines['right'].set_visible(False)
        ax_main.spines['left'].set_color('#2a2e39')
        ax_main.spines['bottom'].set_color('#2a2e39')
        ax_main.tick_params(colors='#787b86', which='both')
        
        # Style volume axis
        ax_vol.set_facecolor('#131722')
        ax_vol.grid(True, color='#1e222d', linestyle='--', linewidth=0.5, alpha=0.3)
        ax_vol.spines['top'].set_visible(False)
        ax_vol.spines['right'].set_visible(False)
        ax_vol.spines['left'].set_color('#2a2e39')
        ax_vol.spines['bottom'].set_color('#2a2e39')
        ax_vol.tick_params(colors='#787b86', which='both')
        
        # Create x-axis values (numeric indices)
        x = np.arange(len(df_plot))
        
        # ========== GRADIENT ZONES (LIKE TRADINGVIEW) ==========
        if 'top_zone_bottom' in df_plot.columns and 'top_zone_top' in df_plot.columns:
            # Red gradient zone (top/sell)
            top_bottom = df_plot['top_zone_bottom'].values
            top_top = df_plot['top_zone_top'].values
            
            # Fill top zone with gradient effect (multiple fills with varying alpha)
            for i, alpha_val in enumerate(np.linspace(0.15, 0.4, 10)):
                y_interp = top_bottom + (top_top - top_bottom) * (i / 10)
                y_interp_next = top_bottom + (top_top - top_bottom) * ((i + 1) / 10)
                ax_main.fill_between(x, y_interp, y_interp_next, 
                                    color='#f23645', alpha=alpha_val, linewidth=0)
            
            # Zone boundary line
            ax_main.plot(x, top_bottom, color='#f23645', linewidth=2, alpha=0.8, linestyle='-')
        
        if 'bottom_zone_top' in df_plot.columns and 'bottom_zone_bottom' in df_plot.columns:
            # Green gradient zone (bottom/buy)
            bottom_top = df_plot['bottom_zone_top'].values
            bottom_bottom = df_plot['bottom_zone_bottom'].values
            
            # Fill bottom zone with gradient effect
            for i, alpha_val in enumerate(np.linspace(0.15, 0.4, 10)):
                y_interp = bottom_top - (bottom_top - bottom_bottom) * (i / 10)
                y_interp_next = bottom_top - (bottom_top - bottom_bottom) * ((i + 1) / 10)
                ax_main.fill_between(x, y_interp, y_interp_next, 
                                    color='#089981', alpha=alpha_val, linewidth=0)
            
            # Zone boundary line  
            ax_main.plot(x, bottom_top, color='#089981', linewidth=2, alpha=0.8, linestyle='-')
        
        # ========== BOLLINGER BANDS ==========
        if 'bb_upper' in df_plot.columns:
            ax_main.plot(x, df_plot['bb_upper'].values, color='#2962FF', 
                        linewidth=1.5, alpha=0.6, linestyle='--', label='BB Upper')
        if 'bb_lower' in df_plot.columns:
            ax_main.plot(x, df_plot['bb_lower'].values, color='#2962FF', 
                        linewidth=1.5, alpha=0.6, linestyle='--', label='BB Lower')
        if 'bb_basis' in df_plot.columns:
            ax_main.plot(x, df_plot['bb_basis'].values, color='#2962FF', 
                        linewidth=1.8, alpha=0.8, label='BB Basis')
        
        # ========== CANDLESTICKS ==========
        for i in range(len(df_plot)):
            o, h, l, c = (df_plot['open'].iloc[i], df_plot['high'].iloc[i], 
                         df_plot['low'].iloc[i], df_plot['close'].iloc[i])
            
            color = '#089981' if c >= o else '#f23645'  # TradingView colors
            
            # Wick
            ax_main.plot([x[i], x[i]], [l, h], color=color, linewidth=1, solid_capstyle='round')
            
            # Body
            body_height = abs(c - o)
            body_bottom = min(o, c)
            
            if body_height > 0:
                rect = mpatches.Rectangle((x[i] - 0.4, body_bottom), 0.8, body_height,
                                         facecolor=color, edgecolor=color, linewidth=0)
                ax_main.add_patch(rect)
            else:
                # Doji - draw thin line
                ax_main.plot([x[i] - 0.4, x[i] + 0.4], [c, c], color=color, linewidth=1.5)
        
        # ========== VOLUME BARS ==========
        for i in range(len(df_plot)):
            vol = df_plot['volume'].iloc[i]
            color = '#089981' if df_plot['close'].iloc[i] >= df_plot['open'].iloc[i] else '#f23645'
            ax_vol.bar(x[i], vol, width=0.8, color=color, alpha=0.5)
        
        # ========== TRADE LEVELS ==========
        if entry_price and axes is not None:
            # Entry line
            entry_color = '#089981' if side == 'long' else '#f23645'
            ax_main.axhline(entry_price, color=entry_color, linewidth=2.5, 
                          linestyle='-', alpha=0.9, 
                          path_effects=[patheffects.withStroke(linewidth=4, foreground='black', alpha=0.3)])
            
            # TP lines
            if tp1:
                ax_main.axhline(tp1, color='#00e676', linewidth=2, linestyle='--', alpha=0.8,
                              label=f'TP1 (50%): {tp1:.2f}')
            if tp2:
                ax_main.axhline(tp2, color='#76ff03', linewidth=2, linestyle='--', alpha=0.8,
                              label=f'TP2 (50%): {tp2:.2f}')
            
            # SL line
            if sl:
                ax_main.axhline(sl, color='#ff1744', linewidth=2, linestyle='--', alpha=0.8,
                              label=f'SL: {sl:.2f}')
            
            # Add text labels on the right side
            ax_right = ax_main.twinx()
            ax_right.set_ylim(ax_main.get_ylim())
            ax_right.set_yticks([])
            
            bbox_props = dict(boxstyle='round,pad=0.4', facecolor='#1e222d', edgecolor='none', alpha=0.9)
            
            ax_right.text(1.01, entry_price, f'  ► {entry_price:.2f}  ', 
                         transform=ax_main.get_yaxis_transform(),
                         color=entry_color, fontweight='bold', fontsize=10,
                         bbox=bbox_props, va='center')
        
        # ========== TITLE AND LABELS ==========
        title_text = f'{symbol} · {timeframe}'
        ax_main.text(0.01, 0.98, title_text, transform=ax_main.transAxes,
                    fontsize=18, fontweight='bold', color='#f0f0f0',
                    verticalalignment='top',
                    path_effects=[patheffects.withStroke(linewidth=3, foreground='#0d1117')])
        
        # Add ADX badge if available
        if 'adx' in df_plot.columns:
            adx_val = df_plot['adx'].iloc[-1]
            badge_color = '#089981' if adx_val > 25 else '#f0b90b' if adx_val > 20 else '#787b86'
            ax_main.text(0.01, 0.92, f'ADX: {adx_val:.1f}', transform=ax_main.transAxes,
                        fontsize=12, fontweight='bold', color=badge_color,
                        bbox=dict(boxstyle='round,pad=0.5', facecolor='#1e222d', alpha=0.8),
                        verticalalignment='top')
        
        # Legend
        handles, labels = ax_main.get_legend_handles_labels()
        if handles:
            ax_main.legend(loc='upper right', framealpha=0.9, facecolor='#1e222d', 
                          edgecolor='#2a2e39', labelcolor='#f0f0f0', fontsize=9)
        
        ax_main.set_ylabel('Price (USDT)', color='#787b86', fontsize=10)
        ax_vol.set_ylabel('Volume', color='#787b86', fontsize=10)
        ax_vol.set_xlabel('', color='#787b86', fontsize=10)
        
        # Remove x-axis labels to match TradingView
        plt.setp(ax_main.get_xticklabels(), visible=False)
        plt.setp(ax_vol.get_xticklabels(), visible=False)
        
        # Tight layout
        plt.tight_layout()
        
        # Save to BytesIO
        buf = BytesIO()
        fig.savefig(buf, format='png', dpi=150, bbox_inches='tight', 
                   facecolor='#0d1117', edgecolor='none')
        buf.seek(0)
        plt.close(fig)
        
        return buf

# ============================================================================
# 🤖 MAIN BOT
# ============================================================================

class TradingBot:
    """Main trading bot orchestrator"""
    
    def __init__(self):
        self.exchange = ccxt.binance({
            'enableRateLimit': True,
            'options': {'defaultType': 'future'}
        })
        self.engine = PaperTradingEngine()
        self.indicator_engine = IndicatorEngine()
        self.chart_generator = ChartGenerator()
        self.signal_bars: Dict[str, Dict[str, int]] = {}  # Track last signal bars per symbol
        self.current_bars: Dict[str, int] = {}  # Track current bar index per symbol
        self.telegram_app: Optional[Application] = None
        
        # Initialize signal tracking
        for symbol in SYMBOLS:
            self.signal_bars[symbol] = {'last_buy': -999, 'last_sell': -999}
            self.current_bars[symbol] = 0
    
    async def fetch_ohlcv(self, symbol: str, timeframe: str = TIMEFRAME, 
                         limit: int = 200) -> pd.DataFrame:
        """Fetch OHLCV data from exchange"""
        try:
            ohlcv = await self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            return df
        except Exception as e:
            print(f"❌ Error fetching {symbol}: {e}")
            return pd.DataFrame()
    
    async def process_symbol(self, symbol: str):
        """Process a single symbol for signals"""
        try:
            # Fetch data
            df = await self.fetch_ohlcv(symbol)
            
            if df.empty or len(df) < SMOOTH_LENGTH + 10:
                return
            
            # Calculate indicators
            df = self.indicator_engine.calculate_adx_adjusted_bb(df)
            
            # Drop NaN rows
            df = df.dropna()
            
            if len(df) < 3:
                return
            
            # Update bar count
            self.current_bars[symbol] += 1
            current_bar = self.current_bars[symbol]
            
            # Get current price
            current_price = df['close'].iloc[-1]
            current_high = df['high'].iloc[-1]
            current_low = df['low'].iloc[-1]
            
            # Check for existing position
            if symbol in self.engine.positions:
                position = self.engine.positions[symbol]
                
                # Update trailing stop
                self.engine.update_trailing_stop(symbol, current_price)
                
                # Check exit conditions
                exit_trade = None
                
                if position.side == 'long':
                    # Check TP2 (final)
                    if current_high >= position.take_profit_2:
                        exit_trade = self.engine.close_position(symbol, position.take_profit_2, 'tp2', partial=False)
                    # Check TP1 (partial)
                    elif not position.partial_tp_hit and current_high >= position.take_profit_1:
                        exit_trade = self.engine.close_position(symbol, position.take_profit_1, 'tp1', partial=True)
                    # Check trailing SL
                    elif position.trailing_stop and current_low <= position.trailing_stop:
                        exit_trade = self.engine.close_position(symbol, position.trailing_stop, 'trailing_sl', partial=False)
                    # Check regular SL
                    elif current_low <= position.stop_loss:
                        exit_trade = self.engine.close_position(symbol, position.stop_loss, 'sl', partial=False)
                
                else:  # short
                    # Check TP2 (final)
                    if current_low <= position.take_profit_2:
                        exit_trade = self.engine.close_position(symbol, position.take_profit_2, 'tp2', partial=False)
                    # Check TP1 (partial)
                    elif not position.partial_tp_hit and current_low <= position.take_profit_1:
                        exit_trade = self.engine.close_position(symbol, position.take_profit_1, 'tp1', partial=True)
                    # Check trailing SL
                    elif position.trailing_stop and current_high >= position.trailing_stop:
                        exit_trade = self.engine.close_position(symbol, position.trailing_stop, 'trailing_sl', partial=False)
                    # Check regular SL
                    elif current_high >= position.stop_loss:
                        exit_trade = self.engine.close_position(symbol, position.stop_loss, 'sl', partial=False)
                
                # Send Telegram notification for exit
                if exit_trade and self.telegram_app:
                    await self.send_exit_notification(exit_trade)
                
                return
            
            # Generate signals
            buy_signal, sell_signal = self.indicator_engine.generate_signals(
                df,
                self.signal_bars[symbol]['last_buy'],
                self.signal_bars[symbol]['last_sell'],
                current_bar
            )
            
            # Get entry price and ATR for TP/SL calculation
            entry_price = df['close'].iloc[-2] if USE_ANTI_REPAINT else df['close'].iloc[-1]
            atr_value = df['atr'].iloc[-1]
            
            # Process buy signal
            if buy_signal:
                sl, tp1, tp2 = self.indicator_engine.calculate_tpsl(entry_price, 'long', atr_value)
                
                if self.engine.open_position(symbol, 'long', entry_price, sl, tp1, tp2, atr_value):
                    self.signal_bars[symbol]['last_buy'] = current_bar
                    
                    # Send Telegram notification with chart
                    if self.telegram_app:
                        await self.send_entry_notification(symbol, 'long', entry_price, sl, tp1, tp2, df)
            
            # Process sell signal
            elif sell_signal:
                sl, tp1, tp2 = self.indicator_engine.calculate_tpsl(entry_price, 'short', atr_value)
                
                if self.engine.open_position(symbol, 'short', entry_price, sl, tp1, tp2, atr_value):
                    self.signal_bars[symbol]['last_sell'] = current_bar
                    
                    # Send Telegram notification with chart
                    if self.telegram_app:
                        await self.send_entry_notification(symbol, 'short', entry_price, sl, tp1, tp2, df)
            
            # Print status
            adx = df['adx'].iloc[-1]
            print(f"[{datetime.now().strftime('%H:%M:%S')}] {symbol:12} | Price: {current_price:10.4f} | ADX: {adx:5.1f} | Balance: ${self.engine.balance:.2f}")
        
        except Exception as e:
            print(f"❌ Error processing {symbol}: {e}")
    
    async def send_entry_notification(self, symbol: str, side: str, entry: float, 
                                     sl: float, tp1: float, tp2: float, df: pd.DataFrame):
        """Send Telegram notification for trade entry with chart"""
        try:
            emoji = "🟢" if side == 'long' else "🔴"
            message = (
                f"{emoji} <b>{side.upper()} Signal: {symbol}</b>\n\n"
                f"📍 Entry: {entry:.4f}\n"
                f"🎯 TP1 (50%): {tp1:.4f}\n"
                f"🎯 TP2 (50%): {tp2:.4f}\n"
                f"🛡 SL: {sl:.4f}\n"
                f"💰 Balance: ${self.engine.balance:.2f}\n"
                f"⏰ {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC"
            )
            
            await self.telegram_app.bot.send_message(
                chat_id=TELEGRAM_USER_ID,
                text=message,
                parse_mode='HTML'
            )
            
            # Generate and send chart
            chart_buf = self.chart_generator.create_chart(df, symbol, TIMEFRAME, entry, tp1, tp2, sl, side)
            await self.telegram_app.bot.send_photo(
                chat_id=TELEGRAM_USER_ID,
                photo=chart_buf,
                caption=f"📊 {symbol} - {side.upper()} Entry Chart"
            )
        except Exception as e:
            print(f"❌ Failed to send entry notification: {e}")
    
    async def send_exit_notification(self, trade: Trade):
        """Send Telegram notification for trade exit"""
        try:
            emoji = "✅" if trade.pnl > 0 else "❌"
            message = (
                f"{emoji} <b>Trade Closed: {trade.symbol}</b>\n\n"
                f"📊 Side: {trade.side.upper()}\n"
                f"🚪 Exit Reason: {trade.exit_reason.upper()}\n"
                f"📈 Entry: {trade.entry_price:.4f}\n"
                f"📉 Exit: {trade.exit_price:.4f}\n"
                f"💵 PnL: ${trade.pnl:.2f} ({trade.pnl_percent:.2f}%)\n"
                f"💰 Balance: ${self.engine.balance:.2f}\n"
                f"⏰ {trade.exit_time.strftime('%Y-%m-%d %H:%M:%S')} UTC"
            )
            
            await self.telegram_app.bot.send_message(
                chat_id=TELEGRAM_USER_ID,
                text=message,
                parse_mode='HTML'
            )
        except Exception as e:
            print(f"❌ Failed to send exit notification: {e}")
    
    async def send_startup_notification(self):
        """Send Telegram notification when bot starts"""
        try:
            message = (
                f"🚀 <b>Bot Started</b>\n\n"
                f"📊 Timeframe: {TIMEFRAME}\n"
                f"💰 Balance: ${self.engine.balance:.2f}\n"
                f"🎯 Symbols: {len(SYMBOLS)}\n"
                f"🔒 Anti-Repaint: {'ACTIVE' if USE_ANTI_REPAINT else 'INACTIVE'}\n"
                f"⏰ {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC"
            )
            
            await self.telegram_app.bot.send_message(
                chat_id=TELEGRAM_USER_ID,
                text=message,
                parse_mode='HTML'
            )
        except Exception as e:
            print(f"❌ Failed to send startup notification: {e}")
    
    async def send_shutdown_notification(self):
        """Send Telegram notification when bot stops"""
        try:
            stats = self.engine.get_stats()
            message = (
                f"🛑 <b>Bot Stopped</b>\n\n"
                f"📊 Final Stats:\n"
                f"💰 Balance: ${stats['balance']:.2f}\n"
                f"📈 Total Trades: {stats['total_trades']}\n"
                f"✅ Wins: {stats['winning_trades']}\n"
                f"❌ Losses: {stats['losing_trades']}\n"
                f"📊 Win Rate: {stats['win_rate']:.1f}%\n"
                f"💵 Total PnL: ${stats['total_pnl']:.2f}\n"
                f"⏰ {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC"
            )
            
            await self.telegram_app.bot.send_message(
                chat_id=TELEGRAM_USER_ID,
                text=message,
                parse_mode='HTML'
            )
        except Exception as e:
            print(f"❌ Failed to send shutdown notification: {e}")
    
    async def run_analysis_loop(self):
        """Main analysis loop - processes all symbols concurrently"""
        print(f"🚀 Starting ADX Volatility Waves Bot")
        print(f"📊 Timeframe: {TIMEFRAME}")
        print(f"💰 Initial Balance: ${INITIAL_BALANCE}")
        print(f"🎯 Symbols: {len(SYMBOLS)}")
        print(f"🔒 Anti-Repaint: {'ACTIVE' if USE_ANTI_REPAINT else 'INACTIVE'}")
        print(f"⚙️  ATR-based TP/SL: {'ACTIVE' if USE_ATR_FOR_TPSL else 'INACTIVE'}\n")
        
        # Send startup notification
        if self.telegram_app:
            await self.send_startup_notification()
        
        try:
            while True:
                try:
                    # Process all symbols concurrently
                    tasks = [self.process_symbol(symbol) for symbol in SYMBOLS]
                    await asyncio.gather(*tasks, return_exceptions=True)
                    
                    # Print separator
                    print("-" * 100)
                    
                    # Wait before next iteration
                    await asyncio.sleep(CHECK_INTERVAL)
                
                except KeyboardInterrupt:
                    print("\n🛑 Shutting down bot...")
                    break
                except Exception as e:
                    print(f"❌ Error in main loop: {e}")
                    await asyncio.sleep(CHECK_INTERVAL)
        finally:
            # Send shutdown notification
            if self.telegram_app:
                await self.send_shutdown_notification()
            
            await self.exchange.close()
    
    async def start_bot(self):
        """Start bot with Telegram integration"""
        # Initialize Telegram bot
        self.telegram_app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
        
        # Add command handlers
        self.telegram_app.add_handler(CommandHandler("status", self.cmd_status))
        self.telegram_app.add_handler(CommandHandler("v", self.cmd_chart))
        
        # Start Telegram bot
        await self.telegram_app.initialize()
        await self.telegram_app.start()
        
        # Start polling in background
        asyncio.create_task(self.telegram_app.updater.start_polling())
        
        # Run analysis loop
        await self.run_analysis_loop()
        
        # Cleanup
        await self.telegram_app.stop()
    
    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command"""
        stats = self.engine.get_stats()
        
        message = (
            f"📊 <b>Trading Bot Status</b>\n\n"
            f"💰 Balance: ${stats['balance']:.2f}\n"
            f"📈 Total Trades: {stats['total_trades']}\n"
            f"✅ Wins: {stats['winning_trades']}\n"
            f"❌ Losses: {stats['losing_trades']}\n"
            f"📊 Win Rate: {stats['win_rate']:.1f}%\n"
            f"💵 Total PnL: ${stats['total_pnl']:.2f}\n"
            f"💸 Total Fees: ${stats['total_fees']:.2f}\n"
            f"🔓 Open Positions: {stats['open_positions']}\n\n"
        )
        
        # Add open positions details
        if self.engine.positions:
            message += "<b>Open Positions:</b>\n"
            for symbol, pos in self.engine.positions.items():
                current_price = 0  # You'd fetch this from exchange
                message += f"• {symbol}: {pos.side.upper()} @ {pos.entry_price:.4f}\n"
        
        await update.message.reply_text(message, parse_mode='HTML')
    
    async def cmd_chart(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /v [symbol] [timeframe] command"""
        try:
            args = context.args
            
            if len(args) < 1:
                await update.message.reply_text("Usage: /v <symbol> [timeframe]\nExample: /v BTC 5")
                return
            
            # Parse arguments
            symbol_short = args[0].upper()
            symbol = f"{symbol_short}/USDT"
            timeframe = f"{args[1]}m" if len(args) > 1 else TIMEFRAME
            
            # Fetch data
            df = await self.fetch_ohlcv(symbol, timeframe, limit=100)
            
            if df.empty:
                await update.message.reply_text(f"❌ No data available for {symbol}")
                return
            
            # Calculate indicators
            df = self.indicator_engine.calculate_adx_adjusted_bb(df)
            df = df.dropna()
            
            # Generate chart
            chart_buf = self.chart_generator.create_chart(df, symbol, timeframe)
            
            # Send chart
            await update.message.reply_photo(
                photo=chart_buf,
                caption=f"📊 {symbol} - {timeframe}"
            )
        
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {e}")

# ============================================================================
# 🚀 MAIN ENTRY POINT
# ============================================================================

# ============================================================================
# 🚀 MAIN ENTRY POINT with FLASK
# ============================================================================

import threading
import os
from flask import Flask

# Flask app for Render health checks
app = Flask(__name__)

@app.route("/")
def health():
    return "OK", 200

async def main():
    """Main entry point"""
    bot = TradingBot()
    await bot.start_bot()

def run_bot_thread():
    """Wrapper to run async bot in a separate thread"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        print("\n✅ Bot stopped by user")
    finally:
        loop.close()

if __name__ == "__main__":
    # Start bot in background thread
    bot_thread = threading.Thread(target=run_bot_thread, daemon=True)
    bot_thread.start()
    
    # Start Flask server (blocks main thread, satisfying Render)
    port = int(os.environ.get("PORT", 10000))
    print(f"🌍 Starting Flask server on port {port}...")
    app.run(host="0.0.0.0", port=port)
