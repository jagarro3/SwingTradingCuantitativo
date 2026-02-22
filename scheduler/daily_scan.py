"""
Script de automatización: ejecutar scan diario y enviar alertas por Telegram.

Uso manual:
    python scheduler/daily_scan.py

Programar en Windows Task Scheduler o cron:
    # Windows (Task Scheduler): ejecutar a las 22:00 L-V
    # Acción: python E:/Proyectos/swing_trader/scheduler/daily_scan.py

    # Linux/Mac (crontab):
    # 0 22 * * 1-5 cd /path/to/swing_trader && python scheduler/daily_scan.py
"""

import sys
import os

# Asegurar path del proyecto
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Cargar .env
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))
except ImportError:
    pass

from datetime import date, timedelta
from config import ATR_STOP_MULT, RISK_PER_TRADE, DEFAULT_CAPITAL, MAX_POSITIONS
from data.downloader import download_ohlcv
from data.universe import get_universe
from data.market_filter import is_bull_market, get_market_status
from indicators.technical import add_indicators
from strategy.momentum import generate_signals
from alerts.notifier import send_message, send_signals
from signals.history import save_daily_signals


def run_daily_scan(capital: float = DEFAULT_CAPITAL):
    today = date.today().strftime("%Y-%m-%d")
    scan_start = (date.today() - timedelta(days=365)).strftime("%Y-%m-%d")

    print(f"\n[Daily Scan] {today}")

    # Filtro de mercado
    market = get_market_status()
    if not market.get("bull_market", True):
        msg = (
            f"🔴 *MERCADO BAJISTA*\n\n"
            f"SPY: `{market.get('close', '?')}` < SMA200: `{market.get('sma200', '?')}`\n"
            f"({market.get('pct_above_sma', '?')}% bajo SMA200)\n\n"
            f"No se generan señales hoy."
        )
        print(f"  Bear market detectado. Sin señales.")
        send_message(msg)
        save_daily_signals([], today)
        return

    print(f"  Bull market OK (SPY {market.get('pct_above_sma', '?')}% sobre SMA200)")

    # Obtener universo
    print("  Obteniendo universo...")
    tickers = get_universe(use_finviz=True)
    print(f"  {len(tickers)} tickers a analizar")

    # Escanear
    signals_found = []
    for i, t in enumerate(tickers):
        try:
            df = download_ohlcv(t, scan_start, today)
            df = add_indicators(df)
            df = generate_signals(df)
            last = df.iloc[-1]
            if last["signal"] == 1:
                price = last["Close"]
                atr = last["atr"]
                stop = price - ATR_STOP_MULT * atr
                risk_per_share = price - stop
                shares = int(capital * RISK_PER_TRADE / risk_per_share)
                if shares < 1:
                    shares = 1
                signals_found.append({
                    "ticker": t,
                    "close": round(price, 2),
                    "rsi2": round(last["rsi2"], 1),
                    "atr": round(atr, 2),
                    "stop_loss": round(stop, 2),
                    "acciones": shares,
                    "coste": round(shares * price, 2),
                    "riesgo": round(shares * risk_per_share, 2),
                })
        except Exception:
            pass

        if (i + 1) % 100 == 0:
            print(f"  {i+1}/{len(tickers)} procesados — {len(signals_found)} señales")

    # Guardar historial
    save_daily_signals(signals_found, today)

    # Ordenar y limitar a TOP
    signals_found.sort(key=lambda s: s["rsi2"])
    top = signals_found[:MAX_POSITIONS]

    print(f"\n  {len(signals_found)} señales encontradas — TOP {MAX_POSITIONS}:")
    for s in top:
        print(f"    {s['ticker']:6s}  RSI={s['rsi2']:.1f}  ${s['close']:.2f}  {s['acciones']} acc")

    # Enviar por Telegram
    if top:
        send_signals(top)
        print(f"\n  Alertas enviadas por Telegram.")
    else:
        send_message(f"📋 *Scan {today}*\n\nNo hay señales de entrada hoy.")
        print(f"\n  Sin señales. Notificación enviada.")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Scan diario automatizado")
    parser.add_argument("--capital", type=float, default=DEFAULT_CAPITAL)
    args = parser.parse_args()
    run_daily_scan(args.capital)
