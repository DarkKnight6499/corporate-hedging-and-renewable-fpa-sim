"""Export reproducible tables, a plain workbook and concise reports."""
import json
import numpy as np
import pandas as pd
from openpyxl import Workbook, load_workbook
from openpyxl.chart import LineChart, Reference
from openpyxl.styles import Font, Alignment
from . import config as C

# CONFIG
MAX_COLUMN_WIDTH = 34
MIN_COLUMN_WIDTH = 14
NUMBER_FORMAT = '#,##0.00;(#,##0.00);0.00'
REPORT_NAME = "hedge_policy_and_fpa_report.md"
SUMMARY_NAME = "summary.json"
VAR_CHART_TITLE = "Synthetic one-month cash-flow VaR (USD)"
CSV_SUFFIX = ".csv"
CSV_FLOAT_FORMAT = "%.17g"
INPUT_TABLES = ("history", "factors", "exposures", "solar_budget", "solar_actuals")
CHART_ANCHOR = "E2"
HEADER_HEIGHT = 42
FREEZE_CELL = "A2"
DATE_FORMAT = "yyyy-mm-dd"


def export(tables, metrics):
    C.DATA.mkdir(exist_ok=True)
    C.OUTPUT.mkdir(exist_ok=True)
    workbook = Workbook()
    workbook.remove(workbook.active)
    workbook.properties.creator = C.AUTHOR
    workbook.properties.lastModifiedBy = C.AUTHOR
    workbook.properties.title = "SYNTHETIC corporate hedging and solar FP&A"
    summary = pd.DataFrame({C.METRIC: list(metrics), C.VALUE: list(metrics.values())})
    assumptions = pd.DataFrame({C.METRIC: ["Data", "Author", "Solar initial debt USD", "Target monthly DSCR", "Calibrated PPA USD/MWh", "Seed"],
                                C.VALUE: ["SYNTHETIC ONLY", C.AUTHOR, C.SOLAR_DEBT, C.TARGET_DSCR,
                                          metrics["solar_ppa_usd_mwh"], C.SEED]})
    for name, frame in {"summary": summary, "assumptions": assumptions, **tables}.items():
        destination = C.DATA if name in INPUT_TABLES else C.OUTPUT
        frame.to_csv(destination / f"{name}{CSV_SUFFIX}", index=False, float_format=CSV_FLOAT_FORMAT)
        sheet = workbook.create_sheet(name)
        sheet.append(list(frame.columns))
        for record in frame.to_dict("records"):
            row = []
            for column in frame.columns:
                value = record[column]
                if isinstance(value, pd.Timestamp):
                    value = value.to_pydatetime()
                if isinstance(value, np.generic):
                    value = value.item()
                row.append(None if pd.isna(value) else value)
            sheet.append(row)
        sheet.freeze_panes = FREEZE_CELL
        sheet.auto_filter.ref = sheet.dimensions
        for cell in sheet[1]:
            cell.font = Font(bold=True)
            cell.alignment = Alignment(wrap_text=True, vertical="top")
        sheet.row_dimensions[1].height = HEADER_HEIGHT
        for column_cells in sheet.columns:
            header = column_cells[0]
            sheet.column_dimensions[header.column_letter].width = min(MAX_COLUMN_WIDTH, max(MIN_COLUMN_WIDTH, len(str(header.value)) + 2))
            for cell in column_cells[1:]:
                if isinstance(cell.value, (int, float)) and not isinstance(cell.value, bool):
                    cell.number_format = NUMBER_FORMAT
                elif hasattr(cell.value, "year"):
                    cell.number_format = DATE_FORMAT
    var_sheet = workbook["cashflow_var"]
    chart = LineChart()
    chart.title = VAR_CHART_TITLE
    chart.y_axis.title = "USD"
    chart.x_axis.title = "Forecast month"
    for column in (C.UNHEDGED, C.HEDGED):
        column_number = list(tables["cashflow_var"].columns).index(column) + 1
        chart.add_data(Reference(var_sheet, min_col=column_number, min_row=1, max_row=var_sheet.max_row), titles_from_data=True)
    month_column = list(tables["cashflow_var"].columns).index(C.MONTH) + 1
    chart.set_categories(Reference(var_sheet, min_col=month_column, min_row=2, max_row=var_sheet.max_row))
    var_sheet.add_chart(chart, CHART_ANCHOR)
    workbook.save(C.OUTPUT / C.BOOK_NAME)
    check = load_workbook(C.OUTPUT / C.BOOK_NAME, read_only=True, data_only=True)
    assert check.properties.creator == C.AUTHOR
    assert check["exposures"].max_row == len(tables["exposures"]) + 1
    assert check["summary"].max_row == len(metrics) + 1
    check.close()
    (C.OUTPUT / SUMMARY_NAME).write_text(json.dumps(metrics, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    variance = tables["variance"]
    scenarios = tables["scenarios"]
    starts = (1, *(end + 1 for end in C.LAYER_ENDS[:-1]))
    layers = ", ".join(f"{ratio:.0%} in months {start} to {end}"
                       for start, end, ratio in zip(starts, C.LAYER_ENDS, C.LAYER_RATIOS))
    report = f"""# Synthetic hedge policy and renewable FP&A report

All observations, exposures and assets are synthetic. Author: {C.AUTHOR}.

## Treasury policy

USD reporting manufacturer sells EUR revenue and purchases copper. Hedge forecast volumes at {layers}. EUR forwards sell EUR; copper forwards buy copper. A pay-fixed, receive-floating swap covers 100% of constant debt principal for {C.MONTHS} months. Each schedule row represents one monthly swap coupon, not additional debt. No rolling rebalance is modeled.

FX forward strikes use continuously compounded USD and EUR rate differentials. Copper carry is zero. Swap coupons use a flat initial floating rate. Positive derivative MTM is an asset. Each outstanding coupon or forward is revalued monthly and removed after settlement. Credit, collateral and transaction costs are omitted.

## Effectiveness and accounting illustration

Regress monthly derivative fair-value changes on the negative of hypothetical hedged-item changes. Screen slope from {C.EFFECT_SLOPE_MIN:.2f} to {C.EFFECT_SLOPE_MAX:.2f}, R squared at least {C.EFFECT_R2_MIN:.2f}, and gross absolute dollar offset from {C.OFFSET_MIN:.2f} to {C.OFFSET_MAX:.2f}. Hypothetical items exactly mirror designated derivatives, so the base case is intentionally perfectly effective. These are educational screens, not authoritative ASC 815 qualification criteria or accounting advice.

Passing changes enter illustrative OCI up to the absolute item change; residual changes enter earnings. Failing changes enter earnings entirely. OCI columns represent pre-reclassification period changes, not an ending OCI balance. Settlement recycling, formal designation, excluded components, taxes and journal entries are omitted. Identical hypothetical terms cannot validate real basis risk.

## Cash-flow risk

Historical simulation uses {C.HISTORY_DAYS - C.MONTH_DAYS} overlapping {C.MONTH_DAYS}-business-day shocks from synthetic history. Each forecast month's exposure is shocked separately at current spot. VaR is the empirical {C.VAR_CONFIDENCE:.0%} quantile of cash loss relative to unchanged factors. It is a one-month marginal measure, not an aggregate program VaR. Forward carry is deterministic and omitted from unexpected cash risk. First-layer VaR changes from ${metrics['var_unhedged_usd']:,.0f} to ${metrics['var_hedged_usd']:,.0f}, a {metrics['var_reduction_pct']:.1f}% reduction.

## Renewable budget and lender report

The {C.SOLAR_MW:g} MW asset has {C.CAPACITY_FACTOR:.0%} base capacity factor and {C.AVAILABILITY:.0%} availability, seasonal irradiance and {C.DEGRADATION:.1%} annual degradation. Flat PPA is solved at ${metrics['solar_ppa_usd_mwh']:.2f}/MWh to make the present value of budget CFADS divided by {C.TARGET_DSCR:.2f} equal ${C.SOLAR_DEBT:,.0f}. This is a financing calibration, not a market price. Debt amortizes over {C.SOLAR_YEARS} years at {C.SOLAR_RATE:.1%}. No negative amortization or balloon is permitted.

CFADS equals EBITDA before reserve transfers, with no taxes, working capital, capex or financing fees. DSCR is monthly CFADS divided by contractual debt service. The illustrative covenant is {C.COVENANT_DSCR:.2f}x. Initial DSRA equals the first {C.DSRA_MONTHS} months of debt service; initial maintenance reserve is ${C.INITIAL_MAINTENANCE:,.0f}. Both reserves and ${C.INITIAL_CASH:,.0f} unrestricted cash are funded by equity outside the debt balance. DSRA is reset to the next {C.DSRA_MONTHS} scheduled payments and released as the loan matures. Maintenance contributions are liquidity-limited; the event in month {C.MAINTENANCE_EVENT_MONTH} uses its reserve and unrestricted cash. Reserve spending is outside this simplified CFADS definition.

Waterfall pays debt service and scheduled maintenance, draws DSRA for net cash deficits, releases excess DSRA, tops up DSRA, contributes maintenance reserve, and distributes cash above ${C.CASH_FLOOR:,.0f} only without a covenant breach and with DSRA funded. Maintenance uses its reserve first and unrestricted cash for any uncovered obligation. DSRA is assumed available for net liquidity deficits in this simplified waterfall, without lender restrictions. Negative cash is reported as a funding shortfall, never assumed financed. Consolidated cash conservation includes both reserves. Budget waterfall covers {len(tables['budget_waterfall'])} months; actual waterfall covers {len(tables['actual_waterfall'])} months and uses the full debt schedule for forward DSRA sizing.

Actual minimum DSCR is {metrics['actual_min_dscr']:.3f}x with {metrics['actual_covenant_breaches']} monthly breaches. Maximum consolidated cash residual is ${metrics['max_cash_residual_usd']:.9f}.

## Actual versus budget narrative

{len(variance)}-month EBITDA variance is ${variance[C.VARIANCE].sum():,.0f}. Energy volume contributes ${variance[C.ENERGY_VARIANCE].sum():,.0f}, price contributes ${variance[C.PRICE_VARIANCE].sum():,.0f}, recurring opex contributes ${variance[C.RECURRING].sum():,.0f}, and the one-time inverter expense contributes ${variance[C.ONE_TIME].sum():,.0f}. Energy differences combine seeded irradiance variation and a persistent availability change from month {C.ACTUAL_CHANGE_MONTH}. Price remains on the contracted budget tariff. Management priority is availability recovery and recurring cost control; the inverter expense is isolated rather than extrapolated.

## Scenario sensitivities

P50 denotes the budget assumption. P90 denotes the configured irradiance stress, not a fitted probability distribution. Every scenario retains original debt service. Values cover the full {C.SOLAR_YEARS}-year term. Configured (name, irradiance, price, opex) multipliers: {C.SCENARIOS}.

"""
    report += scenarios.to_string(index=False) + "\n"
    (C.OUTPUT / REPORT_NAME).write_text(report, encoding="utf-8")
    print(f"Exported {len(tables)} model tables, workbook, Excel chart, JSON summary and policy report")
