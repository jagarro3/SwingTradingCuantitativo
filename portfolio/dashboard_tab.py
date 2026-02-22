"""
Tab de Portfolio para el dashboard Streamlit.
"""

import streamlit as st
import pandas as pd
from datetime import date

from config import MAX_HOLD_DAYS, DEFAULT_COMMISSION_EUR
from portfolio.store import get_open_positions, get_closed_positions
from portfolio.manager import add_position, check_positions, close_position, _download_recent
from data.fx import get_eur_usd


def render_portfolio_tab():
    # --- Tipo de cambio EUR/USD ---
    if "eur_usd_rate" not in st.session_state:
        st.session_state.eur_usd_rate = get_eur_usd()

    eur_usd = st.session_state.eur_usd_rate

    with st.sidebar:
        st.divider()
        st.subheader("💱 Divisa")
        eur_usd = st.number_input(
            "EUR/USD",
            min_value=0.50, max_value=2.00,
            value=eur_usd, step=0.0001, format="%.4f",
            help="Tipo de cambio actual. Se obtiene automáticamente.",
        )
        st.session_state.eur_usd_rate = eur_usd
        st.caption(f"1 EUR = {eur_usd:.4f} USD")

        commission = st.number_input(
            "Comisión/operación (€)",
            min_value=0.0, value=DEFAULT_COMMISSION_EUR, step=0.50, format="%.2f",
            help="Comisión que cobra tu broker por cada operación (compra o venta).",
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
            pnl_eur = pos.pnl_eur(current_price, eur_usd)
            cost_eur = pos.cost_eur(eur_usd)
            cost_usd = pos.shares * pos.entry_price
            days_left = max(0, MAX_HOLD_DAYS - pos.bars_held)

            rows.append({
                "ID": pos.id,
                "Ticker": pos.ticker,
                "Acciones": pos.shares,
                "Entrada": pos.entry_price,
                "Actual": round(current_price, 2),
                "P&L $": round(pnl_usd, 2),
                "P&L €": round(pnl_eur, 2),
                "P&L %": round(pnl_pct, 1),
                "Coste €": round(cost_eur, 2),
                "Comisión €": pos.commission,
                "Stop": pos.stop_loss,
                "Trail": pos.trailing_stop,
                "Dia": f"{pos.bars_held}/{MAX_HOLD_DAYS}",
            })

        df_pos = pd.DataFrame(rows)
        st.dataframe(df_pos, use_container_width=True, hide_index=True)

        total_pnl_usd = sum(r["P&L $"] for r in rows)
        total_pnl_eur = sum(r["P&L €"] for r in rows)
        total_invested_usd = sum(pos.shares * pos.entry_price for pos in open_pos)
        total_invested_eur = sum(r["Coste €"] for r in rows)
        total_commission = sum(pos.commission * 2 for pos in open_pos)

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Invertido", f"€{total_invested_eur:,.0f}", f"${total_invested_usd:,.0f}")
        c2.metric("P&L (USD)", f"${total_pnl_usd:+,.2f}")
        c3.metric("P&L (EUR)", f"€{total_pnl_eur:+,.2f}")
        c4.metric("Comisiones", f"€{total_commission:,.2f}")
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
    st.subheader("Registrar posición")
    with st.form("add_position"):
        col1, col2, col3 = st.columns(3)
        new_ticker = col1.text_input("Ticker", value="").upper()
        new_price = col2.number_input("Precio entrada ($)", min_value=0.01, value=100.0, step=0.01)
        new_shares = col3.number_input("Acciones", min_value=1, value=10, step=1)

        col4, col5, col6 = st.columns(3)
        new_date = col4.date_input("Fecha", value=date.today())
        new_commission = col5.number_input("Comisión (€)", min_value=0.0, value=commission, step=0.50, format="%.2f")
        new_eur_usd = col6.number_input("EUR/USD", min_value=0.50, max_value=2.00, value=eur_usd, step=0.0001, format="%.4f")

        # Preview del coste
        preview_cost_usd = new_price * new_shares
        preview_cost_eur = preview_cost_usd / new_eur_usd if new_eur_usd > 0 else 0
        st.caption(
            f"Coste: ${preview_cost_usd:,.2f} → €{preview_cost_eur:,.2f} "
            f"(+ €{new_commission:.2f} comisión entrada)"
        )

        submitted = st.form_submit_button("Registrar", use_container_width=True)
        if submitted and new_ticker:
            try:
                pos = add_position(
                    new_ticker, new_price, int(new_shares),
                    new_date.strftime("%Y-%m-%d"),
                    commission=new_commission,
                    eur_usd_rate=new_eur_usd,
                )
                cost_eur = pos.cost_eur(new_eur_usd)
                st.success(
                    f"Posición registrada: {pos.id} | "
                    f"Stop: ${pos.stop_loss:.2f} | "
                    f"Coste: €{cost_eur:,.2f} + €{new_commission:.2f} comisión"
                )
                st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")

    # --- Cerrar posicion ---
    if open_pos:
        st.divider()
        st.subheader("Cerrar posición")
        with st.form("close_position"):
            pos_ids = [p.id for p in open_pos]
            selected_id = st.selectbox("Posición", pos_ids)
            col_c1, col_c2 = st.columns(2)
            close_price = col_c1.number_input("Precio de salida ($)", min_value=0.01, value=100.0, step=0.01)
            close_eur_usd = col_c2.number_input("EUR/USD salida", min_value=0.50, max_value=2.00, value=eur_usd, step=0.0001, format="%.4f")

            # Preview P&L
            sel_pos = next((p for p in open_pos if p.id == selected_id), None)
            if sel_pos:
                preview_pnl_usd = (close_price - sel_pos.entry_price) * sel_pos.shares
                preview_pnl_eur = preview_pnl_usd / close_eur_usd - sel_pos.commission * 2
                st.caption(f"P&L estimado: ${preview_pnl_usd:+,.2f} → €{preview_pnl_eur:+,.2f} (neto comisiones)")

            close_btn = st.form_submit_button("Cerrar posición", use_container_width=True)
            if close_btn:
                close_position(selected_id, close_price)
                st.success(f"Posición {selected_id} cerrada a ${close_price:.2f}")
                st.rerun()

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
                    "Comisión €": pos.commission * 2,
                    "EUR/USD": pos.eur_usd_rate,
                    "Motivo": pos.exit_reason,
                })
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

            total_pnl_usd = sum(r["P&L $"] for r in rows)
            total_pnl_eur = sum(r["P&L €"] for r in rows)
            total_commissions = sum(r["Comisión €"] for r in rows)
            winners = sum(1 for r in rows if r["P&L €"] > 0)
            win_rate = winners / len(rows) * 100 if rows else 0
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("P&L total $", f"${total_pnl_usd:+,.2f}")
            c2.metric("P&L total €", f"€{total_pnl_eur:+,.2f}")
            c3.metric("Comisiones", f"€{total_commissions:,.2f}")
            c4.metric("Win rate", f"{win_rate:.0f}%")
