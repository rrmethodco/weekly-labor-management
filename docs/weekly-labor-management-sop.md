# Weekly Labor Management — Standard Operating Procedure

**Owner:** Ross · **Audience:** GMs, Directors, Ross · **Cadence:** Weekly
**System:** Weekly Labor Management (Leonardo / Helixo), live link at the labor-management page

---

## 1. Purpose

Set each outlet's weekly labor spend deliberately — forecast sales, return an
allowable labor target, build a schedule to that target, approve it, and publish
it — then review actuals against the plan at week's end. The goal is to staff to
real demand, keep FOH and BOH labor inside an approved dollar target, and close
the loop every Monday so the next week's plan is sharper than the last.

Every revenue and labor figure flows automatically from Helixo/Leonardo. The
**only number a person types in is the GM's scheduled FOH/BOH dollars** from
TeamWork. Everything else is read live.

---

## 2. Roles

| Role | Responsibility |
|---|---|
| **GM + Directors** | Set and submit the weekly sales forecast in Helixo. |
| **Ross** | Return the weekly FOH + BOH labor targets; approve the built schedule. |
| **GM** | Draft the schedule in TeamWork, enter scheduled dollars, submit for approval, publish once approved. |

---

## 3. The Weekly Cycle

The workflow is a six-step ticket rail. Each step has one owner, one output,
and a target time. Status advances automatically as each step is completed.

| # | Step | Owner | Output | Target time | Status after |
|---|---|---|---|---|---|
| 1 | Forecast Set & Submitted | GM + Directors | Weekly sales forecast (Helixo) | **Mon 10:00 AM** | `SUBMITTED` |
| 2 | Labor Targets Returned | Ross | Total FOH + BOH labor $ target (also approves the forecast) | **Mon EOD** | `TARGETS_ISSUED` |
| 3 | Schedule Drafted in TeamWork | GM | Full schedule built by person in TeamWork | **Tue EOD** | — |
| 4 | Submitted for Approval | GM | Scheduled FOH/BOH $ entered (the approval request) | **Tue EOD** | `APPROVAL_REQUESTED` |
| 5 | Schedule Approved | Ross | One-click approval | **Wed 10:00 AM** | `APPROVED` |
| 6 | Schedule Published in TeamWork | GM | Live schedule confirmed in TeamWork | **Thu 5:00 PM** | `PUBLISHED` |

Then **End-of-Week Variance** closes the loop the following Monday.

---

## 4. Step-by-Step

### Step 1 — Forecast Set & Submitted (GM + Directors · Mon 10:00 AM)

1. In Helixo, set the weekly sales forecast for the outlet. Enter day-of-week
   detail — the daily shape is what sizes FOH/BOH correctly downstream.
2. Review the forecast vs. budget on the workflow page.
3. Click **Submit Forecast**. The row moves to `SUBMITTED` (Awaiting targets).
   → Ross is pinged automatically.

### Step 2 — Labor Targets Returned (Ross · Mon EOD)

1. Open the outlet. The forecast and its variance to budget are shown, along
   with Helixo's suggested FOH and BOH labor dollars (pre-filled).
2. Adjust the **Target FOH $** and **Target BOH $** if needed, add notes/guidance.
3. Click **Approve Forecast & Return Targets**. This single action both approves
   the forecast and issues the labor targets. Row moves to `TARGETS_ISSUED`.
   → GM is pinged.

> **Targets are weekly for now.** A daily target spread is intentionally turned
> off — daily thresholds return later, once the model learns each outlet's daily
> patterns from incoming actuals and can project realistic daily numbers.

*To reject instead:* enter a reason and click **Reject** — the row returns to
`DRAFT` for the GM to redo the forecast.

### Step 3 — Schedule Drafted in TeamWork (GM · Tue EOD)

1. Build the full schedule by person in TeamWork to the returned target.
2. Use Ross's guidance note to weight coverage (e.g., protect weekend brunch,
   trim weekday lunch).

