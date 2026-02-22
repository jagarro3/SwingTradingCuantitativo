"""
Universo de acciones pre-filtrado con criterios CANSLIM fundamentales.

Usa Finviz para aplicar filtros que no se pueden calcular localmente:
  C: Crecimiento EPS trimestral > 25%
  A: Crecimiento EPS 5 años > 25%
  N: Precio cerca del máximo de 52 semanas
  I: Propiedad institucional > 50%
"""


def get_universe_canslim() -> list[str]:
    """
    Pre-screening CANSLIM via Finviz.

    Filtros aplicados:
      - EPS growth quarter over quarter > 25%  (C)
      - EPS growth past 5 years > 25%          (A)
      - 52-week high/low: 0-10% below high     (N)
      - Institutional ownership > 50%           (I)
      - Average Volume > 500K
      - Country: USA

    Returns:
        Lista de tickers que cumplen criterios fundamentales CANSLIM.
        Lista vacía si falla.
    """
    try:
        from finvizfinance.screener.overview import Overview

        foverview = Overview()
        filters_dict = {
            "Country": "USA",
            "Average Volume": "Over 500K",
            "EPS growthqtr over qtr": "Over 25%",
            "EPS growthpast 5 years": "Over 25%",
            "52-Week High/Low": "0-10% below High",
            "InstitutionalOwnership": "Over 50%",
        }
        foverview.set_filter(filters_dict=filters_dict)
        df = foverview.screener_view()
        # Excluir ETFs — solo acciones
        if "Industry" in df.columns:
            df = df[df["Industry"] != "Exchange Traded Fund"]
        tickers = df["Ticker"].dropna().tolist()
        print(f"[Finviz CANSLIM] {len(tickers)} acciones pre-filtradas (sin ETFs)")
        return tickers
    except ImportError:
        print("[!] finvizfinance no instalado, usando fallback S&P500")
        return []
    except Exception as e:
        print(f"[!] Error en Finviz CANSLIM: {e}. Usando fallback S&P500")
        return []
