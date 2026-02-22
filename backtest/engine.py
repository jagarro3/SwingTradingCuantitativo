"""
Motor de backtesting para la estrategia RSI(2) Trend Pullback.

Simulación barra a barra (daily) con:
  - Position sizing basado en ATR y % de riesgo por operación
  - Máximo N posiciones abiertas simultáneamente
  - Stop-loss fijo: entrada - ATR * ATR_STOP_MULT
  - Trailing stop: max_close - ATR * ATR_TRAIL_MULT (se activa tras ganancia >= ATR_TRAIL_TRIGGER * ATR)
  - Time stop: cerrar tras MAX_HOLD_DAYS barras sin que salte ningún stop
"""

from dataclasses import dataclass, field
from typing import Optional
import pandas as pd
from config import (
    RISK_PER_TRADE, MAX_POSITIONS,
    ATR_STOP_MULT, ATR_TRAIL_MULT, ATR_TRAIL_TRIGGER,
    MAX_HOLD_DAYS,
)


@dataclass
class Trade:
    ticker: str
    entry_date: pd.Timestamp
    entry_price: float
    shares: float
    stop_loss: float
    trailing_stop: float
    highest_close: float
    bars_held: int = 0
    exit_date: Optional[pd.Timestamp] = None
    exit_price: Optional[float] = None
    exit_reason: Optional[str] = None

    @property
    def pnl(self) -> float:
        if self.exit_price is None:
            return 0.0
        return (self.exit_price - self.entry_price) * self.shares

    @property
    def pnl_pct(self) -> float:
        if self.exit_price is None:
            return 0.0
        return (self.exit_price - self.entry_price) / self.entry_price


@dataclass
class BacktestResult:
    trades: list[Trade] = field(default_factory=list)
    equity_curve: pd.Series = field(default_factory=pd.Series)
    initial_capital: float = 10_000.0


def run_backtest(df: pd.DataFrame, ticker: str, initial_capital: float) -> BacktestResult:
    """
    Ejecuta el backtest sobre un DataFrame con indicadores y señales.

    Args:
        df: DataFrame con columnas signal, Close, High, Low, atr
        ticker: nombre del activo (para registro)
        initial_capital: capital inicial en EUR/USD

    Returns:
        BacktestResult con lista de trades y equity curve
    """
    capital = initial_capital
    equity = []
    trades: list[Trade] = []
    open_trade: Optional[Trade] = None

    for date, row in df.iterrows():
        # --- Gestión de posición abierta ---
        if open_trade is not None:
            open_trade.bars_held += 1
            close = row["Close"]
            high = row["High"]
            low = row["Low"]
            atr = row["atr"]

            # 1. Stop-loss fijo (intraday: si el mínimo toca el stop)
            if low <= open_trade.stop_loss:
                exit_price = open_trade.stop_loss
                open_trade.exit_date = date
                open_trade.exit_price = exit_price
                open_trade.exit_reason = "stop_loss"
                capital += exit_price * open_trade.shares
                trades.append(open_trade)
                open_trade = None

            # 2. Trailing stop (intraday)
            elif low <= open_trade.trailing_stop and open_trade.trailing_stop > open_trade.stop_loss:
                exit_price = open_trade.trailing_stop
                open_trade.exit_date = date
                open_trade.exit_price = exit_price
                open_trade.exit_reason = "trailing_stop"
                capital += exit_price * open_trade.shares
                trades.append(open_trade)
                open_trade = None

            # 3. Time stop (al cierre)
            elif open_trade.bars_held >= MAX_HOLD_DAYS:
                exit_price = close
                open_trade.exit_date = date
                open_trade.exit_price = exit_price
                open_trade.exit_reason = "time_stop"
                capital += exit_price * open_trade.shares
                trades.append(open_trade)
                open_trade = None

            else:
                # Actualizar máximo cierre
                if close > open_trade.highest_close:
                    open_trade.highest_close = close

                # Activar/actualizar trailing stop
                unrealized_gain = open_trade.highest_close - open_trade.entry_price
                if not pd.isna(atr) and atr > 0 and unrealized_gain >= ATR_TRAIL_TRIGGER * atr:
                    new_trail = open_trade.highest_close - ATR_TRAIL_MULT * atr
                    if new_trail > open_trade.trailing_stop:
                        open_trade.trailing_stop = new_trail

        # --- Nueva entrada ---
        if open_trade is None and row["signal"] == 1:
            atr = row["atr"]
            price = row["Close"]

            if pd.isna(atr) or atr <= 0 or price <= 0:
                equity.append(capital)
                continue

            # Position sizing: arriesgar RISK_PER_TRADE del capital
            risk_amount = capital * RISK_PER_TRADE
            shares = risk_amount / (ATR_STOP_MULT * atr)

            # Cap por máximo de posiciones (no usar más de capital/MAX_POSITIONS)
            max_position_value = capital / MAX_POSITIONS
            cost = shares * price
            if cost > max_position_value:
                shares = max_position_value / price

            if cost > capital:
                shares = capital / price

            if shares <= 0:
                equity.append(capital)
                continue

            capital -= shares * price

            stop = price - ATR_STOP_MULT * atr

            open_trade = Trade(
                ticker=ticker,
                entry_date=date,
                entry_price=price,
                shares=shares,
                stop_loss=stop,
                trailing_stop=stop,     # empieza al nivel del stop fijo
                highest_close=price,    # inicializar con precio de entrada
            )

        # Valor total: efectivo + valor de mercado de posición abierta
        market_value = (open_trade.shares * row["Close"]) if open_trade else 0.0
        equity.append(capital + market_value)

    # Cerrar posición abierta al final del periodo
    if open_trade is not None:
        last_row = df.iloc[-1]
        open_trade.exit_date = df.index[-1]
        open_trade.exit_price = last_row["Close"]
        open_trade.exit_reason = "end_of_period"
        capital += open_trade.exit_price * open_trade.shares
        trades.append(open_trade)

    equity_series = pd.Series(equity, index=df.index, name="equity")

    return BacktestResult(
        trades=trades,
        equity_curve=equity_series,
        initial_capital=initial_capital,
    )


def trades_to_dataframe(trades: list[Trade]) -> pd.DataFrame:
    """Convierte lista de Trade en DataFrame para análisis y visualización."""
    if not trades:
        return pd.DataFrame()

    rows = []
    for t in trades:
        rows.append({
            "ticker":        t.ticker,
            "entry_date":    t.entry_date,
            "entry_price":   t.entry_price,
            "shares":        t.shares,
            "stop_loss":     t.stop_loss,
            "trailing_stop": t.trailing_stop,
            "bars_held":     t.bars_held,
            "exit_date":     t.exit_date,
            "exit_price":    t.exit_price,
            "exit_reason":   t.exit_reason,
            "pnl":           t.pnl,
            "pnl_pct":       t.pnl_pct,
        })
    return pd.DataFrame(rows)
