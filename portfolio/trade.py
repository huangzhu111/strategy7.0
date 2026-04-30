"""
交易记录
"""
from dataclasses import dataclass, field
from typing import List, Optional
from datetime import date
import hashlib
import time


def generate_trade_id() -> str:
    return hashlib.md5(str(time.time()).encode()).hexdigest()[:8]


@dataclass
class TradeRecord:
    """单笔交易记录"""
    trade_id: str
    signal_type: str
    direction: str
    entry_date: date
    entry_price: float
    exit_date: date
    exit_price: float
    size: int
    pnl: float
    commission: float = 0.0
    transfer_count: int = 0
    is_closed: bool = False
    source: str = ""  # trend / rsi
    contract: str = ""


@dataclass
class CompleteTrade:
    """完整交易（含多次加仓、转仓）"""
    signal_type: str
    direction: str
    original_entry_date: date
    original_entry_price: float
    initial_size: int
    entry_date: date = None
    entry_price: float = 0
    total_size: int = 0
    exit_date: date = None
    exit_price: float = 0
    total_pnl: float = 0
    total_commission: float = 0
    total_holding_days: int = 0
    transfers: list = field(default_factory=list)
    partial_closes: list = field(default_factory=list)
    sub_trades: list = field(default_factory=list)
    source: str = ""  # trend / rsi

    def __post_init__(self):
        self.entry_date = self.original_entry_date
        self.entry_price = self.original_entry_price
        self.total_size = self.initial_size

    def add_position(self, size: int, price: float, date: date):
        total_val = self.total_size * self.entry_price + size * price
        self.total_size += size
        self.entry_price = total_val / self.total_size

    def add_transfer(self, close_date: date, close_price: float, open_date: date, open_price: float):
        self.transfers.append({"close_date": close_date, "close_price": close_price,
                                "open_date": open_date, "open_price": open_price})

    def add_partial_close(self, price: float, size: int, date: date, commission: float):
        self.partial_closes.append({"price": price, "size": size, "date": date, "commission": commission})

    def close_trade(self, exit_price: float, exit_date: date, commission: float = 0):
        self.exit_price = exit_price
        self.exit_date = exit_date
        self.total_commission += commission

    def get_total_pnl(self) -> float:
        if self.exit_price and self.exit_price > 0:
            if self.direction == "多":
                pnl = (self.exit_price - self.entry_price) * self.total_size
            else:
                pnl = (self.entry_price - self.exit_price) * self.total_size
            return pnl - self.total_commission
        return self.total_pnl
