"""
Modelo de datos para posiciones del portfolio.
"""

from dataclasses import dataclass, asdict
from typing import Optional


@dataclass
class Position:
    id: str
    ticker: str
    entry_date: str
    entry_price: float
    shares: int
    atr_at_entry: float
    stop_loss: float
    trailing_stop: float
    highest_close: float
    bars_held: int = 0
    status: str = "open"
    exit_date: Optional[str] = None
    exit_price: Optional[float] = None
    exit_reason: Optional[str] = None
    last_checked: Optional[str] = None

    def pnl(self, current_price: float) -> float:
        price = self.exit_price if self.status == "closed" else current_price
        return (price - self.entry_price) * self.shares

    def pnl_pct(self, current_price: float) -> float:
        price = self.exit_price if self.status == "closed" else current_price
        return (price - self.entry_price) / self.entry_price * 100

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Position":
        return cls(**d)
