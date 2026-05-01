"""
仓位分配器 — 统一计算各子策略仓位

每个策略独立计算，分配器统一管理总资金视角。
每次开仓时，按总资金比例分配一半给趋势、一半给RSI。
"""


class PositionAllocator:
    """仓位分配器"""

    def __init__(self, total_capital: float, price_per_hand: int = 10000, max_position: int = 400):
        self.total_capital = total_capital
        self.price_per_hand = price_per_hand
        self.max_position = max_position
        self.dynamic_max_position = self._calc_dynamic_max()

    def _calc_dynamic_max(self) -> int:
        """动态RSI仓位上限 = 总资产 / 2 / 10000"""
        raw = self.total_capital / 2 / self.price_per_hand
        return max(1, int(raw))

    def get_rsi_max_position(self) -> int:
        """获取RSI当前动态仓位上限"""
        return self.dynamic_max_position

    def get_trend_position(self, price: float, ratio: float = 0.5) -> int:
        """
        趋势策略仓位：总资金 × ratio / 当前价格
        ratio = 0.5 → 总资金的50%用于趋势（即对半分的一半）
        """
        raw = self.total_capital * ratio / price
        return max(1, int(raw))

    def get_rsi_position(self, segment_value: int) -> int:
        """
        RSI策略仓位：总资金 × 50% / (price_per_hand × max_position) × segment_value
        segment_value: 超买超卖程度（10/20/40）
        """
        raw = self.total_capital * 0.5 / (self.price_per_hand * self.max_position) * segment_value
        return max(1, int(raw))

    def update_capital(self, new_capital: float):
        """更新资金"""
        self.total_capital = new_capital
        self.dynamic_max_position = self._calc_dynamic_max()
