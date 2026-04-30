"""
合约换月逻辑
"""
from dataclasses import dataclass, field
from typing import List


@dataclass
class RolloverInfo:
    """换月信息"""
    old_contract: str
    new_contract: str
    roll_date: str
    price_gap: float
    direction: str
    size: int


class ContractRollover:
    """合约换月管理"""

    def __init__(self):
        self.rollovers: List[RolloverInfo] = []

    def calculate_roll_adjustment(self, direction: str, size: int, price_gap: float) -> float:
        """计算换月价差调整"""
        if direction == "多":
            return -price_gap * size
        else:
            return price_gap * size

    def record_rollover(self, info: RolloverInfo):
        self.rollovers.append(info)
