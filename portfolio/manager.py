"""
Gestor de posiciones: añadir, revisar, cerrar, listar e historial.
Replica la lógica de salida del backtest engine con datos en vivo.
"""

from datetime import date, timedelta
from typing import Optional
import pandas as pd

from config import (
    ATR_STOP_MULT, ATR_TRAIL_MULT, ATR_TRAIL_TRIGGER, MAX_HOLD_DAYS,
)
from data.downloader import download_ohlcv
from indicators.technical import add_indicators
from portfolio.models import Position
from portfolio.store import load_positions, save_positions, get_open_positions, get_closed_positions


def _download_recent(ticker: str, days_back: int = 60) -> pd.DataFrame:
    end = (date.today() + timedelta(days=1)).strftime("%Y-%m-%d")
    start = (date.today() - timedelta(days=days_back)).strftime("%Y-%m-%d")
    df = download_ohlcv(ticker, start, end, force=True)
    return add_indicators(df)


def _generate_id(ticker: str, entry_date: str, existing: list[Position]) -> str:
    base_id = f"{ticker}-{entry_date.replace('-', '')}"
    existing_ids = {p.id for p in existing}
    if base_id not in existing_ids:
        return base_id
    i = 2
    while f"{base_id}-{i}" in existing_ids:
        i += 1
    return f"{base_id}-{i}"


def _replay_bars(position: Position, df: pd.DataFrame) -> dict:
    """
    Reproduce barras desde last_checked hasta hoy.
    Misma lógica que backtest/engine.py líneas 76-122.
    """
    start_from = pd.Timestamp(position.last_checked or position.entry_date)
    new_bars = df[df.index > start_from]

    old_trailing = position.trailing_stop
    action = "HOLD"
    detail = ""

    for bar_date, row in new_bars.iterrows():
        close = row["Close"]
        low = row["Low"]
        atr = row["atr"]
        position.bars_held += 1

        # 1. Stop-loss fijo
        if low <= position.stop_loss:
            position.status = "closed"
            position.exit_date = bar_date.strftime("%Y-%m-%d")
            position.exit_price = position.stop_loss
            position.exit_reason = "stop_loss"
            position.last_checked = bar_date.strftime("%Y-%m-%d")
            return {
                "action": "CLOSE",
                "reason": "stop_loss",
                "detail": f"stop-loss alcanzado en {position.stop_loss:.2f}",
                "exit_price": position.stop_loss,
                "exit_date": position.exit_date,
            }

        # 2. Trailing stop
        if low <= position.trailing_stop and position.trailing_stop > position.stop_loss:
            position.status = "closed"
            position.exit_date = bar_date.strftime("%Y-%m-%d")
            position.exit_price = position.trailing_stop
            position.exit_reason = "trailing_stop"
            position.last_checked = bar_date.strftime("%Y-%m-%d")
            return {
                "action": "CLOSE",
                "reason": "trailing_stop",
                "detail": f"trailing stop alcanzado en {position.trailing_stop:.2f}",
                "exit_price": position.trailing_stop,
                "exit_date": position.exit_date,
            }

        # 3. Time stop
        if position.bars_held >= MAX_HOLD_DAYS:
            position.status = "closed"
            position.exit_date = bar_date.strftime("%Y-%m-%d")
            position.exit_price = close
            position.exit_reason = "time_stop"
            position.last_checked = bar_date.strftime("%Y-%m-%d")
            return {
                "action": "CLOSE",
                "reason": "time_stop",
                "detail": f"time stop ({MAX_HOLD_DAYS} dias), cierre en {close:.2f}",
                "exit_price": close,
                "exit_date": position.exit_date,
            }

        # 4. Actualizar trailing
        if close > position.highest_close:
            position.highest_close = close

        unrealized_gain = position.highest_close - position.entry_price
        if not pd.isna(atr) and atr > 0 and unrealized_gain >= ATR_TRAIL_TRIGGER * atr:
            new_trail = position.highest_close - ATR_TRAIL_MULT * atr
            if new_trail > position.trailing_stop:
                position.trailing_stop = new_trail

        position.last_checked = bar_date.strftime("%Y-%m-%d")

    # No saltó ningún stop
    if position.trailing_stop > old_trailing:
        action = "UPDATE STOP"
        detail = f"mover stop de {old_trailing:.2f} a {position.trailing_stop:.2f}"
    else:
        detail = "sin accion necesaria"

    return {"action": action, "detail": detail}


