"""
Genera un reporte HTML interactivo con Plotly.
Incluye: equity curve, drawdown, tabla de trades y resumen de métricas.
"""

import os
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from backtest.engine import BacktestResult, trades_to_dataframe
from backtest.metrics import compute_metrics


def generate_report(
    result: BacktestResult,
    df_signals: pd.DataFrame,
    ticker: str,
    output_dir: str = "reports/output",
) -> str:
    """
    Genera un archivo HTML con el reporte completo del backtest.

    Args:
        result: BacktestResult con trades y equity curve
        df_signals: DataFrame con indicadores y señales
        ticker: nombre del activo
        output_dir: carpeta donde guardar el HTML

    Returns:
        Ruta al archivo HTML generado
    """
    os.makedirs(output_dir, exist_ok=True)
    metrics = compute_metrics(result)
    df_trades = trades_to_dataframe(result.trades)
    equity = result.equity_curve

    # --- Drawdown series ---
    rolling_max = equity.cummax()
    drawdown = (equity - rolling_max) / rolling_max * 100

    # ---------------------------------------------------------------
    # Figura 1: Precio + RSI(2) + Volumen
    # ---------------------------------------------------------------
    fig_price = make_subplots(
        rows=3, cols=1,
        shared_xaxes=True,
        row_heights=[0.6, 0.2, 0.2],
        vertical_spacing=0.04,
        subplot_titles=[f"{ticker} — Precio y señales", "RSI(2)", "Volumen"],
    )

    fig_price.add_trace(go.Candlestick(
        x=df_signals.index,
        open=df_signals["Open"], high=df_signals["High"],
        low=df_signals["Low"],  close=df_signals["Close"],
        name="OHLCV",
        increasing_line_color="#26a69a",
        decreasing_line_color="#ef5350",
    ), row=1, col=1)

    fig_price.add_trace(go.Scatter(
        x=df_signals.index, y=df_signals["sma200"],
        name="SMA 200", line=dict(color="orange", width=1),
    ), row=1, col=1)

    # Señales de entrada
    entries = df_signals[df_signals["signal"] == 1]
    fig_price.add_trace(go.Scatter(
        x=entries.index, y=entries["Low"] * 0.98,
        mode="markers",
        marker=dict(symbol="triangle-up", size=10, color="lime"),
        name="Entrada",
    ), row=1, col=1)

    # Marcadores de salida (desde los trades reales)
    if not df_trades.empty:
        exit_colors = {
            "stop_loss": "red", "trailing_stop": "orange",
            "time_stop": "yellow", "end_of_period": "gray",
        }
        for _, trade in df_trades.iterrows():
            color = exit_colors.get(trade["exit_reason"], "red")
            fig_price.add_trace(go.Scatter(
                x=[trade["exit_date"]],
                y=[trade["exit_price"] * 1.02],
                mode="markers",
                marker=dict(symbol="triangle-down", size=10, color=color),
                name=trade["exit_reason"],
                showlegend=False,
            ), row=1, col=1)

    # RSI(2)
    fig_price.add_trace(go.Scatter(
        x=df_signals.index, y=df_signals["rsi2"],
        name="RSI(2)", line=dict(color="yellow", width=1),
    ), row=2, col=1)
    fig_price.add_hline(y=10, line_dash="dash", line_color="lime", row=2, col=1)

    # Volumen
    fig_price.add_trace(go.Bar(
        x=df_signals.index, y=df_signals["Volume"],
        name="Volumen", marker_color="rgba(100,120,200,0.4)",
    ), row=3, col=1)

    fig_price.update_layout(
        template="plotly_dark",
        height=700,
        xaxis_rangeslider_visible=False,
        showlegend=True,
    )

    # ---------------------------------------------------------------
    # Figura 2: Equity curve + Drawdown
    # ---------------------------------------------------------------
    fig_equity = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        row_heights=[0.65, 0.35],
        vertical_spacing=0.05,
        subplot_titles=["Equity Curve", "Drawdown (%)"],
    )

    fig_equity.add_trace(go.Scatter(
        x=equity.index, y=equity.values,
        fill="tozeroy",
        fillcolor="rgba(38,166,154,0.15)",
        line=dict(color="#26a69a", width=2),
        name="Capital",
    ), row=1, col=1)

    fig_equity.add_trace(go.Scatter(
        x=drawdown.index, y=drawdown.values,
        fill="tozeroy",
        fillcolor="rgba(239,83,80,0.2)",
        line=dict(color="#ef5350", width=1),
        name="Drawdown %",
    ), row=2, col=1)

    fig_equity.update_layout(template="plotly_dark", height=500, showlegend=True)

    # ---------------------------------------------------------------
    # Tabla de trades
    # ---------------------------------------------------------------
    if not df_trades.empty:
        df_display = df_trades[[
            "entry_date", "exit_date", "entry_price", "exit_price",
            "shares", "bars_held", "pnl", "pnl_pct", "exit_reason",
        ]].copy()
        df_display["pnl"]     = df_display["pnl"].round(2)
        df_display["pnl_pct"] = (df_display["pnl_pct"] * 100).round(2)
        df_display.columns = [
            "Entrada", "Salida", "Precio entrada", "Precio salida",
            "Acciones", "Dias", "P&L", "P&L (%)", "Motivo salida",
        ]

        colors = ["rgba(38,166,154,0.3)" if v >= 0 else "rgba(239,83,80,0.3)"
                  for v in df_trades["pnl"]]

        fig_table = go.Figure(data=[go.Table(
            header=dict(
                values=list(df_display.columns),
                fill_color="#1e2130",
                font=dict(color="white", size=11),
                align="left",
            ),
            cells=dict(
                values=[df_display[c] for c in df_display.columns],
                fill_color=[colors] * len(df_display.columns),
                font=dict(color="white", size=10),
                align="left",
            ),
        )])
        fig_table.update_layout(template="plotly_dark", height=400)
        table_html = fig_table.to_html(full_html=False, include_plotlyjs=False)
    else:
        table_html = "<p style='color:gray'>Sin operaciones en el periodo.</p>"

    # ---------------------------------------------------------------
    # Tarjetas de métricas
    # ---------------------------------------------------------------
    def metric_card(label: str, value: str, color: str = "#26a69a") -> str:
        return f"""
        <div style="display:inline-block;background:#1e2130;border-radius:8px;
                    padding:12px 20px;margin:6px;min-width:140px;text-align:center;">
          <div style="color:#aaa;font-size:11px">{label}</div>
          <div style="color:{color};font-size:22px;font-weight:bold">{value}</div>
        </div>"""

    dd_color = "#ef5350" if metrics["max_drawdown_pct"] < -20 else "#ffa726"
    metrics_html = (
        metric_card("Retorno total", f"{metrics['total_return_pct']:.1f}%")
        + metric_card("CAGR", f"{metrics['cagr_pct']:.1f}%")
        + metric_card("Sharpe", f"{metrics['sharpe_ratio']:.2f}")
        + metric_card("Max Drawdown", f"{metrics['max_drawdown_pct']:.1f}%", dd_color)
        + metric_card("Win Rate", f"{metrics['win_rate_pct']:.0f}%")
        + metric_card("Profit Factor", f"{metrics['profit_factor']:.2f}")
        + metric_card("Operaciones", str(metrics["total_trades"]))
        + metric_card("P&L medio/op", f"{metrics['avg_pnl_pct']:.2f}%")
        + metric_card("Dias medio/op", f"{metrics['avg_bars_held']:.1f}")
    )

    # ---------------------------------------------------------------
    # HTML final
    # ---------------------------------------------------------------
    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <title>Backtest — {ticker}</title>
  <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
  <style>
    body {{ background:#13151f; color:#e0e0e0; font-family:Arial,sans-serif; padding:20px; }}
    h1 {{ color:#26a69a; }} h2 {{ color:#aaa; font-weight:normal; }}
  </style>
</head>
<body>
  <h1>Backtest: {ticker}</h1>
  <p style="color:#888">Estrategia RSI(2) Trend Pullback + ATR Trailing Stop</p>
  <h2>Rendimiento</h2>
  <div>{metrics_html}</div>
  <h2>Precio y señales</h2>
  {fig_price.to_html(full_html=False, include_plotlyjs=False)}
  <h2>Equity Curve y Drawdown</h2>
  {fig_equity.to_html(full_html=False, include_plotlyjs=False)}
  <h2>Operaciones</h2>
  {table_html}
</body>
</html>"""

    out_path = os.path.join(output_dir, f"report_{ticker}.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)

    return out_path
