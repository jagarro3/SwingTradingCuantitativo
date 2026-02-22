"""
Obtiene el sector de cada ticker usando yfinance.
Cachea resultados en un JSON local para no repetir llamadas.
"""

import os
import json
import yfinance as yf
from config import CACHE_DIR


_SECTOR_CACHE_FILE = os.path.join(CACHE_DIR, "sectors.json")


def _load_sector_cache() -> dict[str, str]:
    if os.path.exists(_SECTOR_CACHE_FILE):
        try:
            with open(_SECTOR_CACHE_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_sector_cache(cache: dict[str, str]):
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(_SECTOR_CACHE_FILE, "w") as f:
        json.dump(cache, f, indent=2)


def get_sector(ticker: str) -> str:
    """Obtiene el sector de un ticker."""
    cache = _load_sector_cache()
    if ticker in cache:
        return cache[ticker]

    try:
        info = yf.Ticker(ticker).info
        sector = info.get("sector", "Unknown")
    except Exception:
        sector = "Unknown"

    cache[ticker] = sector
    _save_sector_cache(cache)
    return sector


def get_sectors_bulk(tickers: list[str]) -> dict[str, str]:
    """Obtiene sectores para una lista de tickers (con cache)."""
    cache = _load_sector_cache()
    missing = [t for t in tickers if t not in cache]

    for t in missing:
        try:
            info = yf.Ticker(t).info
            cache[t] = info.get("sector", "Unknown")
        except Exception:
            cache[t] = "Unknown"

    if missing:
        _save_sector_cache(cache)

    return {t: cache.get(t, "Unknown") for t in tickers}
