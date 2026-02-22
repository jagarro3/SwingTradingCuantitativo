"""
Universo de acciones pre-filtrado para la estrategia Minervini Trend Template.

Usa Finviz para seleccionar acciones en Stage 2 (tendencia alcista fuerte):
  - Precio por encima de SMA200 y SMA50
  - Cerca de máximos de 52 semanas
  - Rendimiento anual positivo
  - Volumen suficiente
"""


def get_universe_minervini() -> list[str]:
    """
    Pre-screening Minervini via Finviz.

    Filtros aplicados:
      - 200-Day SMA: Price above SMA200
      - 50-Day SMA: Price above SMA50
      - 52-Week High/Low: 0-30% below High (cerca de máximos)
      - Performance: Year Up (retorno anual positivo)
      - Average Volume: Over 500K
      - Country: USA
      - Price: Over $10

    Returns:
        Lista de tickers en Stage 2 uptrend.
        Lista vacía si falla.
    """
    try:
        from finvizfinance.screener.overview import Overview

        foverview = Overview()
        filters_dict = {
            "Country": "USA",
            "Average Volume": "Over 500K",
            "Price": "Over $10",
            "200-Day Simple Moving Average": "Price above SMA200",
            "50-Day Simple Moving Average": "Price above SMA50",
            "52-Week High/Low": "0-30% below High",
            "Performance": "Year Up",
        }
        foverview.set_filter(filters_dict=filters_dict)
        df = foverview.screener_view()
        tickers = df["Ticker"].dropna().tolist()
        print(f"[Finviz Minervini] {len(tickers)} candidatos pre-filtrados")
        return tickers
    except ImportError:
        print("[!] finvizfinance no instalado, usando fallback S&P500")
        return []
    except Exception as e:
        print(f"[!] Error en Finviz Minervini: {e}. Usando fallback S&P500")
        return []
