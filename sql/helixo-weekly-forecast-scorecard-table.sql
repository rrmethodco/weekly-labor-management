-- Weekly Labor Management Workflow table.
--
-- One row per location × fiscal week tracking the SOP ticket rail:
--   1. Forecast Set & Submitted (GM + Directors, Helixo, Mon 10 AM) -> SUBMITTED
--   2. Labor Targets Returned (Ross approves forecast & issues
--      target FOH/BOH labor $, Mon EOD*)                            -> TARGETS_ISSUED
--   3. Schedule Built by Person (GM, TeamWork, Tue*)
--   4. Request Approval (GM enters scheduled FOH/BOH $, Tue*)       -> APPROVAL_REQUESTED
--   5. Schedule Approved (Ross, Wed*)                               -> APPROVED
--   6. Schedule Published (GM confirms live in TeamWork, Wed*)      -> PUBLISHED
-- Rejections return the row to DRAFT (forecast stage) or
-- TARGETS_ISSUED (schedule stage) with the reason recorded.
-- (*) placeholder timings per the SOP — confirm and update.
--
-- Revenue/labor budget + forecast figures are read live from
-- HELIXO_DAILY_BUDGET / HELIXO_DAILY_FORECASTS / HELIXO_DAILY_LABOR_TARGETS;
-- this table stores only workflow state, Ross's targets, and the scheduled
-- labor dollars (manual TeamWork entry today, TeamWork API sync later).

CREATE TABLE IF NOT EXISTS HELIXO_WEEKLY_FORECAST_SCORECARD (
    id                       STRING        NOT NULL,
    location_id              STRING        NOT NULL,
    fiscal_year              NUMBER(4, 0)  NOT NULL,
    period                   NUMBER(2, 0)  NOT NULL,
    week                     NUMBER(1, 0)  NOT NULL,
    week_start               DATE          NOT NULL,
    week_end                 DATE          NOT NULL,

    status                   STRING        DEFAULT 'DRAFT',

    -- Step 1: forecast set & submitted (revenue snapshot at submit time)
    submitted_forecast_revenue FLOAT,
    submitted_by             STRING,
    submitted_at             TIMESTAMP_NTZ,

    -- Step 2: labor targets returned by Ross (doubles as forecast approval)
    guidance_foh_labor       FLOAT,
    guidance_boh_labor       FLOAT,
    guidance_notes           STRING,
    guidance_issued_by       STRING,
    guidance_issued_at       TIMESTAMP_NTZ,

    -- Steps 3-4: schedule built in TeamWork; entering the scheduled $ here
    -- is the approval request
    scheduled_foh_labor      FLOAT,
    scheduled_boh_labor      FLOAT,
    schedule_source          STRING        DEFAULT 'TeamWork/Dolce',
    schedule_notes           STRING,
    schedule_submitted_by    STRING,
    schedule_submitted_at    TIMESTAMP_NTZ,

    -- Step 5: schedule approved by Ross
    final_approved_by        STRING,
    final_approved_at        TIMESTAMP_NTZ,

    -- Step 6: schedule published in TeamWork
    published_by             STRING,
    published_at             TIMESTAMP_NTZ,

    -- Rejection trail (most recent)
    rejected_from_status     STRING,
    rejection_reason         STRING,
    rejected_by              STRING,
    rejected_at              TIMESTAMP_NTZ,

    created_at               TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    updated_at               TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),

    PRIMARY KEY (id)
);
