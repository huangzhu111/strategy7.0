"""
持仓和转仓记录
"""
from dataclasses import dataclass, field
from typing import List, Optional
from datetime import date


@dataclass
class TransferRecord:
    """转仓记录"""
    roll_date: date
    old_contract: str
    new_contract: str
    old_close_price: float
    new_open_price: float
    price_gap: float
    strategy_pnl: float
    roll_adjustment: float
    close_commission: float = 0.0
    open_commission: float = 0.0
    size: int = 0
    direction: str = ""
    source: str = ""  # trend / rsi


class Position:
    """持仓对象"""
    def __init__(self, contract: str, size: int, direction: str, entry_price: float,
                 entry_date: date, original_entry_price: float = None, trade_id: str = "",
                 highest_price: float = 0, lowest_price: float = 0,
                 holding_days: int = 0, total_holding_days: int = 0,
                 transfer_count: int = 0, transfer_history: list = None,
                 half_reduced: bool = False, ma_crossed: bool = False,
                 ma_cross_base_price: float = 0, source: str = "",
                 unrealized_pnl: float = 0):
        self.contract = contract
        self.size = size  # 正=多，负=空
        self.direction = direction
        self.entry_price = entry_price
        self.entry_date = entry_date
        self.original_entry_price = original_entry_price or entry_price
        self.trade_id = trade_id
        self.highest_price = highest_price or entry_price
        self.lowest_price = lowest_price or entry_price
        self.holding_days = holding_days
        self.total_holding_days = total_holding_days
        self.transfer_count = transfer_count
        self.transfer_history = transfer_history or []
        self.half_reduced = half_reduced
        self.ma_crossed = ma_crossed
        self.ma_cross_base_price = ma_cross_base_price
        self.source = source
        self.unrealized_pnl = unrealized_pnl

    def update_unrealized_pnl(self, current_price: float):
        if self.direction == "多":
            self.unrealized_pnl = (current_price - self.entry_price) * self.size
        else:
            self.unrealized_pnl = (self.entry_price - current_price) * abs(self.size)
        return self.unrealized_pnl