# ---------------------------------------------------------------
# Funciones públicas
# ---------------------------------------------------------------

def add_position(ticker: str, entry_price: float, shares: int,
                 entry_date: Optional[str] = None,
                 commission: float = 0.0,
                 usd_eur_rate: float = 0.85) -> Position:
    ticker = ticker.upper()
    if entry_date is None:
        entry_date = date.today().strftime("%Y-%m-%d")

    # Descargar datos para obtener ATR del día de entrada
    start = (pd.Timestamp(entry_date) - timedelta(days=60)).strftime("%Y-%m-%d")
    end = (pd.Timestamp(entry_date) + timedelta(days=1)).strftime("%Y-%m-%d")
    df = download_ohlcv(ticker, start, end, force=True)
    df = add_indicators(df)

    # Buscar la barra más cercana a entry_date
    entry_ts = pd.Timestamp(entry_date)
    if entry_ts in df.index:
        atr = df.loc[entry_ts, "atr"]
    else:
        atr = df.iloc[-1]["atr"]

    if pd.isna(atr) or atr <= 0:
        raise ValueError(f"No se pudo calcular ATR para {ticker} en {entry_date}")

    stop_loss = entry_price - ATR_STOP_MULT * atr

    positions = load_positions()
    pos_id = _generate_id(ticker, entry_date, positions)

    pos = Position(
        id=pos_id,
        ticker=ticker,
        entry_date=entry_date,
        entry_price=entry_price,
        shares=shares,
        atr_at_entry=round(atr, 2),
        stop_loss=round(stop_loss, 2),
        trailing_stop=round(stop_loss, 2),
        highest_close=entry_price,
        last_checked=entry_date,
        commission=commission,
        usd_eur_rate=usd_eur_rate,
    )

    positions.append(pos)
    save_positions(positions)

    print(f"\n  Posicion registrada: {pos.id}")
    print(f"  {ticker} | {shares} acc @ {entry_price:.2f}")
    print(f"  ATR: {atr:.2f} | Stop: {stop_loss:.2f}")
    return pos


def check_positions() -> list[dict]:
    positions = load_positions()
    open_positions = [p for p in positions if p.status == "open"]

    if not open_positions:
        print("\n  No hay posiciones abiertas.")
        return []

    today_str = date.today().strftime("%Y-%m-%d")
    print(f"\n{'='*55}")
    print(f"  REVISION DE POSICIONES ({today_str})")
    print(f"{'='*55}")

    results = []
    for pos in open_positions:
        try:
            df = _download_recent(pos.ticker)
            last_bar = df.iloc[-1]
            current_price = last_bar["Close"]
            market_date = df.index[-1].strftime("%Y-%m-%d")

            result = _replay_bars(pos, df)

            pnl_price = pos.exit_price if pos.status == "closed" else current_price
            pnl_val = pos.pnl(pnl_price)
            pnl_pct = pos.pnl_pct(pnl_price)
            days_left = max(0, MAX_HOLD_DAYS - pos.bars_held)

            print(f"\n  {pos.ticker} ({pos.shares} acc @ {pos.entry_price:.2f}) | Dia {pos.bars_held}/{MAX_HOLD_DAYS}")
            print(f"    Cierre: {current_price:.2f} | P&L: {pnl_val:+.2f} ({pnl_pct:+.1f}%)")
            print(f"    Stop fijo: {pos.stop_loss:.2f} | Trailing: {pos.trailing_stop:.2f}")

            if result["action"] == "CLOSE":
                print(f"    >> CLOSE: {result['detail']}")
                print(f"    >> P&L final: {pos.pnl(pos.exit_price):+.2f} ({pos.pnl_pct(pos.exit_price):+.1f}%)")
            elif result["action"] == "UPDATE STOP":
                print(f"    >> UPDATE STOP: {result['detail']}")
            else:
                print(f"    >> HOLD: {result['detail']}")

            result.update({
                "position_id": pos.id,
                "ticker": pos.ticker,
                "close": current_price,
                "pnl": round(pnl_val, 2),
                "pnl_pct": round(pnl_pct, 2),
                "bars_held": pos.bars_held,
                "days_remaining": days_left,
            })
            results.append(result)

        except Exception as e:
            print(f"\n  {pos.ticker}: ERROR — {e}")

    save_positions(positions)
    return results


