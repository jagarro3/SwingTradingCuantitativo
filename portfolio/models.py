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
    commission: float = 0.0          # comisión por operación (USD)
    usd_eur_rate: float = 0.85       # tipo de cambio USD→EUR al entrar (1 USD = X EUR)

    def pnl(self, current_price: float) -> float:
        """P&L en USD (sin comisión)."""
        price = self.exit_price if self.status == "closed" else current_price
        return (price - self.entry_price) * self.shares

    def pnl_pct(self, current_price: float) -> float:
        price = self.exit_price if self.status == "closed" else current_price
        return (price - self.entry_price) / self.entry_price * 100

    def pnl_net(self, current_price: float) -> float:
        """P&L neto en USD (descontando comisiones entrada + salida)."""
        return self.pnl(current_price) - self.commission * 2

    def pnl_eur(self, current_price: float, current_usd_eur: Optional[float] = None) -> float:
        """P&L neto en EUR: USD * tasa USD→EUR."""
        rate = current_usd_eur if current_usd_eur else self.usd_eur_rate
        return self.pnl_net(current_price) * rate

    def cost_eur(self, current_usd_eur: Optional[float] = None) -> float:
        """Coste de entrada en EUR."""
        rate = current_usd_eur if current_usd_eur else self.usd_eur_rate
        return self.entry_price * self.shares * rate

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Position":
        # Migrar eur_usd_rate → usd_eur_rate (versión anterior)
        if "eur_usd_rate" in d and "usd_eur_rate" not in d:
            old_rate = d.pop("eur_usd_rate")
            d["usd_eur_rate"] = round(1.0 / old_rate, 6) if old_rate > 0 else 0.85
        # Compatibilidad con posiciones antiguas
        valid_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in d.items() if k in valid_fields}
        return cls(**filtered)
