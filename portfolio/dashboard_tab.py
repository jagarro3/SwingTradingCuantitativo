"""
Tab de Portfolio para el dashboard Streamlit.
"""

import streamlit as st
import pandas as pd
from datetime import date

from config import MAX_HOLD_DAYS
from portfolio.store import get_open_positions, get_closed_positions
from portfolio.manager import add_position, check_positions, close_position, _download_recent


def render_portfolio_tab():
    open_pos = get_open_positions()
    closed_pos = get_closed_positions()

    # --- Resumen ---
    st.subheader(f"Posiciones abiertas ({len(open_pos)})")

    if open_pos:
        rows = []
        for pos in open_pos:
            try:
                df = _download_recent(pos.ticker, days_back=10)
                current_price = df.iloc[-1]["Close"]
            except Exception:
                current_price = pos.entry_price

            pnl_val = pos.pnl(current_price)
            pnl_pct = pos.pnl_pct(current_price)
            days_left = max(0, MAX_HOLD_DAYS - pos.bars_held)

            rows.append({
                "ID": pos.id,
                "Ticker": pos.ticker,
                "Acciones": pos.shares,
                "Entrada": pos.entry_price,
                "Actual": round(current_price, 2),
                "P&L": round(pnl_val, 2),
                "P&L %": round(pnl_pct, 1),
                "Stop": pos.stop_loss,
                "Trail": pos.trailing_stop,
                "Dia": f"{pos.bars_held}/{MAX_HOLD_DAYS}",
                "Restantes": days_left,
            })

        df_pos = pd.DataFrame(rows)
        st.dataframe(df_pos, use_container_width=True, hide_index=True)

        total_pnl = sum(r["P&L"] for r in rows)
        total_invested = sum(pos.shares * pos.entry_price for pos in open_pos)
        c1, c2, c3 = st.columns(3)
        c1.metric("Posiciones", len(open_pos))
        c2.metric("Total invertido", f"{total_invested:,.2f}")
        c3.metric("P&L total", f"{total_pnl:+,.2f}")
    else:
        st.info("No hay posiciones abiertas.")

    # --- Revision diaria ---
    st.divider()
    if st.button("Revision diaria", type="primary", use_container_width=True):
        if not open_pos:
            st.warning("No hay posiciones que revisar.")
        else:
            with st.spinner("Descargando datos y revisando posiciones..."):
                results = check_positions()

            for r in results:
                if r["action"] == "CLOSE":
                    st.error(f"**{r['ticker']}** — CERRAR: {r['detail']} | P&L: {r['pnl']:+.2f} ({r['pnl_pct']:+.1f}%)")
                elif r["action"] == "UPDATE STOP":
                    st.warning(f"**{r['ticker']}** — {r['detail']}")
                else:
                    st.success(f"**{r['ticker']}** — HOLD | P&L: {r['pnl']:+.2f} ({r['pnl_pct']:+.1f}%)")

    # --- Añadir posicion ---
    st.divider()
    st.subheader("Registrar posicion")
    with st.form("add_position"):
        col1, col2, col3, col4 = st.columns(4)
        new_ticker = col1.text_input("Ticker", value="").upper()
        new_price = col2.number_input("Precio entrada", min_value=0.01, value=100.0, step=0.01)
        new_shares = col3.number_input("Acciones", min_value=1, value=10, step=1)
        new_date = col4.date_input("Fecha", value=date.today())

        submitted = st.form_submit_button("Registrar", use_container_width=True)
        if submitted and new_ticker:
            try:
                pos = add_position(new_ticker, new_price, int(new_shares), new_date.strftime("%Y-%m-%d"))
                st.success(f"Posicion registrada: {pos.id} | Stop: {pos.stop_loss:.2f}")
                st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")

    # --- Cerrar posicion ---
    if open_pos:
        st.divider()
        st.subheader("Cerrar posicion")
        with st.form("close_position"):
            pos_ids = [p.id for p in open_pos]
            selected_id = st.selectbox("Posicion", pos_ids)
            close_price = st.number_input("Precio de salida", min_value=0.01, value=100.0, step=0.01)
            close_btn = st.form_submit_button("Cerrar posicion", use_container_width=True)
            if close_btn:
                close_position(selected_id, close_price)
                st.success(f"Posicion {selected_id} cerrada a {close_price:.2f}")
                st.rerun()

    # --- Historial ---
    if closed_pos:
        st.divider()
        with st.expander(f"Historial ({len(closed_pos)} operaciones)"):
            rows = []
            for pos in sorted(closed_pos, key=lambda p: p.exit_date or "", reverse=True):
                pnl_val = pos.pnl(pos.exit_price)
                pnl_pct = pos.pnl_pct(pos.exit_price)
                rows.append({
                    "ID": pos.id,
                    "Entrada": f"{pos.entry_date} @ {pos.entry_price:.2f}",
                    "Salida": f"{pos.exit_date} @ {pos.exit_price:.2f}",
                    "Dias": pos.bars_held,
                    "P&L": round(pnl_val, 2),
                    "P&L %": round(pnl_pct, 1),
                    "Motivo": pos.exit_reason,
                })
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

            total_pnl = sum(r["P&L"] for r in rows)
            winners = sum(1 for r in rows if r["P&L"] > 0)
            win_rate = winners / len(rows) * 100 if rows else 0
            c1, c2 = st.columns(2)
            c1.metric("P&L total", f"{total_pnl:+,.2f}")
            c2.metric("Win rate", f"{win_rate:.0f}%")
