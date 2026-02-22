"""
Obtener tipo de cambio EUR/USD en tiempo real.
"""

import yfinance as yf


def get_eur_usd() -> float:
    """
    Devuelve el tipo de cambio EUR/USD actual.
    Si falla, devuelve 1.0 como fallback.
    """
    try:
        ticker = yf.Ticker("EURUSD=X")
        data = ticker.history(period="1d")
        if not data.empty:
            rate = float(data["Close"].iloc[-1])
            if rate > 0:
                return round(rate, 4)
    except Exception:
        pass
    return 1.0