def close_position(position_id: str, exit_price: float,
                   exit_date: Optional[str] = None,
                   reason: str = "manual") -> None:
    positions = load_positions()
    found = False
    for pos in positions:
        if pos.id == position_id and pos.status == "open":
            pos.status = "closed"
            pos.exit_price = exit_price
            pos.exit_date = exit_date or date.today().strftime("%Y-%m-%d")
            pos.exit_reason = reason
            found = True

            pnl_val = pos.pnl(exit_price)
            pnl_pct = pos.pnl_pct(exit_price)
            print(f"\n  Posicion cerrada: {pos.id}")
            print(f"  {pos.ticker} | {pos.shares} acc")
            print(f"  Entrada: {pos.entry_price:.2f} -> Salida: {exit_price:.2f}")
            print(f"  P&L: {pnl_val:+.2f} ({pnl_pct:+.1f}%)")
            print(f"  Motivo: {reason}")
            break

    if not found:
        print(f"\n  [!] Posicion '{position_id}' no encontrada o ya cerrada.")
        return

    save_positions(positions)


def list_positions() -> None:
    open_pos = get_open_positions()
    if not open_pos:
        print("\n  No hay posiciones abiertas.")
        return

    print(f"\n{'='*65}")
    print(f"  POSICIONES ABIERTAS ({len(open_pos)})")
    print(f"{'='*65}")

    total_invested = 0
    total_pnl = 0

    for pos in open_pos:
        try:
            df = _download_recent(pos.ticker, days_back=10)
            current_price = df.iloc[-1]["Close"]
        except Exception:
            current_price = pos.entry_price

        pnl_val = pos.pnl(current_price)
        pnl_pct = pos.pnl_pct(current_price)
        invested = pos.shares * pos.entry_price
        days_left = max(0, MAX_HOLD_DAYS - pos.bars_held)
        total_invested += invested
        total_pnl += pnl_val

        print(f"\n  {pos.id}")
        print(f"    {pos.shares} acc @ {pos.entry_price:.2f} | Ahora: {current_price:.2f}")
        print(f"    P&L: {pnl_val:+.2f} ({pnl_pct:+.1f}%) | Dia {pos.bars_held}/{MAX_HOLD_DAYS} ({days_left} restantes)")
        print(f"    Stop: {pos.stop_loss:.2f} | Trail: {pos.trailing_stop:.2f}")

    print(f"\n  Total invertido: {total_invested:,.2f}")
    print(f"  Total P&L: {total_pnl:+,.2f}")


def get_history() -> None:
    closed = get_closed_positions()
    if not closed:
        print("\n  No hay posiciones cerradas.")
        return

    print(f"\n{'='*65}")
    print(f"  HISTORIAL ({len(closed)} operaciones)")
    print(f"{'='*65}")

    total_pnl = 0
    winners = 0

    for pos in sorted(closed, key=lambda p: p.exit_date or "", reverse=True):
        pnl_val = pos.pnl(pos.exit_price)
        pnl_pct = pos.pnl_pct(pos.exit_price)
        total_pnl += pnl_val
        if pnl_val > 0:
            winners += 1

        sign = "+" if pnl_val >= 0 else ""
        print(f"  {pos.id} | {pos.entry_date} -> {pos.exit_date} | {pos.bars_held}d")
        print(f"    {pos.entry_price:.2f} -> {pos.exit_price:.2f} | {sign}{pnl_val:.2f} ({sign}{pnl_pct:.1f}%) | {pos.exit_reason}")

    win_rate = winners / len(closed) * 100 if closed else 0
    print(f"\n  P&L total: {total_pnl:+,.2f}")
    print(f"  Win rate: {win_rate:.0f}% ({winners}/{len(closed)})")
