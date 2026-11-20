"""Seeded risk history, layered hedges and educational effectiveness screens."""
import numpy as np
import pandas as pd
from . import config as C

# CONFIG
RISK_QUANTITIES = {C.FX: C.EUR_REVENUE, C.COPPER: C.COPPER_TONNES, C.RATE: C.CORPORATE_DEBT}
RISK_NAMES = tuple(RISK_QUANTITIES)


def risk_history():
    rng = np.random.default_rng(C.SEED)
    count = C.HISTORY_DAYS + C.MONTHS * C.MONTH_DAYS
    shocks = {risk: rng.normal(size=count) for risk in RISK_NAMES}
    fx = C.FX_INITIAL * np.exp(np.cumsum(
        -0.5 * C.FX_VOL ** 2 / C.TRADING_DAYS + C.FX_VOL / np.sqrt(C.TRADING_DAYS) * shocks[C.FX]))
    copper = C.COPPER_INITIAL * np.exp(np.cumsum(
        -0.5 * C.COPPER_VOL ** 2 / C.TRADING_DAYS + C.COPPER_VOL / np.sqrt(C.TRADING_DAYS) * shocks[C.COPPER]))
    rates = []
    rate = C.RATE_INITIAL
    for shock in shocks[C.RATE]:
        rate = max(C.RATE_FLOOR, rate + C.RATE_REVERSION * (C.RATE_INITIAL - rate)
                   / C.TRADING_DAYS + C.RATE_VOL / np.sqrt(C.TRADING_DAYS) * shock)
        rates.append(rate)
    full = pd.DataFrame({C.FX: fx, C.COPPER: copper, C.RATE: rates})
    history = full.head(C.HISTORY_DAYS).copy()
    history.insert(0, C.DATE, pd.bdate_range(C.HISTORY_START, periods=C.HISTORY_DAYS))
    future = full.tail(C.MONTHS * C.MONTH_DAYS).copy()
    future = future.groupby(np.arange(len(future)) // C.MONTH_DAYS).last().reset_index(drop=True)
    future.insert(0, C.DATE, pd.date_range(C.START, periods=C.MONTHS, freq="MS"))
    print(f"Synthetic history: {len(history)} daily observations; forecast: {len(future)} months")
    return history, future


def build_hedges(history, future):
    spot = history.loc[history.index[-1], list(RISK_NAMES)]
    rows = []
    for month, date in enumerate(future[C.DATE], start=1):
        ratio = next(r for end, r in zip(C.LAYER_ENDS, C.LAYER_RATIOS) if month <= end)
        for risk, quantity in RISK_QUANTITIES.items():
            hedge_ratio = 1.0 if risk == C.RATE else ratio
            strike = float(spot[risk])
            if risk == C.FX:
                strike *= np.exp((C.USD_DISCOUNT - C.EUR_DISCOUNT) * month / 12)
            rows.append({C.MONTH: month, C.MATURITY: date, C.KIND: risk,
                         C.QUANTITY: quantity, C.RATIO: hedge_ratio,
                         C.NOTIONAL: quantity * hedge_ratio, C.STRIKE: strike})
    hedges = pd.DataFrame(rows)
    print(f"Hedge schedule: {len(hedges)} monthly positions; FX/metals layers {C.LAYER_RATIOS}")
    return hedges


def effectiveness(derivative_changes, item_changes):
    x = -np.asarray(item_changes, dtype=float)
    y = np.asarray(derivative_changes, dtype=float)
    if len(x) < C.EFFECT_MIN_OBSERVATIONS or np.std(x) <= C.TOLERANCE or np.std(y) <= C.TOLERANCE:
        return {C.SLOPE: np.nan, C.R2: np.nan, C.OFFSET: np.nan, C.PASS: False}
    slope, intercept = np.linalg.lstsq(np.column_stack((x, np.ones(len(x)))), y, rcond=None)[0]
    r2 = 1 - np.sum((y - (slope * x + intercept)) ** 2) / np.sum((y - y.mean()) ** 2)
    offset = np.sum(np.abs(y)) / np.sum(np.abs(x))
    passed = C.EFFECT_SLOPE_MIN <= slope <= C.EFFECT_SLOPE_MAX and r2 >= C.EFFECT_R2_MIN and C.OFFSET_MIN <= offset <= C.OFFSET_MAX
    return {C.SLOPE: slope, C.R2: r2, C.OFFSET: offset, C.PASS: bool(passed)}


def valuation(hedges, future):
    rows = []
    for deal in hedges.to_dict("records"):
        previous = 0.0
        for month, observation in enumerate(future.head(deal[C.MONTH]).to_dict("records"), start=1):
            remaining = (deal[C.MONTH] - month) / 12
            risk = deal[C.KIND]
            market = observation[risk]
            if risk == C.FX:
                market *= np.exp((C.USD_DISCOUNT - C.EUR_DISCOUNT) * remaining)
            direction = -1 if risk == C.FX else 1
            accrual = 1 / 12 if risk == C.RATE else 1
            value = direction * deal[C.NOTIONAL] * (market - deal[C.STRIKE]) * accrual * np.exp(-C.USD_DISCOUNT * remaining)
            change = value - previous
            rows.append({C.DATE: observation[C.DATE], C.MATURITY: deal[C.MATURITY], C.KIND: risk,
                         C.MTM: value, C.CHANGE: change, C.ITEM_CHANGE: -change})
            previous = value
    mtm = pd.DataFrame(rows)
    stats = []
    for risk, group in mtm.groupby(C.KIND):
        monthly = group.groupby(C.DATE)[[C.CHANGE, C.ITEM_CHANGE]].sum()
        stats.append({C.KIND: risk, **effectiveness(monthly[C.CHANGE], monthly[C.ITEM_CHANGE])})
    stats = pd.DataFrame(stats)
    passed = mtm[C.KIND].map(stats.set_index(C.KIND)[C.PASS])
    effective = np.minimum(mtm[C.CHANGE].abs(), mtm[C.ITEM_CHANGE].abs()) * np.sign(mtm[C.CHANGE])
    mtm[C.OCI] = np.where(passed, effective, 0.0)
    mtm[C.EARNINGS] = mtm[C.CHANGE] - mtm[C.OCI]
    print(f"Educational effectiveness screens passed: {int(stats[C.PASS].sum())}/{len(stats)}")
    return mtm, stats


def cashflows(hedges, future):
    rows = []
    for observation in future.to_dict("records"):
        unhedged = C.EUR_REVENUE * observation[C.FX] - C.COPPER_TONNES * observation[C.COPPER] - C.CORPORATE_DEBT * (observation[C.RATE] + C.DEBT_SPREAD) / 12
        settlement = 0.0
        for deal in hedges.loc[hedges[C.MATURITY] == observation[C.DATE]].to_dict("records"):
            direction = -1 if deal[C.KIND] == C.FX else 1
            accrual = 1 / 12 if deal[C.KIND] == C.RATE else 1
            settlement += direction * deal[C.NOTIONAL] * (observation[deal[C.KIND]] - deal[C.STRIKE]) * accrual
        rows.append({C.DATE: observation[C.DATE], C.UNHEDGED: unhedged,
                     C.SETTLEMENT: settlement, C.HEDGED: unhedged + settlement})
    return pd.DataFrame(rows)


def historical_var(history, hedges):
    lag = C.MONTH_DAYS
    shocks = pd.DataFrame({C.FX: history[C.FX].pct_change(lag),
                           C.COPPER: history[C.COPPER].pct_change(lag),
                           C.RATE: history[C.RATE].diff(lag)}).dropna()
    spot = history.loc[history.index[-1]]
    results = []
    for month, group in hedges.groupby(C.MONTH):
        quantities = group.set_index(C.KIND)[C.QUANTITY]
        residual = quantities - group.set_index(C.KIND)[C.NOTIONAL]
        def losses(amounts):
            return -(amounts[C.FX] * spot[C.FX] * shocks[C.FX]
                     - amounts[C.COPPER] * spot[C.COPPER] * shocks[C.COPPER]
                     - amounts[C.RATE] * shocks[C.RATE] / 12)
        raw = float(np.quantile(losses(quantities), C.VAR_CONFIDENCE))
        hedged = float(np.quantile(losses(residual), C.VAR_CONFIDENCE))
        results.append({C.MONTH: month, C.UNHEDGED: raw, C.HEDGED: hedged})
    result = pd.DataFrame(results)
    print(f"One-month {C.VAR_CONFIDENCE:.0%} cash-flow VaR, first layer: ${result[C.UNHEDGED].iat[0]:,.0f} unhedged; ${result[C.HEDGED].iat[0]:,.0f} hedged")
    return result
