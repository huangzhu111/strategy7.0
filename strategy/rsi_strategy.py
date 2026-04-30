"""
RSI策略 — 源自 strategy6.0

仓位通过 PositionAllocator 分配（总仓位对半分）
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

    def _segment_value(self, rsi: float) -> tuple:
        """返回 (segment_value, reason_label)"""
        if rsi < self.config.rsi_extreme_severe_oversold:
            return self.config.segment_extreme_buy, "极端超卖"
        elif rsi < self.config.rsi_severe_oversold:
            return self.config.segment_severe_buy, "严重超卖"
        elif rsi < self.config.rsi_oversold:
            return self.config.segment_moderate_buy, "中度超卖"

        if rsi >= self.config.rsi_extreme_extreme_overbought:
            return self.config.segment_extreme_sell, "极端超买"
        elif rsi >= self.config.rsi_extreme_overbought:
            return self.config.segment_severe_sell, "极度超买"
        elif rsi >= self.config.rsi_overbought:
            return self.config.segment_moderate_sell, "中度超买"

        return 0, ""

    def generate_signals(self, bar: dict, prev_bar: dict, index_series: list,
                         position_size: int, volume_series: list = None,
                         allocator=None) -> List[Signal]:
        """生成RSI策略信号"""
        signals = []
        index_list = list(index_series) + [bar["index"]]
        index_pd = pd.Series(index_list)
        rsi = self.indicators.calculate_rsi(index_pd, self.config.rsi_period).iloc[-1]

        # ---- 买入（RSI超卖）----
        if rsi < self.config.rsi_oversold:
            seg_val, label = self._segment_value(rsi)
            buy_sz = allocator.get_rsi_position(seg_val) if allocator else 10
            # 仓位上限
            if position_size > 0:
                buy_sz = min(buy_sz, self.config.max_position - position_size)
            if buy_sz > 0:
                signals.append(Signal("buy", "多", bar["close"], buy_sz,
                                      f"RSI{label}买入 RSI={rsi:.2f}", source="rsi"))

        # ---- RSI回升平多 ----
        if rsi > self.config.rsi_buy_stop and position_size > 0:
            signals.append(Signal("close_long", "平多", bar["close"], position_size,
                                   f"RSI>{self.config.rsi_buy_stop}平多 RSI={rsi:.2f}", source="rsi"))

        # ---- 卖出（RSI超买）----
        if rsi >= self.config.rsi_overbought:
            seg_val, label = self._segment_value(rsi)
            sell_sz = allocator.get_rsi_position(seg_val) if allocator else 10
            if position_size < 0:
                sell_sz = min(sell_sz, self.config.max_position - abs(position_size))
            if sell_sz > 0:
                signals.append(Signal("sell", "空", bar["close"], sell_sz,
                                      f"RSI{label}卖出 RSI={rsi:.2f}", source="rsi"))

        # ---- RSI回跌平空 ----
        if rsi < self.config.rsi_sell_stop and position_size < 0:
            signals.append(Signal("close_short", "平空", bar["close"], abs(position_size),
                                   f"RSI<{self.config.rsi_sell_stop}平空 RSI={rsi:.2f}", source="rsi"))

        return signals

    def manage_risk(self, bar: dict, index_series: list, position_size: int) -> Optional[RiskAction]:
        """RSI策略的风控由generate_signals处理"""
        return None
