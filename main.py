"""
Entry point del sistema de Swing Trading Cuantitativo.

Modos de uso:
  python main.py --mode backtest                         # un ticker (default AAPL)
  python main.py --mode backtest --ticker MSFT           # ticker concreto
  python main.py --mode scan                             # escanear universo hoy
  python main.py --mode dashboard                        # lanzar Streamlit

Ejemplos:
  python main.py --mode backtest --ticker NVDA --start 2015-01-01 --capital 50000
  python main.py --mode scan
"""

import argparse
import sys
import os
import webbrowser

# Asegurar que el directorio raíz del proyecto está en el path
sys.path.insert(0, os.path.dirname(__file__))

# Cargar variables de entorno desde .env si existe
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
except ImportError:
    pass

from config import (
    DEFAULT_CAPITAL, DEFAULT_START_DATE, DEFAULT_END_DATE, DEFAULT_TICKER,
    ATR_STOP_MULT, RISK_PER_TRADE,
)
from data.downloader import download_ohlcv
from data.universe import get_universe
from indicators.technical import add_indicators
from strategy.momentum import generate_signals
from backtest.engine import run_backtest
from backtest.metrics import compute_metrics, print_metrics
from reports.html_report import generate_report


def cmd_backtest(args) -> None:
    ticker  = args.ticker.upper()
    start   = args.start
    end     = args.end
    capital = args.capital

    print(f"\n[Backtest] {ticker}  {start} → {end}  capital={capital:,.0f} €")

    print("  Descargando datos...")
    df = download_ohlcv(ticker, start, end)

    print("  Calculando indicadores...")
    df = add_indicators(df)

    print("  Generando señales...")
    df = generate_signals(df)

    print("  Ejecutando backtest...")
    result = run_backtest(df, ticker, capital)

    metrics = compute_metrics(result)
    print_metrics(metrics)

    print("\n  Generando reporte HTML...")
    report_path = generate_report(result, df, ticker)
    print(f"  Reporte guardado en: {report_path}")

    if args.open:
        webbrowser.open(f"file://{os.path.abspath(report_path)}")


def cmd_scan(args) -> None:
    """
    Escanea el universo de acciones y muestra las que generan señal de entrada hoy.
    """
    from datetime import date, timedelta
    import pandas as pd

    end   = date.today().strftime("%Y-%m-%d")
    start = (date.today() - timedelta(days=365)).strftime("%Y-%m-%d")

    print(f"\n[Scanner] Obteniendo universo de acciones...")
    tickers = get_universe(use_finviz=True)
    print(f"  {len(tickers)} tickers a analizar")

    signals_found = []

    for i, ticker in enumerate(tickers):
        try:
            df = download_ohlcv(ticker, start, end)
            df = add_indicators(df)
            df = generate_signals(df)

            last = df.iloc[-1]
            if last["signal"] == 1:
                price = last["Close"]
                atr = last["atr"]
                stop = price - ATR_STOP_MULT * atr
                risk_per_share = price - stop
                shares = int(args.capital * RISK_PER_TRADE / risk_per_share)
                if shares < 1:
                    shares = 1
                signals_found.append({
                    "ticker":       ticker,
                    "close":        round(price, 2),
                    "rsi2":         round(last["rsi2"], 1),
                    "atr":          round(atr, 2),
                    "stop_loss":    round(stop, 2),
                    "acciones":     shares,
                    "coste":        round(shares * price, 2),
                    "riesgo":       round(shares * risk_per_share, 2),
                })
        except Exception:
            pass

        if (i + 1) % 50 == 0:
            print(f"  Procesados {i+1}/{len(tickers)} — señales: {len(signals_found)}")

    print(f"\n{'='*55}")
    print(f"  SEÑALES DE ENTRADA HOY ({end}): {len(signals_found)}")
    print(f"{'='*55}")

    if signals_found:
        df_out = pd.DataFrame(signals_found)
        print(df_out.to_string(index=False))

        # Enviar alertas si está configurado
        if args.alert:
            try:
                from alerts.notifier import send_signals
                send_signals(signals_found)
            except Exception as e:
                print(f"  [!] Error enviando alertas: {e}")
    else:
        print("  Ningún ticker cumple los criterios de entrada hoy.")


