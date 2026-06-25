"""Trading adapter — abstract interface + assetsplit_sdk POC implementation."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Position:
    """Normalized position data."""
    symbol: str
    name: str
    quantity: float
    available_qty: float
    cost_price: float
    market_price: float
    market_value: float
    unrealized_pnl: float
    unrealized_pnl_ratio: float
    holding_days: int = 0
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class AccountSummary:
    """Normalized account summary."""
    total_asset: float
    cash_available: float
    market_value: float
    frozen_cash: float
    unrealized_pnl: float
    currency: str = "CNY"
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class Execution:
    """Normalized execution (fill) record."""
    datetime: str
    symbol: str
    name: str
    side: str  # "buy" or "sell"
    quantity: float
    price: float
    amount: float
    fee: float = 0.0
    extra: dict[str, Any] = field(default_factory=dict)


class TradingAdapter(ABC):
    """Abstract interface for trading API adapters.

    Implement this for each trading API (assetsplit_sdk, IBKR, etc.).
    """

    @abstractmethod
    def connect(self) -> bool:
        """Connect and authenticate. Returns True on success."""

    @abstractmethod
    def disconnect(self) -> None:
        """Close the connection."""

    @abstractmethod
    def get_account_summary(self) -> AccountSummary | None:
        """Return account summary or None if unavailable."""

    @abstractmethod
    def get_positions(self) -> list[Position]:
        """Return all current positions."""

    @abstractmethod
    def get_today_executions(self) -> list[Execution]:
        """Return today's filled orders."""

    @abstractmethod
    def get_open_orders(self) -> list[dict[str, Any]]:
        """Return open/pending orders."""

    @abstractmethod
    def create_order(
        self,
        stock_code: str,
        side: str,
        volume: int,
        price: float | None = None,
        price_type: str = "LIMIT",
    ) -> dict[str, Any]:
        """Place an order. Returns dict with status key."""

    @abstractmethod
    def cancel_order(self, order_id: str) -> dict[str, Any]:
        """Cancel an open order. Returns dict with status key."""
