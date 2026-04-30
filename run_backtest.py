"""
运行双策略回测
"""
import sys
import os

project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from config import EngineConfig
from core.engine import FuturesBacktestEngine


def main():
    config = EngineConfig()
    engine = FuturesBacktestEngine(config)
    report = engine.run()

    # 保存报告
    report_path = os.path.join(project_root, "backtest_report.txt")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\n报告已保存至: {report_path}")


if __name__ == "__main__":
    main()
