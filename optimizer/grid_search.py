"""
Optimizador de parámetros por grid search.

Prueba combinaciones de parámetros de la estrategia RSI(2) Pullback
y devuelve un ranking ordenado por la métrica objetivo (Sharpe, CAGR, etc.).

Uso CLI:
    python main.py optimize --ticker AAPL --metric sharpe_ratio
    python main.py optimize --ticker MSFT --metric cagr_pct --top 10
"""

import itertools
from dataclasses import dataclass
from typing import Optional

import pandas as pd

from data.downloader import download_ohlcv
from indicators.technical import add_indicators
from backtest.engine import run_backtest, BacktestResult
from backtest.metrics import compute_metrics

import config


# ---------------------------------------------------------------
# Rangos por defecto para el grid search
# ---------------------------------------------------------------
DEFAULT_PARAM_GRID = {
    "RSI_ENTRY_THRESHOLD": [5, 10, 15, 20],
    "ATR_STOP_MULT":       [1.5, 2.0, 2.5, 3.0],
    "ATR_TRAIL_MULT":      [2.0, 2.5, 3.0, 3.5],
    "MAX_HOLD_DAYS":       [5, 7, 10, 15],
}

VALID_METRICS = [
    "sharpe_ratio", "cagr_pct", "total_return_pct",
    "profit_factor", "win_rate_pct", "max_drawdown_pct",
]


@dataclass
class OptimizationResult:
    results_df: pd.DataFrame
    best_params: dict
    best_metric_value: float
    metric_name: str
    total_combinations: int


def _generate_signals_with_params(df: pd.DataFrame, rsi_threshold: float) -> pd.DataFrame:
    """Genera señales con un umbral RSI personalizado (sin tocar config global)."""
    df = df.copy()
    sma_col = f"sma{config.SMA_TREND}"

    trend_ok = df["Close"] > df[sma_col]
    rsi_oversold = df["rsi2"] < rsi_threshold
    no_gap_down = df["Close"] >= df["Close"].shift(1) * config.GAP_DOWN_LIMIT

    entry = trend_ok & rsi_oversold & no_gap_down
    exit_rsi = df["rsi2"] > config.RSI_EXIT_THRESHOLD

    df["signal"] = 0
    df.loc[entry, "signal"] = 1
    df.loc[exit_rsi, "signal"] = -1
    df.loc[entry & exit_rsi, "signal"] = 1

    return df


def _run_single_backtest(
    df_with_indicators: pd.DataFrame,
    ticker: str,
    capital: float,
    params: dict,
) -> Optional[dict]:
    """
    Ejecuta un backtest con parámetros personalizados.
    Modifica config temporalmente y lo restaura después.
    """
    # Guardar valores originales
    orig = {
        "RSI_ENTRY_THRESHOLD": config.RSI_ENTRY_THRESHOLD,
        "ATR_STOP_MULT":       config.ATR_STOP_MULT,
        "ATR_TRAIL_MULT":      config.ATR_TRAIL_MULT,
        "MAX_HOLD_DAYS":       config.MAX_HOLD_DAYS,
    }

    try:
        # Aplicar parámetros temporales
        config.ATR_STOP_MULT  = params["ATR_STOP_MULT"]
        config.ATR_TRAIL_MULT = params["ATR_TRAIL_MULT"]
        config.MAX_HOLD_DAYS  = params["MAX_HOLD_DAYS"]

        # Generar señales con el umbral RSI de esta combinación
        df = _generate_signals_with_params(
            df_with_indicators, params["RSI_ENTRY_THRESHOLD"]
        )

        result = run_backtest(df, ticker, capital)
        metrics = compute_metrics(result)

        return {**params, **metrics}

    except Exception:
        return None
    finally:
        # Restaurar valores originales
        for k, v in orig.items():
            setattr(config, k, v)


def run_optimization(
    ticker: str,
    start: str,
    end: str,
    capital: float,
    param_grid: Optional[dict] = None,
    metric: str = "sharpe_ratio",
    top_n: int = 20,
    progress_callback=None,
) -> OptimizationResult:
    """
    Ejecuta grid search sobre combinaciones de parámetros.

    Args:
        ticker: símbolo del activo
        start, end: rango de fechas
        capital: capital inicial
        param_grid: diccionario {param: [valores]}. Si None, usa DEFAULT_PARAM_GRID
        metric: métrica objetivo para ordenar (sharpe_ratio, cagr_pct, etc.)
        top_n: número de mejores resultados a devolver
        progress_callback: función(i, total) para reportar progreso

    Returns:
        OptimizationResult con DataFrame de resultados y mejor combinación
    """
    if metric not in VALID_METRICS:
        raise ValueError(f"Métrica '{metric}' no válida. Opciones: {VALID_METRICS}")

    grid = param_grid or DEFAULT_PARAM_GRID

    # Descargar datos y calcular indicadores una sola vez
    df = download_ohlcv(ticker, start, end)
    df = add_indicators(df)

    # Generar todas las combinaciones
    keys = list(grid.keys())
    values = list(grid.values())
    combinations = list(itertools.product(*values))
    total = len(combinations)

    results = []
    for i, combo in enumerate(combinations):
        params = dict(zip(keys, combo))
        row = _run_single_backtest(df, ticker, capital, params)
        if row is not None:
            results.append(row)

        if progress_callback:
            progress_callback(i + 1, total)

    if not results:
        raise RuntimeError("Ninguna combinación produjo resultados válidos.")

    df_results = pd.DataFrame(results)

    # Ordenar: max_drawdown es negativo, queremos el menos negativo (más cercano a 0)
    ascending = metric == "max_drawdown_pct"
    df_results = df_results.sort_values(metric, ascending=ascending).reset_index(drop=True)

    best = df_results.iloc[0]
    best_params = {k: best[k] for k in keys}

    return OptimizationResult(
        results_df=df_results.head(top_n),
        best_params=best_params,
        best_metric_value=best[metric],
        metric_name=metric,
        total_combinations=total,
    )


def print_optimization_results(opt: OptimizationResult) -> None:
    """Imprime los resultados de la optimización en consola."""
    print(f"\n{'='*60}")
    print(f"  OPTIMIZACIÓN — {opt.total_combinations} combinaciones probadas")
    print(f"  Métrica objetivo: {opt.metric_name}")
    print(f"{'='*60}")

    print(f"\n  MEJOR COMBINACIÓN:")
    for k, v in opt.best_params.items():
        print(f"    {k:<25s} = {v}")
    print(f"    {opt.metric_name:<25s} = {opt.best_metric_value:.4f}")

    print(f"\n  TOP {len(opt.results_df)} RESULTADOS:")
    # Seleccionar columnas relevantes para mostrar
    param_cols = list(opt.best_params.keys())
    metric_cols = ["sharpe_ratio", "cagr_pct", "total_return_pct",
                   "max_drawdown_pct", "win_rate_pct", "profit_factor", "total_trades"]
    show_cols = param_cols + [c for c in metric_cols if c in opt.results_df.columns]
    print(opt.results_df[show_cols].to_string(index=False))
    print(f"{'='*60}")
