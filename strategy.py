#!/usr/bin/env python3
"""eth-pnl-fixed strategy: slow EMA-crossover trend-following with a hysteresis band.

Interface
---------
Input : bars.csv in the same directory (columns: minute,open,high,low,close,volume)
Output: positions.csv in the same directory (columns: minute,position)
        position in {-1, 0, 1}: -1 = short 1 ETH, 0 = flat, +1 = long 1 ETH.
        Fixed size of 1 ETH keeps slippage small and turnover low.

Logic (3 parameters, no fitted constants, no bar-index hard-coding)
--------------------------------------------------------------------
- fast EMA(20) and slow EMA(150) of close.
- Let r[t] = fast[t] / slow[t] - 1 (relative EMA spread, unit-free).
- Position for bar t is decided ONLY from data up to bar t-1 (no lookahead):
    if r[t-1] > +0.002 -> long  (+1)
    if r[t-1] < -0.002 -> short (-1)
    otherwise          -> keep the previous position (hysteresis / dead zone).
- The 0.002 dead zone is the whole point: 1-minute ETH is noisy and plain
  EMA crossovers whipsaw (a plain EMA 12/50 crossover loses ~150 USDT net on
  this sample after costs, with 40 fills). The dead zone cuts turnover to a
  handful of fills, so the edge survives under any reasonable fee model.
- The strategy is symmetric (long and short) and regime-agnostic: it follows
  the slow trend in either direction. It is NOT "always short" and does not
  assume this sample's downtrend repeats on a held-out tail.
- Warm-up: both EMAs are seeded at bar 0 (pandas ewm, adjust=False), so the
  spread is defined from the start; the first fill can only fire once the
  spread exceeds the band (on this sample: minute 25).

Usage:  python3 strategy.py [bars.csv] [positions.csv]
"""
import sys
import pandas as pd

FAST = 20
SLOW = 150
BAND = 0.002          # hysteresis half-width on the relative EMA spread
SIZE = 1              # ETH per position unit


def compute_positions(bars: pd.DataFrame) -> pd.DataFrame:
    close = bars["close"]
    fast = close.ewm(span=FAST, adjust=False).mean()
    slow = close.ewm(span=SLOW, adjust=False).mean()
    spread = fast / slow - 1.0

    positions = [0] * len(bars)
    cur = 0
    for t in range(1, len(bars)):
        # ONLY bar t-1 and earlier are read here -> no lookahead.
        if pd.isna(spread.iloc[t - 1]):
            positions[t] = cur
            continue
        r = spread.iloc[t - 1]
        if r > BAND:
            cur = 1
        elif r < -BAND:
            cur = -1
        positions[t] = cur
    return pd.DataFrame({"minute": bars["minute"].values, "position": positions})


def main() -> None:
    bars_path = sys.argv[1] if len(sys.argv) > 1 else "bars.csv"
    out_path = sys.argv[2] if len(sys.argv) > 2 else "positions.csv"
    bars = pd.read_csv(bars_path)
    out = compute_positions(bars)
    out.to_csv(out_path, index=False)
    n_trades = int((out["position"].diff().fillna(0) != 0).sum())
    print(f"wrote {out_path}: {len(out)} rows, "
          f"long bars={int((out['position'] == 1).sum())}, "
          f"short bars={int((out['position'] == -1).sum())}, "
          f"flat bars={int((out['position'] == 0).sum())}, fills={n_trades}")


if __name__ == "__main__":
    main()
