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
    commission: float = 0.0          # comisión por operación (EUR)
    eur_usd_rate: float = 1.0        # tipo de cambio EUR/USD al entrar

    def pnl(self, current_price: float) -> float:
        """P&L en USD (sin comisión)."""
        price = self.exit_price if self.status == "closed" else current_price
        return (price - self.entry_price) * self.shares

    def pnl_pct(self, current_price: float) -> float:
        price = self.exit_price if self.status == "closed" else current_price
        return (price - self.entry_price) / self.entry_price * 100

    def pnl_eur(self, current_price: float, current_eur_usd: Optional[float] = None) -> float:
        """P&L neto en EUR: convierte USD→EUR y descuenta comisiones (entrada + salida)."""
        rate = current_eur_usd if current_eur_usd else self.eur_usd_rate
        usd_pnl = self.pnl(current_price)
        eur_pnl = usd_pnl / rate if rate > 0 else usd_pnl
        total_commission = self.commission * 2  # entrada + salida
        return eur_pnl - total_commission

    def cost_eur(self, current_eur_usd: Optional[float] = None) -> float:
        """Coste de entrada en EUR."""
        rate = current_eur_usd if current_eur_usd else self.eur_usd_rate
        return (self.entry_price * self.shares) / rate if rate > 0 else 0

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Position":
        # Compatibilidad con posiciones antiguas sin commission/eur_usd_rate
        valid_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in d.items() if k in valid_fields}
        return cls(**filtered)
