"""
RSI策略 — 源自 strategy6.0

仓位公式: 仓位 = allocated_capital / (price_per_hand * max_position) × RSI分段值
"""
import pandas as pd
from typing import List, Optional
from core.indicators import TechnicalIndicators
from config import RSIStrategyConfig
from . import Signal, RiskAction


class RSIStrategy:
    """RSI高卖低买策略"""

    def __init__(self, config: RSIStrategyConfig):
        self.config = config
        self.indicators = TechnicalIndicators()

    def _calc_size(self, allocated_capital: float, segment_value: int) -> int:
        """新仓位公式: 资金 / (10000 * 400) × 分段值"""
        raw = allocated_capital / (self.config.price_per_hand * self.config.max_position) * segment_value
        return max(1, int(raw))

    def generate_signals(self, bar: dict, prev_bar: dict, index_series: list,
                         position_size: int, volume_series: list = None,
                         allocated_capital: float = None) -> List[Signal]:
        """生成RSI策略信号"""
        signals = []
        index_list = list(index_series) + [bar["index"]]
        index_pd = pd.Series(index_list)
        rsi = self.indicators.calculate_rsi(index_pd, self.config.rsi_period).iloc[-1]
        cap = allocated_capital if allocated_capital else 3820773.90

        # ---- 买入（RSI超卖）----
        if rsi < self.config.rsi_oversold:
            if rsi < self.config.rsi_extreme_severe_oversold:
                buy_sz = self._calc_size(cap, self.config.segment_extreme_buy)
                reason = f"RSI极端超卖买入 RSI={rsi:.2f}"
            elif rsi < self.config.rsi_severe_oversold:
                buy_sz = self._calc_size(cap, self.config.segment_severe_buy)
                reason = f"RSI严重超卖买入 RSI={rsi:.2f}"
            else:
                buy_sz = self._calc_size(cap, self.config.segment_moderate_buy)
                reason = f"RSI中度超卖买入 RSI={rsi:.2f}"
            # 仓位上限
            if position_size > 0:
                buy_sz = min(buy_sz, self.config.max_position - position_size)
            if buy_sz > 0:
                signals.append(Signal("buy", "多", bar["close"], buy_sz, reason, source="rsi"))

        # ---- RSI回升平多 ----
        if rsi > self.config.rsi_buy_stop and position_size > 0:
            signals.append(Signal("close_long", "平多", bar["close"], position_size,
                                   f"RSI>{self.config.rsi_buy_stop}平多 RSI={rsi:.2f}", source="rsi"))

        # ---- 卖出（RSI超买）----
        if rsi >= self.config.rsi_overbought:
            if rsi >= self.config.rsi_extreme_extreme_overbought:
                sell_sz = self._calc_size(cap, self.config.segment_extreme_sell)
                reason = f"RSI极端超买卖出 RSI={rsi:.2f}"
            elif rsi >= self.config.rsi_extreme_overbought:
                sell_sz = self._calc_size(cap, self.config.segment_severe_sell)
                reason = f"RSI极度超买卖出 RSI={rsi:.2f}"
            else:
                sell_sz = self._calc_size(cap, self.config.segment_moderate_sell)
                reason = f"RSI中度超买卖出 RSI={rsi:.2f}"
            if position_size < 0:
                sell_sz = min(sell_sz, self.config.max_position - abs(position_size))
            if sell_sz > 0:
                signals.append(Signal("sell", "空", bar["close"], sell_sz, reason, source="rsi"))

        # ---- RSI回跌平空 ----
        if rsi < self.config.rsi_sell_stop and position_size < 0:
            signals.append(Signal("close_short", "平空", bar["close"], abs(position_size),
                                   f"RSI<{self.config.rsi_sell_stop}平空 RSI={rsi:.2f}", source="rsi"))

        return signals

    def manage_risk(self, bar: dict, index_series: list, position_size: int) -> Optional[RiskAction]:
        """RSI策略的风控由generate_signals处理"""
        return None
