"""
Descarga y caché de datos OHLCV usando yfinance.
Los datos se guardan en CSV en la carpeta cache/ para evitar descargas repetidas.
"""

import os
import pandas as pd
import yfinance as yf
from config import CACHE_DIR


def _cache_path(ticker: str, start: str, end: str) -> str:
    os.makedirs(CACHE_DIR, exist_ok=True)
    return os.path.join(CACHE_DIR, f"{ticker}_{start}_{end}.csv")


def download_ohlcv(ticker: str, start: str, end: str, force: bool = False) -> pd.DataFrame:
    """
    Descarga datos OHLCV ajustados para un ticker.
    Usa caché local si ya existe el archivo.

    Args:
        ticker: símbolo del activo (ej. 'AAPL')
        start: fecha inicio 'YYYY-MM-DD'
        end: fecha fin 'YYYY-MM-DD'
        force: si True, descarga aunque exista caché

    Returns:
        DataFrame con columnas: Open, High, Low, Close, Volume
        Index: DatetimeIndex (fechas de trading)
    """
    path = _cache_path(ticker, start, end)

    if not force and os.path.exists(path):
        df = pd.read_csv(path, index_col=0, parse_dates=True)
        return df

    df = yf.download(ticker, start=start, end=end, auto_adjust=True, progress=False)

    if df.empty:
        raise ValueError(f"No se encontraron datos para {ticker} entre {start} y {end}")

    # Aplanar columnas si yfinance devuelve MultiIndex
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df = df[["Open", "High", "Low", "Close", "Volume"]].dropna()
    df.to_csv(path)
    return df


def download_multiple(tickers: list[str], start: str, end: str) -> dict[str, pd.DataFrame]:
    """
    Descarga datos OHLCV para una lista de tickers.
    Omite silenciosamente los tickers que fallan.

    Returns:
        dict {ticker: DataFrame}
    """
    result = {}
    for ticker in tickers:
        try:
            result[ticker] = download_ohlcv(ticker, start, end)
        except Exception as e:
            print(f"  [!] {ticker}: {e}")
    return result
