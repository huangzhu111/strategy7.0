"""
绩效归因分析 — 双策略版本
"""
from portfolio.account import FuturesAccount


class PerformanceAttribution:
    """绩效归因"""

    def generate_report(self, account: FuturesAccount) -> str:
        perf = account.get_performance_summary()
        lines = []
        lines.append("=" * 98)
        lines.append("策略7.0 双策略绩效归因报告".center(98))
        lines.append("=" * 98)
        lines.append("")
        lines.append("一、综合绩效".center(98))
        lines.append("-" * 98)
        lines.append(f"初始资金: {perf['initial_capital']:,.2f}")
        lines.append(f"最终资金: {perf['final_capital']:,.2f}")
        lines.append("")
        strategy_return = ((perf['final_capital'] - perf['initial_capital']) / perf['initial_capital'] * 100) if perf['initial_capital'] > 0 else 0
        lines.append(f"策略收益率: {strategy_return:.2f}%")
        lines.append(f"手续费成本: {perf['commissions']:,.2f}")
        net_return = ((perf['final_capital'] - perf['initial_capital'] + perf['commissions']) / perf['initial_capital'] * 100) if perf['initial_capital'] > 0 else 0
        lines.append(f"净收益率: {net_return:.2f}%")

        lines.append("")
        lines.append("二、双策略盈亏分解".center(98))
        lines.append("-" * 98)
        lines.append(f"趋势策略盈亏: {perf['trend_pnl']:+,.2f}")
        lines.append(f"RSI策略盈亏:   {perf['rsi_pnl']:+,.2f}")
        lines.append(f"策略盈亏合计:  {perf['strategy_pnl']:+,.2f}")
        lines.append(f"换月价差调整:  {perf['roll_adjustments']:+,.2f}")
        lines.append(f"净盈亏:        {perf['net_pnl']:+,.2f}")

        lines.append("")
        lines.append("三、风险指标".center(98))
        lines.append("-" * 98)
        lines.append(f"最大回撤: {perf['max_drawdown']:,.2f}")
        dd_rate = (perf['max_drawdown'] / perf['peak_value'] * 100) if perf['peak_value'] > 0 else 0
        lines.append(f"最大回撤率: {dd_rate:.2f}%")
        lines.append(f"峰值资金: {perf['peak_value']:,.2f}")

        lines.append("")
        lines.append("四、交易统计".center(98))
        lines.append("-" * 98)
        lines.append(f"趋势策略交易笔数: {perf['trend_trades']}")
        lines.append(f"RSI策略交易笔数:   {perf['rsi_trades']}")
        lines.append(f"总交易笔数:        {perf['trade_count']}")
        lines.append(f"换月次数: {perf['transfer_count']}")

        # 统计每个子策略的胜率
        for name, sub in [("趋势", account.trend_pnl), ("RSI", account.rsi_pnl)]:
            if sub.complete_trades:
                wins = sum(1 for t in sub.complete_trades if t.get_total_pnl() > 0)
                total = len(sub.complete_trades)
                pnl = sum(t.get_total_pnl() for t in sub.complete_trades)
                lines.append(f"")
                lines.append(f"  {name}策略完整交易: {total}笔, 盈利: {wins}笔 ({wins/total*100:.2f}%), 总盈亏: {pnl:+,.2f}")

        lines.append("")
        lines.append("=" * 98)
        lines.append("重要说明：")
        lines.append("1. 策略盈亏 = 趋势策略 + RSI策略 的实际交易盈亏（不含换月价差）")
        lines.append("2. 换月价差调整 = 新旧合约价格差异产生的资金调整")
        lines.append("3. 最终资金 = 初始资金 + 策略盈亏合计 + 换月调整 - 手续费")
        lines.append("=" * 98)

        return "\n".join(lines)
