# Strategy 7.0

Combined FFA Trading Strategy - merging strategy5.0 and strategy6.0.

## Overview

- **Strategies**: 5.0 (legacy) + 6.0 (RSI-based) → 7.0 (combined)
- **Asset**: Capesize FFA (M1 contract)
- **Signal**: RSI-based with position sizing

## Structure

```
strategy7.0/
├── strategy/    # Strategy logic
├── core/        # Data feed, indicators, engine
├── execution/   # Trade execution, rollover
├── portfolio/   # Account, position tracking
├── risk/        # Risk management, stop-loss
├── analytics/   # Performance analysis
└── config.py    # Configuration
```
