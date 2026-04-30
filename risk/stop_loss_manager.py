"""
止损管理
"""
from typing import Optional
from core.indicators import TechnicalIndicators
from config import StopLossConfig


class StopLossManager:
    """止损管理器"""
    def __init__(self, config: StopLossConfig, indicators: TechnicalIndicators):
        self.config = config
        self.indicators = indicators
        self.price_history = []

    def update_price_history(self, price: float):
        self.price_history.append(price)
        if len(self.price_history) > 100:
            self.price_history = self.price_history[-100:]

    def check_all_stop_losses(self, position, index, dt, index_series, close_price) -> Optional[dict]:
        """检查所有止损条件"""
        # 趋势反转止损
        if self.config.trend_reversal_enabled:
            return self._check_trend_reversal(position, index, close_price)
        return None

    def _check_trend_reversal(self, position, index, close_price) -> Optional[dict]:
        """趋势反转止损"""
        if not position.ma_crossed:
            return None
        if position.direction == "多":
            if close_price <= position.ma_cross_base_price - self.config.trend_reversal_price_threshold:
                return {"stop_type": "趋势反转止损", "price": close_price,
                        "reason": f"多头趋势反转止损 (价格:{close_price:.0f}, 基准:{position.ma_cross_base_price:.0f})"}
        else:
            if close_price >= position.ma_cross_base_price + self.config.trend_reversal_price_threshold:
                return {"stop_type": "趋势反转止损", "price": close_price,
                        "reason": f"空头趋势反转止损 (价格:{close_price:.0f}, 基准:{position.ma_cross_base_price:.0f})"}
        return None

    def generate_report(self) -> str:
        return ""
