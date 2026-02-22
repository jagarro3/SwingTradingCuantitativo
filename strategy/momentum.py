"""
Estrategia RSI(2) Trend Pullback.

Reglas de ENTRADA (señal = 1) — las 3 condiciones a la vez:
  1. Close > SMA(200)              → tendencia alcista confirmada
  2. RSI(2) < RSI_ENTRY_THRESHOLD  → pullback profundo a corto plazo
  3. Close >= Close_ant * 0.95     → no hay gap bajista catastrófico

Las SALIDAS se gestionan íntegramente en el motor de backtest
(trailing stop, stop-loss fijo, time stop).
"""

import pandas as pd
from config import SMA_TREND, RSI_ENTRY_THRESHOLD, GAP_DOWN_LIMIT


def generate_signals(df: pd.DataFrame) -> pd.DataFrame:
    """
    Genera señales de entrada sobre el DataFrame con indicadores.

    Columnas añadidas:
        signal  →  1 = entrada long, 0 = sin acción

    Args:
        df: DataFrame con indicadores ya calculados (output de add_indicators)

    Returns:
        DataFrame con columna 'signal'
    """
    df = df.copy()

    sma_col = f"sma{SMA_TREND}"

    # 1. Filtro de tendencia: precio por encima de SMA largo
    trend_ok = df["Close"] > df[sma_col]

    # 2. Pullback: RSI(2) en zona de sobreventa extrema
    rsi_oversold = df["rsi2"] < RSI_ENTRY_THRESHOLD

    # 3. Seguridad: no entrar en días con gap bajista > 5%
    no_gap_down = df["Close"] >= df["Close"].shift(1) * GAP_DOWN_LIMIT

    # Señal de entrada
    entry = trend_ok & rsi_oversold & no_gap_down

    df["signal"] = 0
    df.loc[entry, "signal"] = 1

    return df
