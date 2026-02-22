"""
Obtiene el sector y nombre de cada ticker usando yfinance.
Cachea resultados en un JSON local para no repetir llamadas.
"""

import os
import json
import yfinance as yf
from config import CACHE_DIR


_SECTOR_CACHE_FILE = os.path.join(CACHE_DIR, "sectors.json")


def _load_cache() -> dict[str, dict]:
    if os.path.exists(_SECTOR_CACHE_FILE):
        try:
            with open(_SECTOR_CACHE_FILE, "r") as f:
                data = json.load(f)
            # Migrar formato antiguo (str) al nuevo (dict)
            migrated = {}
            for k, v in data.items():
                if isinstance(v, str):
                    migrated[k] = {"sector": v, "name": ""}
                else:
                    migrated[k] = v
            return migrated
        except Exception:
            pass
    return {}


def _save_cache(cache: dict[str, dict]):
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(_SECTOR_CACHE_FILE, "w") as f:
        json.dump(cache, f, indent=2)


def _fetch_info(ticker: str) -> dict:
    """Descarga info de yfinance y devuelve sector + nombre."""
    try:
        info = yf.Ticker(ticker).info
        return {
            "sector": info.get("sector", "Unknown"),
            "name": info.get("shortName", ""),
        }
    except Exception:
        return {"sector": "Unknown", "name": ""}


def get_sector(ticker: str) -> str:
    """Obtiene el sector de un ticker."""
    cache = _load_cache()
    if ticker in cache:
        return cache[ticker]["sector"]

    info = _fetch_info(ticker)
    cache[ticker] = info
    _save_cache(cache)
    return info["sector"]


def get_name(ticker: str) -> str:
    """Obtiene el nombre corto de la empresa."""
    cache = _load_cache()
    if ticker in cache and cache[ticker].get("name"):
        return cache[ticker]["name"]

    info = _fetch_info(ticker)
    cache[ticker] = info
    _save_cache(cache)
    return info["name"]


def get_names_bulk(tickers: list[str]) -> dict[str, str]:
    """Obtiene nombres para una lista de tickers (con cache)."""
    cache = _load_cache()
    missing = [t for t in tickers if t not in cache or not cache[t].get("name")]

    for t in missing:
        cache[t] = _fetch_info(t)

    if missing:
        _save_cache(cache)

    return {t: cache.get(t, {}).get("name", "") for t in tickers}


def get_sectors_bulk(tickers: list[str]) -> dict[str, str]:
    """Obtiene sectores para una lista de tickers (con cache)."""
    cache = _load_cache()
    missing = [t for t in tickers if t not in cache]

    for t in missing:
        cache[t] = _fetch_info(t)

    if missing:
        _save_cache(cache)

    return {t: cache.get(t, {}).get("sector", "Unknown") for t in tickers}
