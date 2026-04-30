"""
金融技术指标计算
"""
import math
import pandas as pd
import numpy as np
from typing import Tuple


class TechnicalIndicators:
    """技术指标计算"""

    @staticmethod
    def calculate_rsi(prices: pd.Series, period: int = 14) -> pd.Series:
        """计算RSI指标"""
        delta = prices.diff()
        gain = delta.where(delta > 0, 0.0)
        loss = (-delta).where(delta < 0, 0.0)

        avg_gain = gain.rolling(window=period, min_periods=period).mean()
        avg_loss = loss.rolling(window=period, min_periods=period).mean()

        # 使用 Wilder's smoothing (SMMA)
        for i in range(period, len(gain)):
            avg_gain.iloc[i] = (avg_gain.iloc[i - 1] * (period - 1) + gain.iloc[i]) / period
            avg_loss.iloc[i] = (avg_loss.iloc[i - 1] * (period - 1) + loss.iloc[i]) / period

        rs = avg_gain / avg_loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))
        rsi = rsi.fillna(50.0)
        return rsi

    @staticmethod
    def calculate_ma(prices: pd.Series, period: int) -> pd.Series:
        """计算移动平均线"""
        return prices.rolling(window=period, min_periods=period).mean()

    @staticmethod
    def detect_crossover(
        current_price: float,
        current_ma: float,
        prev_price: float,
        prev_ma: float,
    ) -> int:
        """检测金叉/死叉: 返回 1(金叉), -1(死叉), 0(无交叉)"""
        if prev_price < prev_ma and current_price >= current_ma:
            return 1
        if prev_price > prev_ma and current_price <= current_ma:
            return -1
        return 0

    @staticmethod
    def check_basis_filter(
        index: float,
        close: float,
        date,
        basis_amplitude: int = -7000,
        basis_decay_rate: float = 0.002,
        basis_asymptote: int = 6500,
        basis_width_month_start: int = 10000,
        basis_width_month_mid: int = 7000,
        basis_width_month_end: int = 4000,
        seasonal_months: list = None,
        seasonal_multiplier: float = 2.0,
    ) -> dict:
        """检查基差过滤条件"""
        if seasonal_months is None:
            seasonal_months = [1, 2, 12]

        days_in_month = 30
        day_of_month = date.day if hasattr(date, "day") else 1
        days_remaining = days_in_month - day_of_month + 1

        # 计算基差宽度
        month_progress = day_of_month / days_in_month
        if month_progress < 0.33:
            bandwidth = basis_width_month_start
        elif month_progress < 0.66:
            bandwidth = basis_width_month_mid
        else:
            bandwidth = basis_width_month_end

        # 季节性调整
        if hasattr(date, "month") and date.month in (seasonal_months or []):
            bandwidth *= seasonal_multiplier

        # 指数衰减模型: basis = A + (A0 - A) * e^(-k * t)
        basis = basis_asymptote + (basis_amplitude) * math.exp(-basis_decay_rate * days_remaining)
        lower = basis - bandwidth / 2
        upper = basis + bandwidth / 2

        return {
            "basis": basis,
            "lower": lower,
            "upper": upper,
            "days_remaining": days_remaining,
            "is_valid": lower <= (index - close) <= upper,
        }
