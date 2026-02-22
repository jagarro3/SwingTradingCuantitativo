"""
Filtro de régimen de mercado basado en SPY > SMA(200).
Si el mercado está en bear market, no se generan señales de entrada.
"""

import pandas as pd
from config import MARKET_FILTER_TICKER, MARKET_FILTER_SMA
from data.downloader import download_ohlcv
from indicators.technical import add_indicators


def is_bull_market(reference_date: str = None) -> bool:
    """
    Comprueba si el mercado está en régimen alcista.
    SPY cierre > SMA(200) → bull market.

    Args:
        reference_date: fecha a comprobar (default: última disponible)

    Returns:
        True si bull market, False si bear market
    """
    from datetime import date, timedelta

    end = reference_date or (date.today() + timedelta(days=1)).strftime("%Y-%m-%d")
    start = (pd.Timestamp(end) - timedelta(days=400)).strftime("%Y-%m-%d")

    try:
        df = download_ohlcv(MARKET_FILTER_TICKER, start, end)
        df = add_indicators(df)
        last = df.iloc[-1]
        sma_col = f"sma{MARKET_FILTER_SMA}"
        return last["Close"] > last[sma_col]
    except Exception:
        return True  # en caso de error, no bloquear


def get_market_status() -> dict:
    """
    Devuelve info detallada del estado del mercado.
    """
    from datetime import date, timedelta

    end = (date.today() + timedelta(days=1)).strftime("%Y-%m-%d")
    start = (date.today() - timedelta(days=400)).strftime("%Y-%m-%d")

    try:
        df = download_ohlcv(MARKET_FILTER_TICKER, start, end)
        df = add_indicators(df)
        last = df.iloc[-1]
        sma_col = f"sma{MARKET_FILTER_SMA}"
        close = last["Close"]
        sma_val = last[sma_col]
        bull = close > sma_val
        pct_above = (close - sma_val) / sma_val * 100

        return {
            "ticker": MARKET_FILTER_TICKER,
            "close": round(close, 2),
            "sma200": round(sma_val, 2),
            "bull_market": bull,
            "pct_above_sma": round(pct_above, 1),
        }
    except Exception as e:
        return {"ticker": MARKET_FILTER_TICKER, "bull_market": True, "error": str(e)}
