# Codex Task: Refactor and Harden EA Susanoo Grid Recovery v2 (MT5)

## 0. Mission

Work directly on this repository:

`D:\git\EA Susanoo`

Primary source file:

`D:\git\EA Susanoo\EA Susanoo Grid Recovery v2.mq5`

This EA is private proprietary source code. Do not upload, publish, paste, or send the source code to GitHub, gists, paste sites, third-party services, external APIs, or any network destination. Do not enable web search. Do not use external package managers or download dependencies.

The goal is to fix correctness, trade-execution safety, performance, and then add a robust MT5 News Filter while preserving the existing trading strategy unless a change is explicitly listed below.

Do not rewrite the EA from scratch.

---

# 1. Hard Environment Restrictions

You may inspect and modify files only as needed inside:

`D:\git\EA Susanoo`

For MetaTrader-related execution, compilation, or testing, you may use ONLY these executables from this installation:

- `D:\MetaTrader\MetaTrader 5 - 02\MetaEditor64.exe`
- `D:\MetaTrader\MetaTrader 5 - 02\terminal64.exe`

Do NOT use any other MetaEditor, terminal64, MetaTrader installation, compiler, Wine installation, or MT5 folder.

Do not copy the EA into another MetaTrader installation.

Do not modify unrelated files.

Do not delete or overwrite user work.

Never run destructive Git commands such as:

- `git reset --hard`
- `git clean -fd`
- `git checkout -- .`
- `git restore .`

Before editing, inspect:

