"""
Backtest multi-ticker: simula el sistema completo sobre el universo histórico.

Reproduce el flujo real:
  1. Cada día, escanea señales en todo el universo
  2. Ordena por RSI(2) ascendente (mejor pullback primero)
  3. Abre hasta MAX_POSITIONS con position sizing
  4. Gestiona salidas (stops, trailing, RSI exit, time stop)
  5. Aplica filtro de mercado SPY > SMA200
  6. Aplica diversificación por sector (máx 2 del mismo sector)
"""

import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from typing import Optional

from config import (
    RISK_PER_TRADE, MAX_POSITIONS, ATR_STOP_MULT, ATR_TRAIL_MULT,
    ATR_TRAIL_TRIGGER, MAX_HOLD_DAYS, SMA_TREND, COMMISSION_PCT,
    SLIPPAGE_PCT, RSI_EXIT_THRESHOLD, MARKET_FILTER_SMA,
)


@dataclass
class PortfolioTrade:
    ticker: str
    sector: str
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
class MultiBacktestResult:
    trades: list[PortfolioTrade] = field(default_factory=list)
    equity_curve: pd.Series = field(default_factory=pd.Series)
    initial_capital: float = 10_000.0
    market_filter_days: int = 0
    total_days: int = 0


MAX_PER_SECTOR = 2  # máximo de posiciones del mismo sector


