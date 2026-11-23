# Fabric Plan authoring reference — opening balances, movements, and closing balances

Use this reference when a business request asks for a balance that changes from one planning period to the next. Examples include cash, inventory, receivables, headcount, and deferred revenue. Each case shows the source grain, editable fields, forecast series, formulas, and expected output.

The formulas below use readable measure labels and the Fabric Plan formula conventions supplied for this task. Resolve the references against the target sheet during artifact generation. Validate formulas in that sheet’s editor or parser and then test their results in the grid. The worked values are acceptance fixtures based on illustrative inputs.

## 1. Model the balance before writing formulas

| Role | What to create or bind | Examples |
|---|---|---|
| Native Power BI measure | Bind an existing semantic model measure at the required entity and period grain. Use sources that respect the sheet’s filters and dimensions. | Actual ending cash, on-hand snapshot, actual headcount, shipments, invoice sales |
| Data input measure | Create an editable field for a planner decision, assumption, or override. Use appropriate units, edit windows, and defaults. | Emergency cash draw, purchase receipt adjustment, attrition, credit adjustment |
| Forecast measure | Create the series whose closed periods take actuals and whose open periods carry a baseline, prefill, or planner forecast as needed. | Projected receipts, forecast demand, hiring forecast |
| Formula measure | Calculate the opening, signed movements, closing balance, and any threshold or reconciliation. | Opening Cash, Net Cash Movement, Closing Cash |

