"""
主引擎 — 双策略事件驱动回测

同时运行趋势策略和RSI策略，分别跟踪盈亏
"""
from datetime import datetime
from typing import Optional, List

from .data_feed import FuturesDataFeed
from .indicators import TechnicalIndicators
from portfolio.account import FuturesAccount
from portfolio.position import Position, TransferRecord
from portfolio.trade import TradeRecord, CompleteTrade, generate_trade_id
from portfolio.position_manager import PositionManager
from portfolio.allocator import PositionAllocator
from execution.rollover import ContractRollover
from execution.executor import OrderExecutor
from strategy.trend_strategy import TrendStrategy
from strategy.rsi_strategy import RSIStrategy
from strategy import Signal, RiskAction
from analytics.attribution import PerformanceAttribution
from config import EngineConfig
from risk.stop_loss_manager import StopLossManager
from utils.commission import CommissionCalculator


class FuturesBacktestEngine:
    """双策略回测引擎"""

    def __init__(self, config: EngineConfig = None):
        self.config = config or EngineConfig()
        self.data_feed = FuturesDataFeed.from_config(self.config.data)
        self.account = FuturesAccount(self.config.account.initial_capital)
        self.pos_mgr = PositionManager(self.config.position_manager.combined_max_position)
        self.rollover = ContractRollover()
        self.indicators = TechnicalIndicators()

        # 两个策略实例
        self.trend_strategy = TrendStrategy(self.config.trend_strategy)
        self.rsi_strategy = RSIStrategy(self.config.rsi_strategy)

        self.analytics = PerformanceAttribution()
        self.stop_loss_manager = StopLossManager(self.config.stop_loss, self.indicators)

        # 仓位分配器（统一计算总仓位对半分）
        self.allocator = PositionAllocator(
            total_capital=self.config.account.initial_capital,
            price_per_hand=self.config.rsi_strategy.price_per_hand,
            max_position=self.config.rsi_strategy.max_position,
        )

        self.index_series: List[float] = []
        self.volume_series: List[float] = []
        self.log_file = None

    def run(self) -> str:
        print("=" * 80)
        print("策略7.0 双策略回测引擎".center(80))
        print("趋势策略(MA交叉+基差) + RSI策略(高卖低买)".center(80))
        print("=" * 80)

        df = self.data_feed.load_data(
            from_date=self.config.data.from_date, to_date=self.config.data.to_date
        )
        if df is None:
            print("数据加载失败")
            return ""

        self.log_file = open(self.config.log_file, "w", encoding="utf-8")
        self._log("系统", "回测开始")

        dates = df.index.tolist()
        warmup_period = max(self.config.trend_strategy.rsi_period,
                            self.config.rsi_strategy.rsi_period) + 5

        for i, dt in enumerate(dates):
            self.current_date = dt
            bar = df.loc[dt].to_dict()
            bar["datetime"] = dt
            prev_bar = df.loc[dates[i - 1]].to_dict() if i > 0 else bar

            if i > 0:
                self.index_series.append(prev_bar["index"])
                self.volume_series.append(prev_bar["volume"])

            if i < warmup_period:
                if self.account.position:
                    self.account.update_market_value(bar["close"], dt)
                continue

            # 步骤1：月初换月开仓
            if hasattr(self, "_pending_roll") and self._pending_roll:
                if not self.data_feed.is_roll_date(dt):
                    self._execute_roll_open(dt, bar)
                    self._pending_roll = False

            # 步骤2：动态更新仓位分配器（每次都用当前资金计算）
            self.allocator.update_capital(self.account.current_capital)

            # 步骤2：同时运行两个策略的信号（先收集，后统一执行）
            all_signals = []
            for source_name, strategy_obj in [("trend", self.trend_strategy),
                                               ("rsi", self.rsi_strategy)]:
                sub_pos = self.pos_mgr.get_sub_position(source_name)
                signals = strategy_obj.generate_signals(
                    bar, prev_bar, self.index_series, sub_pos.size, self.volume_series,
                    allocator=self.allocator,
                )
                for signal in signals:
                    signal.source = source_name
                all_signals.extend(signals)

            # 统一仓位管理：趋势策略决定方向，RSI只能顺向操作
            trend_pos = self.pos_mgr.get_sub_position("trend")
            trend_direction = trend_pos.direction if trend_pos.has_position else None
            for signal in all_signals:
                # RSI开仓方向必须与趋势方向一致（或趋势无仓位时自由操作）
                if signal.source == "rsi" and signal.signal_type in ["buy", "sell"]:
                    if trend_direction is not None and signal.direction != trend_direction:
                        self._log("冲突",
                            f"[rsi] 方向冲突: 趋势={trend_direction}, RSI信号={signal.direction}, 跳过 {signal.reason}"
                        )
                        continue
                self._execute_signal(signal, bar, dt)

            # 步骤3：止损检查
            if self.account.position and self.account.position.size != 0:
                self.stop_loss_manager.update_price_history(bar["close"])
                stop_loss_action = self.stop_loss_manager.check_all_stop_losses(
                    self.account.position, bar["index"], dt, self.index_series, bar["close"],
                )
                if stop_loss_action:
                    self._execute_stop_loss_action(stop_loss_action, bar, dt)

            # 步骤4：风控（趋势策略的RSI风控）
            for source_name, strategy_obj in [("trend", self.trend_strategy),
                                               ("rsi", self.rsi_strategy)]:
                sub_pos = self.pos_mgr.get_sub_position(source_name)
                risk_action = strategy_obj.manage_risk(bar, self.index_series, sub_pos.size)
                if risk_action:
                    self._execute_risk_action(risk_action, bar, dt, source_name)

            # 步骤5：月末换月
            if self.data_feed.is_roll_date(dt):
                self._handle_rollover(dt, bar)

            if self.account.position:
                self.account.update_market_value(bar["close"], dt)

        self._log("系统", "回测结束")

        if self.account.position and self.account.position.size != 0:
            self._handle_final_close(df, dates)

        self.log_file.close()

        # 打印仓位摘要
        print("\n" + "=" * 80)
        print("仓位管理摘要".center(80))
        print(self.pos_mgr.get_summary())
        print("=" * 80)

        report = self.analytics.generate_report(self.account)
        print(report)

        # 打印完整交易明细
        self._print_trade_details()

        return report

    def _execute_signal(self, signal: Signal, bar: dict, dt: datetime):
        """执行交易信号"""
        source = signal.source

        if signal.signal_type in ["close_long", "close_short"]:
            if self.account.position:
                sub_pos = self.pos_mgr.get_sub_position(source)
                if not sub_pos.has_position:
                    return  # 该策略无仓位，跳过

                close_size = min(signal.size, sub_pos.abs_size)
                if close_size <= 0:
                    return

                # 用子策略自己的入场价算盈亏（不依赖账户均价）
                if sub_pos.direction == "多":
                    pnl = (signal.entry_price - sub_pos.entry_price) * close_size
                else:
                    pnl = (sub_pos.entry_price - signal.entry_price) * close_size

                sub_pos.close(signal.entry_price, close_size)

                commission = CommissionCalculator.calculate_for_trade(signal.entry_price, close_size)
                trade = TradeRecord(
                    trade_id=generate_trade_id(), signal_type=signal.signal_type,
                    direction=sub_pos.direction,
                    entry_date=self.account.position.entry_date,
                    entry_price=sub_pos.entry_price,
                    exit_date=dt, exit_price=signal.entry_price,
                    size=close_size, pnl=pnl, commission=commission,
                    transfer_count=self.account.position.transfer_count,
                    is_closed=True, source=source,
                    contract=self.account.position.contract,
                )
                self.account.execute_strategy_trade(trade, source)

                # 如果是全平或只剩一个策略了
                new_size = abs(self.account.position.size) - close_size
                if new_size <= 0:
                    self.account.close_complete_trade(
                        exit_price=signal.entry_price, exit_date=dt,
                        commission=commission,
                        total_holding_days=self.account.position.total_holding_days
                        if self.account.position else 0,
                    )
                    self.account.position = None
                else:
                    # 只减仓，另一个策略继续持有
                    self.account.position.size = \
                        new_size if self.account.position.direction == "多" else -new_size
                    self.account.add_partial_close_to_complete_trade(
                        signal.entry_price, close_size, dt, commission)

                self._log("交易",
                    f"[{source}] {sub_pos.direction} {close_size}手 @ {signal.entry_price:.2f}, "
                    f"盈亏: {pnl:+,.2f} (子策略独立平仓) | {self.pos_mgr.get_summary()}"
                )

        elif signal.signal_type in ["buy", "sell"]:
            sub_pos = self.pos_mgr.get_sub_position(source)
            new_size = signal.size

            # 子策略仓位上限
            if source == "rsi":
                max_pos = self.config.rsi_strategy.max_position
                if sub_pos.direction == signal.direction:
                    if sub_pos.abs_size + new_size > max_pos:
                        new_size = max_pos - sub_pos.abs_size
                else:
                    if new_size > max_pos:
                        new_size = max_pos

            # 综合仓位上限
            if self.pos_mgr.net_abs_size + new_size > self.pos_mgr.combined_max:
                new_size = self.pos_mgr.combined_max - self.pos_mgr.net_abs_size

            if new_size <= 0:
                self._log("交易", f"[{source}] 仓位已达上限，跳过 {signal.direction} {signal.size}手")
                return

            signal.size = new_size

            if self.account.position and self.account.position.direction == signal.direction:
                # 同向加仓
                commission = CommissionCalculator.calculate_for_trade(signal.entry_price, signal.size)
                old_size = abs(self.account.position.size)
                old_price = self.account.position.entry_price
                total_val = old_size * old_price + new_size * signal.entry_price
                new_total = old_size + new_size
                new_avg = total_val / new_total

                self.account.position.size = new_total if signal.direction == "多" else -new_total
                self.account.position.entry_price = new_avg

                # 更新子策略仓位
                sub_pos.add(signal.entry_price, new_size)

                if self.account.current_complete_trade:
                    self.account.current_complete_trade.add_position(new_size, signal.entry_price, dt)

                self.account.current_capital -= commission
                self.account.commissions += commission

                self._log("交易",
                    f"[{source}] 加仓 {signal.direction} {new_size}手 @ {signal.entry_price:.2f}, "
                    f"累计: {new_total}手@{new_avg:.0f}, {signal.reason} | {self.pos_mgr.get_summary()}"
                )
            else:
                # 新开仓
                trade, position = OrderExecutor.open_position(
                    signal.direction, signal.entry_price, new_size, dt,
                    bar["current_contract"], signal.signal_type, source,
                )
                self.account.current_capital -= trade.commission
                self.account.commissions += trade.commission
                self.account.position = position

                sub_pos.open(signal.direction, signal.entry_price, new_size)

                self.account.start_complete_trade(
                    signal_type=signal.signal_type, direction=signal.direction,
                    entry_date=dt, entry_price=signal.entry_price, size=new_size, source=source,
                )

                self._log("交易",
                    f"[{source}] 开仓 {signal.direction} {new_size}手 @ {signal.entry_price:.2f}, "
                    f"手续费: {trade.commission:,.2f}, {signal.reason} | {self.pos_mgr.get_summary()}"
                )

        elif signal.signal_type in ["bull", "bear", "bobaniu"]:
            if not self.account.has_position():
                sub_pos = self.pos_mgr.get_sub_position(source)
                # 趋势策略通过分配器计算仓位
                ratio = self.config.trend_strategy.position_ratio
                size = self.allocator.get_trend_position(bar["open"], ratio)
                # 综合上限
                if size + self.pos_mgr.net_abs_size > self.pos_mgr.combined_max:
                    size = self.pos_mgr.combined_max - self.pos_mgr.net_abs_size
                if size <= 0:
                    return

                trade, position = OrderExecutor.open_position(
                    signal.direction, signal.entry_price, size, dt,
                    bar["current_contract"], signal.signal_type, source,
                )
                self.account.current_capital -= trade.commission
                self.account.commissions += trade.commission
                self.account.position = position

                sub_pos.open(signal.direction, signal.entry_price, size)

                self.account.start_complete_trade(
                    signal_type=signal.signal_type, direction=signal.direction,
                    entry_date=dt, entry_price=signal.entry_price, size=size, source=source,
                )
                self._log("交易",
                    f"[{source}] 开仓 {signal.direction} {size}手 @ {signal.entry_price:.2f}, "
                    f"手续费: {trade.commission:,.2f}, {signal.reason}"
                )
            else:
                self._log("交易", f"[{source}] 已有持仓，跳过趋势信号")

        elif signal.signal_type == "bobaniu_fail":
            if self.account.position and self.account.position.size != 0:
                sub_pos = self.pos_mgr.get_sub_position(source)
                old_size = abs(self.account.position.size)

                trade = OrderExecutor.close_position(
                    self.account.position, signal.entry_price, dt, "搏一把失败平仓"
                )
                trade.source = source
                self.account.execute_strategy_trade(trade, source)
                sub_pos.close(signal.entry_price, abs(sub_pos.size))
                self.account.position = None

                self._log("交易", f"[{source}] 平仓 {trade.size}手 @ {signal.entry_price:.2f}, 盈亏: {trade.pnl:+,.2f}")
            else:
                old_size = 0

            # 反向开仓
            if old_size > 0:
                sub_pos = self.pos_mgr.get_sub_position(source)
                trade, position = OrderExecutor.open_position(
                    signal.direction, signal.entry_price, old_size, dt,
                    bar["current_contract"], signal.signal_type, source,
                )
                self.account.current_capital -= trade.commission
                self.account.commissions += trade.commission
                self.account.position = position
                sub_pos.open(signal.direction, signal.entry_price, old_size)
                self._log("交易",
                    f"[{source}] 反向开仓 {signal.direction} {old_size}手 @ {signal.entry_price:.2f}"
                )

    def _execute_risk_action(self, action: RiskAction, bar: dict, dt: datetime, source: str):
        """执行风险管理"""
        if not self.account.position:
            return
        sub_pos = self.pos_mgr.get_sub_position(source)

        if action.action_type == "close_all":
            trade = OrderExecutor.close_position(
                self.account.position, action.price, dt, action.reason
            )
            trade.source = source
            self.account.execute_strategy_trade(trade, source)

            self.account.close_complete_trade(
                exit_price=action.price, exit_date=dt,
                commission=trade.commission,
                total_holding_days=self.account.position.total_holding_days
                if self.account.position else 0,
            )
            sub_pos.reset()

            self._log("风控",
                f"[{source}] 清仓 {trade.size}手 @ {action.price:.2f}, "
                f"盈亏: {trade.pnl:+,.2f}, {action.reason}"
            )
            self.account.position = None

        elif action.action_type == "reduce_half":
            trade, new_position = OrderExecutor.reduce_position(
                self.account.position, action.size, action.price, dt
            )
            trade.source = source
            self.account.execute_strategy_trade(trade, source)

            # 子策略同步减仓
            sub_pos.close(action.price, action.size)

            self.account.add_partial_close_to_complete_trade(
                close_price=action.price, close_size=action.size,
                close_date=dt, commission=trade.commission,
            )
            self.account.position = new_position
            self._log("风控",
                f"[{source}] 减仓 {trade.size}手 @ {action.price:.2f}, "
                f"盈亏: {trade.pnl:+,.2f}, {action.reason}"
            )

    def _execute_stop_loss_action(self, action: dict, bar: dict, dt: datetime):
        """执行止损"""
        if not self.account.position:
            return
        if action["stop_type"] == "趋势反转止损":
            exit_price = bar["low"] if self.account.position.direction == "多" else bar["high"]
        else:
            exit_price = action["price"]

        trade = OrderExecutor.close_position(
            self.account.position, exit_price, dt, action["reason"]
        )
        # 标记来源
        src = self.account.position.source
        trade.source = src
        self.account.execute_strategy_trade(trade, src)

        sub_pos = self.pos_mgr.get_sub_position(src)
        sub_pos.close(exit_price, abs(sub_pos.size))

        self.account.close_complete_trade(
            exit_price=exit_price, exit_date=dt,
            commission=trade.commission,
            total_holding_days=self.account.position.total_holding_days
            if self.account.position else 0,
        )

        self._log("止损",
            f"[{src}] 止损平仓 {trade.size}手 @ {exit_price:.2f}, "
            f"盈亏: {trade.pnl:+,.2f}, {action['stop_type']}"
        )
        self.account.position = None

    def _handle_rollover(self, dt: datetime, bar: dict):
        """处理月末换月（双策略各算各的）"""
        if not (self.account.position and self.account.position.size != 0):
            return

        position = self.account.position

        # 记录两个子策略各自的换月信息
        self._roll_infos = []
        for src_name in ["trend", "rsi"]:
            sub_pos = self.pos_mgr.get_sub_position(src_name)
            if sub_pos.has_position:
                # 用子策略自己的入场价算盈亏
                if sub_pos.direction == "多":
                    sub_pnl = (bar["close"] - sub_pos.entry_price) * sub_pos.abs_size
                else:
                    sub_pnl = (sub_pos.entry_price - bar["close"]) * sub_pos.abs_size

                # 记录信息（先close确保后续还要持仓记录）
                self._roll_infos.append({
                    "source": src_name,
                    "direction": sub_pos.direction,
                    "size": sub_pos.abs_size,
                    "old_contract": position.contract,
                    "close_price": bar["close"],
                    "close_date": dt,
                    "original_entry_price": sub_pos.entry_price,
                    "pnl": sub_pnl,
                })

                sub_pos.close(bar["close"], sub_pos.abs_size)

                close_trade = TradeRecord(
                    trade_id=generate_trade_id(), signal_type="月末换月",
                    direction=sub_pos.direction,
                    entry_date=position.entry_date,
                    entry_price=sub_pos.entry_price, exit_date=dt,
                    exit_price=bar["close"], size=sub_pos.abs_size,
                    pnl=sub_pnl, commission=0.0, transfer_count=0,
                    is_closed=True, source=src_name, contract=position.contract,
                )
                self.account.execute_strategy_trade(close_trade, src_name)

                self._log("换月",
                    f"月末平仓 [{src_name}] {sub_pos.direction} {sub_pos.abs_size}手 @ {bar['close']:.2f}, "
                    f"盈亏: {sub_pnl:+,.2f}"
                )

        self._pending_roll = True
        self.account.position = None

    def _execute_roll_open(self, dt: datetime, bar: dict):
        """执行月初开仓（双策略各开各的）"""
        infos = getattr(self, "_roll_infos", [])
        if not infos:
            return

        new_contract = self.data_feed.calendar.get_next_contract(infos[0]["old_contract"])
        if not new_contract:
            return

        total_size = 0
        total_direction = ""

        for info in infos:
            src = info["source"]
            price_gap = bar["open"] - info["close_price"]
            roll_adj = -price_gap * info["size"] if info["direction"] == "多" else price_gap * info["size"]

            # 换月调整记录
            transfer = TransferRecord(
                roll_date=dt, old_contract=info["old_contract"], new_contract=new_contract,
                old_close_price=info["close_price"], new_open_price=bar["open"],
                price_gap=price_gap, strategy_pnl=info["pnl"], roll_adjustment=roll_adj,
                size=info["size"], direction=info["direction"], source=src,
            )
            self.account.execute_rollover(transfer)

            # 重新开子策略仓位（检查仓位上限）
            sub_pos = self.pos_mgr.get_sub_position(src)
            reopen_size = info["size"]
            
            # RSI策略：不超过动态仓位上限
            if src == "rsi":
                rsi_max = self.allocator.get_rsi_max_position()
                if reopen_size > rsi_max:
                    self._log("换月", f"[rsi] 转仓仓位 {reopen_size}手 超过上限 {rsi_max}手，缩减至上限")
                    reopen_size = rsi_max
            
            # 综合仓位上限
            current_net = self.pos_mgr.net_abs_size
            if current_net + reopen_size > self.pos_mgr.combined_max:
                reopen_size = max(1, self.pos_mgr.combined_max - current_net)
                self._log("换月", f"[{src}] 转仓缩减至 {reopen_size}手（综合上限 {self.pos_mgr.combined_max}）")
            
            if reopen_size > 0:
                sub_pos.open(info["direction"], bar["open"], reopen_size)
                total_size += reopen_size
                total_direction = info["direction"]

            self._log("换月",
                f"月初开仓 [{src}] {info['direction']} {info['size']}手 @ {bar['open']:.2f}, "
                f"价差调整: {roll_adj:+,.2f}"
            )

        # 重新设置账户综合仓位
        if total_size > 0:
            self.account.position = Position(
                contract=new_contract,
                size=total_size if total_direction == "多" else -total_size,
                direction=total_direction, entry_price=bar["open"], entry_date=dt,
                original_entry_price=bar["open"],
                trade_id="", source="combined",
                total_holding_days=0, transfer_count=0,
            )

    def _handle_final_close(self, df, dates):
        """处理回测结束平仓 — 分别平掉两个子策略的仓位"""
        last_dt = dates[-1]
        last_bar = df.loc[last_dt].to_dict()
        last_bar["datetime"] = last_dt
        position = self.account.position

        if not position or position.size == 0:
            return

        # 分别处理每个子策略的平仓
        for src_name in ["trend", "rsi"]:
            sub_pos = self.pos_mgr.get_sub_position(src_name)
            if not sub_pos.has_position:
                continue

            if sub_pos.direction == "多":
                pnl = (last_bar["close"] - sub_pos.entry_price) * sub_pos.abs_size
            else:
                pnl = (sub_pos.entry_price - last_bar["close"]) * sub_pos.abs_size

            trade = TradeRecord(
                trade_id=generate_trade_id(), signal_type="回测结束平仓",
                direction=sub_pos.direction, entry_date=position.entry_date,
                entry_price=sub_pos.entry_price, exit_date=last_dt,
                exit_price=last_bar["close"], size=sub_pos.abs_size,
                pnl=pnl, commission=0.0, transfer_count=position.transfer_count,
                is_closed=True, source=src_name, contract=position.contract,
            )
            self.account.execute_strategy_trade(trade, src_name)
            sub_pos.close(last_bar["close"], sub_pos.abs_size)

            self._log("系统", f"回测结束平仓 [{src_name}] {sub_pos.direction} {sub_pos.abs_size}手 @ {last_bar['close']:.2f}, 盈亏: {pnl:+,.2f}")

        self.account.close_complete_trade(
            exit_price=last_bar["close"], exit_date=last_dt, commission=0.0,
            total_holding_days=position.total_holding_days,
        )
        self.account.position = None

    def _print_trade_details(self):
        """打印完整交易明细"""
        print("\n" + "=" * 98)
        print("完整交易明细".center(98))
        print("-" * 98)
        print(f"{'交易ID':<12} | {'来源':<6} | {'方向':<4} | {'开仓日期':<12} | {'开仓价':<9} | {'平仓日期':<12} | {'平仓价':<9} | {'数量':<5} | {'盈亏':<10} | {'策略'}")
        print("-" * 98)
        for ct in self.account.complete_trades:
            pnl = ct.get_total_pnl()
            src = ct.source
            print(f"{ct.original_entry_date.strftime('%Y-%m-%d') if hasattr(ct.original_entry_date, 'strftime') else str(ct.original_entry_date)[:10]:<12} | "
                  f"{src:<6} | {ct.direction:<4} | "
                  f"{ct.original_entry_date.strftime('%Y-%m-%d') if hasattr(ct.original_entry_date, 'strftime') else str(ct.original_entry_date)[:10]:<12} | "
                  f"{ct.original_entry_price:<9.0f} | "
                  f"{ct.exit_date.strftime('%Y-%m-%d') if hasattr(ct.exit_date, 'strftime') else str(ct.exit_date)[:10] if ct.exit_date else '':<12} | "
                  f"{ct.exit_price or 0:<9.0f} | "
                  f"{ct.initial_size:<5} | {pnl:<+10,.0f} | {src}")

    def _log(self, category: str, message: str):
        date_str = ""
        if hasattr(self, "current_date"):
            dt = self.current_date
            date_str = dt.strftime("%Y-%m-%d") if hasattr(dt, "strftime") else str(dt)[:10]

        log_line = f"[{date_str}] [{category}] {message}" if date_str else f"[{category}] {message}"
        print(log_line)
        if self.log_file:
            self.log_file.write(log_line + "\n")
            self.log_file.flush()
