"""Recompute headline results from CSVs and scalar math, without model functions."""
import calendar
import csv
import importlib.util
import json
import math
import sys
from datetime import datetime
from pathlib import Path

# CONFIG
ROOT = Path(__file__).resolve().parents[1]
SUMMARY_PATH = ROOT / "outputs" / "summary.json"
HISTORY_PATH = ROOT / "data" / "history.csv"
BUDGET_PATH = ROOT / "data" / "solar_budget.csv"
ACTUAL_PATH = ROOT / "data" / "solar_actuals.csv"
DEBT_PATH = ROOT / "outputs" / "debt.csv"
VAR_PATH = ROOT / "outputs" / "cashflow_var.csv"
WATERFALL_PATHS = (ROOT / "outputs" / "budget_waterfall.csv",
                   ROOT / "outputs" / "actual_waterfall.csv")
ABSOLUTE_TOLERANCE = 1e-4
DEPENDENCIES = ("numpy", "pandas", "openpyxl", "matplotlib", "pytest")
sys.path.insert(0, str(ROOT))
from python import config as C


def records(path):
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def quantile(values, probability):
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    return ordered[lower] + (position - lower) * (ordered[upper] - ordered[lower])


def test_independent_var():
    metrics = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
    history = records(HISTORY_PATH)
    spot = history[-1]
    raw_losses, residual_losses = [], []
    for current, previous in zip(history[C.MONTH_DAYS:], history):
        fx_change = float(current[C.FX]) / float(previous[C.FX]) - 1
        copper_change = float(current[C.COPPER]) / float(previous[C.COPPER]) - 1
        rate_change = float(current[C.RATE]) - float(previous[C.RATE])
        fx_cash = C.EUR_REVENUE * float(spot[C.FX]) * fx_change
        copper_cash = -C.COPPER_TONNES * float(spot[C.COPPER]) * copper_change
        interest_cash = -C.CORPORATE_DEBT * rate_change / 12
        raw_losses.append(-(fx_cash + copper_cash + interest_cash))
        residual_losses.append(-(fx_cash + copper_cash))
    unhedged = quantile(raw_losses, C.VAR_CONFIDENCE)
    for row in records(VAR_PATH):
        month = int(float(row[C.MONTH]))
        ratio = next(ratio for end, ratio in zip(C.LAYER_ENDS, C.LAYER_RATIOS) if month <= end)
        hedged = quantile([(1 - ratio) * loss for loss in residual_losses], C.VAR_CONFIDENCE)
        assert abs(unhedged - float(row[C.UNHEDGED])) < ABSOLUTE_TOLERANCE
        assert abs(hedged - float(row[C.HEDGED])) < ABSOLUTE_TOLERANCE
    first_hedged = quantile([(1 - C.LAYER_RATIOS[0]) * loss for loss in residual_losses], C.VAR_CONFIDENCE)
    assert abs(unhedged - metrics["var_unhedged_usd"]) < ABSOLUTE_TOLERANCE
    assert abs(first_hedged - metrics["var_hedged_usd"]) < ABSOLUTE_TOLERANCE
    print(f"PASS independent VaR: ${unhedged:,.6f} unhedged; ${first_hedged:,.6f} hedged")