A forecast measure may combine a closed-period source and an open-period forecast. Set its prefill and allowed edits for the specific workflow. When open-period values are stored and editable, establish when the prefill runs and how repeat fills treat existing planner changes. An input of zero may represent a deliberate override. In the worked grids, optional movements without entries are zero by the input policy. [Microsoft Learn — Create forecasts using predictions and historical data](https://learn.microsoft.com/en-us/fabric/iq/plan/planning-forecasting/planning-how-to-build-forecasts)

Use a continuous date axis ordered by the business calendar. Choose a leaf grain such as company × week or SKU × warehouse × month. Define the stock unit and sign convention. All cases below enter increases and decreases as positive magnitudes and subtract decreases in the formulas. Explicitly allow signed manual corrections when the business needs them.

### Opening and closing formula templates

The calculation is **opening in period t = closing in period t−1**. Closing is opening plus the current period net movement. The first opening is a governed seed, usually the actual closing balance immediately before the first forecast period. When the sheet starts at the first forecast bucket, bind `[Opening Seed]` to that prior actual. For these examples, the seed measure is available on the first forecast bucket.

**Opening Balance**

```text
IFNA([Closing Balance].RELATIVE(-1), [Opening Seed])
```

**Closing Balance**

```text
[Opening Balance] + [Net Movement]
```

Use this fallback form when the missing preceding period is the expected seed condition and the engine returns an NA for it. If an unexpected missing value could occur later, use an explicit first-forecast-period condition and flag missing prior closes for review. If the grid includes history, use the actual closing snapshot for closed periods and start the forecast from the last actual close. A forecast series such as `[Receipts Forecast]` can provide a closed-period flag via `[Receipts Forecast].CLOSEDPERIOD` when its period settings match the balance. Check that a newly closed period resets the downstream chain to the now-authoritative actual. [Microsoft Learn — Planning identifiers](https://learn.microsoft.com/en-us/fabric/iq/plan/planning-reference-formulas/identifiers)

For a mixed actual and forecast grid, the closing formula can branch like this when the forecast's closed-period flag is valid at the evaluated grain:

```text
IF([Movement Forecast].CLOSEDPERIOD, [Actual Closing Balance], [Opening Balance] + [Net Movement])
```

The first open period's relative read then picks up the last actual close. Define a separate first-visible seed if prior history may fall outside the evaluation axis.

The formula dependency is backward across periods, with `Closing(t-1) → Opening(t) → Closing(t)`. Create and resolve the two measure references together and test whether the target planner and artifact authoring path accept the dependency. A same-period dependency back to closing is a cycle. For example, a draw that goes into Closing Cash should be based on Cash Before Draw.

### Cumulative alternative for independent movements

If the authoring path rejects the cross-period dependency, calculate each close from a seeded cumulative range of independent movements. This version assumes a forecast-only grid, one seed at its first date, and a movement measure that can be computed without the closing balance.

**Closing Balance**

```text
var seed = SUM(SELECT.BYDATE([Opening Seed], MINDATE, MINDATE))
var movements = SUM(SELECT.BYDATE([Net Movement], MINDATE, COLUMN.CURRENT_PERIOD))
seed + movements
```

**Opening Balance**, when movements are additive and the closing has no nonlinear adjustment or recursive rounding

```text
[Closing Balance] - [Net Movement]
```

On a mixed history and forecast grid, use the explicit forecast start in both selections, with the seed bound to that forecast bucket, and branch closed-period values to actuals. Reconcile short periods, gaps, and horizon changes before choosing a date anchor. A direct cumulative sum is equivalent only when movements are independent of the opening or prior closing. If a cap, replenishment rule, or attrition rate feeds the next balance, keep the recurrence or calculate the state sequentially in a supported upstream process.

### Aggregation and reconciliation

- Sum compatible flows over time. For a time subtotal, use the beginning balance of the first included period and the ending balance of the last included period. Across entities, add balances only for the same date and comparable currency or units.
- Keep the calculation precise and apply display rounding at the end when feasible. When the policy rounds a movement, apply `ROUND` to that movement before it enters the balance. A rule that rounds each intermediate closing can change the next opening.
- Use a reconciliation measure such as `[Closing Balance] - [Opening Balance] - [Net Movement]`, with an expected result of zero at leaf grain. At time subtotals, use first opening, last closing, and total movement.
- Keep explicit modeling rules for blank seeds, missing mandatory forecast values, and optional inputs. `IFNA(expression, fallback)` handles NA. Check the target sheet’s blank behavior before relying on it to handle empty inputs. [Microsoft Learn — Conditional statements](https://learn.microsoft.com/en-us/fabric/iq/plan/planning-reference-formulas/conditional-statements)

## 2. Formula patterns for the skill

| Business question | Pattern | What to verify |
|---|---|---|
| What was this measure’s previous value? | `[Closing Cash].RELATIVE(-1)` | The previous leaf period is the one intended. A positive offset reads forward. The target accepts relative reference for this series. |
| What was the forecast for the next bucket? | `[Demand Forecast].RELATIVE(1)` | A rightward read at the last bucket has an explicit missing-value policy. A read alone does not schedule a receipt. |
| What is demand from the first position through the current leaf? | `SUM(SELECT.BYINDEX([Demand Forecast], 1, LEAF_INDEX))` | `LEAF_INDEX` is the current evaluating leaf index in the supplied convention. Confirm its spelling, start index, and selection scope in the target. A within-group position may restart at a year or quarter boundary. |
| What is the demand in the first three positions? | `SUM(SELECT.BYINDEX([Demand Forecast], 1, 3))` | The expected positions match the target selection axis. Use the applicable column count if the end should be dynamic. |
| What is demand for the first date in the grid? | `SUM(SELECT.BYDATE([Demand Forecast], MINDATE, MINDATE))` | Both boundaries are the same date. Confirm there is one intended period value per selected measure and row. |
| What is demand over the displayed date horizon? | `SUM(SELECT.BYDATE([Demand Forecast], MINDATE, MAXDATE))` | The first and last available column dates match the intended business horizon, especially after filtering. |
| What is demand from one month before through five months after this bucket? | `SUM(SELECT.BYDATE([Demand Forecast], ADDMONTHS(COLUMN.CURRENT_PERIOD, -1), ADDMONTHS(COLUMN.CURRENT_PERIOD, 5)))` | With a complete monthly axis and inclusive endpoints, this covers seven months. Check partial windows and fiscal periods. |
| What are the typical, lowest, or highest values in a window? | `AVERAGE(SELECT.BYDATE(...))`, `MIN(SELECT.BYDATE(...))`, or `MAX(SELECT.BYDATE(...))` | Choose the aggregation from the business question and define how to handle an empty selection. |
| What is the displayed column Grand Total value? | `CR_<grand-total-column-id>.M_<measure-id>` | Resolve both IDs from the target artifact. Read the configured total when subtotal logic matters. Use a range calculation when the business rule defines its own range. |
| What is the rounded amount or order multiple? | `ROUND(value, 2)` or `CEILING(units, packSize)` | `ROUND` sets decimal precision. `CEILING` applies an upward multiple. Validate pack size before using it. |

Use the [Microsoft Learn identifier reference](https://learn.microsoft.com/en-us/fabric/iq/plan/planning-reference-formulas/identifiers) for period dates and relative reads and the [rounding function reference](https://learn.microsoft.com/en-us/fabric/iq/plan/planning-reference-formulas/math-functions/rounding-formatting-functions) for precision and multiples. The dotted selectors, `LEAF_INDEX`, `ADDMONTHS`, and the column/measure ID pair follow the supplied target conventions. Confirm those tokens and their evaluation context in the target build. Examples from another formula surface can use different names for the same business operation.

**Declare a variable, keep the array, then filter it**

```text
var window = SELECT.BYINDEX([Demand Forecast], 1, LEAF_INDEX)
var positive = FILTERIF(window, ">0")
IF(COUNTIF(window, ">0") > 0, ROUND(AVERAGE(positive), 1), BLANK)
```

With 80, 0, and 100 in the range, the result at the third leaf is 90.0. The zero is excluded by policy in this diagnostic. In a stock movement or forecast total, a genuine zero may need to stay in scope. Test the empty result and whether the formula editor accepts an array in a local variable. [Microsoft Learn — Conditional statements](https://learn.microsoft.com/en-us/fabric/iq/plan/planning-reference-formulas/conditional-statements)

**Calculate a date boundary before selecting values**

```text
var fromDate = ADDMONTHS(COLUMN.CURRENT_PERIOD, -1)
var throughDate = ADDMONTHS(COLUMN.CURRENT_PERIOD, 5)
SUM(SELECT.BYDATE([Demand Forecast], fromDate, throughDate))
```

Choose offsets that match the calendar. For a four-week week-based plan, use the target’s supported week shift and date axis. A relative offset moves by position, so validate behavior with missing periods, hidden periods, reordered columns, and year boundaries.

**Conditional calculation and forecast fill**

Use an `IF` expression to choose a value at evaluation time, for example `IF([Closing Cash] < [Cash Floor], "Below floor", "OK")`. For forecast fill, set the source and open periods in the forecast configuration when the requirement is to initialize editable values. If a request specifically calls for a formula-language `FILL` statement, check the target editor or implementation for its signature and whether it evaluates values or writes inputs. Bind the confirmed operation only after identifying the destination, period scope, and overwrite behavior. The examples use forecast prefill or calculation formulas as appropriate. [Microsoft Learn — Forecast configuration](https://learn.microsoft.com/en-us/fabric/iq/plan/planning-forecasting/planning-how-to-build-forecasts)

## 3. Five worked use cases

All examples start with the first open period unless noted. Values are illustrative. Use one Plan formula measure per named formula.

### 1. Treasury cash flow forecast

**Decision.** How much cash is left at week-end, and when does treasury need to arrange funding?

**Grain.** Company × bank account × week, in thousands of account currency. Bind actual closing cash from the bank/GL reconciliation. Seed the first open week with the previous week’s reconciled closing cash of 500. Configure receipts and operating payments as forecast measures with actuals in closed weeks. Enter capex payments and funding draws as separate cash timing inputs. Set a cash floor of 450 for the example.

| Measure | Type | Role |
|---|---|---|
| Actual Closing Cash | Native Power BI | Reconciled closing cash per week |
| Cash Opening Seed | Native Power BI or approved input | Prior actual close mapped to the first forecast week |
| Cash Receipts Forecast, Operating Payments Forecast | Forecast | Open-week collections and payments |
| Capex Payments, Funding Draw, Cash Floor | Input | Payment timing, financing, and threshold |
| Opening Cash, Cash Before Draw, Net Cash Movement, Closing Cash, Funding Gap | Formula | Weekly cash bridge and funding decision |

| Formula measure | Expression |
|---|---|
| Opening Cash | `IFNA([Closing Cash].RELATIVE(-1), [Cash Opening Seed])` |
| Cash Before Draw | `[Opening Cash] + [Cash Receipts Forecast] - [Operating Payments Forecast] - [Capex Payments]` |
| Net Cash Movement | `[Cash Receipts Forecast] - [Operating Payments Forecast] - [Capex Payments] + [Funding Draw]` |
| Closing Cash | `[Opening Cash] + [Net Cash Movement]` |
| Funding Gap | `MAX(0, [Cash Floor] - [Cash Before Draw])` |

| Week | Open | Receipts | OpEx paid | Capex paid | Draw | Net movement | Close | Gap before draw |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| W1 | 500 | 180 | 150 | 0 | 0 | 30 | 530 | 0 |
| W2 | 530 | 120 | 200 | 80 | 100 | -60 | 470 | 80 |
| W3 | 470 | 210 | 130 | 20 | 0 | 60 | 530 | 0 |

Week 2 has 370 before funding. The gap to 450 is 80 and the planned 100 draw produces a close of 470. With the draw removed, week 2 closes at 370 and week 3 opens at 370. With manually planned draws, the movements are independent and the cumulative alternative applies. Test transfers separately when aggregating accounts so that internal transfers cancel for the company.

### 2. Inventory and replenishment forecast

**Decision.** When will projected inventory run short, and how many units should the planner add to cover demand and safety stock?

**Grain.** SKU × warehouse × month, in stocking units. Bind actual on-hand snapshots and historical received/shipped quantities from ERP as native measures. The first month opens at 120 units. Forecast receipts represent scheduled inbound arrivals, and forecast demand represents planned outbound requirements. A manual receipt adjustment changes the arrival month’s supply.

| Measure | Type | Role |
|---|---|---|
| Actual On Hand, Actual Receipts, Actual Shipments | Native Power BI | Prior close and historical actual flows |
| Inventory Opening Seed | Native Power BI or approved input | Prior month-end on-hand mapped to first forecast month |
| Receipts Forecast, Demand Forecast | Forecast | Scheduled inbound and expected outbound |
| Receipt Adjustment, Safety Stock, Pack Size | Input | Signed incremental inbound quantity and ordering policy |
| Opening Inventory, Net Inventory Movement, Closing Inventory, Shortage, Coverage Buy | Formula | Monthly inventory bridge and order recommendation |

| Formula measure | Expression |
|---|---|
| Opening Inventory | `IFNA([Closing Inventory].RELATIVE(-1), [Inventory Opening Seed])` |
| Net Inventory Movement | `[Receipts Forecast] + [Receipt Adjustment] - [Demand Forecast]` |
| Closing Inventory | `[Opening Inventory] + [Net Inventory Movement]` |
| Shortage | `MAX(0, -[Closing Inventory])` |

Allow negative projected net inventory in this example so unmet demand remains visible and carries forward. If the requirement calls for physical inventory floored at zero, keep a separate backlog or lost-sales measure and decide how to carry it. For a purchasing suggestion, compare the current close to future demand and receipts. Under this policy the horizon is the next two monthly buckets, and the suggestion is advisory.

**Coverage Buy**

```text
var nextMonth = ADDMONTHS(COLUMN.CURRENT_PERIOD, 1)
var secondMonth = ADDMONTHS(COLUMN.CURRENT_PERIOD, 2)
var demand = SUM(SELECT.BYDATE([Demand Forecast], nextMonth, secondMonth))
var receipts = SUM(SELECT.BYDATE([Receipts Forecast], nextMonth, secondMonth))
var adjustments = SUM(SELECT.BYDATE([Receipt Adjustment], nextMonth, secondMonth))
var gap = MAX(0, demand + [Safety Stock] - [Closing Inventory] - receipts - adjustments)
IF(AND(secondMonth <= MAXDATE, [Pack Size] > 0), CEILING(gap, [Pack Size]), BLANK)
```

| Month | Open | Receipts | Adjustment | Demand | Net movement | Close | Shortage |
|---|---:|---:|---:|---:|---:|---:|---:|
| Apr | 120 | 40 | 0 | 80 | -40 | 80 | 0 |
| May | 80 | 20 | 10 | 100 | -70 | 10 | 0 |
| Jun | 10 | 0 | 0 | 90 | -90 | -80 | 80 |

In April, the May–June window contains 190 demand, 20 receipts, and 10 added receipts. With a safety stock of 20 and a pack size of 12, the gap is 100 and the suggested order is 108. The two-month window is incomplete at the end of this fixture, so the recommendation should be blank there. If the planner approves a buy, place the accepted quantity into the receipt input at its expected arrival date. In a monthly grid with a fixed one-bucket lead, `[Released Order Qty].RELATIVE(-1)` can read the previous bucket’s released orders into the arrival bucket. Use this only when order release and receipt periods share the same regular axis and the shift matches the lead-time policy. Keep forecast receipts free of those same quantities if an added receipt series supplies them.

### 3. Accounts receivable and collections forecast

**Decision.** What receivables will remain outstanding, and how does a slower collections assumption change cash timing?

**Grain.** Company × customer segment × month, in thousands of reporting currency. Bind posted receivables, invoices, and collections from the semantic model. Seed AR with 200 at the start of April and use March credit sales of 100 as the historical lookback. The collection policy in this example allocates 40% of new invoices to the invoice month and 60% to the next month. Opening AR above the modeled historical collections remains outstanding until explicitly collected or written off.

| Measure | Type | Role |
|---|---|---|
| Actual Closing AR, Actual Credit Sales, Actual Collections | Native Power BI | Balance and posted activity |
| AR Opening Seed | Native Power BI or approved input | Actual AR at the start of the first open month |
| Credit Sales Forecast | Forecast | Actual credit sales in closed periods and projected credit sales in open periods |
| Same Month Collection Rate, Extra Collections, Credit Writeoffs | Input | Current-bucket share, incremental collections, and AR reductions |
| Opening AR, Planned Collections, Net AR Movement, Closing AR | Formula | Roll-forward and collections projection |

| Formula measure | Expression |
|---|---|
| Opening AR | `IFNA([Closing AR].RELATIVE(-1), [AR Opening Seed])` |
| Planned Collections | `ROUND([Credit Sales Forecast]*[Same Month Collection Rate] + [Credit Sales Forecast].RELATIVE(-1)*(1-[Same Month Collection Rate].RELATIVE(-1)) + [Extra Collections], 2)` |
| Net AR Movement | `[Credit Sales Forecast] - [Planned Collections] - [Credit Writeoffs]` |
| Closing AR | `IF([Credit Sales Forecast].CLOSEDPERIOD, [Actual Closing AR], [Opening AR] + [Net AR Movement])` |

Use the **invoice month’s** collection rate for the prior invoice cohort. Expose March on the evaluation axis as a closed lookback bucket, with a 40% rate and actual AR close of 200, even if the planning view highlights April onwards. If the axis begins in April, supply a separate governed March collection carry-in. The first open month needs both the prior closing balance and the prior credit-sales cohort. If an existing baseline forecasts receipts from old invoices, restrict `Extra Collections` to incremental items.

| Month | Open AR | Credit sales | Collections | Writeoffs | Net movement | Close AR |
|---|---:|---:|---:|---:|---:|---:|
| Apr | 200 | 150 | 120 | 5 | 25 | 225 |
| May | 225 | 180 | 162 | 0 | 18 | 243 |
| Jun | 243 | 160 | 182 | 10 | -32 | 211 |

June collections are 64 from June invoices, 108 from May, and 10 of extra collections. The remaining June cohort schedules 96 for July under the 40% assumption. Changing May’s rate should move May cohort cash between May and June. The collection formula is independent of the opening AR as written, so the cumulative alternative applies. If business policy caps receipts at available AR, that limit introduces a balance dependency.

### 4. Headcount and hiring forecast

**Decision.** How many filled positions will there be at month-end, and how will planned hiring and attrition affect staffing?

**Grain.** Department × location × month, measured in people. Bind month-end active headcount from HR. Seed July at 50. Configure expected starts as a forecast measure, with actual starts in closed months and approved hiring targets as an open-period prefill. Use an editable attrition rate and separate transfers. Forecast the period’s departures from opening headcount and round once to a whole person.

| Measure | Type | Role |
|---|---|---|
| Actual Closing Headcount, Actual Starts, Approved Starts Baseline | Native Power BI | HR actuals and starting forecast baseline |
| Headcount Opening Seed | Native Power BI or approved input | Prior actual close mapped to July |
| Starts Forecast | Forecast | Expected starts by month |
| Attrition Rate, Transfers In, Transfers Out | Input | Percentage assumption and movements |
| Opening Headcount, Expected Exits, Net Headcount Movement, Closing Headcount | Formula | Staffing bridge |

| Formula measure | Expression |
|---|---|
| Opening Headcount | `IFNA([Closing Headcount].RELATIVE(-1), [Headcount Opening Seed])` |
| Expected Exits | `ROUND([Opening Headcount] * [Attrition Rate], 0)` |
| Net Headcount Movement | `[Starts Forecast] + [Transfers In] - [Transfers Out] - [Expected Exits]` |
| Closing Headcount | `[Opening Headcount] + [Net Headcount Movement]` |

| Month | Open | Starts | Attrition rate | Exits | Transfers in | Transfers out | Close |
|---|---:|---:|---:|---:|---:|---:|---:|
| Jul | 50 | 4 | 4% | 2 | 1 | 0 | 53 |
| Aug | 53 | 2 | 6% | 3 | 0 | 1 | 51 |
| Sep | 51 | 5 | 4% | 2 | 0 | 0 | 54 |

August exits are `ROUND(53*0.06, 0) = 3`. September opens at 51. Try changing July starts to zero. August should open at 49 and its exit calculation should use 49. Here attrition depends on opening headcount, so the independent-movement cumulative alternative cannot replace the recurrence. If the target rejects the recurrence, supply a calculated staffing schedule upstream or use independent forecast exits if that is the user’s chosen business rule. For FTE, use FTE movements and the agreed decimal precision. Round at the planning grain and use the period-end count for a quarter close.

### 5. Deferred revenue forecast

**Decision.** How much prepaid revenue remains unrecognized, and how do recognition and cancellations change that balance?

**Grain.** Legal entity × contract cohort × month, in thousands of reporting currency. Bind revenue subledger actuals and an approved recognition schedule. Seed the first forecast month at 300. Forecast prepaid amounts credited to deferred revenue and releases to recognized revenue. Enter credits that reduce the deferred revenue liability as separate inputs. Keep tax, FX, and other accounting adjustments separate if the contract requires them.

| Measure | Type | Role |
|---|---|---|
| Actual Deferred Revenue, Actual Deferrals, Actual Recognition, Recognition Schedule | Native Power BI | Closed balances and contract schedule |
| Deferred Revenue Opening Seed | Native Power BI or approved input | Previous actual close |
| New Deferrals Forecast, Recognition Forecast | Forecast | New liabilities and scheduled releases |
| Deferred Revenue Credits | Input | Positive amount reducing the liability |
| Opening Deferred Revenue, Net Deferral Movement, Closing Deferred Revenue, Horizon Recognition | Formula | Liability bridge and forward recognition |

| Formula measure | Expression |
|---|---|
| Opening Deferred Revenue | `IFNA([Closing Deferred Revenue].RELATIVE(-1), [Deferred Revenue Opening Seed])` |
| Net Deferral Movement | `[New Deferrals Forecast] - [Recognition Forecast] - [Deferred Revenue Credits]` |
| Closing Deferred Revenue | `[Opening Deferred Revenue] + [Net Deferral Movement]` |
| Horizon Recognition | `SUM(SELECT.BYDATE([Recognition Forecast], MINDATE, MAXDATE))` |

| Month | Open | New deferrals | Recognition | Credits | Net movement | Close |
|---|---:|---:|---:|---:|---:|---:|
| Oct | 300 | 90 | 70 | 0 | 20 | 320 |
| Nov | 320 | 60 | 85 | 10 | -35 | 285 |
| Dec | 285 | 120 | 95 | 5 | 20 | 305 |

Quarter opening is 300, recognition totals 250, and quarter closing is 305. Since the recognition schedule and credit inputs are independent movements here, a cumulative close also works. Add a check for negative balances at cohort level to surface a schedule or adjustment that releases more than is available. Test a cancellation in November and verify that the forecast contains the agreed remaining recognition for December.

## 4. Instructions to add to the authoring skill

1. **Translate the business request into a planning contract.** Identify the row grain, date buckets, scenario, source measures, authority for the seed, movement sign, forecast cutoff, and editable fields. When a source measure is absent, identify the missing binding or explicitly use an illustrative input for a demo.
2. **Create the types the business needs.** Bind actuals as native Power BI measures. Use inputs for planner changes. Use forecast measures for a series with closed/open period behavior. Use formula measures for the bridge and diagnostics. The same measure may serve as an input baseline or a downstream result only if its edit and dependency behavior matches what was requested.
3. **Resolve the target references after measures and columns exist.** The examples use bracketed labels for readability. Convert them using the current artifact schema, parser, or editor reference insertion. For stored Grand Total references, resolve the target column and measure independently and compose the ID pair. Preserve multiline variable declarations or serialize them according to the applicable authoring contract. Verify saved and loaded formulas on a small target sheet.
4. **Choose the calculation direction.** Build a backward opening/closing chain when supported. Use cumulative ranges for independent movements. Keep forward estimates such as coverage advisory unless the business explicitly defines how they become planned receipts, draws, or hires.
5. **Configure presentation and editability.** Show source actuals, planner inputs, forecast series, and formula outputs distinctly. Keep opening, key movements, and closing visible in the same sheet. Add the business unit of measure, directions for what to enter, and a small reconciliation. Configure time and entity aggregation separately.
6. **Test against the intended planning behavior.** Verify the first seed, the next two openings, a planner edit and its downstream effects, an actual-to-open rollover, year boundaries, range endpoints, and the time subtotal. Include at least one explicit zero, one blank, and one out-of-horizon read. For prefill, test an existing override and a newly opened period. For publishing or writeback, separately verify saved inputs and refreshed results in the connected target when that is part of the request.

Suggested first validation grid: one entity, three consecutive periods, an actual seed, a positive movement, a negative movement, and a roll-forward edit. Then expand to a second entity and a subtotal across periods. Use the worked tables to check the business math and validate the target’s concrete formula syntax before reusing the patterns at scale.
