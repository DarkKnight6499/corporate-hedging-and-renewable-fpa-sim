"""Regenerate the complete synthetic project from its configured seed."""
from python import config as C
from python.hedging import risk_history, build_hedges, valuation, cashflows, historical_var
from python.solar import budget, sculpt, actuals, waterfall, sensitivities
from python.reporting import export

# CONFIG: shared inputs are defined in python/config.py.


def main():
    history, factors = risk_history()
    exposures = build_hedges(history, factors)
    mtm, stats = valuation(exposures, factors)
    corporate_cash = cashflows(exposures, factors)
    var = historical_var(history, exposures)
    solar_budget = budget()
    debt = sculpt(solar_budget)
    solar_actuals, variance = actuals(solar_budget)
    budget_cash = waterfall(solar_budget, debt)
    actual_cash = waterfall(solar_actuals, debt)
    scenarios = sensitivities(solar_budget, debt)
    metrics = {
        "var_unhedged_usd": float(var[C.UNHEDGED].iat[0]),
        "var_hedged_usd": float(var[C.HEDGED].iat[0]),
        "var_reduction_pct": float((1 - var[C.HEDGED].iat[0] / var[C.UNHEDGED].iat[0]) * 100),
        "effectiveness_passes": int(stats[C.PASS].sum()),
        "solar_ppa_usd_mwh": float(solar_budget[C.PPA].iat[0]),
        "budget_min_dscr": float(budget_cash[C.DSCR].min()),
        "actual_min_dscr": float(actual_cash[C.DSCR].min()),
        "actual_covenant_breaches": int(actual_cash[C.BREACH].sum()),
        "actual_liquidity_shortfall_usd": float(actual_cash[C.SHORTFALL].max()),
        "ending_debt_usd": float(debt[C.BALANCE].iat[-1]),
        "actual_ebitda_variance_usd": float(variance[C.VARIANCE].sum()),
        "max_cash_residual_usd": float(max(budget_cash[C.RESIDUAL].abs().max(), actual_cash[C.RESIDUAL].abs().max())),
    }
    tables = {"history": history, "factors": factors, "exposures": exposures,
              "hedge_mtm": mtm, "effectiveness": stats, "corporate_cash": corporate_cash,
              "cashflow_var": var, "solar_budget": solar_budget, "debt": debt,
              "solar_actuals": solar_actuals, "variance": variance,
              "budget_waterfall": budget_cash, "actual_waterfall": actual_cash, "scenarios": scenarios}
    export(tables, metrics)
    print("Completed SYNTHETIC project successfully")
    return metrics


if __name__ == "__main__":
    main()
