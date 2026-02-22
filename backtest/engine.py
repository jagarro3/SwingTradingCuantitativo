"""
Motor de backtesting para la estrategia RSI(2) Trend Pullback.

Simulación barra a barra (daily) con:
  - Position sizing basado en ATR y % de riesgo por operación
  - Máximo N posiciones abiertas simultáneamente
  - Stop-loss fijo: entrada - ATR * ATR_STOP_MULT
  - Trailing stop: max_close - ATR * ATR_TRAIL_MULT (se activa tras ganancia >= ATR_TRAIL_TRIGGER * ATR)
  - Time stop: cerrar tras MAX_HOLD_DAYS barras sin que salte ningún stop
  - Salida por RSI(2) > 90 (fortaleza)
  - Comisiones y slippage configurables
"""

from dataclasses import dataclass, field
from typing import Optional
import pandas as pd
import config as cfg


@dataclass
class Trade:
    ticker: str
    entry_date: pd.Timestamp
    entry_price: float
    shares: int
    stop_loss: float
    trailing_stop: float
    highest_close: float
    bars_held: int = 0
    exit_date: Optional[pd.Timestamp] = None
    exit_price: Optional[float] = None
    exit_reason: Optional[str] = None
    commission_entry: float = 0.0   # comisión pagada al entrar
    commission_exit: float = 0.0    # comisión pagada al salir

    @property
    def pnl(self) -> float:
        """P&L neto (descontando comisiones de entrada y salida)."""
        if self.exit_price is None:
            return 0.0
        gross = (self.exit_price - self.entry_price) * self.shares
        return gross - self.commission_entry - self.commission_exit

    @property
    def pnl_pct(self) -> float:
        """P&L % sobre el coste total de entrada (precio + comisión)."""
        if self.exit_price is None:
            return 0.0
        cost = self.entry_price * self.shares + self.commission_entry
        if cost <= 0:
            return 0.0
        return self.pnl / cost


@dataclass
class BacktestResult:
    trades: list[Trade] = field(default_factory=list)
    equity_curve: pd.Series = field(default_factory=pd.Series)
    initial_capital: float = 10_000.0


def _apply_slippage(price: float, direction: str) -> float:
    """Aplica slippage: peor precio para el trader."""
    if direction == "buy":
        return price * (1 + cfg.SLIPPAGE_PCT)
    else:
        return price * (1 - cfg.SLIPPAGE_PCT)


def _commission(value: float) -> float:
    """Calcula comisión sobre un valor de operación."""
    return value * cfg.COMMISSION_PCT


def run_backtest(df: pd.DataFrame, ticker: str, initial_capital: float) -> BacktestResult:
    """
    Ejecuta el backtest sobre un DataFrame con indicadores y señales.
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
            low = row["Low"]
            atr = row["atr"]

            # 1. Stop-loss fijo (intraday: si el mínimo toca el stop)
            if low <= open_trade.stop_loss:
                exit_price = _apply_slippage(open_trade.stop_loss, "sell")
                commission = _commission(exit_price * open_trade.shares)
                open_trade.exit_date = date
                open_trade.exit_price = exit_price
                open_trade.exit_reason = "stop_loss"
                open_trade.commission_exit = commission
                capital += exit_price * open_trade.shares - commission
                trades.append(open_trade)
                open_trade = None

            # 2. Trailing stop (intraday)
            elif low <= open_trade.trailing_stop and open_trade.trailing_stop > open_trade.stop_loss:
                exit_price = _apply_slippage(open_trade.trailing_stop, "sell")
                commission = _commission(exit_price * open_trade.shares)
                open_trade.exit_date = date
                open_trade.exit_price = exit_price
                open_trade.exit_reason = "trailing_stop"
                open_trade.commission_exit = commission
                capital += exit_price * open_trade.shares - commission
                trades.append(open_trade)
                open_trade = None

            # 3. Salida por RSI alto (fortaleza) - señal = -1
            elif row.get("signal", 0) == -1:
                exit_price = _apply_slippage(close, "sell")
                commission = _commission(exit_price * open_trade.shares)
                open_trade.exit_date = date
                open_trade.exit_price = exit_price
                open_trade.exit_reason = "rsi_exit"
                open_trade.commission_exit = commission
                capital += exit_price * open_trade.shares - commission
                trades.append(open_trade)
                open_trade = None

            # 4. Time stop (al cierre)
            elif open_trade.bars_held >= cfg.MAX_HOLD_DAYS:
                exit_price = _apply_slippage(close, "sell")
                commission = _commission(exit_price * open_trade.shares)
                open_trade.exit_date = date
                open_trade.exit_price = exit_price
                open_trade.exit_reason = "time_stop"
                open_trade.commission_exit = commission
                capital += exit_price * open_trade.shares - commission
                trades.append(open_trade)
                open_trade = None

            else:
                # Actualizar máximo cierre
                if close > open_trade.highest_close:
                    open_trade.highest_close = close

                # Activar/actualizar trailing stop
                unrealized_gain = open_trade.highest_close - open_trade.entry_price
                if not pd.isna(atr) and atr > 0 and unrealized_gain >= cfg.ATR_TRAIL_TRIGGER * atr:
                    new_trail = open_trade.highest_close - cfg.ATR_TRAIL_MULT * atr
                    if new_trail > open_trade.trailing_stop:
                        open_trade.trailing_stop = new_trail

        # --- Nueva entrada ---
        if open_trade is None and row["signal"] == 1:
            atr = row["atr"]
            price = row["Close"]

            if pd.isna(atr) or atr <= 0 or price <= 0:
                equity.append(capital)
                continue

            entry_price = _apply_slippage(price, "buy")

            # Position sizing: arriesgar RISK_PER_TRADE del capital
            risk_amount = capital * cfg.RISK_PER_TRADE
            shares = risk_amount / (cfg.ATR_STOP_MULT * atr)

            # Cap por máximo de posiciones (no usar más de capital/MAX_POSITIONS)
            max_position_value = capital / cfg.MAX_POSITIONS
            if shares * entry_price > max_position_value:
                shares = max_position_value / entry_price

            if shares * entry_price > capital:
                shares = capital / entry_price

            # Redondear a entero (no se compran fracciones de acción)
            shares = int(shares)

            if shares <= 0:
                equity.append(capital)
                continue

            commission = _commission(shares * entry_price)
            capital -= shares * entry_price + commission

            stop = entry_price - cfg.ATR_STOP_MULT * atr

            open_trade = Trade(
                ticker=ticker,
                entry_date=date,
                entry_price=entry_price,
                shares=shares,
                stop_loss=stop,
                trailing_stop=stop,
                highest_close=entry_price,
                commission_entry=commission,
            )

        # Valor total: efectivo + valor de mercado de posición abierta
        market_value = (open_trade.shares * row["Close"]) if open_trade else 0.0
        equity.append(capital + market_value)

    # Cerrar posición abierta al final del periodo
    if open_trade is not None:
        last_row = df.iloc[-1]
        exit_price = _apply_slippage(last_row["Close"], "sell")
        commission = _commission(exit_price * open_trade.shares)
        open_trade.exit_date = df.index[-1]
        open_trade.exit_price = exit_price
        open_trade.exit_reason = "end_of_period"
        open_trade.commission_exit = commission
        capital += exit_price * open_trade.shares - commission
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
            "commission":    t.commission_entry + t.commission_exit,
        })
    return pd.DataFrame(rows)
