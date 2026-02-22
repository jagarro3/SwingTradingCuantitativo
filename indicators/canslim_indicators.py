"""
Indicadores técnicos para la estrategia CANSLIM.

Calcula:
  - Proximidad al máximo de 52 semanas (N: New High)
  - Volume surge vs media 50 días (S: Supply/Demand)
  - Relative Strength vs SPY (L: Leader)
  - SMA200 y ATR (reutilizados para filtro de tendencia y position sizing)
"""

import pandas as pd
from indicators.technical import add_indicators
from config import SMA_TREND


def add_canslim_indicators(df: pd.DataFrame, spy_df: pd.DataFrame = None) -> pd.DataFrame:
    """
    Añade indicadores CANSLIM al DataFrame OHLCV.

    Columnas añadidas:
        sma200, atr         — reutilizados de technical.py
        high_252d           — máximo cierre de 252 días
        pct_from_high       — % por debajo del max 52 semanas (0 = en máximo)
        vol_sma50           — media de volumen 50 días
        vol_ratio           — Volume / vol_sma50 (> 1.5 = surge)
        rel_strength        — retorno 252d stock / retorno 252d SPY

    Args:
        df: DataFrame OHLCV del ticker
        spy_df: DataFrame OHLCV de SPY (para relative strength)
    """
    # Indicadores base (SMA200, RSI2, ATR)
    df = add_indicators(df)

    # N: Proximidad al máximo de 52 semanas (252 días de trading)
    df["high_252d"] = df["Close"].rolling(window=252, min_periods=50).max()
    df["pct_from_high"] = (1 - df["Close"] / df["high_252d"]) * 100

    # S: Volume surge — volumen actual vs media 50 días
    df["vol_sma50"] = df["Volume"].rolling(window=50, min_periods=10).mean()
    df["vol_ratio"] = df["Volume"] / df["vol_sma50"]

    # L: Relative Strength vs SPY — retorno 252 días del stock vs SPY
    df["ret_252d"] = df["Close"].pct_change(periods=252)

    if spy_df is not None and len(spy_df) > 0:
        spy_ret = spy_df["Close"].pct_change(periods=252)
        # Alinear por fecha
        spy_ret = spy_ret.reindex(df.index, method="ffill")
        df["spy_ret_252d"] = spy_ret
        # Evitar división por cero
        df["rel_strength"] = df["ret_252d"] / df["spy_ret_252d"].replace(0, float("nan"))
    else:
        df["rel_strength"] = float("nan")

    return df
