"""
Persistencia de posiciones en archivo JSON.
"""

import json
import os
from typing import Optional
from portfolio.models import Position


PORTFOLIO_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "portfolio")
POSITIONS_FILE = os.path.join(PORTFOLIO_DIR, "positions.json")


def load_positions() -> list[Position]:
    if not os.path.exists(POSITIONS_FILE):
        return []
    with open(POSITIONS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    return [Position.from_dict(d) for d in data.get("positions", [])]


def save_positions(positions: list[Position]) -> None:
    os.makedirs(PORTFOLIO_DIR, exist_ok=True)
    data = {"positions": [p.to_dict() for p in positions]}
    with open(POSITIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def get_open_positions() -> list[Position]:
    return [p for p in load_positions() if p.status == "open"]


def get_closed_positions() -> list[Position]:
    return [p for p in load_positions() if p.status == "closed"]


def find_position(position_id: str) -> Optional[Position]:
    for p in load_positions():
        if p.id == position_id:
            return p
    return None


def delete_position(position_id: str) -> bool:
    """Elimina una posición por ID. Devuelve True si se encontró y eliminó."""
    positions = load_positions()
    before = len(positions)
    positions = [p for p in positions if p.id != position_id]
    if len(positions) < before:
        save_positions(positions)
        return True
    return False


def update_position(position_id: str, **kwargs) -> Optional[Position]:
    """Actualiza campos de una posición. Devuelve la posición actualizada o None."""
    positions = load_positions()
    for pos in positions:
        if pos.id == position_id:
            for key, value in kwargs.items():
                if hasattr(pos, key):
                    setattr(pos, key, value)
            save_positions(positions)
            return pos
    return None
