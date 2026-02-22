"""
Cálculo de indicadores técnicos para la estrategia RSI(2) Pullback.
Recibe un DataFrame OHLCV y devuelve el mismo DataFrame con columnas adicionales.
"""

import pandas as pd
import pandas_ta_classic as ta
from config import SMA_TREND, RSI_PERIOD, ATR_PERIOD


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Añade indicadores técnicos al DataFrame OHLCV.

    Columnas añadidas:
        sma200  — SMA de cierre (filtro de tendencia)
        rsi2    — RSI(2) ultra-corto para detectar pullbacks
        atr     — ATR(14) para stops y position sizing

    Args:
        df: DataFrame con columnas Open, High, Low, Close, Volume

    Returns:
        DataFrame con indicadores añadidos
    """
    df = df.copy()

    df[f"sma{SMA_TREND}"] = ta.sma(df["Close"], length=SMA_TREND)
    df["rsi2"]             = ta.rsi(df["Close"], length=RSI_PERIOD)
    df["atr"]              = ta.atr(df["High"], df["Low"], df["Close"], length=ATR_PERIOD)

    return df
