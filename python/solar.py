"""Solar budget, exact debt sculpt, cash waterfall and variance bridge."""
import numpy as np
import pandas as pd
from . import config as C

# CONFIG
SOLAR_SEED = C.SEED + 1


def budget():
    dates = pd.date_range(C.START, periods=C.SOLAR_YEARS * 12, freq="MS")
    age = np.arange(len(dates)) / 12
    season = 1 + C.SEASON_AMPLITUDE * np.cos(2 * np.pi * (dates.month - C.SEASON_PEAK_MONTH) / 12)
    energy = C.SOLAR_MW * dates.days_in_month * 24 * C.CAPACITY_FACTOR * C.AVAILABILITY * season * (1 - C.DEGRADATION) ** age
    opex = C.ANNUAL_OPEX / 12 * (1 + C.OPEX_ESCALATION) ** age
    discount = (1 + C.SOLAR_RATE / 12) ** -np.arange(1, len(dates) + 1)
    tariff = (C.SOLAR_DEBT * C.TARGET_DSCR + np.sum(opex * discount)) / np.sum(energy * discount)
    frame = pd.DataFrame({C.DATE: dates, C.MONTH: np.arange(1, len(dates) + 1),
                          C.ENERGY: energy, C.PPA: tariff, C.OPEX: opex})
    frame[C.REVENUE] = frame[C.ENERGY] * frame[C.PPA]
    frame[C.EBITDA] = frame[C.REVENUE] - frame[C.OPEX]
    frame[C.CFADS] = frame[C.EBITDA]
    print(f"Solar budget: {C.SOLAR_MW:g} MW, calibrated flat PPA ${tariff:.2f}/MWh")
    return frame


def sculpt(frame):
    frame = frame.sort_values(C.DATE)
    if frame[C.DATE].duplicated().any():
        raise ValueError("Duplicate budget dates")
    balance = C.SOLAR_DEBT
    rows = []
    for row in frame.to_dict("records"):
        service = row[C.CFADS] / C.TARGET_DSCR
        interest = balance * C.SOLAR_RATE / 12
        principal = service - interest
        balance -= principal
        if principal < -C.TOLERANCE or balance < -C.TOLERANCE:
            raise ValueError("Debt sculpt infeasible under configured cash flows")
        rows.append({C.DATE: row[C.DATE], C.SERVICE: service, C.INTEREST: interest,
                     C.PRINCIPAL: principal, C.BALANCE: max(0.0, balance), C.DSCR: row[C.CFADS] / service})
    result = pd.DataFrame(rows)
    if abs(balance) > C.TOLERANCE:
        raise ValueError("Debt does not fully amortize")
    print(f"Debt sculpt: ${C.SOLAR_DEBT:,.0f}; target DSCR {C.TARGET_DSCR:.2f}; ending debt ${balance:.8f}")
    return result


def actuals(frame):
    rng = np.random.default_rng(SOLAR_SEED)
    result = frame.head(C.MONTHS).copy()
    availability = np.where(result[C.MONTH] >= C.ACTUAL_CHANGE_MONTH,
                            (C.AVAILABILITY + C.ACTUAL_AVAILABILITY_CHANGE) / C.AVAILABILITY, 1.0)
    result[C.ENERGY] *= availability * (1 + rng.normal(0, C.IRRADIANCE_NOISE, len(result)))
    recurring_opex = result[C.OPEX] * (1 + C.ACTUAL_OPEX_PREMIUM + rng.normal(0, C.OPEX_NOISE, len(result)))
    one_time = np.where(result[C.MONTH] == C.ONE_TIME_MONTH, C.ONE_TIME_COST, 0.0)
    result[C.OPEX] = recurring_opex + one_time
    result[C.REVENUE] = result[C.ENERGY] * result[C.PPA]
    result[C.EBITDA] = result[C.REVENUE] - result[C.OPEX]
    result[C.CFADS] = result[C.EBITDA]
    base = frame.head(C.MONTHS)
    variance = pd.DataFrame({C.DATE: result[C.DATE], C.BUDGET: base[C.EBITDA], C.ACTUAL: result[C.EBITDA],
                             C.ENERGY_VARIANCE: (result[C.ENERGY] - base[C.ENERGY]) * base[C.PPA],
                             C.PRICE_VARIANCE: result[C.ENERGY] * (result[C.PPA] - base[C.PPA]),
                             C.RECURRING: -(recurring_opex - base[C.OPEX]), C.ONE_TIME: -one_time})
    variance[C.VARIANCE] = variance[C.ACTUAL] - variance[C.BUDGET]
    print(f"{len(result)}-month actual EBITDA variance: ${variance[C.VARIANCE].sum():,.0f}; one-time ${variance[C.ONE_TIME].sum():,.0f}")
    return result, variance


