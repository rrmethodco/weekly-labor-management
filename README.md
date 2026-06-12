# Weekly Labor Management Workflow — Developer Handoff

A weekly forecast → labor targets → schedule → approval → publish workflow for
Method Co restaurant operations, fed by Leonardo/Helixo data. This package is
the complete, working implementation extracted from the Leonardo codebase so
it can live as its own application/integration.

## What it does (the SOP ticket rail)

FORECAST → TARGETS → SCHEDULE → REQUEST → APPROVE → PUBLISH, then End-of-Week
Variance closes the loop.

| Step | Owner | Output | When | Status after |
|---|---|---|---|---|
| 1. Forecast Set & Submitted | GM + Directors | Weekly sales forecast (Helixo) | Mon 10:00 AM | `SUBMITTED` |
| 2. Labor Targets Returned | Ross | Target total FOH + BOH labor $ (doubles as forecast approval; daily targets auto-spread pro-rata to the forecast) | Mon EOD | `TARGETS_ISSUED` |
| 3. Schedule Drafted in TeamWork | GM | Full schedule in TeamWork | Tue EOD | — |
| 4. Submitted for Approval | GM | Scheduled FOH/BOH $ entered (the approval request — the ONLY manual entry in the cycle) | Tue EOD | `APPROVAL_REQUESTED` |
| 5. Schedule Approved | Ross | One-click approval (Slack ping automated) | Wed 10:00 AM | `APPROVED` |
| 6. Schedule Published in TeamWork | GM | Live schedule confirmed in TeamWork | Thu 5:00 PM | `PUBLISHED` |

Rejections: forecast stage → back to `DRAFT`; schedule stage → back to
`TARGETS_ISSUED`, with reason + actor recorded.

Three views: **Approval Workflow** (action queue with one-click approvals,
weekly plan grid Budget · Target · Scheduled with FOH/BOH labor % of revenue,
auto-generated daily targets sheet), **In-Week Actuals** (WTD vs target,
moving target, remaining-day plan, labor suggestions), **End-of-Week
Variance** (Budget vs Scheduled vs Actual by day per FOH/BOH, green=under /
red=over per the SOP).

`mockup/index.html` is a fully interactive, self-contained design reference
with sample data — open in any browser, or deploy as a static site
(`npx vercel mockup --prod`). It encodes the exact intended UX.

## Package contents

- `backend/` — FastAPI service + router (Python 3.11, type-hinted):
  - `forecast_scorecard_service.py` — workflow state machine, weekly plan
    builder, in-week actuals/moving target/remaining-day plan, daily target
    spread, end-of-week variance sheet.
  - `router_forecast_scorecard.py` — REST endpoints (see docs/setup-and-api.md).
  - `forecast_scorecard_share_service.py` — signed HS256 share tokens for the
    public, login-free live link.
  - `forecast_scorecard_share_html.py` — server-rendered live-link page
    (self-contained HTML, light/dark, 5-min auto-refresh).
  - `labor_workflow_notify_service.py` — Slack stage-change pings (no-op
    unless `SLACK_BOT_TOKEN` + `LABOR_WORKFLOW_SLACK_CHANNEL` are set).
- `frontend/labor-management-page.tsx` — the full React page (Next.js App
  Router, shadcn/ui, Tailwind). Three tabs as above.
- `sql/helixo-weekly-forecast-scorecard-table.sql` — Snowflake DDL for the
  one workflow table (`HELIXO_WEEKLY_FORECAST_SCORECARD`).
- `docs/setup-and-api.md` — endpoint reference, data sources, env vars.

## Leonardo dependencies (the "feeds")

All revenue/labor numbers are read live from Leonardo's Snowflake tables —
nothing is duplicated. The backend modules import four Leonardo internals:

| Import | Provides | If running OUTSIDE Leonardo |
|---|---|---|
| `backend.services.helixo_snowflake_storage` (`fetch_helixo_table_rows[_safe]`) | Paginated reads of `HELIXO_DAILY_BUDGET`, `HELIXO_DAILY_FORECASTS`, `HELIXO_DAILY_LABOR_TARGETS`, `HELIXO_DAILY_ACTUALS_RCO_ONLY`, `HELIXO_DAILY_LABOR` | Re-implement against the same Snowflake tables (simple SELECTs filtered by location_id + business_date), or call Leonardo's API |
| `backend.services.locations_storage` (`list_active_locations`, `get_location_by_id`) | Active outlet list (id, name, city) | Same: one `locations` table query |
| `backend.snowflake.SnowflakeConnection` | Pooled Snowflake connection (env-driven config) | Any Snowflake connector with the same env vars |
| `backend.services.auth_service` JWT pattern | Session auth on the API; share tokens fall back to `JWT_SECRET_KEY` | Any bearer-token middleware; keep the share path public |

Fastest path to production: mount these modules in the Leonardo backend
exactly as packaged (router prefix `/forecast-scorecard`, public path
exemption for `/api/v1/forecast-scorecard/share/`). Standalone path: swap the
four imports above for thin adapters and deploy as its own FastAPI + Next.js
app pointing at the same Snowflake.

FOH/BOH mapping (matches Leonardo): FOH = Server, Bartender, Host, Barista,
Support, Training · BOH = Line Cooks, Prep Cooks, Pastry, Dishwashers.

## Wiring checklist

1. Run `sql/helixo-weekly-forecast-scorecard-table.sql` in the target
   Snowflake schema.
2. Register the router: `include_router(forecast_scorecard.router,
   prefix="/forecast-scorecard")` under `/api/v1`.
3. Exempt `GET /api/v1/forecast-scorecard/share/{token}` from auth (the
   handler verifies the signed token itself). Keep everything else behind
   session auth.
4. Frontend: drop the page at your route of choice; it needs `apiFetch`
   (bearer-token fetch helper), `useAuth` (current user email for the actor
   stamp), and shadcn `Card/Tabs/Select/Input/Textarea/Button/Badge/Skeleton`.
   Add a rewrite `/share/labor-management/:token →
   {API}/api/v1/forecast-scorecard/share/:token` for app-domain live links.
5. Env: `JWT_SECRET_KEY` (or `FORECAST_SCORECARD_SHARE_SECRET`),
   `FORECAST_SCORECARD_SHARE_TTL_DAYS` (default 90), optional
   `SLACK_BOT_TOKEN` + `LABOR_WORKFLOW_SLACK_CHANNEL`, `FRONTEND_URL` (deep
   links in Slack pings).

## Constraints to preserve

- The GM's TeamWork scheduled FOH/BOH $ is the ONLY manual entry; everything
  else flows from Helixo/Leonardo. (Columns are in place for a future
  TeamWork API sync to replace the manual entry.)
- Daily Scheduled in the variance sheet is the approved weekly total
  pro-rated by forecast share until that TeamWork sync exists — keep the
  footnote honest.
- Deltas are blue (sign carries direction); orange = action required. The
  variance sheet is the one sanctioned green/red exception, per the SOP.

— Extracted from the Leonardo branch `claude/clever-feynman-d28evs`
(rrmethodco/leonardo) on 2026-06-11; that branch holds the full development
history if needed.
