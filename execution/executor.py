"""
交易执行器
"""
from typing import Tuple, Optional
from datetime import date
from .rollover import ContractRollover
from portfolio.position import Position
from portfolio.trade import TradeRecord
from portfolio.trade import generate_trade_id
from utils.commission import CommissionCalculator


class OrderExecutor:
    """订单执行器"""

    @staticmethod
    def open_position(direction: str, price: float, size: int, dt: date,
                       contract: str, signal_type: str, source: str = "") -> Tuple[TradeRecord, Position]:
        """开仓"""
        commission = CommissionCalculator.calculate_for_trade(price, size)
        trade = TradeRecord(
            trade_id=generate_trade_id(), signal_type=signal_type,
            direction=direction, entry_date=dt, entry_price=price,
            exit_date=dt, exit_price=price, size=size, pnl=0,
            commission=commission, source=source, contract=contract,
        )
        pos = Position(contract=contract, size=size if direction == "多" else -size,
                       direction=direction, entry_price=price, entry_date=dt,
                       original_entry_price=price, trade_id=trade.trade_id,
                       source=source)
        return trade, pos

    @staticmethod
    def close_position(position: Position, price: float, dt: date, reason: str) -> TradeRecord:
        """平仓"""
        if position.direction == "多":
            pnl = (price - position.entry_price) * position.size
        else:
            pnl = (position.entry_price - price) * abs(position.size)
        commission = CommissionCalculator.calculate_for_trade(price, abs(position.size))
        return TradeRecord(
            trade_id=generate_trade_id(), signal_type=reason,
            direction=position.direction, entry_date=position.entry_date,
            entry_price=position.entry_price, exit_date=dt, exit_price=price,
            size=abs(position.size), pnl=pnl, commission=commission,
            transfer_count=position.transfer_count, is_closed=True,
            source=position.source, contract=position.contract,
        )

    @staticmethod
    def reduce_position(position: Position, reduce_size: int, price: float, dt: date) -> Tuple[TradeRecord, Position]:
        """减仓"""
        reduce_size = min(reduce_size, abs(position.size))
        if position.direction == "多":
            pnl = (price - position.entry_price) * reduce_size
        else:
            pnl = (position.entry_price - price) * reduce_size
        commission = CommissionCalculator.calculate_for_trade(price, reduce_size)
        trade = TradeRecord(
            trade_id=generate_trade_id(), signal_type="减仓",
            direction=position.direction, entry_date=position.entry_date,
            entry_price=position.entry_price, exit_date=dt, exit_price=price,
            size=reduce_size, pnl=pnl, commission=commission,
            transfer_count=position.transfer_count, is_closed=False,
            source=position.source, contract=position.contract,
        )
        new_size = abs(position.size) - reduce_size
        if new_size > 0:
            position.size = new_size if position.direction == "多" else -new_size
            position.half_reduced = True
        return trade, position

    @staticmethod
    def calculate_position_size(total_value: float, price: float, ratio: float, round_to: int) -> int:
        """计算仓位大小"""
        raw = total_value * ratio / price
        return max(1, int(round(raw / round_to) * round_to))