def align_debt(frame, debt):
    aligned = frame.merge(debt[[C.DATE, C.SERVICE]], on=C.DATE, how="left", validate="one_to_one")
    if aligned[C.SERVICE].isna().any() or (aligned[C.SERVICE] <= 0).any():
        raise ValueError("Every cash-flow date requires positive scheduled debt service")
    return aligned.sort_values(C.DATE).reset_index(drop=True)


def waterfall(frame, debt):
    debt = debt.sort_values(C.DATE)
    aligned = align_debt(frame, debt)
    if not aligned[C.DATE].equals(debt[C.DATE].head(len(aligned)).reset_index(drop=True)):
        raise ValueError("Waterfall requires consecutive debt dates from inception")
    cash = C.INITIAL_CASH
    dsra = debt[C.SERVICE].head(C.DSRA_MONTHS).sum()
    maintenance = C.INITIAL_MAINTENANCE
    rows = []
    for row in aligned.to_dict("records"):
        month = row[C.MONTH]
        opening_cash, opening_dsra, opening_maintenance = cash, dsra, maintenance
        service = row[C.SERVICE]
        spend = C.MAINTENANCE_EVENT_COST if month == C.MAINTENANCE_EVENT_MONTH else 0.0
        reserve_spend = min(maintenance, spend)
        maintenance -= reserve_spend
        cash += row[C.CFADS] - service - (spend - reserve_spend)
        draw = min(dsra, max(0.0, -cash))
        dsra -= draw
        cash += draw
        target = debt.loc[(debt[C.DATE] > row[C.DATE])].head(C.DSRA_MONTHS)[C.SERVICE].sum()
        release = max(0.0, dsra - target)
        dsra -= release
        cash += release
        topup = min(max(0.0, cash - C.CASH_FLOOR), max(0.0, target - dsra))
        dsra += topup
        cash -= topup
        contribution = min(C.MAINTENANCE_MONTHLY, max(0.0, cash - C.CASH_FLOOR))
        maintenance += contribution
        cash -= contribution
        breach = row[C.CFADS] / service < C.COVENANT_DSCR
        distribution = max(0.0, cash - C.CASH_FLOOR) if not breach and dsra >= target - C.TOLERANCE else 0.0
        cash -= distribution
        residual = cash + dsra + maintenance - (opening_cash + opening_dsra + opening_maintenance + row[C.CFADS] - service - spend - distribution)
        rows.append({C.DATE: row[C.DATE], C.OPEN_CASH: opening_cash, C.CFADS: row[C.CFADS],
                     C.SERVICE: service, C.DSCR: row[C.CFADS] / service, C.BREACH: breach,
                     C.DSRA_TRANSFER: topup - draw - release, C.MAINT_TRANSFER: contribution,
                     C.MAINT_SPEND: spend, C.DSRA: dsra, C.MAINT: maintenance,
                     C.DISTRIBUTION: distribution, C.CLOSE_CASH: cash,
                     C.SHORTFALL: max(0.0, -cash), C.RESIDUAL: residual})
    result = pd.DataFrame(rows)
    print(f"Waterfall: minimum DSCR {result[C.DSCR].min():.3f}; breaches {int(result[C.BREACH].sum())}; maximum cash residual ${result[C.RESIDUAL].abs().max():.9f}")
    return result


def sensitivities(frame, debt):
    frame = align_debt(frame, debt)
    rows = []
    for name, irradiance, price, opex in C.SCENARIOS:
        case = frame.copy()
        case[C.REVENUE] = case[C.ENERGY] * irradiance * case[C.PPA] * price
        case[C.OPEX] *= opex
        case[C.CFADS] = case[C.REVENUE] - case[C.OPEX]
        dscr = case[C.CFADS] / case[C.SERVICE]
        rows.append({C.SCENARIO: name, C.EBITDA: case[C.CFADS].sum(), C.DSCR: dscr.min(),
                     C.BREACH: int((dscr < C.COVENANT_DSCR).sum())})
    print(f"Scenario sensitivities: {len(rows)} cases with fixed original debt service")
    return pd.DataFrame(rows)
