"""
Historial de señales: guarda y consulta las señales generadas cada día.
Archivo por día: signals_history/YYYY-MM-DD.json
"""

import os
import json
from datetime import date
from config import SIGNALS_DIR


def _ensure_dir():
    os.makedirs(SIGNALS_DIR, exist_ok=True)


def save_daily_signals(signals: list[dict], scan_date: str = None):
    """Guarda las señales del día."""
    _ensure_dir()
    scan_date = scan_date or date.today().strftime("%Y-%m-%d")
    path = os.path.join(SIGNALS_DIR, f"{scan_date}.json")
    with open(path, "w") as f:
        json.dump({"date": scan_date, "count": len(signals), "signals": signals}, f, indent=2)


def load_daily_signals(scan_date: str) -> list[dict]:
    """Carga las señales de un día concreto."""
    path = os.path.join(SIGNALS_DIR, f"{scan_date}.json")
    if not os.path.exists(path):
        return []
    with open(path, "r") as f:
        data = json.load(f)
    return data.get("signals", [])


def get_signal_dates() -> list[str]:
    """Lista todas las fechas con señales guardadas."""
    _ensure_dir()
    files = [f.replace(".json", "") for f in os.listdir(SIGNALS_DIR) if f.endswith(".json")]
    return sorted(files, reverse=True)


def get_signal_history(last_n: int = 30) -> list[dict]:
    """Resumen de las últimas N fechas."""
    dates = get_signal_dates()[:last_n]
    summary = []
    for d in dates:
        signals = load_daily_signals(d)
        summary.append({
            "date": d,
            "count": len(signals),
            "tickers": [s.get("Ticker", s.get("ticker", "")) for s in signals[:10]],
        })
    return summary
