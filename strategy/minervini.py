"""
Estrategia Minervini Trend Template (SEPA).

Basada en Mark Minervini (US Investing Champion).
Compra acciones líderes en Stage 2 (tendencia alcista confirmada)
cuando hacen un pullback moderado hacia SMA(21).

Entrada: Trend Template completo + RSI(14) pullback + cerca de SMA(21)
Salida:  Gestionada por el engine (trailing stop ATR, stop-loss, time stop)
         No usa señal de salida basada en MA (evita salidas prematuras
         durante pullbacks normales dentro de tendencia alcista).

Diseñada para acciones de alto momentum (NVDA, AAPL, MSFT...)
con holds de ~40-60 días para capturar movimientos grandes.
"""

import pandas as pd
from config import (
    MIN_PRICE,
    MINERVINI_SMA200_RISING_DAYS,
    MINERVINI_MAX_PCT_FROM_HIGH,
    MINERVINI_MIN_PCT_FROM_LOW,
    MINERVINI_RSI_LOW,
    MINERVINI_RSI_HIGH,
    MINERVINI_MAX_PCT_FROM_SMA21,
)


def generate_signals(df: pd.DataFrame) -> pd.DataFrame:
    """
    Genera señales de compra Minervini Trend Template.

    Entrada (signal = 1) — TODAS las condiciones simultáneamente:
        1. Close > SMA(200) — tendencia largo plazo
        2. Close > SMA(150) — tendencia medio plazo
        3. Close > SMA(50)  — tendencia corto plazo
        4. SMA(50) > SMA(150) > SMA(200) — MA alignment correcto
        5. SMA(200) subiendo 20+ días — tendencia confirmada
        6. Precio dentro del 25% del máximo 52 sem — cerca de máximos
        7. Precio al menos 25% encima del mínimo 52 sem — fortaleza
        8. RSI(14) entre 30-60 — pullback moderado (no sobrecomprado)
        9. Close dentro del 8% de SMA(21) — cerca del soporte dinámico
       10. Close >= MIN_PRICE — excluir penny stocks

    Salida: gestionada por el engine (trailing stop, stop-loss, time stop).
        No se usa señal=-1 basada en MA para evitar salidas prematuras
        durante pullbacks normales en tendencia alcista.

    Columna extra:
        minervini_score (0-7) — cuántas condiciones del trend template cumple
    """
    df = df.copy()

    # --- TREND TEMPLATE (Stage 2 uptrend) ---
    # 1. Close > SMA(200)
    above_sma200 = df["Close"] > df["sma200"]

    # 2. Close > SMA(150)
    above_sma150 = df["Close"] > df["sma150"]

    # 3. Close > SMA(50)
    above_sma50 = df["Close"] > df["sma50"]

    # 4. SMA(50) > SMA(150) > SMA(200) — MA alignment
    ma_alignment = (df["sma50"] > df["sma150"]) & (df["sma150"] > df["sma200"])

    # 5. SMA(200) subiendo 20+ días
    sma200_rising = df["sma200"] > df["sma200"].shift(MINERVINI_SMA200_RISING_DAYS)

    # 6. Precio dentro del 25% del máximo 52 sem
    near_high = df["pct_from_high"] <= MINERVINI_MAX_PCT_FROM_HIGH

    # 7. Precio al menos 25% encima del mínimo 52 sem
    above_low = df["pct_from_low"] >= MINERVINI_MIN_PCT_FROM_LOW

    # Full trend template
    trend_template = (
        above_sma200 & above_sma150 & above_sma50
        & ma_alignment & sma200_rising & near_high & above_low
    )

    # --- PULLBACK ENTRY TRIGGER ---
    # 8. RSI(14) entre 30-50 (pullback moderado, no sobrecomprado)
    rsi_pullback = (df["rsi14"] >= MINERVINI_RSI_LOW) & (df["rsi14"] <= MINERVINI_RSI_HIGH)

    # 9. Close dentro del 5% de SMA(21) (cerca del soporte dinámico)
    near_sma21 = df["pct_from_sma21"] <= MINERVINI_MAX_PCT_FROM_SMA21

    # 10. Precio mínimo
    price_ok = df["Close"] >= MIN_PRICE

    # --- ENTRY ---
    entry = trend_template & rsi_pullback & near_sma21 & price_ok

    # --- SCORE (0-7): cuántas condiciones del trend template se cumplen ---
    df["minervini_score"] = (
        above_sma200.astype(int) + above_sma150.astype(int) + above_sma50.astype(int)
        + ma_alignment.astype(int) + sma200_rising.astype(int)
        + near_high.astype(int) + above_low.astype(int)
    )

    # --- SIGNAL ---
    # Solo señal de entrada. La salida la gestiona el engine
    # (trailing stop ATR, stop-loss fijo, time stop).
    # No usamos signal=-1 para evitar salidas prematuras durante
    # pullbacks normales dentro de una tendencia alcista.
    df["signal"] = 0
    df.loc[entry, "signal"] = 1

    return df
