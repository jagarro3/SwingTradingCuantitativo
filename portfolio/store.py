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