### Step 4 — Submitted for Approval (GM · Tue EOD)

1. Back on the workflow page, enter the **Scheduled FOH $** and **Scheduled BOH $**
   from TeamWork. *(This is the only manual entry in the whole cycle.)*
2. Click **Submit for Approval**. The system flags whether the schedule is
   within or over the target. Row moves to `APPROVAL_REQUESTED`.
   → Ross is pinged.

### Step 5 — Schedule Approved (Ross · Wed 10:00 AM)

1. Open the outlet. The requested FOH/BOH dollars are shown with a
   within-target / over-target chip.
2. Click **Schedule is Approved**. Row moves to `APPROVED`.
   → GM is pinged.

*To reject instead:* enter a reason and click **Reject** — the row returns to
`TARGETS_ISSUED` for the GM to rework the schedule.

### Step 6 — Schedule Published in TeamWork (GM · Thu 5:00 PM)

1. Publish the schedule in TeamWork so it is live to the team.
2. Click **Mark Published in TeamWork**. Row moves to `PUBLISHED`.

### Close the loop — End-of-Week Variance (Monday)

Review **Budget vs Scheduled vs Actual** labor by day for FOH and BOH:
- Green = under (favorable), red = over.
- Three variance pairs: Scheduled − Budget, Actual − Scheduled, Actual − Budget.
- This is the Monday conversation that informs the next week's forecast and targets.

---

## 5. The Three Views

| View | When | What it shows |
|---|---|---|
| **Approval Workflow** | Pre-week | The action queue and the weekly plan per outlet: Revenue and FOH/BOH labor across **Budget · Target · Scheduled**, with variances. Toggle labor between **$ / % of revenue / Hrs**. |
| **In-Week Actuals** | During the week | WTD revenue and labor vs. target, the moving target (required revenue/day, remaining allowable labor/day), the remaining-day plan, and labor suggestions to stay on target. |
| **End-of-Week Variance** | Monday after | Budget vs Scheduled vs Actual by day per FOH/BOH — the close-out review. |

---

## 6. Definitions

- **Budget** — Helixo daily position budgets, summed for the week.
- **Target** — the allowable labor dollars Ross returns in Step 2 (revenue target
  is the GM's approved Helixo forecast).
- **Scheduled** — the FOH/BOH dollars the GM enters from TeamWork (the one manual
  entry). Scheduled revenue is held at the approved Target.
- **Actual** — revenue from Toast; labor from Helixo daily labor, mapped to FOH/BOH.
- **Labor %** — labor dollars over revenue (Budget revenue for the Budget column,
  Target revenue for the Target and Scheduled columns).

### FOH / BOH mapping

- **FOH:** Server, Bartender, Host, Barista, Support, Training
- **BOH:** Line Cooks, Prep Cooks, Pastry, Dishwashers

---

## 7. Rules & Conventions

- **One manual entry:** only the GM's scheduled FOH/BOH dollars are typed in.
  Everything else flows from Helixo/Leonardo. (Columns are in place for a future
  TeamWork API sync to replace even that entry.)
- **Rejections** are recorded with a reason and the actor: forecast-stage
  rejections return to `DRAFT`; schedule-stage rejections return to
  `TARGETS_ISSUED`.
- **Notifications:** every status change posts a Slack ping to the next owner —
  no one has to poll the page.
- **Color:** deltas are blue (direction carried by the sign); orange marks a row
  waiting on action. The End-of-Week Variance sheet is the one sanctioned
  green (under) / red (over) exception.
- **Timings** above are the working cadence; confirm with Ross before locking
  them into team calendars.

---

## 8. Escalation

- A step is past its target time → the next owner follows up via the Slack ping
  thread.
- A schedule comes in over target → Ross either approves with a note or rejects
  back to `TARGETS_ISSUED` with the reason.
- Data looks wrong (revenue/labor not matching Helixo) → flag to the Leonardo/
  Helixo data owner; do not hand-edit numbers on the page.