def run_multi_backtest(
    all_data: dict[str, pd.DataFrame],
    spy_data: pd.DataFrame,
    sector_map: dict[str, str],
    initial_capital: float,
) -> MultiBacktestResult:
    """
    Backtest multi-ticker con gestión de portfolio.

    Args:
        all_data: {ticker: DataFrame con indicadores y señales}
        spy_data: DataFrame de SPY con indicadores
        sector_map: {ticker: sector}
        initial_capital: capital inicial

    Returns:
        MultiBacktestResult
    """
    # Obtener todas las fechas de trading
    all_dates = set()
    for df in all_data.values():
        all_dates.update(df.index.tolist())
    if spy_data is not None and not spy_data.empty:
        all_dates.update(spy_data.index.tolist())
    trading_dates = sorted(all_dates)

    capital = initial_capital
    equity = []
    open_positions: list[PortfolioTrade] = []
    closed_trades: list[PortfolioTrade] = []
    market_filter_days = 0
    sma_col = f"sma{MARKET_FILTER_SMA}"

    for date in trading_dates:
        # --- Filtro de mercado ---
        bull_market = True
        if spy_data is not None and date in spy_data.index:
            spy_row = spy_data.loc[date]
            if not pd.isna(spy_row.get(sma_col, float("nan"))):
                bull_market = spy_row["Close"] > spy_row[sma_col]

        if not bull_market:
            market_filter_days += 1

        # --- Gestionar posiciones abiertas ---
        positions_to_close = []
        for pos in open_positions:
            if date not in all_data.get(pos.ticker, pd.DataFrame()).index:
                continue

            row = all_data[pos.ticker].loc[date]
            pos.bars_held += 1
            close = row["Close"]
            low = row["Low"]
            atr = row["atr"]

            closed = False

            # 1. Stop-loss
            if low <= pos.stop_loss:
                pos.exit_price = pos.stop_loss * (1 - SLIPPAGE_PCT)
                pos.exit_reason = "stop_loss"
                closed = True

            # 2. Trailing stop
            elif low <= pos.trailing_stop and pos.trailing_stop > pos.stop_loss:
                pos.exit_price = pos.trailing_stop * (1 - SLIPPAGE_PCT)
                pos.exit_reason = "trailing_stop"
                closed = True

            # 3. RSI exit
            elif row.get("signal", 0) == -1:
                pos.exit_price = close * (1 - SLIPPAGE_PCT)
                pos.exit_reason = "rsi_exit"
                closed = True

            # 4. Time stop
            elif pos.bars_held >= MAX_HOLD_DAYS:
                pos.exit_price = close * (1 - SLIPPAGE_PCT)
                pos.exit_reason = "time_stop"
                closed = True

            # 5. Bear market → cerrar todas
            elif not bull_market:
                pos.exit_price = close * (1 - SLIPPAGE_PCT)
                pos.exit_reason = "market_filter"
                closed = True

            if closed:
                pos.exit_date = date
                commission = pos.exit_price * pos.shares * COMMISSION_PCT
                capital += pos.exit_price * pos.shares - commission
                positions_to_close.append(pos)
            else:
                if close > pos.highest_close:
                    pos.highest_close = close
                unrealized = pos.highest_close - pos.entry_price
                if not pd.isna(atr) and atr > 0 and unrealized >= ATR_TRAIL_TRIGGER * atr:
                    new_trail = pos.highest_close - ATR_TRAIL_MULT * atr
                    if new_trail > pos.trailing_stop:
                        pos.trailing_stop = new_trail

        for pos in positions_to_close:
            open_positions.remove(pos)
            closed_trades.append(pos)

        # --- Nuevas entradas (solo en bull market) ---
        if bull_market and len(open_positions) < MAX_POSITIONS:
            candidates = []
            for ticker, df in all_data.items():
                if date not in df.index:
                    continue
                row = df.loc[date]
                if row["signal"] != 1:
                    continue
                if any(p.ticker == ticker for p in open_positions):
                    continue
                atr = row["atr"]
                if pd.isna(atr) or atr <= 0:
                    continue
                candidates.append((ticker, row["rsi2"], row["Close"], atr))

            # Ordenar por RSI ascendente (mejor pullback primero)
            candidates.sort(key=lambda x: x[1])

            # Contar sectores actuales
            sector_count = {}
            for pos in open_positions:
                s = pos.sector
                sector_count[s] = sector_count.get(s, 0) + 1

            for ticker, rsi, price, atr in candidates:
                if len(open_positions) >= MAX_POSITIONS:
                    break

                sector = sector_map.get(ticker, "Unknown")

                # Diversificación: máximo MAX_PER_SECTOR del mismo sector
                if sector_count.get(sector, 0) >= MAX_PER_SECTOR:
                    continue

                entry_price = price * (1 + SLIPPAGE_PCT)
                risk_amount = capital * RISK_PER_TRADE
                shares = risk_amount / (ATR_STOP_MULT * atr)

                max_pos_value = capital / MAX_POSITIONS
                cost = shares * entry_price
                if cost > max_pos_value:
                    shares = max_pos_value / entry_price
                if shares * entry_price > capital:
                    continue
                if shares <= 0:
                    continue

                commission = shares * entry_price * COMMISSION_PCT
                capital -= shares * entry_price + commission
                stop = entry_price - ATR_STOP_MULT * atr

                pos = PortfolioTrade(
                    ticker=ticker,
                    sector=sector,
                    entry_date=date,
                    entry_price=entry_price,
                    shares=shares,
                    stop_loss=stop,
                    trailing_stop=stop,
                    highest_close=entry_price,
                )
                open_positions.append(pos)
                sector_count[sector] = sector_count.get(sector, 0) + 1

        # Equity = capital + valor de mercado
        market_value = 0.0
        for pos in open_positions:
            if date in all_data.get(pos.ticker, pd.DataFrame()).index:
                market_value += pos.shares * all_data[pos.ticker].loc[date]["Close"]
            else:
                market_value += pos.shares * pos.entry_price
        equity.append(capital + market_value)

    # Cerrar posiciones al final
    for pos in open_positions:
        last_date = trading_dates[-1]
        if last_date in all_data.get(pos.ticker, pd.DataFrame()).index:
            pos.exit_price = all_data[pos.ticker].loc[last_date]["Close"]
        else:
            pos.exit_price = pos.entry_price
        pos.exit_date = last_date
        pos.exit_reason = "end_of_period"
        capital += pos.exit_price * pos.shares
        closed_trades.append(pos)

    equity_series = pd.Series(equity, index=trading_dates, name="equity")

    return MultiBacktestResult(
        trades=closed_trades,
        equity_curve=equity_series,
        initial_capital=initial_capital,
        market_filter_days=market_filter_days,
        total_days=len(trading_dates),
    )


def multi_trades_to_dataframe(trades: list[PortfolioTrade]) -> pd.DataFrame:
    if not trades:
        return pd.DataFrame()
    rows = []
    for t in trades:
        rows.append({
            "ticker": t.ticker, "sector": t.sector,
            "entry_date": t.entry_date, "entry_price": round(t.entry_price, 2),
            "shares": round(t.shares, 2), "bars_held": t.bars_held,
            "exit_date": t.exit_date, "exit_price": round(t.exit_price, 2) if t.exit_price else None,
            "exit_reason": t.exit_reason,
            "pnl": round(t.pnl, 2), "pnl_pct": round(t.pnl_pct * 100, 2),
        })
    return pd.DataFrame(rows)
