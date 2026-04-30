"""
仓位管理 — 核心创新：分别跟踪两个子策略的仓位和盈亏
"""
from typing import Optional


class SubStrategyPosition:
    """单个子策略的仓位跟踪"""

    def __init__(self, name: str):
        self.name = name  # "trend" 或 "rsi"
        self.size: int = 0           # 正数=多, 负数=空
        self.direction: str = ""     # "多" | "空" | ""
        self.entry_price: float = 0.0
        self.strategy_pnl: float = 0.0  # 该子策略累计盈亏
        self.trade_count: int = 0

    @property
    def abs_size(self) -> int:
        return abs(self.size)

    def open(self, direction: str, price: float, size: int):
        self.direction = direction
        self.size = size if direction == "多" else -size
        self.entry_price = price

    def add(self, price: float, add_size: int):
        total = self.abs_size * self.entry_price + add_size * price
        self.size += add_size if self.direction == "多" else -add_size
        self.entry_price = total / self.abs_size if self.abs_size > 0 else price

    def close(self, price: float, close_size: int) -> float:
        close_size = min(close_size, self.abs_size)
        if self.direction == "多":
            pnl = (price - self.entry_price) * close_size
        else:
            pnl = (self.entry_price - price) * close_size
        self.strategy_pnl += pnl
        self.size = (self.abs_size - close_size) * (1 if self.size > 0 else -1)
        self.trade_count += 1
        if self.size == 0:
            self.direction = ""
            self.entry_price = 0.0
        return pnl

    @property
    def has_position(self) -> bool:
        return self.size != 0

    def reset(self):
        self.size = 0
        self.direction = ""
        self.entry_price = 0.0
        self.strategy_pnl = 0.0
        self.trade_count = 0


class PositionManager:
    """
    仓位管理器 — 分别跟踪趋势策略和RSI策略的仓位

    两个子策略各自独立开仓平仓，各自记录盈亏。
    PositionManager 汇总后给引擎一个"净仓位"用于执行。
    """

    def __init__(self, combined_max: int = 600):
        self.trend = SubStrategyPosition("trend")
        self.rsi = SubStrategyPosition("rsi")
        self.combined_max = combined_max

    @property
    def net_size(self) -> int:
        """综合净仓位（正=多，负=空）"""
        return self.trend.size + self.rsi.size

    @property
    def net_abs_size(self) -> int:
        return abs(self.net_size)

    @property
    def has_net_position(self) -> bool:
        return self.net_size != 0

    @property
    def total_pnl(self) -> float:
        return self.trend.strategy_pnl + self.rsi.strategy_pnl

    def get_sub_position(self, source: str) -> SubStrategyPosition:
        if source == "trend":
            return self.trend
        elif source == "rsi":
            return self.rsi
        raise ValueError(f"未知子策略: {source}")

    def can_open(self, direction: str, add_size: int, source: str) -> bool:
        """检查是否可以开仓（不超过综合上限）"""
        sub = self.get_sub_position(source)
        if sub.direction == direction:
            new_total = sub.abs_size + add_size
        else:
            new_total = add_size
        return new_total <= self.combined_max

    def get_summary(self) -> str:
        """返回仓位摘要"""
        t = self.trend
        r = self.rsi
        t_info = f"趋势: {t.direction}{t.abs_size}手@{t.entry_price:.0f} (盈亏:{t.strategy_pnl:+,.0f})" if t.has_position else "趋势: 空仓"
        r_info = f"RSI: {r.direction}{r.abs_size}手@{r.entry_price:.0f} (盈亏:{r.strategy_pnl:+,.0f})" if r.has_position else "RSI: 空仓"
        net_dir = "多" if self.net_size > 0 else "空" if self.net_size < 0 else "0"
        net_info = f"净仓位: {net_dir}{self.net_abs_size}手 | 总盈亏: {self.total_pnl:+,.0f}"
        return f"{t_info} | {r_info} | {net_info}"
