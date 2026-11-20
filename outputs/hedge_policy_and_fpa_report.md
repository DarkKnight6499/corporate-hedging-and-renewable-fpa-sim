# Synthetic hedge policy and renewable FP&A report

All observations, exposures and assets are synthetic. Author: Project Author.

## Treasury policy

USD reporting manufacturer sells EUR revenue and purchases copper. Hedge forecast volumes at 80% in months 1 to 12, 60% in months 13 to 24, 40% in months 25 to 36. EUR forwards sell EUR; copper forwards buy copper. A pay-fixed, receive-floating swap covers 100% of constant debt principal for 36 months. Each schedule row represents one monthly swap coupon, not additional debt. No rolling rebalance is modeled.

FX forward strikes use continuously compounded USD and EUR rate differentials. Copper carry is zero. Swap coupons use a flat initial floating rate. Positive derivative MTM is an asset. Each outstanding coupon or forward is revalued monthly and removed after settlement. Credit, collateral and transaction costs are omitted.

## Effectiveness and accounting illustration

Regress monthly derivative fair-value changes on the negative of hypothetical hedged-item changes. Screen slope from 0.80 to 1.25, R squared at least 0.80, and gross absolute dollar offset from 0.80 to 1.25. Hypothetical items exactly mirror designated derivatives, so the base case is intentionally perfectly effective. These are educational screens, not authoritative ASC 815 qualification criteria or accounting advice.

Passing changes enter illustrative OCI up to the absolute item change; residual changes enter earnings. Failing changes enter earnings entirely. OCI columns represent pre-reclassification period changes, not an ending OCI balance. Settlement recycling, formal designation, excluded components, taxes and journal entries are omitted. Identical hypothetical terms cannot validate real basis risk.

## Cash-flow risk

Historical simulation uses 735 overlapping 21-business-day shocks from synthetic history. Each forecast month's exposure is shocked separately at current spot. VaR is the empirical 95% quantile of cash loss relative to unchanged factors. It is a one-month marginal measure, not an aggregate program VaR. Forward carry is deterministic and omitted from unexpected cash risk. First-layer VaR changes from $95,708 to $18,865, a 80.3% reduction.

## Renewable budget and lender report

The 50 MW asset has 25% base capacity factor and 98% availability, seasonal irradiance and 0.4% annual degradation. Flat PPA is solved at $89.89/MWh to make the present value of budget CFADS divided by 1.30 equal $70,000,000. This is a financing calibration, not a market price. Debt amortizes over 20 years at 5.0%. No negative amortization or balloon is permitted.

CFADS equals EBITDA before reserve transfers, with no taxes, working capital, capex or financing fees. DSCR is monthly CFADS divided by contractual debt service. The illustrative covenant is 1.15x. Initial DSRA equals the first 6 months of debt service; initial maintenance reserve is $250,000. Both reserves and $1,000,000 unrestricted cash are funded by equity outside the debt balance. DSRA is reset to the next 6 scheduled payments and released as the loan matures. Maintenance contributions are liquidity-limited; the event in month 60 uses its reserve and unrestricted cash. Reserve spending is outside this simplified CFADS definition.

Waterfall pays debt service and scheduled maintenance, draws DSRA for net cash deficits, releases excess DSRA, tops up DSRA, contributes maintenance reserve, and distributes cash above $250,000 only without a covenant breach and with DSRA funded. Maintenance uses its reserve first and unrestricted cash for any uncovered obligation. DSRA is assumed available for net liquidity deficits in this simplified waterfall, without lender restrictions. Negative cash is reported as a funding shortfall, never assumed financed. Consolidated cash conservation includes both reserves. Budget waterfall covers 240 months; actual waterfall covers 36 months and uses the full debt schedule for forward DSRA sizing.

Actual minimum DSCR is 1.073x with 1 monthly breaches. Maximum consolidated cash residual is $0.000000001.

## Actual versus budget narrative

36-month EBITDA variance is $-394,579. Energy volume contributes $-39,493, price contributes $0, recurring opex contributes $-175,087, and the one-time inverter expense contributes $-180,000. Energy differences combine seeded irradiance variation and a persistent availability change from month 6. Price remains on the contracted budget tariff. Management priority is availability recovery and recurring cost control; the inverter expense is isolated rather than extrapolated.

## Scenario sensitivities

P50 denotes the budget assumption. P90 denotes the configured irradiance stress, not a fitted probability distribution. Every scenario retains original debt service. Values cover the full 20-year term. Configured (name, irradiance, price, opex) multipliers: (('P50', 1.0, 1.0, 1.0), ('P90 irradiance', 0.9, 1.0, 1.0), ('Price down 10%', 1.0, 0.9, 1.0), ('Opex up 15%', 1.0, 1.0, 1.15), ('Combined downside', 0.9, 0.9, 1.15)).

         scenario   ebitda_usd     dscr  covenant_breach
              P50 1.416298e+08 1.300000                0
   P90 irradiance 1.230534e+08 1.071368              240
   Price down 10% 1.230534e+08 1.071368              240
      Opex up 15% 1.350096e+08 1.152051                0
Combined downside 9.971435e+07 0.717650              240
