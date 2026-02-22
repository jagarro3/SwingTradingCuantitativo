"""
Tab de Portfolio para el dashboard Streamlit.
"""

import streamlit as st
import pandas as pd
from datetime import date

from config import MAX_HOLD_DAYS, DEFAULT_COMMISSION_USD
from portfolio.store import (
    get_open_positions, get_closed_positions,
    delete_position, update_position,
)
from portfolio.manager import add_position, check_positions, close_position, _download_recent
from data.fx import get_usd_eur


def render_portfolio_tab():
    # --- Tipo de cambio USD→EUR ---
    if "usd_eur_rate" not in st.session_state:
        st.session_state.usd_eur_rate = get_usd_eur()

    usd_eur = st.session_state.usd_eur_rate

    with st.sidebar:
        st.divider()
        st.subheader("💱 Divisa")
        usd_eur = st.number_input(
            "USD → EUR",
            min_value=0.30, max_value=1.50,
            value=usd_eur, step=0.000001, format="%.6f",
            help="1 USD = X EUR. Se obtiene automáticamente.",
        )
        st.session_state.usd_eur_rate = usd_eur
        st.caption(f"1 USD = {usd_eur:.6f} EUR")

        commission = st.number_input(
            "Comisión/operación ($)",
            min_value=0.0, value=DEFAULT_COMMISSION_USD, step=0.50, format="%.2f",
            help="Comisión que cobra tu broker por cada operación en USD (compra o venta).",
        )

    open_pos = get_open_positions()
    closed_pos = get_closed_positions()

    # --- Resumen posiciones abiertas ---
    st.subheader(f"Posiciones abiertas ({len(open_pos)})")

    if open_pos:
        rows = []
        for pos in open_pos:
            try:
                df = _download_recent(pos.ticker, days_back=10)
                current_price = df.iloc[-1]["Close"]
            except Exception:
                current_price = pos.entry_price

            pnl_usd = pos.pnl(current_price)
            pnl_pct = pos.pnl_pct(current_price)
            pnl_eur = pos.pnl_eur(current_price, usd_eur)
            cost_eur = pos.cost_eur()  # usa rate de entrada
            days_left = max(0, MAX_HOLD_DAYS - pos.bars_held)

            rows.append({
                "ID": pos.id,
                "Ticker": pos.ticker,
                "Acciones": pos.shares,
                "Entrada $": pos.entry_price,
                "Actual $": round(current_price, 2),
                "Neto $": round(pos.cost_usd(), 2),
                "Neto €": round(cost_eur, 2),
                "P&L $": round(pnl_usd, 2),
                "P&L €": round(pnl_eur, 2),
                "P&L %": round(pnl_pct, 1),
                "Comisión $": pos.commission,
                "USD→EUR": pos.usd_eur_rate,
                "Stop": pos.stop_loss,
                "Trail": pos.trailing_stop,
                "Dia": f"{pos.bars_held}/{MAX_HOLD_DAYS}",
            })

        df_pos = pd.DataFrame(rows)
        st.dataframe(df_pos, use_container_width=True, hide_index=True)

        total_pnl_usd = sum(r["P&L $"] for r in rows)
        total_pnl_eur = sum(r["P&L €"] for r in rows)
        total_neto_usd = sum(r["Neto $"] for r in rows)
        total_neto_eur = sum(r["Neto €"] for r in rows)
        total_commission = sum(pos.commission for pos in open_pos)

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Invertido", f"€{total_neto_eur:,.2f}", f"${total_neto_usd:,.2f}")
        c2.metric("P&L (USD)", f"${total_pnl_usd:+,.2f}")
        c3.metric("P&L (EUR)", f"€{total_pnl_eur:+,.2f}")
        c4.metric("Comisión entrada", f"${total_commission:,.2f}")

        # --- Editar / Eliminar posición abierta ---
        st.divider()
        st.subheader("Gestionar posición")
        pos_ids = [p.id for p in open_pos]
        selected_manage = st.selectbox("Seleccionar posición", pos_ids, key="manage_pos")
        sel_pos = next((p for p in open_pos if p.id == selected_manage), None)

        if sel_pos:
            tab_edit, tab_close, tab_delete = st.tabs(["✏️ Editar", "📤 Cerrar", "🗑️ Eliminar"])

            with tab_edit:
                with st.form("edit_position"):
                    col1, col2, col3 = st.columns(3)
                    edit_price = col1.number_input(
                        "Precio entrada ($)", value=sel_pos.entry_price,
                        min_value=0.01, step=0.01, format="%.2f",
                    )
                    edit_shares = col2.number_input(
                        "Acciones", value=sel_pos.shares,
                        min_value=1, step=1,
                    )
                    edit_stop = col3.number_input(
                        "Stop Loss ($)", value=sel_pos.stop_loss,
                        min_value=0.01, step=0.01, format="%.2f",
                    )

                    col4, col5, col6 = st.columns(3)
                    edit_commission = col4.number_input(
                        "Comisión ($)", value=sel_pos.commission,
                        min_value=0.0, step=0.50, format="%.2f",
                    )
                    edit_usd_eur = col5.number_input(
                        "USD→EUR entrada", value=sel_pos.usd_eur_rate,
                        min_value=0.30, max_value=1.50, step=0.000001, format="%.6f",
                    )
                    edit_trail = col6.number_input(
                        "Trailing Stop ($)", value=sel_pos.trailing_stop,
                        min_value=0.01, step=0.01, format="%.2f",
                    )

                    if st.form_submit_button("Guardar cambios", use_container_width=True):
                        update_position(
                            sel_pos.id,
                            entry_price=edit_price,
                            shares=int(edit_shares),
                            stop_loss=edit_stop,
                            trailing_stop=edit_trail,
                            commission=edit_commission,
                            usd_eur_rate=edit_usd_eur,
                        )
                        st.success(f"Posición {sel_pos.id} actualizada.")
                        st.rerun()

            with tab_close:
                with st.form("close_position"):
                    col_c1, col_c2 = st.columns(2)
                    close_price = col_c1.number_input(
                        "Precio de salida ($)", min_value=0.01, value=sel_pos.entry_price, step=0.01,
                    )
                    close_usd_eur = col_c2.number_input(
                        "USD→EUR salida", min_value=0.30, max_value=1.50,
                        value=usd_eur, step=0.000001, format="%.6f",
                    )

                    preview_pnl_usd = (close_price - sel_pos.entry_price) * sel_pos.shares - sel_pos.commission * 2
                    preview_pnl_eur = preview_pnl_usd * close_usd_eur
                    st.caption(f"P&L estimado: ${preview_pnl_usd:+,.2f} → €{preview_pnl_eur:+,.2f} (neto comisiones)")

                    if st.form_submit_button("Cerrar posición", use_container_width=True):
                        close_position(sel_pos.id, close_price)
                        st.success(f"Posición {sel_pos.id} cerrada a ${close_price:.2f}")
                        st.rerun()

            with tab_delete:
                st.warning(f"⚠️ Eliminar **{sel_pos.id}** — {sel_pos.ticker} "
                           f"({sel_pos.shares} acc @ ${sel_pos.entry_price:.2f})")
                st.caption("Esta acción no se puede deshacer.")
                if st.button("Eliminar posición", type="primary", use_container_width=True, key="delete_open"):
                    delete_position(sel_pos.id)
                    st.success(f"Posición {sel_pos.id} eliminada.")
                    st.rerun()
    else:
        st.info("No hay posiciones abiertas.")

    # --- Revision diaria ---
    st.divider()
    if st.button("Revisión diaria", type="primary", use_container_width=True):
        if not open_pos:
            st.warning("No hay posiciones que revisar.")
        else:
            with st.spinner("Descargando datos y revisando posiciones..."):
                results = check_positions()

            for r in results:
                if r["action"] == "CLOSE":
                    st.error(f"**{r['ticker']}** — CERRAR: {r['detail']} | P&L: ${r['pnl']:+.2f} ({r['pnl_pct']:+.1f}%)")
                elif r["action"] == "UPDATE STOP":
                    st.warning(f"**{r['ticker']}** — {r['detail']}")
                else:
                    st.success(f"**{r['ticker']}** — HOLD | P&L: ${r['pnl']:+.2f} ({r['pnl_pct']:+.1f}%)")

    # --- Añadir posicion ---
    st.divider()
    st.subheader("Registrar posición")
    with st.form("add_position"):
        col1, col2, col3 = st.columns(3)
        new_ticker = col1.text_input("Ticker", value="").upper()
        new_price = col2.number_input("Precio entrada ($)", min_value=0.01, value=100.0, step=0.01)
        new_shares = col3.number_input("Acciones", min_value=1, value=10, step=1)

        col4, col5, col6 = st.columns(3)
        new_date = col4.date_input("Fecha", value=date.today())
        new_commission = col5.number_input("Comisión ($)", min_value=0.0, value=commission, step=0.50, format="%.2f")
        new_usd_eur = col6.number_input("USD→EUR", min_value=0.30, max_value=1.50, value=usd_eur, step=0.000001, format="%.6f")

        preview_cost_usd = new_price * new_shares + new_commission
        preview_cost_eur = preview_cost_usd * new_usd_eur
        st.caption(
            f"Importe neto: ${preview_cost_usd:,.2f} "
            f"(${new_price * new_shares:,.2f} + ${new_commission:.2f} comisión) "
            f"→ €{preview_cost_eur:,.2f}"
        )

        submitted = st.form_submit_button("Registrar", use_container_width=True)
        if submitted and new_ticker:
            try:
                pos = add_position(
                    new_ticker, new_price, int(new_shares),
                    new_date.strftime("%Y-%m-%d"),
                    commission=new_commission,
                    usd_eur_rate=new_usd_eur,
                )
                cost_eur = pos.cost_eur()
                st.success(
                    f"Posición registrada: {pos.id} | "
                    f"Stop: ${pos.stop_loss:.2f} | "
                    f"Importe neto: €{cost_eur:,.2f}"
                )
                st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")

    # --- Historial ---
    if closed_pos:
        st.divider()
        with st.expander(f"Historial ({len(closed_pos)} operaciones)"):
            rows = []
            for pos in sorted(closed_pos, key=lambda p: p.exit_date or "", reverse=True):
                pnl_usd = pos.pnl(pos.exit_price)
                pnl_eur = pos.pnl_eur(pos.exit_price)
                pnl_pct = pos.pnl_pct(pos.exit_price)
                rows.append({
                    "ID": pos.id,
                    "Entrada": f"{pos.entry_date} @ ${pos.entry_price:.2f}",
                    "Salida": f"{pos.exit_date} @ ${pos.exit_price:.2f}",
                    "Dias": pos.bars_held,
                    "P&L $": round(pnl_usd, 2),
                    "P&L €": round(pnl_eur, 2),
                    "P&L %": round(pnl_pct, 1),
                    "Comisión $": pos.commission * 2,
                    "USD→EUR": pos.usd_eur_rate,
                    "Motivo": pos.exit_reason,
                })
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

            total_pnl_usd = sum(r["P&L $"] for r in rows)
            total_pnl_eur = sum(r["P&L €"] for r in rows)
            total_commissions = sum(r["Comisión $"] for r in rows)
            winners = sum(1 for r in rows if r["P&L €"] > 0)
            win_rate = winners / len(rows) * 100 if rows else 0
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("P&L total $", f"${total_pnl_usd:+,.2f}")
            c2.metric("P&L total €", f"€{total_pnl_eur:+,.2f}")
            c3.metric("Comisiones", f"${total_commissions:,.2f}")
            c4.metric("Win rate", f"{win_rate:.0f}%")

            # --- Eliminar del historial ---
            st.divider()
            closed_ids = [r["ID"] for r in rows]
            col_h1, col_h2 = st.columns([3, 1])
            selected_hist = col_h1.selectbox("Seleccionar operación", closed_ids, key="hist_pos")
            if col_h2.button("Eliminar", key="delete_hist", use_container_width=True):
                delete_position(selected_hist)
                st.success(f"Operación {selected_hist} eliminada del historial.")
                st.rerun()
