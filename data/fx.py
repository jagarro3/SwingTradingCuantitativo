"""
Obtener tipo de cambio USD→EUR en tiempo real.
"""

import yfinance as yf


def get_usd_eur() -> float:
    """
    Devuelve el tipo de cambio USD→EUR actual.
    Ejemplo: 0.86 significa 1 USD = 0.86 EUR.
    Si falla, devuelve 0.85 como fallback.
    """
    try:
        ticker = yf.Ticker("USDEUR=X")
        data = ticker.history(period="1d")
        if not data.empty:
            rate = float(data["Close"].iloc[-1])
            if rate > 0:
                return round(rate, 6)
    except Exception:
        pass
    return 0.85
