"""
RSI策略 — 源自 strategy6.0

核心逻辑:
- RSI < 25: 买入10手(中度超卖)
- RSI < 20: 买入20手(严重超卖)
- RSI < 15: 买入40手(极端超卖)
- RSI > 65: 有多单则平仓
- RSI >= 85: 卖出10手(严重超买)
- RSI >= 90: 卖出20手(极度超买)
- RSI >= 95: 卖出40手(极端超买)
- RSI < 40: 有空单则平仓
- 仓位上限: 400手
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

    def generate_signals(self, bar: dict, prev_bar: dict, index_series: list,
                         position_size: int, volume_series: list = None) -> List[Signal]:
        """生成RSI策略信号"""
        signals = []
        index_list = list(index_series) + [bar["index"]]
        index_pd = pd.Series(index_list)
        rsi = self.indicators.calculate_rsi(index_pd, self.config.rsi_period).iloc[-1]
        ft = self.config.fixed_trade_size

        # RSI分层买入
        if rsi < self.config.rsi_oversold:
            if rsi < self.config.rsi_extreme_severe_oversold:
                buy_sz = ft * 8
                reason = f"RSI极端超卖买入 RSI={rsi:.2f}"
            elif rsi < self.config.rsi_severe_oversold:
                buy_sz = ft * 4
                reason = f"RSI严重超卖买入 RSI={rsi:.2f}"
            else:
                buy_sz = ft * 2
                reason = f"RSI中度超卖买入 RSI={rsi:.2f}"
            # 仓位上限检查
            if position_size > 0:
                buy_sz = min(buy_sz, self.config.max_position - position_size)
            if buy_sz > 0:
                signals.append(Signal("buy", "多", bar["close"], buy_sz, reason, source="rsi"))

        # RSI > 65 平多
        if rsi > self.config.rsi_buy_stop and position_size > 0:
            signals.append(Signal("close_long", "平多", bar["close"], position_size,
                                   f"RSI>{self.config.rsi_buy_stop}平多 RSI={rsi:.2f}", source="rsi"))

        # RSI分层卖出
        if rsi >= self.config.rsi_overbought:
            if rsi >= self.config.rsi_extreme_extreme_overbought:
                sell_sz = ft * 8
                reason = f"RSI极端超买卖出 RSI={rsi:.2f}"
            elif rsi >= self.config.rsi_extreme_overbought:
                sell_sz = ft * 4
                reason = f"RSI极度超买卖出 RSI={rsi:.2f}"
            else:
                sell_sz = ft * 2
                reason = f"RSI严重超买卖出 RSI={rsi:.2f}"
            if position_size < 0:
                sell_sz = min(sell_sz, self.config.max_position - abs(position_size))
            if sell_sz > 0:
                signals.append(Signal("sell", "空", bar["close"], sell_sz, reason, source="rsi"))

        # RSI < 40 平空
        if rsi < self.config.rsi_sell_stop and position_size < 0:
            signals.append(Signal("close_short", "平空", bar["close"], abs(position_size),
                                   f"RSI<{self.config.rsi_sell_stop}平空 RSI={rsi:.2f}", source="rsi"))

        return signals

    def manage_risk(self, bar: dict, index_series: list, position_size: int) -> Optional[RiskAction]:
        """RSI策略的风控由generate_signals处理"""
        return None
