"""
Dashboard interactivo con Streamlit.

Lanzar:
    streamlit run dashboard/app.py

Desde la raíz del proyecto (swing_trader/).
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Cargar .env para Telegram y otros servicios
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))
except ImportError:
    pass

import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd

import json
from datetime import date, timedelta

from config import DEFAULT_START_DATE, DEFAULT_END_DATE, DEFAULT_CAPITAL, ATR_STOP_MULT, RISK_PER_TRADE, MAX_POSITIONS, CACHE_DIR
from data.downloader import download_ohlcv
from data.universe import get_universe
from indicators.technical import add_indicators
from strategy.momentum import generate_signals
from backtest.engine import run_backtest, trades_to_dataframe
from backtest.metrics import compute_metrics


# ---------------------------------------------------------------
# Cache del scanner
# ---------------------------------------------------------------
def _scanner_cache_path(scan_date: str) -> str:
    cache_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), CACHE_DIR)
    os.makedirs(cache_dir, exist_ok=True)
    return os.path.join(cache_dir, f"scanner_{scan_date}.json")


def _load_scanner_cache(scan_date: str, capital: float):
    path = _scanner_cache_path(scan_date)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r") as f:
            data = json.load(f)
        if data.get("capital") != capital:
            return None
        return data["signals"]
    except Exception:
        return None


def _save_scanner_cache(scan_date: str, capital: float, signals: list):
    path = _scanner_cache_path(scan_date)
    with open(path, "w") as f:
        json.dump({"date": scan_date, "capital": capital, "signals": signals}, f, indent=2)


# ---------------------------------------------------------------
# Configuración de página
# ---------------------------------------------------------------
st.set_page_config(
    page_title="Swing Trader Cuantitativo",
    page_icon="📈",
    layout="wide",
)

st.title("📈 Swing Trading Cuantitativo")
st.markdown("Estrategia RSI(2) Trend Pullback + ATR Trailing Stop")

# ---------------------------------------------------------------
# Sidebar: parámetros
# ---------------------------------------------------------------
with st.sidebar:
    st.header("⚙️ Parámetros")

    mode = st.radio("Modo", ["Backtest (un ticker)", "Scanner (universo hoy)", "Portfolio (posiciones)"])

    ticker  = st.text_input("Ticker", value="AAPL").upper()
    start   = st.date_input("Fecha inicio", value=pd.Timestamp(DEFAULT_START_DATE))
    end     = st.date_input("Fecha fin",    value=pd.Timestamp.today())
    capital = st.number_input("Capital inicial", min_value=1_000, value=int(DEFAULT_CAPITAL), step=1_000)

    run_btn = st.button("Ejecutar", type="primary", use_container_width=True)

# ---------------------------------------------------------------
# MODO BACKTEST
# ---------------------------------------------------------------
if mode == "Backtest (un ticker)":
    if run_btn:
        with st.spinner(f"Descargando y analizando {ticker}..."):
            try:
                df = download_ohlcv(ticker, str(start), str(end))
                df = add_indicators(df)
                df = generate_signals(df)
                result = run_backtest(df, ticker, float(capital))
                metrics = compute_metrics(result)
                df_trades = trades_to_dataframe(result.trades)
            except Exception as e:
                st.error(f"Error: {e}")
                st.stop()

        # --- Métricas ---
        st.subheader("Métricas de rendimiento")
        cols = st.columns(9)
        cols[0].metric("Retorno total", f"{metrics['total_return_pct']:.1f}%")
        cols[1].metric("CAGR",          f"{metrics['cagr_pct']:.1f}%")
        cols[2].metric("Sharpe",        f"{metrics['sharpe_ratio']:.2f}")
        cols[3].metric("Max Drawdown",  f"{metrics['max_drawdown_pct']:.1f}%")
        cols[4].metric("Win Rate",      f"{metrics['win_rate_pct']:.0f}%")
        cols[5].metric("Profit Factor", f"{metrics['profit_factor']:.2f}")
        cols[6].metric("Operaciones",   str(metrics['total_trades']))
        cols[7].metric("P&L medio/op",  f"{metrics['avg_pnl_pct']:.2f}%")
        cols[8].metric("Dias medio/op", f"{metrics['avg_bars_held']:.1f}")

        # --- Gráfico de precio ---
        st.subheader(f"Precio y señales — {ticker}")
        fig = make_subplots(
            rows=3, cols=1,
            shared_xaxes=True,
            row_heights=[0.6, 0.2, 0.2],
            vertical_spacing=0.04,
            subplot_titles=["Precio", "RSI(2)", "Volumen"],
        )

        fig.add_trace(go.Candlestick(
            x=df.index, open=df["Open"], high=df["High"],
            low=df["Low"], close=df["Close"], name="OHLCV",
            increasing_line_color="#26a69a", decreasing_line_color="#ef5350",
        ), row=1, col=1)

        fig.add_trace(go.Scatter(x=df.index, y=df["sma200"], name="SMA200",
                                 line=dict(color="orange", width=1)), row=1, col=1)

        entries = df[df["signal"] == 1]
        fig.add_trace(go.Scatter(x=entries.index, y=entries["Low"] * 0.98,
                                 mode="markers",
                                 marker=dict(symbol="triangle-up", size=10, color="lime"),
                                 name="Entrada"), row=1, col=1)

        # RSI(2) con linea de umbral
        fig.add_trace(go.Scatter(x=df.index, y=df["rsi2"], name="RSI(2)",
                                 line=dict(color="yellow", width=1)), row=2, col=1)
        fig.add_hline(y=10, line_dash="dash", line_color="lime", row=2, col=1)

        fig.add_trace(go.Bar(x=df.index, y=df["Volume"], name="Vol",
                             marker_color="rgba(100,120,200,0.4)"), row=3, col=1)

        fig.update_layout(template="plotly_dark", height=700,
                          xaxis_rangeslider_visible=False, showlegend=True)
        st.plotly_chart(fig, use_container_width=True)

        # --- Equity curve ---
        st.subheader("Equity Curve y Drawdown")
        equity = result.equity_curve
        rolling_max = equity.cummax()
        drawdown = (equity - rolling_max) / rolling_max * 100

        fig_eq = make_subplots(rows=2, cols=1, shared_xaxes=True,
                               row_heights=[0.65, 0.35], vertical_spacing=0.05)
        fig_eq.add_trace(go.Scatter(x=equity.index, y=equity.values,
                                    fill="tozeroy", fillcolor="rgba(38,166,154,0.15)",
                                    line=dict(color="#26a69a", width=2), name="Capital"),
                         row=1, col=1)
        fig_eq.add_trace(go.Scatter(x=drawdown.index, y=drawdown.values,
                                    fill="tozeroy", fillcolor="rgba(239,83,80,0.2)",
                                    line=dict(color="#ef5350", width=1), name="Drawdown %"),
                         row=2, col=1)
        fig_eq.update_layout(template="plotly_dark", height=450)
        st.plotly_chart(fig_eq, use_container_width=True)

        # --- Tabla de trades ---
        if not df_trades.empty:
            st.subheader(f"Operaciones ({len(df_trades)})")
            df_show = df_trades.copy()
            df_show["pnl_pct"] = (df_show["pnl_pct"] * 100).round(2)
            df_show["pnl"]     = df_show["pnl"].round(2)
            st.dataframe(df_show, use_container_width=True)
        else:
            st.info("No se registraron operaciones en el periodo.")

# ---------------------------------------------------------------
# MODO SCANNER — resultados persisten en session_state
# ---------------------------------------------------------------
elif mode == "Scanner (universo hoy)":
    today = date.today().strftime("%Y-%m-%d")
    scan_start = (date.today() - timedelta(days=365)).strftime("%Y-%m-%d")

    st.subheader(f"Scanner — {today}")

    # Ejecutar scan fresco cuando se pulsa "Ejecutar"
    if run_btn:
        progress = st.progress(0)
        status   = st.empty()

        with st.spinner("Obteniendo universo de acciones..."):
            tickers = get_universe(use_finviz=True)

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
                        "Ticker":     t,
                        "Precio":     round(price, 2),
                        "RSI(2)":     round(last["rsi2"], 1),
                        "ATR":        round(atr, 2),
                        "Stop Loss":  round(stop, 2),
                        "Acciones":   shares,
                        "Coste":      round(shares * price, 2),
                        "Riesgo":     round(shares * risk_per_share, 2),
                    })
            except Exception:
                pass

            progress.progress((i + 1) / len(tickers))
            status.text(f"Procesando {i+1}/{len(tickers)} — señales: {len(signals_found)}")

        progress.empty()
        status.empty()

        _save_scanner_cache(today, float(capital), signals_found)
        st.session_state.scanner_signals = signals_found
        st.session_state.scanner_capital = float(capital)

    # Auto-cargar de cache si no hay datos en sesión (o capital cambió)
    if ("scanner_signals" not in st.session_state
            or st.session_state.get("scanner_capital") != float(capital)):
        cached = _load_scanner_cache(today, float(capital))
        if cached is not None:
            st.session_state.scanner_signals = cached
            st.session_state.scanner_capital = float(capital)

    # Mostrar resultados
    if "scanner_signals" in st.session_state and st.session_state.get("scanner_capital") == float(capital):
        signals_found = st.session_state.scanner_signals

        if not run_btn:
            st.info(f"Resultados cacheados ({len(signals_found)} señales). Pulsa **Ejecutar** para re-escanear.")

        if signals_found:
            df_signals = pd.DataFrame(signals_found).sort_values("RSI(2)").reset_index(drop=True)
            top = df_signals.head(MAX_POSITIONS)
            resto = df_signals.iloc[MAX_POSITIONS:]

            st.success(f"{len(df_signals)} señales encontradas — TOP {MAX_POSITIONS} mostradas")

            st.subheader(f"TOP {MAX_POSITIONS} — Mejores señales")
            st.dataframe(top, use_container_width=True, hide_index=True)

            if len(resto) > 0:
                with st.expander(f"Ver otras {len(resto)} señales"):
                    st.dataframe(resto, use_container_width=True, hide_index=True)

            # Botón enviar por Telegram
            if st.button("Enviar TOP por Telegram", use_container_width=True):
                try:
                    from alerts.notifier import send_signals
                    top_signals = top.rename(columns={
                        "Ticker": "ticker", "Precio": "close", "RSI(2)": "rsi2",
                        "ATR": "atr", "Stop Loss": "stop_loss",
                        "Acciones": "acciones", "Coste": "coste", "Riesgo": "riesgo",
                    }).to_dict("records")
                    send_signals(top_signals)
                    st.success("Señales enviadas por Telegram")
                except Exception as e:
                    st.error(f"Error enviando Telegram: {e}")
        else:
            st.info("Ningún ticker cumple los criterios de entrada hoy.")
    else:
        st.info("Pulsa **Ejecutar** para escanear el universo de acciones.")

# ---------------------------------------------------------------
# MODO PORTFOLIO
# ---------------------------------------------------------------
elif mode == "Portfolio (posiciones)":
    from portfolio.dashboard_tab import render_portfolio_tab
    render_portfolio_tab()
