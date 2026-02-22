"""
Estrategia CANSLIM (William O'Neil).

Los criterios fundamentales (C, A, I) se pre-filtran con Finviz en el universo.
Aquí se evalúan los criterios TÉCNICOS sobre datos OHLCV:

Reglas de ENTRADA (señal = 1) — las 3 condiciones técnicas a la vez:
  N: Close >= 85% del máximo de 52 semanas (near new high)
  S: Volume > 1.5x media 50 días (volume surge / demanda)
  L: Relative Strength > 1.0 (stock supera a SPY en 12 meses)
  + Close > SMA(200) y Close >= MIN_PRICE

Reglas de SALIDA (señal = -1):
  Precio cae más del 25% desde el máximo 52 semanas (pierde liderazgo)
"""

import pandas as pd
from config import (
    SMA_TREND, MIN_PRICE,
    CANSLIM_HIGH_PROXIMITY, CANSLIM_VOLUME_SURGE, CANSLIM_RS_THRESHOLD,
)


def generate_signals(df: pd.DataFrame) -> pd.DataFrame:
    """
    Genera señales CANSLIM sobre el DataFrame con indicadores CANSLIM.

    Columnas añadidas:
        canslim_score  → 0-3, cuántos criterios técnicos (N, S, L) cumple
        signal         → 1 = entrada, -1 = salida, 0 = sin acción

    Args:
        df: DataFrame con indicadores de canslim_indicators.add_canslim_indicators()
    """
    df = df.copy()

    sma_col = f"sma{SMA_TREND}"

    # Filtros base
    trend_ok = df["Close"] > df[sma_col]
    price_ok = df["Close"] >= MIN_PRICE

    # N: Near new high — precio dentro del 15% del máximo 52 semanas
    near_high = df["pct_from_high"] <= (1 - CANSLIM_HIGH_PROXIMITY) * 100  # <= 15%

    # S: Supply/Demand — volume surge
    vol_surge = df["vol_ratio"] > CANSLIM_VOLUME_SURGE

    # L: Leader — relative strength supera al mercado
    leader = df["rel_strength"] > CANSLIM_RS_THRESHOLD

    # Score: cuántos criterios técnicos cumple (0-3)
    df["canslim_score"] = near_high.astype(int) + vol_surge.astype(int) + leader.astype(int)

    # Entrada: los 3 criterios técnicos + filtros base
    entry = trend_ok & price_ok & near_high & vol_surge & leader

    # Salida: cae más del 25% desde el máximo (pierde liderazgo)
    exit_canslim = df["pct_from_high"] > 25

    df["signal"] = 0
    df.loc[entry, "signal"] = 1
    df.loc[exit_canslim, "signal"] = -1

    # Entrada tiene prioridad si ambas se activan el mismo día
    df.loc[entry & exit_canslim, "signal"] = 1

    return df
