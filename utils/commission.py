"""
手续费计算
"""


class CommissionCalculator:
    """手续费计算器"""

    RATE = 0.002  # 手续费率 0.2%

    @classmethod
    def calculate_for_trade(cls, price: float, size: int) -> float:
        """计算单笔交易手续费"""
        return max(price * size * cls.RATE, 0.0)
