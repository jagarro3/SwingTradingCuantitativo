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


def _get_pipeline(strategy: str):
    """Devuelve (add_indicators, generate_signals) según estrategia."""
    if strategy == "canslim":
        from indicators.canslim_indicators import add_canslim_indicators
        from strategy.canslim import generate_signals as gen
        return add_canslim_indicators, gen
    else:
        return add_indicators, generate_signals


def cmd_backtest(args) -> None:
    ticker  = args.ticker.upper()
    start   = args.start
    end     = args.end
    capital = args.capital
    strategy = args.strategy

    strat_label = "CANSLIM" if strategy == "canslim" else "RSI(2) Pullback"
    print(f"\n[Backtest {strat_label}] {ticker}  {start} → {end}  capital={capital:,.0f} €")

    add_ind, gen_sig = _get_pipeline(strategy)

    print("  Descargando datos...")
    df = download_ohlcv(ticker, start, end)

    print("  Calculando indicadores...")
    if strategy == "canslim":
        spy_df = download_ohlcv("SPY", start, end)
        df = add_ind(df, spy_df)
    else:
        df = add_ind(df)

    print("  Generando señales...")
    df = gen_sig(df)

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

    strategy = args.strategy
    add_ind, gen_sig = _get_pipeline(strategy)
    strat_label = "CANSLIM" if strategy == "canslim" else "RSI(2) Pullback"

    end   = date.today().strftime("%Y-%m-%d")
    start = (date.today() - timedelta(days=365)).strftime("%Y-%m-%d")

    print(f"\n[Scanner {strat_label}] Obteniendo universo de acciones...")
    tickers = get_universe(use_finviz=True, strategy=strategy)
    print(f"  {len(tickers)} tickers a analizar")

    # CANSLIM necesita SPY para relative strength
    spy_df = None
    if strategy == "canslim":
        spy_df = download_ohlcv("SPY", start, end)

    signals_found = []

    for i, ticker in enumerate(tickers):
        try:
            df = download_ohlcv(ticker, start, end)
            if strategy == "canslim":
                df = add_ind(df, spy_df)
            else:
                df = add_ind(df)
            df = gen_sig(df)

            last = df.iloc[-1]
            if last["signal"] == 1:
                price = last["Close"]
                atr = last["atr"]
                stop = price - ATR_STOP_MULT * atr
                risk_per_share = price - stop
                shares = int(args.capital * RISK_PER_TRADE / risk_per_share)
                if shares < 1:
                    shares = 1

                if strategy == "canslim":
                    rs = last.get("rel_strength", 0) or 0
                    vr = last.get("vol_ratio", 0) or 0
                    pfh = last.get("pct_from_high", 0) or 0
                    score = last.get("canslim_score", 0) or 0
                    signals_found.append({
                        "ticker":       ticker,
                        "nombre":       "",
                        "close":        round(price, 2),
                        "score":        int(score),
                        "rel_strength": round(rs, 2),
                        "vol_ratio":    round(vr, 1),
                        "pct_from_high": round(pfh, 1),
                        "stop_loss":    round(stop, 2),
                        "acciones":     shares,
                        "coste":        round(shares * price, 2),
                        "riesgo":       round(shares * risk_per_share, 2),
                    })
                else:
                    sma = last[f"sma{200}"]
                    rsi = last["rsi2"]
                    pct_sma = (price / sma - 1) * 100
                    if rsi < 3:
                        pullback = "pullback extremo"
                    elif rsi < 7:
                        pullback = "pullback fuerte"
                    else:
                        pullback = "pullback moderado"
                    signals_found.append({
                        "ticker":       ticker,
                        "nombre":       "",
                        "close":        round(price, 2),
                        "rsi2":         round(rsi, 1),
                        "atr":          round(atr, 2),
                        "stop_loss":    round(stop, 2),
                        "acciones":     shares,
                        "coste":        round(shares * price, 2),
                        "riesgo":       round(shares * risk_per_share, 2),
                        "motivo":       f"RSI(2)={rsi:.1f} ({pullback}), +{pct_sma:.1f}% sobre SMA200",
                    })
        except Exception:
            pass

        if (i + 1) % 50 == 0:
            print(f"  Procesados {i+1}/{len(tickers)} — señales: {len(signals_found)}")

    # Resolver nombres de empresas
    if signals_found:
        from data.sectors import get_names_bulk
        names = get_names_bulk([s["ticker"] for s in signals_found])
        for s in signals_found:
            s["nombre"] = names.get(s["ticker"], "")

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


def cmd_optimize(args) -> None:
    from optimizer.grid_search import run_optimization, print_optimization_results

    print(f"\n[Optimización] {args.ticker}  {args.start} → {args.end}")
    print(f"  Métrica objetivo: {args.metric}")

    def progress(i, total):
        if i % 10 == 0 or i == total:
            print(f"  Combinación {i}/{total}...")

    opt = run_optimization(
        ticker=args.ticker,
        start=args.start,
        end=args.end,
        capital=args.capital,
        metric=args.metric,
        top_n=args.top,
        progress_callback=progress,
    )
    print_optimization_results(opt)


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
    bt.add_argument("--strategy", default="rsi2", choices=["rsi2", "canslim"],
                    help="Estrategia: rsi2 (RSI(2) Pullback) o canslim (CANSLIM)")

    # --- scan ---
    sc = subparsers.add_parser("scan", help="Escanear universo y mostrar señales de hoy")
    sc.add_argument("--capital", default=DEFAULT_CAPITAL, type=float,
                    help=f"Capital disponible en € (default {DEFAULT_CAPITAL:,.0f})")
    sc.add_argument("--alert", action="store_true", help="Enviar alertas por Telegram")
    sc.add_argument("--strategy", default="rsi2", choices=["rsi2", "canslim"],
                    help="Estrategia: rsi2 (RSI(2) Pullback) o canslim (CANSLIM)")

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

    # --- optimize ---
    opt = subparsers.add_parser("optimize", help="Optimizar parámetros por grid search")
    opt.add_argument("--ticker",  default=DEFAULT_TICKER, help="Ticker para optimizar")
    opt.add_argument("--start",   default=DEFAULT_START_DATE, help="Fecha inicio YYYY-MM-DD")
    opt.add_argument("--end",     default=DEFAULT_END_DATE, help="Fecha fin YYYY-MM-DD")
    opt.add_argument("--capital", default=DEFAULT_CAPITAL, type=float, help="Capital inicial")
    opt.add_argument("--metric",  default="sharpe_ratio",
                     choices=["sharpe_ratio", "cagr_pct", "total_return_pct",
                              "profit_factor", "win_rate_pct", "max_drawdown_pct"],
                     help="Métrica objetivo (default: sharpe_ratio)")
    opt.add_argument("--top",     default=20, type=int, help="Top N resultados a mostrar")

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
    elif args.mode == "optimize":
        cmd_optimize(args)
    elif args.mode == "dashboard":
        cmd_dashboard(args)


if __name__ == "__main__":
    main()
