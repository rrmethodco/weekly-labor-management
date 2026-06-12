# Weekly Labor Management Workflow

The weekly forecast → labor targets → schedule cycle, with two views:

1. **Approval Workflow** (pre-week) — the weekly plan per outlet: Revenue and
   FOH/BOH labor across **Budget · Target (Ross-provided allowable $) ·
   Scheduled (manually entered from TeamWork/Dolce)** with variances and FOH/BOH
   labor % of revenue, wrapped in the approval workflow. Everything flows from
   Helixo/Leonardo data; the only manual entry is the GM's TeamWork scheduled
   FOH/BOH dollars.
2. **In-Week Actuals** — daily revenue and labor actuals against the approved
   Target, with a moving target (required revenue $/day, remaining allowable
   labor $/day), a **Remaining-Day Plan** (remaining FOH/BOH allowance
   pro-rated across the days ahead by Target-revenue share), and labor
   suggestions to stay on Target.

## Workflow — the SOP ticket rail

FORECAST → TARGETS → SCHEDULE → REQUEST → APPROVE → PUBLISH, then
End-of-Week Variance closes the loop. (*) placeholder timings — confirm.

| Step | Owner | Output | When | Status after |
|---|---|---|---|---|
| 1. Forecast Set & Submitted | GM + Directors | Weekly sales forecast (Helixo) | Mon 10:00 AM | `SUBMITTED` |
| 2. Labor Targets Returned | Ross | Target total FOH + BOH labor $ (doubles as forecast approval; daily targets auto-spread pro-rata to the forecast) | Mon EOD* | `TARGETS_ISSUED` |
| 3. Schedule Built by Person | GM | Full schedule in TeamWork | Tue* | — |
| 4. Request Approval | GM | Scheduled FOH/BOH $ entered (the approval request) | Tue* | `APPROVAL_REQUESTED` |
| 5. Schedule Approved | Ross | Written approval (one click; Slack ping) | Wed* | `APPROVED` |
| 6. Schedule Published | GM | Live schedule confirmed in TeamWork | Wed* | `PUBLISHED` |

Rejections at the forecast stage return the row to `DRAFT`; rejections at the
schedule stage return to `TARGETS_ISSUED`. The reason and actor are recorded.

The page opens focused on the first outlet needing attention and shows an
**Action Queue** (Ross / GM / GM + Directors) with one-click actions for the
stages that need no form input; approval requests show a within-target /
over-target chip. The Target form pre-fills with Helixo's suggested labor;
the TeamWork entry pre-fills with the Target.

### End-of-Week Variance

The third tab closes the loop each Monday: Budget vs Scheduled vs Actual by
day for FOH and BOH with all three variance pairs (Sched−Bud, Act−Sched,
Act−Bud). Green = under (favorable), red = over — the SOP's explicit
exception to the house blue-only delta rule. Daily Scheduled is the approved
weekly TeamWork total pro-rated by forecast share until a TeamWork sync
provides true daily schedule data.

## Setup

Run `backend/snowflake/sql/helixo/helixo-weekly-forecast-scorecard-table.sql`
against the Leonardo Snowflake database/schema to create
`HELIXO_WEEKLY_FORECAST_SCORECARD` (table name retained for continuity). No
other configuration is needed — revenue and labor figures are read live from
the existing Helixo tables.

## Data sources

- **Revenue budget / FOH-BOH labor budget** — `HELIXO_DAILY_BUDGET` (position
  budget columns grouped FOH: server, bartender, host, barista, support,
  training; BOH: line cooks, prep cooks, pastry, dishwashers).
- **Revenue Target** — `HELIXO_DAILY_FORECASTS` (`manager_revenue` falling back
  to `ai_suggested_revenue`); snapshotted onto the workflow row at submit. The
  Scheduled column's revenue is held at the approved Target.
- **Helixo labor suggestion** — `HELIXO_DAILY_LABOR_TARGETS` (pre-fills Ross's
  Target form).
- **Scheduled FOH/BOH labor** — entered manually from TeamWork/Dolce on the
  workflow page (the only manual entry); the columns are in place for a future
  TeamWork API sync.
- **Actuals** — `HELIXO_DAILY_ACTUALS_RCO_ONLY` (revenue) and
  `HELIXO_DAILY_LABOR` (`mapped_position` → FOH/BOH).

## API

Endpoints remain under the original `/api/v1/forecast-scorecard` prefix
(internal name retained; user-facing name is Weekly Labor Management):

- `GET  /api/v1/forecast-scorecard/week?period=&week=&year=` — weekly plans +
  workflow state for all active locations.
- `GET  /api/v1/forecast-scorecard/actuals?location_id=&period=&week=&year=` —
  in-week actuals with moving targets, remaining-day plan, and suggestions.
- `POST /api/v1/forecast-scorecard/submissions/ensure` — create the DRAFT
  workflow row for a location/week.
- `POST /api/v1/forecast-scorecard/submissions/{id}/action` — body
  `{action, actor, payload}`; actions: `submit`, `issue_targets`,
  `submit_schedule`, `approve_schedule`, `publish`, `reject`.

## Frontend

`/performance/food-beverage/labor-management` (sidebar: Performance → Food &
Beverage → Labor Management), with **Approval Workflow**, **In-Week Actuals**, and **End-of-Week Variance** tabs.

## Public live link (outside Leonardo)

Shareable, login-free link rendered by the backend in the Leonardo Report
Canvas style (dark hero, light/dark toggle, 5-minute auto-refresh, defaults to
the current fiscal week with prev/next navigation):

- `POST /api/v1/forecast-scorecard/share` (authenticated; "Share live link"
  button) — body `{location_id?: string, expires_days?: int}`; omit
  `location_id` for the portfolio view.
- `GET  /api/v1/forecast-scorecard/share/{token}` (public) — the live HTML
  page. Optional `?period=&week=&year=` query overrides.
- On the app domain the link is served at `/share/labor-management/<token>`
  via a Next.js rewrite.

Access control: the URL embeds a signed HS256 JWT (audience
`forecast-scorecard-share`, default TTL 90 days, max 365). Anyone with the
link can view — treat the URL like a password and re-issue if it leaks. Share
tokens cannot be used as Leonardo session tokens and vice versa.

Env:

- `FORECAST_SCORECARD_SHARE_SECRET` — signing secret (falls back to
  `JWT_SECRET_KEY`; rotating either invalidates issued links).
- `FORECAST_SCORECARD_SHARE_TTL_DAYS` — default link lifetime (90).

## Slack notifications

Every workflow action posts a stage-change message (key numbers + deep link)
so the next actor never has to poll the page. Configure:

- `SLACK_BOT_TOKEN` — already used by other Leonardo Slack features.
- `LABOR_WORKFLOW_SLACK_CHANNEL` — channel id/name for the pings; unset = off.
