"""
Cálculo de métricas de rendimiento del backtest.
"""

import numpy as np
import pandas as pd
from backtest.engine import BacktestResult, trades_to_dataframe


def compute_metrics(result: BacktestResult) -> dict:
    """
    Calcula métricas de rendimiento a partir de un BacktestResult.

    Returns:
        dict con claves:
            total_return_pct    — retorno total %
            cagr_pct            — CAGR %
            sharpe_ratio        — ratio de Sharpe anualizado (rf=0)
            max_drawdown_pct    — máximo drawdown %
            win_rate_pct        — % de operaciones ganadoras
            profit_factor       — suma ganancias / suma pérdidas absolutas
            total_trades        — número total de operaciones
            avg_pnl_pct         — P&L medio por operación %
    """
    equity = result.equity_curve
    initial = result.initial_capital

    # --- Retorno total ---
    total_return = (equity.iloc[-1] - initial) / initial * 100

    # --- CAGR ---
    years = (equity.index[-1] - equity.index[0]).days / 365.25
    if years > 0:
        cagr = ((equity.iloc[-1] / initial) ** (1 / years) - 1) * 100
    else:
        cagr = 0.0

    # --- Sharpe ratio anualizado (retornos diarios, rf=0) ---
    daily_returns = equity.pct_change().dropna()
    if daily_returns.std() > 0:
        sharpe = (daily_returns.mean() / daily_returns.std()) * np.sqrt(252)
    else:
        sharpe = 0.0

    # --- Máximo drawdown ---
    rolling_max = equity.cummax()
    drawdown = (equity - rolling_max) / rolling_max * 100
    max_dd = drawdown.min()

    # --- Métricas por operación ---
    df_trades = trades_to_dataframe(result.trades)
    if df_trades.empty:
        return {
            "total_return_pct": round(total_return, 2),
            "cagr_pct":         round(cagr, 2),
            "sharpe_ratio":     round(sharpe, 3),
            "max_drawdown_pct": round(max_dd, 2),
            "win_rate_pct":     0.0,
            "profit_factor":    0.0,
            "total_trades":     0,
            "avg_pnl_pct":      0.0,
            "avg_bars_held":    0.0,
        }

    winners = df_trades[df_trades["pnl"] > 0]
    losers  = df_trades[df_trades["pnl"] <= 0]

    win_rate = len(winners) / len(df_trades) * 100
    gross_profit = winners["pnl"].sum()
    gross_loss   = abs(losers["pnl"].sum())
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else float("inf")
    avg_pnl_pct   = df_trades["pnl_pct"].mean() * 100
    avg_bars_held = df_trades["bars_held"].mean() if "bars_held" in df_trades.columns else 0.0

    return {
        "total_return_pct": round(total_return, 2),
        "cagr_pct":         round(cagr, 2),
        "sharpe_ratio":     round(sharpe, 3),
        "max_drawdown_pct": round(max_dd, 2),
        "win_rate_pct":     round(win_rate, 1),
        "profit_factor":    round(profit_factor, 2),
        "total_trades":     len(df_trades),
        "avg_pnl_pct":      round(avg_pnl_pct, 2),
        "avg_bars_held":    round(avg_bars_held, 1),
    }


def print_metrics(metrics: dict) -> None:
    """Imprime un resumen legible de las métricas."""
    print("\n" + "=" * 40)
    print("  RESUMEN DEL BACKTEST")
    print("=" * 40)
    print(f"  Retorno total  : {metrics['total_return_pct']:>8.2f} %")
    print(f"  CAGR           : {metrics['cagr_pct']:>8.2f} %")
    print(f"  Sharpe ratio   : {metrics['sharpe_ratio']:>8.3f}")
    print(f"  Max Drawdown   : {metrics['max_drawdown_pct']:>8.2f} %")
    print(f"  Win rate       : {metrics['win_rate_pct']:>8.1f} %")
    print(f"  Profit factor  : {metrics['profit_factor']:>8.2f}")
    print(f"  Total trades   : {metrics['total_trades']:>8d}")
    print(f"  P&L medio/op   : {metrics['avg_pnl_pct']:>8.2f} %")
    print(f"  Dias medio/op  : {metrics['avg_bars_held']:>8.1f}")
    print("=" * 40)
