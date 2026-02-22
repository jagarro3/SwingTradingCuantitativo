"""
Indicadores técnicos para la estrategia Minervini Trend Template (SEPA).

Calcula:
  - SMAs múltiples (200, 150, 50, 21) para MA alignment
  - RSI(14) para detectar pullbacks moderados
  - Proximidad al máximo/mínimo de 52 semanas
  - Distancia al SMA(21) para entry timing
  - Relative Strength vs SPY
  - SMA200 y ATR (reutilizados de technical.py)
"""

import pandas as pd
import pandas_ta_classic as ta
from indicators.technical import add_indicators


def add_minervini_indicators(df: pd.DataFrame, spy_df: pd.DataFrame = None) -> pd.DataFrame:
    """
    Añade indicadores Minervini Trend Template al DataFrame OHLCV.

    Columnas añadidas:
        sma200, rsi2, atr     — reutilizados de technical.py
        sma150                — SMA 150 días (tendencia medio plazo)
        sma50                 — SMA 50 días (tendencia corto plazo)
        sma21                 — SMA 21 días (soporte dinámico para pullback)
        rsi14                 — RSI 14 periodos (pullback moderado 30-50)
        high_252d             — máximo cierre 252 días
        low_252d              — mínimo cierre 252 días
        pct_from_high         — % por debajo del max 52 sem (0 = en máximo)
        pct_from_low          — % por encima del min 52 sem
        pct_from_sma21        — distancia absoluta % al SMA(21)
        rel_strength          — retorno 252d stock / retorno 252d SPY

    Args:
        df: DataFrame OHLCV del ticker
        spy_df: DataFrame OHLCV de SPY (para relative strength)
    """
    # Indicadores base (SMA200, RSI2, ATR)
    df = add_indicators(df)

    # SMAs para MA alignment
    df["sma150"] = ta.sma(df["Close"], length=150)
    df["sma50"] = ta.sma(df["Close"], length=50)
    df["sma21"] = ta.sma(df["Close"], length=21)

    # RSI(14) para pullback moderado
    df["rsi14"] = ta.rsi(df["Close"], length=14)

    # 52-week high/low (252 días de trading)
    df["high_252d"] = df["Close"].rolling(window=252, min_periods=50).max()
    df["low_252d"] = df["Close"].rolling(window=252, min_periods=50).min()
    df["pct_from_high"] = (1 - df["Close"] / df["high_252d"]) * 100
    df["pct_from_low"] = (df["Close"] / df["low_252d"] - 1) * 100

    # Distancia al SMA(21) — valor absoluto
    df["pct_from_sma21"] = ((df["Close"] / df["sma21"]) - 1).abs() * 100

    # Relative Strength vs SPY (mismo patrón que CANSLIM)
    df["ret_252d"] = df["Close"].pct_change(periods=252)

    if spy_df is not None and len(spy_df) > 0:
        spy_ret = spy_df["Close"].pct_change(periods=252)
        spy_ret = spy_ret.reindex(df.index, method="ffill")
        df["spy_ret_252d"] = spy_ret
        df["rel_strength"] = df["ret_252d"] / df["spy_ret_252d"].replace(0, float("nan"))
    else:
        df["rel_strength"] = float("nan")

    return df