1. `AGENTS.md`
2. `.agents\` if relevant
3. `.codex\` if relevant
4. `git status --short`
5. the complete `EA Susanoo Grid Recovery v2.mq5`
6. relevant files in `tests\`

If there are existing uncommitted user changes, preserve them and work around them. Do not revert them.

---

# 2. Required Working Method

Do this as a staged refactor.

Do NOT make unrelated cleanup or style changes.

Before changing behavior, understand and document the current control flow.

After every meaningful phase:

1. inspect the diff,
2. compile the MQ5,
3. fix all compile errors,
4. investigate warnings caused by your changes,
5. run available relevant tests,
6. confirm strategy invariants listed below.

Do not claim success without actual compile/test evidence.

---

# 3. Strategy Invariants — MUST NOT CHANGE

These behaviors are intentional and must remain.

## 3.1 TimeTrade controls NEW basket entry only

`UseTime`, `TimeStart`, and `TimeEnd` must prevent only a new First Entry.

If an existing basket already exists, Recovery/Basket management may continue outside the TimeTrade window.

Do NOT change TimeTrade into a global trading lock.

## 3.2 ProfitPerday controls NEW basket entry only

When realized daily profit reaches `ProfitPerday`:

- do not begin a new basket,
- but allow an existing basket to continue its Recovery and closing logic until completed.

Do NOT make ProfitPerday stop an active basket.

## 3.3 BuyOnly / SellOnly / Trade Mode controls NEW basket direction only

Trade Mode must control creation of a new basket.

If an old basket already exists from before a Mode change, allow that basket to continue its own Recovery/exit management.

Do NOT force-close a basket merely because ModeTradeP changes.

## 3.4 Preserve Grid Recovery strategy

Keep the existing concept:

- First Entry based on the selected signal.
- If price moves adversely, the EA creates a STOP pending order for recovery.
- BUY recovery uses Buy Stop.
- SELL recovery uses Sell Stop.
- Pending orders trail in the existing favorable direction.
- Basket average TP remains conceptually unchanged.
- Existing trailing/basket TP/money TP/money SL/percentage TP/percentage SL/Secure Profit behavior remains unless explicitly fixed below.

The purpose of this task is correctness and safety, not strategy optimization.

---

# 4. Phase 1 — Core Correctness Fixes

## 4.1 Fix MA Cross correctly

Current MA Cross compares both closes against effectively one MA value.

Correct it to use independent MA values:

BUY cross:

- `Close[2] <= MA[2]`
- `Close[1] > MA[1]`

SELL cross:

- `Close[2] >= MA[2]`
- `Close[1] < MA[1]`

Do not change the meaning of the other FirstEntry modes.

## 4.2 Stop creating/releasing an MA handle repeatedly

Create the MA indicator handle once in `OnInit()`.

Reuse it with `CopyBuffer()`.

Release it in `OnDeinit()`.

Handle invalid handles and insufficient CopyBuffer data safely.

Avoid unnecessary MA calculations when the selected FirstEntry mode does not need MA data.

## 4.3 Remove Lot Multiply completely

Remove the multiply lot mode.

Remove or simplify all code that exists only for:

- `lot_multiply`
- `LotExponent`
- multiplication loops
- related dead variables

The EA must retain only Lot Plus behavior.

Expected lot progression:

`next_lot = actual_latest_position_lot + LotPlus`

Then normalize to broker volume constraints and cap with `MaxLot`.

Keep the first order at `Lots`.

If removal of `LotType` would unnecessarily break existing `.set` compatibility, prefer keeping a deprecated input only if absolutely necessary, but it must no longer introduce multiply behavior. Document the compatibility decision in the final report.

## 4.4 Find the actual latest BUY and SELL position

Do NOT assume the last position returned by terminal enumeration is the newest.

For each side, determine the actual newest matching position using:

- current `_Symbol`
- matching `MagicNumber`
- correct position type
- greatest `POSITION_TIME_MSC`
- use ticket as deterministic tie-breaker if needed

Use the actual newest matching position to populate information needed for:

- `LastLotsBuy`
- `LastLotsSell`
- `BarB`
- `BarS`
- latest BUY ticket if useful
- latest SELL ticket if useful

This must fix both Last Lot and BarB/BarS correctness together.

## 4.5 MaxOrder must work symmetrically

BUY Recovery already has a MaxOrder limit.

SELL Recovery must also require:

`CountS < MaxOrder`

Ensure both BUY and SELL cannot create a recovery order after the side has reached `MaxOrder`.

Do not accidentally count unrelated symbols or other MagicNumbers.

## 4.6 Separate BUY and SELL last-action bars

Replace the shared recovery-action state `LastBar` with independent state, e.g.:

- `LastBarBuy`
- `LastBarSell`

BUY activity must not block SELL recovery in the same candle and vice versa.

Preserve the existing rule that a side should not repeatedly create its recovery pending in the same bar.

## 4.7 Fix CheckLastOrder semantics

Because Lot Multiply is being removed, the order-number comment must not control lot calculation.

If comments such as:

- `EA-1`
- `EA-2`
- `EA-3`

are retained, make `CheckLastOrder()` (or its replacement) return the actual maximum valid numeric suffix among matching current Symbol + Magic + side positions/orders as appropriate.

Use it only for human-readable order sequencing/comment purposes.

Malformed or missing comments must not break trading logic.

---

# 5. Phase 2 — Trade Execution and Risk Priority

## 5.1 Reorder OnTick so Risk/Close has priority over Open

Current structure can create a recovery/entry and return before reaching risk-close logic.

Refactor the control flow so the conceptual priority is:

1. Refresh current positions/orders/state.
2. Hard safety locks (including future News lock).
3. Risk exits:
   - SL money
   - SL percent
   - TP money
   - TP percent
4. Existing basket management:
   - basket TP updates
   - trailing
   - Secure Profit
   - orphan pending cleanup
5. Recovery creation if allowed.
6. New First Entry if allowed.
7. Finish tick.

A risk-close condition must never lose priority to a new entry or recovery order in the same tick.

Do not unintentionally change thresholds or strategy formulas.

## 5.2 Remove every `Sleep(5000)` from trading flow

Do not block EA processing for five seconds after trade requests.

Do not replace it with another blocking sleep.

Use state refresh and next-tick/OnTradeTransaction handling instead.

It is acceptable to finish processing the current tick after a successful main trading action, but only AFTER higher-priority risk/safety logic has already been evaluated.

## 5.3 Check every trade result

Every important request must be checked.

This includes at least:

- `Trade.Buy`
- `Trade.Sell`
- `Trade.BuyStop`
- `Trade.SellStop`
- `Trade.PositionClose`
- `Trade.PositionModify`
- `Trade.OrderModify`
- `Trade.OrderDelete`

Check both the immediate bool return and the relevant CTrade result code/description.

Do not print a success message when the broker rejected the request.

Logging should be concise but sufficient for diagnosis, for example:

- operation
- symbol
- ticket/order if available
- CTrade retcode
- retcode description

Avoid log spam on every tick.

## 5.4 Safe close-all with verification

Do not rely on `SetAsyncMode(true)` for safety-critical close-all behavior.

For risk close and News hard close:

- block all new order creation first,
- delete matching pending orders,
- close matching positions,
- refresh/re-scan matching positions/orders,
- if anything remains, remain locked and retry on a future event/tick/timer,
- never assume `PositionClose()` means the exposure is already zero.

Only affect current `_Symbol` + this EA's `MagicNumber`, unless an explicitly account-level metric is being calculated.

Use synchronous trade execution for safety-critical closing unless there is a very strong documented reason otherwise.

`OnTradeTransaction()` may be added to update state/caches when trade-server transactions arrive.

---

# 6. Phase 3 — Performance, Dead Code, and Drawdown

## 6.1 Remove dead code safely

Identify and remove declarations/functions/calculations that truly have no behavior.

Examples previously suspected include items such as:

- `myOrderType`
- unused C1/EMA1 calculations
- unused lot-history helper functions
- unused old button state
- other variables with no reads

Do not remove something merely because its purpose is unclear; confirm references first.

Prefer removing dead CALCULATIONS first because they have actual runtime cost.

## 6.2 Dashboard must not do expensive history scans every tick

Preserve the useful existing dashboard unless a field is explicitly replaced.

Move dashboard rendering/update to a timer (approximately once per second is sufficient).

Do not call full-history scanning functions every tick.

For metrics such as total historical lot:

- calculate once at initialization,
- update incrementally on trade/deal transaction when possible,
- or refresh on a low-frequency timer if incremental handling is impractical.

Floating basket values should reuse already collected position state rather than re-scan unnecessarily.

## 6.3 Implement accurate Daily Max DD and Portfolio Max DD

Replace misleading current Max DD behavior.

### Daily Max DD

Track ACCOUNT-level equity drawdown from the highest equity seen during the current broker/server calendar day.

Use server date/time, not local PC time.

Concept:

- dailyPeakEquity = maximum observed account equity for current server day
- dailyCurrentDD = dailyPeakEquity - current equity
- dailyMaxDD = maximum dailyCurrentDD observed during that day
- also calculate percent relative to dailyPeakEquity
- reset daily tracking only when server calendar day changes

### Portfolio Max DD (since tracking)

Track ACCOUNT-level equity drawdown from the all-time highest observed account equity since this new tracker was introduced.

Persist enough state across EA/terminal restarts so restarting the EA does not erase the Portfolio Max DD.

Use a safe MT5-native persistence method such as terminal global variables, with names scoped by account login and metric name to avoid collision.

Concept:

- portfolioPeakEquity = highest observed account equity since tracking began
- portfolioMaxDD = maximum drop from that peak seen since tracking began
- calculate money and percentage values

Do not falsely call this pre-installation historical DD. Label/document it as "since tracking".

If multiple EA charts on the same account could update the same account-level persistent metric, design it so duplicate instances do not corrupt/reset the value.

## 6.4 Dashboard display for DD

Keep dashboard concise.

Show clearly distinguishable metrics such as:

- Daily Max DD: money + %
- Portfolio Max DD: money + %

Avoid implying one is EA-symbol-only if it is account-level.

---

# 7. Phase 4 — Add Strong MT5 News Filter

This News Filter is a SAFETY LAYER and is intentionally stronger than TimeTrade, ProfitPerday, and ModeTrade.

Use the native MT5 Economic Calendar, not ForexFactory scraping.

Use MT5 trade-server/calendar time. Do NOT base News timing on `TimeLocal()`.

Default scope:

- Currency: USD
- Importance: High
- Intended primarily to protect XAUUSD from scheduled USD high-impact news

Expose sensible input parameters so these values can be changed later.

## 7.1 News state behavior

Default parameters:

- Stop new trading: 30 minutes before news
- Hard close deadline: 15 minutes before news
- Resume delay: 60 minutes after news

### NORMAL

Strategy works normally.

### PRE-NEWS / -30 minutes

At 30 minutes before a qualifying event:

- block ALL new First Entries,
- block ALL new Recovery orders,
- block ALL new pending orders,
- delete existing matching EA pending orders so they cannot trigger during the protected window,
- allow existing open positions to continue normal exit management such as TP/trailing/Secure Profit during the prepare window.

### HARD CLOSE / -15 minutes

At 15 minutes before qualifying news:

- keep global News lock active,
- force-close every remaining matching EA position regardless of profit/loss,
- delete every remaining matching pending order,
- verify repeatedly until matching exposure is actually zero.

No First Entry and no Recovery is allowed.

### NEWS + POST-NEWS LOCK

During the news and for the configured post-news delay:

- First Entry blocked
- Recovery blocked
- pending creation blocked

Default resume is 60 minutes after the relevant news window.

### OVERLAPPING NEWS

If multiple qualifying USD High events overlap:

- merge protection windows logically,
- do not resume between events,
- resume only after the last relevant event's post-news delay has expired.

## 7.2 News calendar refresh

Do not perform expensive calendar downloads every tick.

Design a cached calendar layer.

Requirements:

- initial full refresh on EA initialization,
- full refresh approximately every 24 hours,
- optionally perform a lightweight calendar-change refresh/check at a reasonable interval such as every 60 minutes,
- use `OnTimer()` for calendar maintenance/state updates rather than abusing `OnTick()`.

Calendar/API failure must fail safely:

- do not crash,
- log the failure without spamming,
- preserve last known valid cache,
- if a protection window is already active, a refresh failure must not unlock it prematurely.

## 7.3 News dashboard

Create a very small separate News panel only.

It must show only the necessary information:

- News: event name
- Time: server/calendar event time
- Status: OPEN or CLOSED

Use clear color for status, e.g. green OPEN / red CLOSED.

Do not add large countdowns, spread panels, many statistics, or unnecessary visual noise.

When no upcoming matching news is currently cached, display a clear neutral value.

---

# 8. Time Handling Rules

Existing `TimeTrade` behavior may remain based on its current semantics for now unless changing it is necessary for correctness.

BUT the new News Filter and Daily DD date rollover MUST use broker/server time consistently.

Do not mix local PC time with calendar server time when evaluating News windows.

Document all time bases in code comments where ambiguity is possible.

---

# 9. Reliability Requirements

The EA must never intentionally:

- open a new First Entry while News lock is active,
- create a Recovery order while News lock is active,
- leave a pending order active after entering the News pre-lock if it belongs to current Symbol + Magic,
- resume after news while another overlapping protected event still applies,
- exceed `MaxOrder` because SELL forgot the limit,
- use an arbitrary enumeration position as "latest",
- block risk-close execution behind a five-second sleep,
- claim a failed broker request succeeded.

All close/delete loops must be bounded and event-driven. Do not create tight infinite loops waiting for broker confirmation.

---

# 10. Compatibility and Scope

Preserve:

- current filename unless a strong reason requires otherwise,
- MagicNumber filtering,
- Symbol filtering,
- existing signal modes,
- existing recovery concept,
- basket TP concept,
- Secure Profit concept,
- TimeTrade/ProfitPerday/ModeTrade First-Entry-only semantics.

Avoid changing default trading parameters unless required for a new feature.

New News inputs should default to the agreed values.

If an input is removed due to Lot Multiply removal, note it clearly in the final report because existing `.set` files may contain obsolete parameters.

Do not modify the `.ex5` manually. Generate it only via MetaEditor compilation.

---

# 11. Compilation

Compile using ONLY:

`D:\MetaTrader\MetaTrader 5 - 02\MetaEditor64.exe`

Use the full executable path.

Compile the source in the repository.

Capture/read the compiler log and confirm:

- 0 errors
- resolve warnings introduced by this change
- do not hide warnings without understanding them

Do not use MetaEditor from any other location.

If command-line MetaEditor syntax differs on this installation, inspect the executable help or use a safe known MetaEditor command-line invocation. Do not search for or use another installed copy.

---

# 12. Testing

First inspect the existing `tests` directory and use relevant existing tests.

Add focused regression tests or test harnesses where practical without replacing real MetaTrader compile validation.

At minimum reason/test the following cases:

1. MA Cross:
   - BUY only when Close[2] <= MA[2] and Close[1] > MA[1]
   - SELL inverse

2. Lot Plus:
   - newest actual position lot is used
   - enumeration order cannot change next lot

3. MaxOrder:
   - BUY cannot exceed limit
   - SELL cannot exceed limit

4. Last bar:
   - BUY action does not block SELL same-bar action
   - SELL action does not block BUY same-bar action

5. Risk vs Entry:
   - when SL condition and Recovery condition occur together, close/risk wins

6. Trade rejection:
   - rejected open does not log success or advance state incorrectly

7. Close verification:
   - partially failed close remains locked and retries later

8. TimeTrade:
   - stops new basket entry outside time
   - existing basket Recovery remains allowed when News is not locking

9. ProfitPerday:
   - prevents a new basket after target
   - existing basket can still be managed

10. ModeTrade:
   - controls new basket direction
   - old basket remains manageable

11. News -30:
   - no new First Entry
   - no new Recovery
   - existing pending removed

12. News -15:
   - all remaining matching exposure is targeted for close
   - system stays locked until zero exposure confirmed

13. Overlapping news:
   - no premature resume

14. DD:
   - Daily resets only on new server day
   - Portfolio persists across EA re-init/restart state restoration

15. Dashboard performance:
   - no full-history scan every market tick

If terminal testing requires `terminal64.exe`, use ONLY:

`D:\MetaTrader\MetaTrader 5 - 02\terminal64.exe`

Do not launch any other MetaTrader terminal.

Do not modify broker/account settings, place live trades, or connect to a live account merely to test this task. Prefer compile/static/regression tests and Strategy Tester if it can be invoked safely with existing project configuration.

---

# 13. Final Review Before Declaring Completion

Before finishing:

1. run `git diff --check`
2. inspect `git diff`
3. confirm no unrelated file was changed
4. compile with the permitted MetaEditor
5. run relevant tests
6. inspect `git status --short`
7. re-check all Strategy Invariants
8. verify News global lock cannot be bypassed by Recovery code
9. verify SELL MaxOrder is present
10. verify `Sleep(5000)` no longer exists in trading flow
11. verify no Lot Multiply execution path remains
12. verify latest position is selected deterministically
13. verify trade result checks exist
14. verify hard close uses verification rather than blind async assumption
15. verify dashboard does not scan full history each tick

Do not commit unless the user explicitly asked for a commit.

---

# 14. Final Response Format

At completion, report:

## Files changed
List each changed file.

## Strategy behavior preserved
Explicitly confirm:

- TimeTrade = First Entry only
- ProfitPerday = First Entry only
- ModeTrade = new basket direction only
- existing basket Recovery remains active outside those First-Entry rules unless News lock is active

## Bugs fixed
Summarize each bug fixed.

## News Filter behavior
Summarize:

- currency/impact
- -30 behavior
- -15 hard close behavior
- post-news delay
- overlap behavior
- server-time basis

## Performance changes
Explain MA handle reuse, dashboard timer/caching, and removal of unnecessary work.

## Compile result
Provide the exact permitted MetaEditor executable used and compiler result.

## Test result
List commands/tests run and pass/fail status.

## Remaining risks / limitations
State anything not fully verifiable.

## Diff summary
Give a concise summary of the meaningful diff, not the entire proprietary source.

Do not reproduce the full EA source code in the final response.
