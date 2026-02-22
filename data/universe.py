"""
Obtiene el universo de acciones a analizar.
Prioridad:
  1. finvizfinance: pre-screening de candidatos (precio > SMA200, volumen alto)
  2. Fallback: lista S&P 500 desde Wikipedia
"""

import pandas as pd


def get_universe_finviz() -> list[str]:
    """
    Usa finvizfinance para obtener tickers que ya cumplen criterios básicos:
    - Precio por encima de SMA(200)
    - Volumen medio > 500K acciones/día
    - Acciones USA ordinarias (no ETFs, no ADRs)

    Returns:
        Lista de tickers. Vacía si finvizfinance no está instalado o falla.
    """
    try:
        from finvizfinance.screener.overview import Overview

        foverview = Overview()
        filters_dict = {
            "Country": "USA",
            "Average Volume": "Over 500K",
            "20-Day Simple Moving Average": "SMA20 above SMA200",
        }
        foverview.set_filter(filters_dict=filters_dict)
        df = foverview.screener_view()
        tickers = df["Ticker"].dropna().tolist()
        print(f"[Finviz] {len(tickers)} candidatos pre-filtrados")
        return tickers
    except ImportError:
        print("[!] finvizfinance no instalado, usando fallback S&P500")
        return []
    except Exception as e:
        print(f"[!] Error en Finviz: {e}. Usando fallback S&P500")
        return []


def get_sp500_wikipedia() -> list[str]:
    """
    Descarga la lista actual del S&P 500 desde Wikipedia.

    Returns:
        Lista de ~500 tickers.
    """
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    tables = pd.read_html(url, storage_options={"User-Agent": "Mozilla/5.0"})
    tickers = tables[0]["Symbol"].str.replace(".", "-", regex=False).tolist()
    print(f"[Wikipedia] {len(tickers)} tickers del S&P500")
    return tickers


def get_universe(use_finviz: bool = True, strategy: str = "rsi2") -> list[str]:
    """
    Devuelve el universo de tickers a analizar.

    Args:
        use_finviz: si True, intenta usar Finviz primero
        strategy: "rsi2", "canslim" o "minervini"

    Returns:
        Lista de tickers (strings)
    """
    if use_finviz:
        if strategy == "canslim":
            from data.universe_canslim import get_universe_canslim
            tickers = get_universe_canslim()
        elif strategy == "minervini":
            from data.universe_minervini import get_universe_minervini
            tickers = get_universe_minervini()
        else:
            tickers = get_universe_finviz()
        if tickers:
            return tickers

    return get_sp500_wikipedia()
