"""
配置文件 - 双策略融合引擎 (v7.0)
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class TrendStrategyConfig:
    """趋势策略配置 (源自 strategy5.0)"""
    enabled: bool = True
    ma_period: int = 10
    rsi_period: int = 11
    rsi_overbought: float = 80.0
    rsi_extreme_overbought: float = 90.0
    rsi_oversold: float = 24.5
    bull_price_change: int = 500
    bear_price_change: int = 100
    bobaniu_price_change: int = 550
    signal_validity_days: int = 4
    bobaniu_validity_days: int = 5

    # 成交量过滤
    volume_filter_enabled: bool = False
    volume_lookback_days: int = 10

    # 双策略模式下禁用RSI风控（RSI策略负责）
    disable_rsi_risk: bool = True

    # 基差过滤
    basis_amplitude: int = -7000
    basis_decay_rate: float = 0.002
    basis_asymptote: int = 6500
    basis_width_month_start: int = 10000
    basis_width_month_mid: int = 7000
    basis_width_month_end: int = 4000
    basis_seasonal_months: list = None
    basis_seasonal_multiplier: float = 2.0

    def __post_init__(self):
        if self.basis_seasonal_months is None:
            self.basis_seasonal_months = [1, 2, 12]


@dataclass
class RSIStrategyConfig:
    """RSI策略配置 (源自 strategy6.0)"""
    enabled: bool = True
    rsi_period: int = 11
    fixed_trade_size: int = 5

    # 买入阈值
    rsi_oversold: float = 25.0
    rsi_moderate_oversold: float = 25.0     # 10手
    rsi_severe_oversold: float = 20.0        # 20手
    rsi_extreme_severe_oversold: float = 15.0  # 40手

    # 卖出阈值
    rsi_overbought: float = 85.0
    rsi_very_overbought: float = 85.0         # 10手
    rsi_extreme_overbought: float = 90.0      # 20手
    rsi_extreme_extreme_overbought: float = 95.0  # 40手

    # 平仓阈值
    rsi_buy_stop: float = 65        # 有多单则平仓
    rsi_sell_stop: float = 40       # 有空单则平仓

    # 仓位上限
    max_position: int = 400
    # RSI分段仓位值（新公式: 仓位 = 资金 / (10000*400) × 分段值）
    price_per_hand: int = 10000       # 每手合约价值基数
    # 超卖（买入）分段值
    segment_moderate_buy: int = 10     # RSI 20-25
    segment_severe_buy: int = 20       # RSI 15-20
    segment_extreme_buy: int = 40      # RSI < 15
    # 超买（卖出）分段值
    segment_moderate_sell: int = 10    # RSI 85-90
    segment_severe_sell: int = 20      # RSI 90-95
    segment_extreme_sell: int = 40     # RSI >= 95


@dataclass
class PositionManagerConfig:
    """仓位管理配置"""
    # 综合仓位上限
    combined_max_position: int = 600
    # 子策略资金分配比例
    trend_capital_ratio: float = 0.50   # 趋势策略分配50%初始资金
    rsi_capital_ratio: float = 0.50     # RSI策略分配50%初始资金


@dataclass
class CommissionConfig:
    """手续费配置"""
    rate: float = 0.002
    min_commission: float = 0.0


@dataclass
class AccountConfig:
    """账户配置"""
    initial_capital: float = 3820773.90
    position_ratio: float = 0.5
    position_round: int = 5


@dataclass
class DataConfig:
    """数据配置"""
    db_path: str = "D:/Onedrive/Documents/backtrader/FFA Strategy/strategy3.0/databasse/message.db"
    table_name: str = "m1_daily_ohlc"
    use_remote: bool = True
    vps_host: str = "178.128.53.99"
    vps_port: int = 22
    vps_username: str = "root"
    vps_db_path: str = "/root/ffa-data/messages.db"
    from_date: str = "2018-01-01"
    to_date: str = "2026-12-31"


@dataclass
class StopLossConfig:
    """止损配置"""
    fixed_point_enabled: bool = False
    fixed_point_stop_loss: float = 2000.0
    atr_enabled: bool = False
    atr_multiplier: float = 2.0
    atr_period: int = 14
    price_percent_enabled: bool = False
    price_percent_stop: float = 0.085
    time_stop_enabled: bool = False
    time_stop_days: int = 15
    time_stop_threshold: float = 2000.0
    trailing_stop_enabled: bool = False
    trailing_stop_activation: float = 100000.0
    trailing_stop_distance: float = 50000.0
    trend_reversal_enabled: bool = True
    trend_reversal_ma_period: int = 10
    trend_reversal_price_threshold: float = 2000.0
    stop_loss_priority: list = None

    def __post_init__(self):
        if self.stop_loss_priority is None:
            object.__setattr__(self, "stop_loss_priority", [
                "trend_reversal", "fixed_point", "atr_dynamic",
                "price_percent", "time_based", "rsi_risk",
            ])


@dataclass
class EngineConfig:
    """引擎配置"""
    trend_strategy: TrendStrategyConfig = None
    rsi_strategy: RSIStrategyConfig = None
    position_manager: PositionManagerConfig = None
    commission: CommissionConfig = None
    account: AccountConfig = None
    data: DataConfig = None
    stop_loss: StopLossConfig = None
    verbose: bool = True
    log_file: str = "backtest_log.txt"

    def __post_init__(self):
        if self.trend_strategy is None:
            self.trend_strategy = TrendStrategyConfig()
        if self.rsi_strategy is None:
            self.rsi_strategy = RSIStrategyConfig()
        if self.position_manager is None:
            self.position_manager = PositionManagerConfig()
        if self.commission is None:
            self.commission = CommissionConfig()
        if self.account is None:
            self.account = AccountConfig()
        if self.data is None:
            self.data = DataConfig()
        if self.stop_loss is None:
            self.stop_loss = StopLossConfig()
