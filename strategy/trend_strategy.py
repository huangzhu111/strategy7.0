"""
趋势策略 — 源自 strategy5.0

核心逻辑:
- MA交叉检测趋势方向(金叉做多/死叉做空)
- 搏一把信号: 趋势反转
- 基差过滤 + 成交量过滤
- RSI风控
"""
import pandas as pd
from typing import List, Optional
from core.indicators import TechnicalIndicators
from config import TrendStrategyConfig
from . import Signal, RiskAction


class TrendStrategy:
    """趋势策略"""

    def __init__(self, config: TrendStrategyConfig):
        self.config = config
        self.indicators = TechnicalIndicators()
        self.bull_signal = False
        self.bear_signal = False
        self.bull_counter = 0
        self.bear_counter = 0
        self.bobaniu_signal = False
        self.bobaniu_days = 0

    def generate_signals(self, bar: dict, prev_bar: dict, index_series: list,
                         position_size: int, volume_series: list = None) -> List[Signal]:
        """生成趋势策略信号"""
        signals = []
        index_list = list(index_series) + [bar["index"]]
        index_pd = pd.Series(index_list)

        ma = self.indicators.calculate_ma(index_pd, self.config.ma_period).iloc[-1]
        rsi = self.indicators.calculate_rsi(index_pd, self.config.rsi_period).iloc[-1]

        if len(index_list) >= self.config.ma_period + 1:
            prev_ma_series = self.indicators.calculate_ma(index_pd, self.config.ma_period)
            prev_ma = prev_ma_series.iloc[-2]
        else:
            prev_ma = ma

        crossover = self.indicators.detect_crossover(bar["index"], ma, prev_bar["index"], prev_ma)

        # 基差过滤
        basis_filter = self.indicators.check_basis_filter(
            index=bar["index"], close=bar["close"], date=bar["datetime"],
            basis_amplitude=self.config.basis_amplitude,
            basis_decay_rate=self.config.basis_decay_rate,
            basis_asymptote=self.config.basis_asymptote,
            basis_width_month_start=self.config.basis_width_month_start,
            basis_width_month_mid=self.config.basis_width_month_mid,
            basis_width_month_end=self.config.basis_width_month_end,
            seasonal_months=self.config.basis_seasonal_months,
            seasonal_multiplier=self.config.basis_seasonal_multiplier,
        )
        basis_info = {"basis": basis_filter["basis"], "lower": basis_filter["lower"],
                       "upper": basis_filter["upper"], "days_remaining": basis_filter["days_remaining"]}

        # 搏一把信号
        if self._check_bobaniu(bar, prev_bar, ma):
            vol_ok = self._check_volume_filter(bar.get("volume", 0), volume_series, "多")
            if basis_filter["is_valid"] and vol_ok:
                signals.append(Signal("bobaniu", "多", bar["high"], 0, "搏一把信号", source="trend", basis_info=basis_info))
                self.bobaniu_signal = True
                self.bobaniu_days = 0

        if self.bobaniu_signal:
            self.bobaniu_days += 1
            if bar["close"] < bar["open"] and bar["index"] < ma:
                if basis_filter["is_valid"]:
                    signals.append(Signal("bobaniu_fail", "空", bar["low"], 0, "搏一把失败", source="trend", basis_info=basis_info))
                self.bobaniu_signal = False
            if self.bobaniu_days > self.config.bobaniu_validity_days:
                self.bobaniu_signal = False

        # 牛市信号
        if crossover > 0 and not self.bobaniu_signal:
            self.bull_signal = True
            self.bull_counter = 1

        if self.bull_signal and bar["index"] > ma and position_size <= 0:
            self.bull_counter += 1
            if (bar["close"] - bar["open"] >= self.config.bull_price_change
                    and rsi <= 60 and self.bull_counter <= self.config.signal_validity_days):
                if not basis_filter["is_valid"]:
                    self.bull_signal = False
                    self.bull_counter = 0
                else:
                    vol_ok = self._check_volume_filter(bar.get("volume", 0), volume_series, "多")
                    if not vol_ok:
                        self.bull_signal = False
                        self.bull_counter = 0
                    else:
                        if position_size < 0:
                            signals.append(Signal("close_short", "平空", bar["high"], abs(position_size),
                                                   "牛市信号平空仓", source="trend"))
                        signals.append(Signal("bull", "多", bar["high"], 0,
                                               f"牛市信号第{self.bull_counter}天", source="trend", basis_info=basis_info))
                        self.bull_signal = False
                        self.bull_counter = 0

        # 熊市信号
        if crossover < 0:
            self.bear_signal = True
            self.bear_counter = 1

        if self.bear_signal and bar["index"] < ma and position_size >= 0:
            self.bear_counter += 1
            if (bar["open"] - bar["close"] >= self.config.bear_price_change
                    and rsi >= 42 and self.bear_counter <= self.config.signal_validity_days
                    and bar["index"] - bar["open"] < 17000):
                if not basis_filter["is_valid"]:
                    self.bear_signal = False
                    self.bear_counter = 0
                else:
                    vol_ok = self._check_volume_filter(bar.get("volume", 0), volume_series, "空")
                    if not vol_ok:
                        self.bear_signal = False
                        self.bear_counter = 0
                    else:
                        if position_size > 0:
                            signals.append(Signal("close_long", "平多", bar["low"], position_size,
                                                   "熊市信号平多仓", source="trend"))
                        signals.append(Signal("bear", "空", bar["low"], 0,
                                               f"熊市信号第{self.bear_counter}天", source="trend", basis_info=basis_info))
                        self.bear_signal = False
                        self.bear_counter = 0

        return signals

    def manage_risk(self, bar: dict, index_series: list, position_size: int) -> Optional[RiskAction]:
        """趋势策略的风险管理"""
        if position_size == 0:
            return None
        index_list = list(index_series) + [bar["index"]]
        index_pd = pd.Series(index_list)
        rsi = self.indicators.calculate_rsi(index_pd, self.config.rsi_period).iloc[-1]

        if rsi >= self.config.rsi_extreme_overbought:
            return RiskAction("close_all", abs(position_size), bar["low"], f"RSI极度超买清仓 ({rsi:.2f})", )
        if rsi >= self.config.rsi_overbought:
            return RiskAction("reduce_half", abs(position_size) // 2, bar["low"], f"RSI超买减仓 ({rsi:.2f})")
        if rsi <= self.config.rsi_oversold:
            return RiskAction("close_all", abs(position_size), bar["high"], f"RSI超卖清仓 ({rsi:.2f})")
        return None

    def _check_bobaniu(self, bar, prev_bar, ma) -> bool:
        price_change = bar["close"] - bar["open"]
        if price_change < self.config.bobaniu_price_change:
            return False
        ma_gap = ma - bar["index"]
        index_change = bar["index"] - prev_bar["index"]
        return 0 <= ma_gap <= index_change

    def _check_volume_filter(self, current_vol, volume_series, direction) -> bool:
        if not self.config.volume_filter_enabled or not volume_series or len(volume_series) == 0:
            return True
        if len(volume_series) < self.config.volume_lookback_days:
            return True
        past = volume_series[-self.config.volume_lookback_days:]
        if direction == "多":
            return current_vol <= max(past)
        else:
            return current_vol >= min(past)
