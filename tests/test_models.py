"""Plain-script regression and invariant tests; no pytest dependency required."""
import sys
from pathlib import Path
import numpy as np

# CONFIG
ROOT = Path(__file__).resolve().parents[1]
LINEAR_COUNT = 50
LINEAR_SLOPE = 1.05
BAD_SLOPE = 1.5
STRESS_CFADS = -1_000_000.0
SHUFFLE_SEED = 42
sys.path.insert(0, str(ROOT))
from python import config as C
from python.hedging import risk_history, build_hedges, effectiveness, valuation, cashflows, historical_var
from python.solar import budget, sculpt, actuals, waterfall, sensitivities


def test_hedges_and_determinism():
    history, factors = risk_history()
    second_history, second_factors = risk_history()
    assert history.equals(second_history) and factors.equals(second_factors)
    hedges = build_hedges(history, factors)
    assert len(hedges) == C.MONTHS * 3
    assert (hedges[C.NOTIONAL] <= hedges[C.QUANTITY] + C.TOLERANCE).all()
    assert (hedges[C.NOTIONAL] >= 0).all()
    for end, ratio in zip(C.LAYER_ENDS, C.LAYER_RATIOS):
        rows = hedges.loc[(hedges[C.MONTH] == end) & (hedges[C.KIND] != C.RATE)]
        assert np.allclose(rows[C.RATIO], ratio)
    var = historical_var(history, hedges)
    assert (var[C.HEDGED] < var[C.UNHEDGED]).all()


def test_known_effectiveness():
    x = np.arange(1, LINEAR_COUNT + 1, dtype=float)
    result = effectiveness(LINEAR_SLOPE * x, -x)
    assert np.isclose(result[C.SLOPE], LINEAR_SLOPE)
    assert np.isclose(result[C.R2], 1)
    assert np.isclose(result[C.OFFSET], LINEAR_SLOPE)
    assert result[C.PASS]
    assert not effectiveness(BAD_SLOPE * x, -x)[C.PASS]
    assert not effectiveness(np.ones(LINEAR_COUNT), -x)[C.PASS]


def test_mtm_settlement_and_accounting():
    history, factors = risk_history()
    hedges = build_hedges(history, factors)
    mtm, stats = valuation(hedges, factors)
    cash = cashflows(hedges, factors)
    assert stats[C.PASS].all()
    assert np.allclose(mtm[C.CHANGE], mtm[C.OCI] + mtm[C.EARNINGS])
    settled = mtm.loc[mtm[C.DATE] == mtm[C.MATURITY]].groupby(C.DATE)[C.MTM].sum()
    assert np.allclose(settled.to_numpy(), cash.set_index(C.DATE).loc[settled.index, C.SETTLEMENT].to_numpy())
    assert np.allclose(cash[C.HEDGED], cash[C.UNHEDGED] + cash[C.SETTLEMENT])


def test_debt_sculpt():
    frame = budget()
    debt = sculpt(frame)
    assert np.allclose(debt[C.DSCR], C.TARGET_DSCR)
    assert abs(debt[C.PRINCIPAL].sum() - C.SOLAR_DEBT) < C.TOLERANCE
    assert debt[C.BALANCE].iat[-1] < C.TOLERANCE
    assert (debt[C.PRINCIPAL] >= 0).all()
    assert np.allclose(debt[C.INTEREST] + debt[C.PRINCIPAL], debt[C.SERVICE])


def test_waterfall_and_stress():
    frame = budget()
    debt = sculpt(frame)
    result = waterfall(frame, debt)
    assert result[C.RESIDUAL].abs().max() < C.TOLERANCE
    assert (result[[C.DSRA, C.MAINT, C.CLOSE_CASH]] >= -C.TOLERANCE).all().all()
    assert np.isclose(result[C.MAINT_SPEND].sum(), C.MAINTENANCE_EVENT_COST)
    assert result[C.DSRA].iat[-1] < C.TOLERANCE
    stressed = frame.copy()
    stressed[C.CFADS] = STRESS_CFADS
    stress = waterfall(stressed, debt)
    assert stress[C.RESIDUAL].abs().max() < C.TOLERANCE
    assert stress[C.BREACH].all() and (stress[C.DISTRIBUTION] == 0).all()
    assert stress[C.SHORTFALL].max() > 0
    assert (stress[[C.DSRA, C.MAINT]] >= -C.TOLERANCE).all().all()


def test_variance_and_scenarios():
    frame = budget()
    debt = sculpt(frame)
    actual, variance = actuals(frame)
    bridge = variance[[C.ENERGY_VARIANCE, C.PRICE_VARIANCE, C.RECURRING, C.ONE_TIME]].sum(axis=1)
    assert np.allclose(bridge, variance[C.VARIANCE])
    assert np.isclose(variance[C.ONE_TIME].sum(), -C.ONE_TIME_COST)
    assert len(actual) == C.MONTHS
    scenarios = sensitivities(frame, debt)
    assert np.isclose(scenarios[C.DSCR].iat[0], C.TARGET_DSCR)
    assert (scenarios[C.DSCR].tail(len(scenarios) - 1) < C.TARGET_DSCR).all()


def test_date_alignment_and_missing_debt():
    frame = budget()
    debt = sculpt(frame)
    shuffled = debt.sample(frac=1, random_state=SHUFFLE_SEED).reset_index(drop=True)
    expected = sensitivities(frame, debt)
    assert expected.equals(sensitivities(frame, shuffled))
    assert waterfall(frame, debt).equals(waterfall(frame, shuffled))
    assert debt.equals(sculpt(frame.sample(frac=1, random_state=SHUFFLE_SEED)))
    incomplete = debt.tail(len(debt) - 1)
    for function in (waterfall, sensitivities):
        try:
            function(frame, incomplete)
        except ValueError as error:
            assert "scheduled debt service" in str(error)
        else:
            raise AssertionError("Missing debt dates must not silently remove cash flows")
    try:
        waterfall(frame.drop(index=1), debt)
    except ValueError as error:
        assert "consecutive debt dates" in str(error)
    else:
        raise AssertionError("Missing waterfall months must be rejected")


if __name__ == "__main__":
    tests = [test_hedges_and_determinism, test_known_effectiveness, test_mtm_settlement_and_accounting,
             test_debt_sculpt, test_waterfall_and_stress, test_variance_and_scenarios,
             test_date_alignment_and_missing_debt]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print(f"{len(tests)} tests passed")
