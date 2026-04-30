"""
账户管理 — 增强版：分别跟踪趋势和RSI子策略的盈亏
"""
from typing import Optional, List
from dataclasses import dataclass, field
from datetime import date
from .position import Position, TransferRecord
from .trade import TradeRecord, CompleteTrade


@dataclass
class DailyValue:
    date: date
    value: float
    position_value: float
    cash: float


class SubStrategyPnL:
    """单个子策略的盈亏追踪"""
    def __init__(self, name: str):
        self.name = name
        self.pnl: float = 0.0
        self.commissions: float = 0.0
        self.trades: List[TradeRecord] = []
        self.complete_trades: List[CompleteTrade] = []
        self.trade_count: int = 0

    def add_trade(self, trade: TradeRecord):
        self.pnl += trade.pnl
        self.commissions += trade.commission
        self.trades.append(trade)
        self.trade_count += 1


class FuturesAccount:
    """期货账户 — 双策略盈亏跟踪"""

    def __init__(self, initial_capital: float):
        self.initial_capital = initial_capital
        self.current_capital = initial_capital

        # 公共部分
        self.roll_adjustments = 0.0
        self.commissions = 0.0

        # 子策略盈亏
        self.trend_pnl = SubStrategyPnL("trend")
        self.rsi_pnl = SubStrategyPnL("rsi")

        # 持仓(用于引擎执行的净仓位)
        self.position: Optional[Position] = None

        # 历史记录
        self.trades: List[TradeRecord] = []
        self.transfers: List[TransferRecord] = []
        self.complete_trades: List[CompleteTrade] = []
        self.current_complete_trade: Optional[CompleteTrade] = None

        # 风险指标
        self.daily_values: List[DailyValue] = []
        self.peak_value = initial_capital
        self.max_drawdown = 0.0

    def get_sub_pnl(self, source: str) -> SubStrategyPnL:
        return self.trend_pnl if source == "trend" else self.rsi_pnl

    def has_position(self) -> bool:
        return self.position is not None and self.position.size != 0

    def get_total_value(self, current_price: float = 0) -> float:
        if not self.position or self.position.size == 0:
            return self.current_capital
        if self.position.direction == "多":
            pv = (current_price - self.position.entry_price) * abs(self.position.size)
        else:
            pv = (self.position.entry_price - current_price) * abs(self.position.size)
        return self.current_capital + pv

    def execute_strategy_trade(self, trade: TradeRecord, source: str = ""):
        """执行策略交易，按source分别记录盈亏"""
        sub = self.get_sub_pnl(source)
        sub.add_trade(trade)

        self.current_capital += trade.pnl - trade.commission
        self.commissions += trade.commission
        self.trades.append(trade)
        self._update_risk_metrics()

    def execute_rollover(self, transfer: TransferRecord):
        self.roll_adjustments += transfer.roll_adjustment
        self.current_capital += transfer.strategy_pnl + transfer.roll_adjustment
        self.transfers.append(transfer)
        self._update_risk_metrics()

    def start_complete_trade(self, signal_type, direction, entry_date, entry_price, size, source=""):
        self.current_complete_trade = CompleteTrade(
            signal_type=signal_type, direction=direction,
            original_entry_date=entry_date, original_entry_price=entry_price,
            initial_size=size, source=source,
        )

    def add_transfer_to_complete_trade(self, close_date, close_price, open_date, open_price):
        if self.current_complete_trade:
            self.current_complete_trade.add_transfer(close_date, close_price, open_date, open_price)

    def add_partial_close_to_complete_trade(self, close_price, close_size, close_date, commission):
        if self.current_complete_trade:
            self.current_complete_trade.add_partial_close(close_price, close_size, close_date, commission)

    def close_complete_trade(self, exit_price, exit_date, commission=0, total_holding_days=0):
        if self.current_complete_trade:
            self.current_complete_trade.close_trade(exit_price, exit_date, commission)
            self.current_complete_trade.total_holding_days = total_holding_days
            # 记录到对应子策略
            src = self.current_complete_trade.source
            sub = self.get_sub_pnl(src)
            sub.complete_trades.append(self.current_complete_trade)

            self.complete_trades.append(self.current_complete_trade)
            self.current_complete_trade = None

    def _update_risk_metrics(self):
        if self.current_capital > self.peak_value:
            self.peak_value = self.current_capital
        drawdown = self.peak_value - self.current_capital
        if drawdown > self.max_drawdown:
            self.max_drawdown = drawdown

    def update_market_value(self, current_price: float, current_date: date):
        pv = 0.0
        if self.position and self.position.size != 0:
            self.position.update_unrealized_pnl(current_price)
            pv = abs(self.position.unrealized_pnl)
        self.daily_values.append(DailyValue(date=current_date, value=self.current_capital,
                                             position_value=pv, cash=self.current_capital))

    def get_pnl_summary(self) -> str:
        t = self.trend_pnl
        r = self.rsi_pnl
        return (f"趋势策略: {t.pnl:+,.0f} ({t.trade_count}笔) | "
                f"RSI策略: {r.pnl:+,.0f} ({r.trade_count}笔) | "
                f"合计: {t.pnl + r.pnl:+,.0f}")

    def get_performance_summary(self) -> dict:
        return {
            "initial_capital": self.initial_capital,
            "final_capital": self.current_capital,
            "trend_pnl": self.trend_pnl.pnl,
            "rsi_pnl": self.rsi_pnl.pnl,
            "strategy_pnl": self.trend_pnl.pnl + self.rsi_pnl.pnl,
            "roll_adjustments": self.roll_adjustments,
            "commissions": self.commissions,
            "net_pnl": self.trend_pnl.pnl + self.rsi_pnl.pnl - self.commissions,
            "peak_value": self.peak_value,
            "max_drawdown": self.max_drawdown,
            "trend_trades": self.trend_pnl.trade_count,
            "rsi_trades": self.rsi_pnl.trade_count,
            "trade_count": len(self.trades),
            "transfer_count": len(self.transfers),
        }