def test_independent_ppa_and_debt():
    metrics = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
    budget = records(BUDGET_PATH)
    energy_pv, opex_pv = [], []
    for row in budget:
        month = int(float(row[C.MONTH]))
        date = datetime.fromisoformat(row[C.DATE])
        age = (month - 1) / 12
        season = 1 + C.SEASON_AMPLITUDE * math.cos(2 * math.pi * (date.month - C.SEASON_PEAK_MONTH) / 12)
        energy = C.SOLAR_MW * calendar.monthrange(date.year, date.month)[1] * 24 * C.CAPACITY_FACTOR
        energy *= C.AVAILABILITY * season * (1 - C.DEGRADATION) ** age
        opex = C.ANNUAL_OPEX / 12 * (1 + C.OPEX_ESCALATION) ** age
        discount = (1 + C.SOLAR_RATE / 12) ** -month
        assert abs(energy - float(row[C.ENERGY])) < ABSOLUTE_TOLERANCE
        energy_pv.append(energy * discount)
        opex_pv.append(opex * discount)
    tariff = (C.SOLAR_DEBT * C.TARGET_DSCR + math.fsum(opex_pv)) / math.fsum(energy_pv)
    assert abs(tariff - metrics["solar_ppa_usd_mwh"]) < ABSOLUTE_TOLERANCE
    debt_by_date = {row[C.DATE]: row for row in records(DEBT_PATH)}
    balance = C.SOLAR_DEBT
    for row in budget:
        service = (float(row[C.ENERGY]) * tariff - float(row[C.OPEX])) / C.TARGET_DSCR
        balance = balance * (1 + C.SOLAR_RATE / 12) - service
        assert abs(service - float(debt_by_date[row[C.DATE]][C.SERVICE])) < ABSOLUTE_TOLERANCE
        assert abs(balance - float(debt_by_date[row[C.DATE]][C.BALANCE])) < ABSOLUTE_TOLERANCE
    assert abs(balance) < ABSOLUTE_TOLERANCE
    print(f"PASS independent PPA: ${tariff:.9f}/MWh; ending debt ${balance:.9f}")


def test_independent_variance_and_cash():
    metrics = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
    budget = {row[C.DATE]: row for row in records(BUDGET_PATH)}
    debt = {row[C.DATE]: row for row in records(DEBT_PATH)}
    changes = []
    actual_dscr = []
    for actual in records(ACTUAL_PATH):
        base = budget[actual[C.DATE]]
        actual_ebitda = float(actual[C.ENERGY]) * float(actual[C.PPA]) - float(actual[C.OPEX])
        budget_ebitda = float(base[C.ENERGY]) * float(base[C.PPA]) - float(base[C.OPEX])
        changes.append(actual_ebitda - budget_ebitda)
        actual_dscr.append(actual_ebitda / float(debt[actual[C.DATE]][C.SERVICE]))
    variance = math.fsum(changes)
    assert abs(variance - metrics["actual_ebitda_variance_usd"]) < ABSOLUTE_TOLERANCE
    assert abs(min(actual_dscr) - metrics["actual_min_dscr"]) < ABSOLUTE_TOLERANCE
    assert sum(value < C.COVENANT_DSCR for value in actual_dscr) == metrics["actual_covenant_breaches"]
    initial_dsra = math.fsum(float(row[C.SERVICE]) for row in records(DEBT_PATH)[:C.DSRA_MONTHS])
    max_error = 0.0
    for path in WATERFALL_PATHS:
        opening_total = C.INITIAL_CASH + initial_dsra + C.INITIAL_MAINTENANCE
        for row in records(path):
            ending_total = math.fsum(float(row[column]) for column in (C.CLOSE_CASH, C.DSRA, C.MAINT))
            external_change = float(row[C.CFADS]) - float(row[C.SERVICE])
            external_change -= float(row[C.MAINT_SPEND]) + float(row[C.DISTRIBUTION])
            max_error = max(max_error, abs(ending_total - opening_total - external_change))
            opening_total = ending_total
    assert max_error < ABSOLUTE_TOLERANCE
    print(f"PASS independent EBITDA variance: ${variance:,.6f}; cash error ${max_error:.9f}")


def main():
    for dependency in DEPENDENCIES:
        status = "available" if importlib.util.find_spec(dependency) else "MISSING"
        print(f"Runtime dependency: {dependency} {status}")
    test_independent_var()
    test_independent_ppa_and_debt()
    test_independent_variance_and_cash()
    print("3 independent numerical checks passed")


if __name__ == "__main__":
    main()
