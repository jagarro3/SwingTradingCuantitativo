"""
Estrategia RSI(2) Trend Pullback.

Reglas de ENTRADA (señal = 1) — las 3 condiciones a la vez:
  1. Close > SMA(200)              → tendencia alcista confirmada
  2. RSI(2) < RSI_ENTRY_THRESHOLD  → pullback profundo a corto plazo
  3. Close >= Close_ant * 0.95     → no hay gap bajista catastrófico

Reglas de SALIDA (señal = -1):
  4. RSI(2) > RSI_EXIT_THRESHOLD   → salida por fortaleza (rebote completo)

Las demás SALIDAS (trailing stop, stop-loss, time stop) se gestionan
en el motor de backtest.
"""

import pandas as pd
from config import SMA_TREND, RSI_ENTRY_THRESHOLD, RSI_EXIT_THRESHOLD, GAP_DOWN_LIMIT, MIN_PRICE


def generate_signals(df: pd.DataFrame) -> pd.DataFrame:
    """
    Genera señales de entrada y salida sobre el DataFrame con indicadores.

    Columnas añadidas:
        signal  →  1 = entrada long, -1 = salida por RSI, 0 = sin acción

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

    # 4. Filtro de precio: excluir penny stocks
    price_ok = df["Close"] >= MIN_PRICE

    # Señal de entrada
    entry = trend_ok & rsi_oversold & no_gap_down & price_ok

    # Señal de salida por fortaleza (RSI alto)
    exit_rsi = df["rsi2"] > RSI_EXIT_THRESHOLD

    df["signal"] = 0
    df.loc[entry, "signal"] = 1
    df.loc[exit_rsi, "signal"] = -1

    # Entrada tiene prioridad si ambas se activan el mismo día (raro pero posible)
    df.loc[entry & exit_rsi, "signal"] = 1

    return df
