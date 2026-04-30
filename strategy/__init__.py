"""
交易信号和风险动作基类
"""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Signal:
    """交易信号"""
    signal_type: str      # buy, sell, close_long, close_short, bull, bear, bobaniu, bobaniu_fail
    direction: str        # 多, 空, 平多, 平空
    entry_price: float
    size: int
    reason: str
    source: str = ""      # "trend" | "rsi"
    basis_info: dict = None


@dataclass
class RiskAction:
    """风险管理动作"""
    action_type: str      # reduce_half, close_all
    size: int
    price: float
    reason: str