def cmd_portfolio(args) -> None:
    from portfolio.manager import (
        add_position, check_positions, close_position,
        list_positions, get_history,
    )

    if args.portfolio_cmd == "add":
        add_position(args.ticker, args.entry_price, args.shares, args.date)
    elif args.portfolio_cmd == "check":
        check_positions()
    elif args.portfolio_cmd == "close":
        close_position(args.position_id, args.exit_price, reason=args.reason)
    elif args.portfolio_cmd == "list":
        list_positions()
    elif args.portfolio_cmd == "history":
        get_history()


def cmd_dashboard(_args) -> None:
    import subprocess
    dashboard_path = os.path.join(os.path.dirname(__file__), "dashboard", "app.py")
    print("  Lanzando Streamlit dashboard...")
    subprocess.run(["streamlit", "run", dashboard_path], check=True)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Sistema de Swing Trading Cuantitativo",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    subparsers = parser.add_subparsers(dest="mode", required=True)

    # --- backtest ---
    bt = subparsers.add_parser("backtest", help="Ejecutar backtest sobre un ticker")
    bt.add_argument("--ticker",  default=DEFAULT_TICKER,     help="Símbolo del activo (ej. AAPL)")
    bt.add_argument("--start",   default=DEFAULT_START_DATE, help="Fecha inicio YYYY-MM-DD")
    bt.add_argument("--end",     default=DEFAULT_END_DATE,   help="Fecha fin YYYY-MM-DD")
    bt.add_argument("--capital", default=DEFAULT_CAPITAL, type=float,
                    help=f"Capital inicial en € (default {DEFAULT_CAPITAL:,.0f})")
    bt.add_argument("--open",    action="store_true", help="Abrir reporte HTML en el navegador")

    # --- scan ---
    sc = subparsers.add_parser("scan", help="Escanear universo y mostrar señales de hoy")
    sc.add_argument("--capital", default=DEFAULT_CAPITAL, type=float,
                    help=f"Capital disponible en € (default {DEFAULT_CAPITAL:,.0f})")
    sc.add_argument("--alert", action="store_true", help="Enviar alertas por Telegram")

    # --- portfolio ---
    pf = subparsers.add_parser("portfolio", help="Gestionar posiciones abiertas")
    pf_sub = pf.add_subparsers(dest="portfolio_cmd", required=True)

    pf_add = pf_sub.add_parser("add", help="Registrar nueva posicion")
    pf_add.add_argument("ticker", help="Ticker comprado (ej. OMC)")
    pf_add.add_argument("entry_price", type=float, help="Precio de entrada")
    pf_add.add_argument("shares", type=int, help="Numero de acciones")
    pf_add.add_argument("--date", default=None, help="Fecha de entrada YYYY-MM-DD (default: hoy)")

    pf_sub.add_parser("check", help="Revisar posiciones y obtener recomendaciones")

    pf_close = pf_sub.add_parser("close", help="Cerrar una posicion manualmente")
    pf_close.add_argument("position_id", help="ID de la posicion (ej. OMC-20240315)")
    pf_close.add_argument("exit_price", type=float, help="Precio de salida")
    pf_close.add_argument("--reason", default="manual", help="Motivo de cierre")

    pf_sub.add_parser("list", help="Ver posiciones abiertas")
    pf_sub.add_parser("history", help="Ver historial de posiciones cerradas")

    # --- dashboard ---
    subparsers.add_parser("dashboard", help="Lanzar dashboard Streamlit")

    return parser.parse_args()


def main():
    args = parse_args()

    if args.mode == "backtest":
        cmd_backtest(args)
    elif args.mode == "scan":
        cmd_scan(args)
    elif args.mode == "portfolio":
        cmd_portfolio(args)
    elif args.mode == "dashboard":
        cmd_dashboard(args)


if __name__ == "__main__":
    main()
