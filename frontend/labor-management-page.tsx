"use client"

import { Fragment, useCallback, useEffect, useMemo, useState } from "react"
import { DashboardShell } from "@/components/dashboard-shell"
import { ProtectedRoute } from "@/components/protected-route"
import { IntelPageHeading } from "@/components/intel-page-heading"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Skeleton } from "@/components/ui/skeleton"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { apiFetch, getApiErrorMessage } from "@/lib/api-client"
import { useAuth } from "@/contexts/auth-context"
import { toast } from "sonner"
import { ArrowDown, ArrowUp, Check, RefreshCw, Share2 } from "lucide-react"

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:9000"

// Action-required orange (house style: the only non-blue status color)
const ALERT_CLASS = "text-[#ea580c] dark:text-[#fb923c]"

type Variance = { dollars: number | null; pct: number | null }

type LaborLine = {
  budget: number
  helixoTarget: number
  guidance: number | null
  scheduled: number | null
  guidanceVsBudget: Variance
  scheduledVsGuidance: Variance
}

type Submission = {
  id: string
  locationId: string
  status: string
  submittedForecastRevenue: number | null
  submittedBy: string | null
  submittedAt: string | null
  guidanceFohLabor: number | null
  guidanceBohLabor: number | null
  guidanceNotes: string | null
  guidanceIssuedBy: string | null
  guidanceIssuedAt: string | null
  scheduledFohLabor: number | null
  scheduledBohLabor: number | null
  scheduleSource: string
  scheduleNotes: string | null
  scheduleSubmittedBy: string | null
  scheduleSubmittedAt: string | null
  approvedBy: string | null
  approvedAt: string | null
  publishedBy: string | null
  publishedAt: string | null
  rejectedFromStatus: string | null
  rejectionReason: string | null
  rejectedBy: string | null
  rejectedAt: string | null
}

type DailyTarget = {
  date: string
  forecastRevenue: number
  targetFoh: number
  targetBoh: number
  laborPct: number | null
}

type Scorecard = {
  location: { id: string; name: string; city: string }
  revenue: { budget: number; forecast: number; variance: Variance }
  labor: { foh: LaborLine; boh: LaborLine; total: LaborLine }
  laborPct: { budget: number | null; guidance: number | null; scheduled: number | null }
  dailyTargets: DailyTarget[]
  submission: Submission | null
}

type WeekPayload = {
  meta: {
    period: number
    week: number
    year: number
    weekStart: string
    weekEnd: string
    statusCounts: Record<string, number>
  }
  scorecards: Scorecard[]
}

type ActualsDay = {
  date: string
  elapsed: boolean
  actualRevenue: number
  forecastRevenue: number
  revenueVariance: Variance
  fohLabor: number
  bohLabor: number
  laborDollars: number
  laborPct: number | null
}

type ActualsPayload = {
  meta: { weekStart: string; weekEnd: string; elapsedDays: number; remainingDays: number }
  days: ActualsDay[]
  wtd: {
    revenueActual: number
    revenueForecastToDate: number
    revenueVariance: Variance
    fohLabor: number
    bohLabor: number
    otherLabor: number
    laborDollars: number
    laborPct: number | null
  }
  movingTarget: {
    weekForecastRevenue: number
    remainingForecastRevenue: number
    requiredRevenuePerDay: number | null
    forecastRemainingPerDay: number | null
    weekLaborAllowance: number | null
    targetLaborPct: number | null
    projectedWeekLaborPct: number | null
    laborRemaining: number | null
    laborPerDayRemaining: number | null
    fohAllowance: number | null
    fohRemaining: number | null
    bohAllowance: number | null
    bohRemaining: number | null
  }
  remainingPlan: {
    date: string
    forecastRevenue: number
    share: number
    suggestedFoh: number | null
    suggestedBoh: number | null
    suggestedTotal: number | null
    impliedLaborPct: number | null
  }[]
  varianceSheet: {
    rows: {
      date: string
      elapsed: boolean
      foh: { budget: number; scheduled: number | null; actual: number | null }
      boh: { budget: number; scheduled: number | null; actual: number | null }
    }[]
    totals: {
      foh: { budget: number | null; scheduled: number | null; actual: number | null }
      boh: { budget: number | null; scheduled: number | null; actual: number | null }
    }
    scheduledIsProRated: boolean
  }
  suggestions: { kind: string; alert: boolean; text: string }[]
  submission: Submission | null
}

// The SOP ticket rail — FORECAST → TARGETS → SCHEDULE → REQUEST → APPROVE → PUBLISH.
// (*) placeholder timings per the SOP — confirm and update.
const WORKFLOW_STEPS = [
  { label: "Forecast Set & Submitted", hint: "GM + Directors · Helixo", deadline: "Mon 10:00 AM" },
  { label: "Labor Targets Returned", hint: "Ross · FOH/BOH $", deadline: "Mon EOD*" },
  { label: "Schedule Built by Person", hint: "GM · TeamWork", deadline: "Tue*" },
  { label: "Request Approval", hint: "GM · scheduled $", deadline: "Tue*" },
  { label: "Schedule Approved", hint: "Ross", deadline: "Wed*" },
  { label: "Schedule Published", hint: "GM · TeamWork", deadline: "Wed*" },
]

const STATUS_LABELS: Record<string, string> = {
  NOT_STARTED: "Not started",
  DRAFT: "Forecast due",
  SUBMITTED: "Awaiting targets (Ross)",
  TARGETS_ISSUED: "Schedule due (TeamWork)",
  APPROVAL_REQUESTED: "Awaiting approval (Ross)",
  APPROVED: "Approved — publish",
  PUBLISHED: "Published",
}

const STATUS_STEP: Record<string, number> = {
  NOT_STARTED: 0,
  DRAFT: 0,
  SUBMITTED: 1,
  TARGETS_ISSUED: 2,
  // Steps 3 (built) and 4 (requested) collapse into one in-app action: the GM
  // entering the TeamWork scheduled $ is the approval request.
  APPROVAL_REQUESTED: 4,
  APPROVED: 5,
  PUBLISHED: 6,
}

function fmtUsd(v: number | null | undefined, opts: { sign?: boolean } = {}): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—"
  const sign = opts.sign && v > 0 ? "+" : v < 0 ? "−" : ""
  return `${sign}$${Math.abs(v).toLocaleString("en-US", { maximumFractionDigits: 0 })}`
}

function fmtPct(v: number | null | undefined, opts: { sign?: boolean } = {}): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—"
  const sign = opts.sign && v > 0 ? "+" : v < 0 ? "−" : ""
  return `${sign}${Math.abs(v * 100).toFixed(1)}%`
}

// End-of-Week Variance cell — the SOP sheet explicitly uses green = under
// (favorable) / red = over, the one sanctioned exception to blue-only deltas.
function VarCell({ value }: { value: number | null }) {
  if (value === null || Number.isNaN(value)) return <span className="text-muted-foreground">—</span>
  const rounded = Math.round(value)
  if (rounded === 0) return <span className="text-muted-foreground tabular-nums">$0</span>
  const cls = rounded > 0 ? "text-red-600 dark:text-red-400" : "text-emerald-600 dark:text-emerald-400"
  return (
    <span className={`font-semibold tabular-nums ${cls}`}>
      {rounded > 0 ? "+" : "−"}${Math.abs(rounded).toLocaleString("en-US")}
    </span>
  )
}

// Deltas are blue in both directions; the sign carries the meaning.
function DeltaCell({ variance }: { variance: Variance }) {
  if (variance.pct === null && variance.dollars === null) {
    return <span className="text-muted-foreground">—</span>
  }
  return (
    <span className="font-semibold text-primary tabular-nums">
      {fmtUsd(variance.dollars, { sign: true })}
      {variance.pct !== null ? ` (${fmtPct(variance.pct, { sign: true })})` : ""}
    </span>
  )
}

function detectCurrentPeriodWeek(baseYear: number): { period: string; week: string } {
  const fyStart = new Date(baseYear - 1, 11, 29)
  const diffDays = Math.floor((Date.now() - fyStart.getTime()) / 86400000)
  const period = Math.min(13, Math.max(1, Math.floor(diffDays / 28) + 1))
  const dayInPeriod = ((diffDays % 28) + 28) % 28
  const week = Math.min(4, Math.max(1, Math.floor(dayInPeriod / 7) + 1))
  return { period: String(period), week: String(week) }
}

function dayLabel(iso: string): string {
  const d = new Date(`${iso}T00:00:00`)
  return d.toLocaleDateString("en-US", { weekday: "short", month: "numeric", day: "numeric" })
}

function statusBadge(status: string) {
  const label = STATUS_LABELS[status] ?? status
  if (status === "PUBLISHED" || status === "APPROVED") {
    return <Badge className="bg-primary text-primary-foreground">{label}</Badge>
  }
  if (status === "NOT_STARTED" || status === "DRAFT") {
    return <Badge variant="secondary">{label}</Badge>
  }
  return <Badge variant="outline">{label}</Badge>
}

export default function ForecastScorecardPage() {
  const { user } = useAuth()
  const actor = user?.email || "unknown"

  const currentYear = String(new Date().getFullYear())
  const initial = detectCurrentPeriodWeek(Number(currentYear))
  const [period, setPeriod] = useState(initial.period)
  const [week, setWeek] = useState(initial.week)
  const [year, setYear] = useState(currentYear)

  const [weekData, setWeekData] = useState<WeekPayload | null>(null)
  const [weekLoading, setWeekLoading] = useState(true)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [actionBusy, setActionBusy] = useState(false)

  const [actualsLocation, setActualsLocation] = useState<string | null>(null)
  const [actualsData, setActualsData] = useState<ActualsPayload | null>(null)
  const [actualsLoading, setActualsLoading] = useState(false)

  // form state for guidance / schedule / rejection
  const [guidanceFoh, setGuidanceFoh] = useState("")
  const [guidanceBoh, setGuidanceBoh] = useState("")
  const [guidanceNotes, setGuidanceNotes] = useState("")
  const [schedFoh, setSchedFoh] = useState("")
  const [schedBoh, setSchedBoh] = useState("")
  const [schedNotes, setSchedNotes] = useState("")
  const [rejectReason, setRejectReason] = useState("")

  const loadWeek = useCallback(async () => {
    setWeekLoading(true)
    try {
      const res = await apiFetch(
        `${API_BASE}/api/v1/forecast-scorecard/week?period=${period}&week=${week}&year=${year}`,
      )
      if (!res.ok) {
        toast.error(await getApiErrorMessage(res))
        setWeekData(null)
        return
      }
      const data: WeekPayload = await res.json()
      setWeekData(data)
      // Open on the outlet that needs attention first, not the biggest one.
      const firstActionable =
        data.scorecards.find((s) => (s.submission?.status ?? "NOT_STARTED") !== "PUBLISHED")?.location.id ?? null
      setSelectedId((prev) => prev ?? firstActionable ?? data.scorecards[0]?.location.id ?? null)
      setActualsLocation((prev) => prev ?? data.scorecards[0]?.location.id ?? null)
    } catch {
      toast.error("Failed to load forecast scorecard")
      setWeekData(null)
    } finally {
      setWeekLoading(false)
    }
  }, [period, week, year])

  useEffect(() => {
    loadWeek()
  }, [loadWeek])

  const loadActuals = useCallback(async () => {
    if (!actualsLocation) return
    setActualsLoading(true)
    try {
      const res = await apiFetch(
        `${API_BASE}/api/v1/forecast-scorecard/actuals?location_id=${encodeURIComponent(actualsLocation)}&period=${period}&week=${week}&year=${year}`,
      )
      if (!res.ok) {
        toast.error(await getApiErrorMessage(res))
        setActualsData(null)
        return
      }
      setActualsData(await res.json())
    } catch {
      toast.error("Failed to load actuals scorecard")
      setActualsData(null)
    } finally {
      setActualsLoading(false)
    }
  }, [actualsLocation, period, week, year])

  useEffect(() => {
    loadActuals()
  }, [loadActuals])

  const selected = useMemo(
    () => weekData?.scorecards.find((s) => s.location.id === selectedId) ?? null,
    [weekData, selectedId],
  )

  // Prefill the guidance/schedule forms from the selected location's data.
  useEffect(() => {
    if (!selected) return
    const sub = selected.submission
    setGuidanceFoh(
      sub?.guidanceFohLabor != null ? String(Math.round(sub.guidanceFohLabor)) : String(Math.round(selected.labor.foh.helixoTarget || selected.labor.foh.budget)),
    )
    setGuidanceBoh(
      sub?.guidanceBohLabor != null ? String(Math.round(sub.guidanceBohLabor)) : String(Math.round(selected.labor.boh.helixoTarget || selected.labor.boh.budget)),
    )
    setGuidanceNotes(sub?.guidanceNotes ?? "")
    // Schedules usually land at Target — pre-fill so the GM only adjusts.
    setSchedFoh(
      sub?.scheduledFohLabor != null
        ? String(Math.round(sub.scheduledFohLabor))
        : sub?.guidanceFohLabor != null
          ? String(Math.round(sub.guidanceFohLabor))
          : "",
    )
    setSchedBoh(
      sub?.scheduledBohLabor != null
        ? String(Math.round(sub.scheduledBohLabor))
        : sub?.guidanceBohLabor != null
          ? String(Math.round(sub.guidanceBohLabor))
          : "",
    )
    setSchedNotes(sub?.scheduleNotes ?? "")
    setRejectReason("")
  }, [selected])

  const runActionFor = useCallback(
    async (card: Scorecard, action: string, payload: Record<string, unknown> = {}) => {
      setActionBusy(true)
      try {
        let submissionId = card.submission?.id
        if (!submissionId) {
          const ensureRes = await apiFetch(`${API_BASE}/api/v1/forecast-scorecard/submissions/ensure`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              location_id: card.location.id,
              period: Number(period),
              week: Number(week),
              year: Number(year),
            }),
          })
          if (!ensureRes.ok) {
            toast.error(await getApiErrorMessage(ensureRes))
            return
          }
          submissionId = (await ensureRes.json()).id as string
        }
        const res = await apiFetch(
          `${API_BASE}/api/v1/forecast-scorecard/submissions/${submissionId}/action`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ action, actor, payload }),
          },
        )
        if (!res.ok) {
          toast.error(await getApiErrorMessage(res))
          return
        }
        toast.success(`${card.location.name} updated`)
        await loadWeek()
        await loadActuals()
      } catch {
        toast.error("Action failed")
      } finally {
        setActionBusy(false)
      }
    },
    [actor, period, week, year, loadWeek, loadActuals],
  )

  const runAction = useCallback(
    (action: string, payload: Record<string, unknown> = {}) => {
      if (selected) return runActionFor(selected, action, payload)
    },
    [selected, runActionFor],
  )

  const createShareLink = useCallback(
    async (locationId: string | null) => {
      try {
        const res = await apiFetch(`${API_BASE}/api/v1/forecast-scorecard/share`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ location_id: locationId }),
        })
        if (!res.ok) {
          toast.error(await getApiErrorMessage(res))
          return
        }
        const data = await res.json()
        // Live link on the app's own domain (Vercel rewrites it to the backend).
        const url = `${window.location.origin}/share/labor-management/${data.token}`
        try {
          await navigator.clipboard.writeText(url)
          toast.success(`Live link copied — works without a Leonardo login, valid until ${String(data.expiresAt).slice(0, 10)}`)
        } catch {
          // Clipboard can be blocked (non-HTTPS/iframe); still surface the URL.
          window.prompt("Copy the live link:", url)
        }
      } catch {
        toast.error("Failed to create share link")
      }
    },
    [],
  )

  const status = selected?.submission?.status ?? "NOT_STARTED"
  const stepReached = STATUS_STEP[status] ?? 0

  const totals = useMemo(() => {
    const cards = weekData?.scorecards ?? []
    const budget = cards.reduce((a, s) => a + s.revenue.budget, 0)
    const forecast = cards.reduce((a, s) => a + s.revenue.forecast, 0)
    const published = cards.filter((s) => s.submission?.status === "PUBLISHED").length
    const awaitingRoss = cards.filter((s) =>
      ["SUBMITTED", "APPROVAL_REQUESTED"].includes(s.submission?.status ?? ""),
    ).length
    const awaitingGm = cards.filter((s) =>
      ["NOT_STARTED", "DRAFT", "TARGETS_ISSUED", "APPROVED"].includes(s.submission?.status ?? "NOT_STARTED"),
    ).length
    return { budget, forecast, published, awaitingRoss, awaitingGm, count: cards.length }
  }, [weekData])

  type QueueItem = {
    card: Scorecard
    role: "Ross" | "GM + Directors" | "GM"
    stageLabel: string
    quickAction?: { action: string; label: string; payload?: Record<string, unknown> }
    overTarget?: number | null
  }

  // Who owes what, with one-click actions where no form input is needed.
  const actionQueue = useMemo<QueueItem[]>(() => {
    const items: QueueItem[] = []
    for (const s of weekData?.scorecards ?? []) {
      const st = s.submission?.status ?? "NOT_STARTED"
      const schedOver =
        s.labor.total.scheduled != null && s.labor.total.guidance != null
          ? s.labor.total.scheduled - s.labor.total.guidance
          : null
      if (st === "NOT_STARTED" || st === "DRAFT") {
        items.push({
          card: s,
          role: "GM + Directors",
          stageLabel: `submit ${fmtUsd(s.revenue.forecast)} forecast (Mon 10 AM)`,
          quickAction: {
            action: "submit",
            label: "Submit",
            payload: { forecast_revenue: s.revenue.forecast },
          },
        })
      } else if (st === "SUBMITTED") {
        items.push({ card: s, role: "Ross", stageLabel: "approve forecast & return targets" })
      } else if (st === "TARGETS_ISSUED") {
        items.push({ card: s, role: "GM", stageLabel: "build TeamWork schedule & request approval" })
      } else if (st === "APPROVAL_REQUESTED") {
        items.push({
          card: s,
          role: "Ross",
          stageLabel: "approve schedule",
          quickAction: { action: "approve_schedule", label: "Approve" },
          overTarget: schedOver,
        })
      } else if (st === "APPROVED") {
        items.push({
          card: s,
          role: "GM",
          stageLabel: "publish in TeamWork",
          quickAction: { action: "publish", label: "Mark Published" },
        })
      }
    }
    return items
  }, [weekData])

  const filterBar = (
    <div className="flex flex-wrap items-center gap-2">
      <Select value={period} onValueChange={setPeriod}>
        <SelectTrigger className="w-[120px]">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {Array.from({ length: 13 }, (_, i) => String(i + 1)).map((p) => (
            <SelectItem key={p} value={p}>
              Period {p}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      <Select value={week} onValueChange={setWeek}>
        <SelectTrigger className="w-[110px]">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {["1", "2", "3", "4"].map((w) => (
            <SelectItem key={w} value={w}>
              Week {w}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      <Select value={year} onValueChange={setYear}>
        <SelectTrigger className="w-[100px]">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {[Number(currentYear) - 1, Number(currentYear), Number(currentYear) + 1].map((y) => (
            <SelectItem key={y} value={String(y)}>
              {y}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      <Button variant="outline" size="sm" onClick={() => { loadWeek(); loadActuals() }} disabled={weekLoading}>
        <RefreshCw className="h-3.5 w-3.5" />
      </Button>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="outline" size="sm">
            <Share2 className="h-3.5 w-3.5 mr-1" /> Share live link
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="start">
          <DropdownMenuItem onClick={() => createShareLink(null)}>All locations (portfolio)</DropdownMenuItem>
          {selected && (
            <DropdownMenuItem onClick={() => createShareLink(selected.location.id)}>
              {selected.location.name} only
            </DropdownMenuItem>
          )}
        </DropdownMenuContent>
      </DropdownMenu>
      {weekData && (
        <span className="text-xs text-muted-foreground">
          {weekData.meta.weekStart} → {weekData.meta.weekEnd}
        </span>
      )}
    </div>
  )

  return (
    <ProtectedRoute>
      <DashboardShell>
        <main className="p-3 lg:p-4 space-y-6">
          <IntelPageHeading title="Weekly Labor Management" />
          <Tabs defaultValue="submission">
            <div className="flex flex-wrap items-center justify-between gap-3">
              {filterBar}
              <TabsList>
                <TabsTrigger value="submission">Approval Workflow</TabsTrigger>
                <TabsTrigger value="actuals">In-Week Actuals</TabsTrigger>
                <TabsTrigger value="variance">End-of-Week Variance</TabsTrigger>
              </TabsList>
            </div>

            {/* ------------------------------------------------------- */}
            {/* TAB 1: pre-week submission scorecard + approval workflow */}
            {/* ------------------------------------------------------- */}
            <TabsContent value="submission" className="space-y-6 mt-4">
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                <Card>
                  <CardContent className="pt-4">
                    <div className="text-[9px] uppercase tracking-widest text-muted-foreground">Portfolio Forecast</div>
                    <div className="text-2xl font-light tabular-nums">{fmtUsd(totals.forecast)}</div>
                    <div className="text-xs font-semibold text-primary">
                      {fmtUsd(totals.forecast - totals.budget, { sign: true })} vs {fmtUsd(totals.budget)} budget
                    </div>
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="pt-4">
                    <div className="text-[9px] uppercase tracking-widest text-muted-foreground">Published</div>
                    <div className="text-2xl font-light tabular-nums">
                      {totals.published}/{totals.count}
                    </div>
                    <div className="text-xs text-muted-foreground">schedules live in TeamWork</div>
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="pt-4">
                    <div className="text-[9px] uppercase tracking-widest text-muted-foreground">In GM Court</div>
                    <div className="text-2xl font-light tabular-nums">{totals.awaitingGm}</div>
                    <div className="text-xs text-muted-foreground">forecast, schedule, or publish</div>
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="pt-4">
                    <div className="text-[9px] uppercase tracking-widest text-muted-foreground">Awaiting Ross</div>
                    <div className={`text-2xl font-light tabular-nums ${totals.awaitingRoss > 0 ? ALERT_CLASS : ""}`}>
                      {totals.awaitingRoss}
                    </div>
                    <div className="text-xs text-muted-foreground">forecast targets or schedule approval</div>
                  </CardContent>
                </Card>
              </div>

              {actionQueue.length > 0 && (
                <Card>
                  <CardHeader className="pb-2">
                    <div className="text-[9px] uppercase tracking-widest text-muted-foreground">
                      One click per outlet · forms open in the detail below
                    </div>
                    <CardTitle className="font-serif text-lg font-semibold">Action Queue</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                      {(["Ross", "GM", "GM + Directors"] as const).map((role) => {
                        const items = actionQueue.filter((q) => q.role === role)
                        if (items.length === 0) return null
                        return (
                          <div key={role} className="rounded-lg border p-3 space-y-2">
                            <div className="text-[9px] uppercase tracking-widest text-muted-foreground">
                              {role} · {items.length} waiting
                            </div>
                            {items.map((q) => (
                              <div key={q.card.location.id} className="flex items-center gap-2 text-xs">
                                <button
                                  type="button"
                                  className="flex-1 min-w-0 text-left hover:text-primary truncate"
                                  onClick={() => setSelectedId(q.card.location.id)}
                                >
                                  <span className="font-medium">{q.card.location.name}</span>{" "}
                                  <span className="text-muted-foreground">— {q.stageLabel}</span>
                                  {q.overTarget != null && (
                                    <span className={q.overTarget > 0 ? ` ${ALERT_CLASS}` : " text-primary"}>
                                      {" "}
                                      {q.overTarget > 0
                                        ? `+${fmtUsd(q.overTarget)} over target`
                                        : "✓ within target"}
                                    </span>
                                  )}
                                </button>
                                {q.quickAction ? (
                                  <Button
                                    size="sm"
                                    className="h-6 px-2 text-[11px]"
                                    disabled={actionBusy}
                                    onClick={() => runActionFor(q.card, q.quickAction!.action, q.quickAction!.payload)}
                                  >
                                    {q.quickAction.label}
                                  </Button>
                                ) : (
                                  <Button
                                    size="sm"
                                    variant="outline"
                                    className="h-6 px-2 text-[11px]"
                                    onClick={() => setSelectedId(q.card.location.id)}
                                  >
                                    Open
                                  </Button>
                                )}
                              </div>
                            ))}
                          </div>
                        )
                      })}
                    </div>
                  </CardContent>
                </Card>
              )}

              <Card>
                <CardHeader className="pb-2">
                  <div className="text-[9px] uppercase tracking-widest text-muted-foreground">
                    Budget · Target · Scheduled
                  </div>
                  <CardTitle className="font-serif text-lg font-semibold">Weekly Submissions</CardTitle>
                </CardHeader>
                <CardContent>
                  {weekLoading ? (
                    <div className="space-y-2">
                      <Skeleton className="h-8 w-full" />
                      <Skeleton className="h-8 w-full" />
                      <Skeleton className="h-8 w-full" />
                    </div>
                  ) : (
                    <div className="overflow-x-auto">
                      <table className="w-full text-xs">
                        <thead>
                          <tr className="border-b text-muted-foreground">
                            <th className="text-left py-2 pr-3 font-medium">Location</th>
                            <th className="text-left py-2 pr-3 font-medium">Status</th>
                            <th className="text-right py-2 px-2 font-medium">Rev Budget</th>
                            <th className="text-right py-2 px-2 font-medium">Rev Target</th>
                            <th className="text-right py-2 px-2 font-medium">Δ Bud</th>
                            <th className="text-right py-2 px-2 font-medium">FOH Target</th>
                            <th className="text-right py-2 px-2 font-medium">FOH Sched</th>
                            <th className="text-right py-2 px-2 font-medium">FOH %</th>
                            <th className="text-right py-2 px-2 font-medium">BOH Target</th>
                            <th className="text-right py-2 px-2 font-medium">BOH Sched</th>
                            <th className="text-right py-2 px-2 font-medium">BOH %</th>
                            <th className="text-right py-2 pl-2 font-medium">Total %</th>
                          </tr>
                        </thead>
                        <tbody>
                          {weekData?.scorecards.map((s) => {
                            const st = s.submission?.status ?? "NOT_STARTED"
                            const isSel = s.location.id === selectedId
                            // % of Target revenue, using Scheduled $ once entered, else Target $
                            const grpPct = (line: LaborLine) => {
                              const v = line.scheduled ?? line.guidance
                              return v != null && s.revenue.forecast > 0 ? v / s.revenue.forecast : null
                            }
                            const fohPct = grpPct(s.labor.foh)
                            const bohPct = grpPct(s.labor.boh)
                            const totPct = fohPct != null && bohPct != null ? fohPct + bohPct : null
                            return (
                              <tr
                                key={s.location.id}
                                onClick={() => setSelectedId(s.location.id)}
                                className={`border-b cursor-pointer hover:bg-primary/5 ${isSel ? "bg-primary/5" : ""}`}
                              >
                                <td className="py-2 pr-3">
                                  <div className="font-medium">{s.location.name}</div>
                                  <div className="text-muted-foreground">{s.location.city}</div>
                                </td>
                                <td className="py-2 pr-3">{statusBadge(st)}</td>
                                <td className="py-2 px-2 text-right font-semibold tabular-nums">{fmtUsd(s.revenue.budget)}</td>
                                <td className="py-2 px-2 text-right font-semibold tabular-nums">{fmtUsd(s.revenue.forecast)}</td>
                                <td className="py-2 px-2 text-right tabular-nums font-semibold text-primary">
                                  {fmtPct(s.revenue.variance.pct, { sign: true })}
                                </td>
                                <td className="py-2 px-2 text-right tabular-nums">{fmtUsd(s.labor.foh.guidance)}</td>
                                <td className="py-2 px-2 text-right tabular-nums">{fmtUsd(s.labor.foh.scheduled)}</td>
                                <td className="py-2 px-2 text-right tabular-nums">{fmtPct(fohPct)}</td>
                                <td className="py-2 px-2 text-right tabular-nums">{fmtUsd(s.labor.boh.guidance)}</td>
                                <td className="py-2 px-2 text-right tabular-nums">{fmtUsd(s.labor.boh.scheduled)}</td>
                                <td className="py-2 px-2 text-right tabular-nums">{fmtPct(bohPct)}</td>
                                <td className="py-2 pl-2 text-right tabular-nums font-semibold">{fmtPct(totPct)}</td>
                              </tr>
                            )
                          })}
                        </tbody>
                      </table>
                    </div>
                  )}
                </CardContent>
              </Card>

              {selected && (
                <Card>
                  <CardHeader className="pb-2">
                    <div className="text-[9px] uppercase tracking-widest text-muted-foreground">
                      {selected.location.city} · Week of {weekData?.meta.weekStart}
                    </div>
                    <CardTitle className="font-serif text-lg font-semibold">
                      {selected.location.name} — Submission Detail
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-5">
                    {/* the SOP ticket rail */}
                    <div className="flex rounded-lg border overflow-hidden flex-wrap">
                      {WORKFLOW_STEPS.map((step, idx) => {
                        const done = stepReached > idx
                        const active = stepReached === idx
                        return (
                          <div
                            key={step.label}
                            className={`flex-1 min-w-[130px] px-3 py-2 text-center border-r last:border-r-0 ${
                              active ? "bg-primary/10 shadow-[inset_0_0_0_1px_var(--primary)]" : ""
                            }`}
                          >
                            <div className="text-[8px] uppercase tracking-widest text-muted-foreground">
                              Step {idx + 1} · {step.deadline}
                            </div>
                            <div className="text-[10px] uppercase tracking-wide font-medium">{step.label}</div>
                            <div className={`text-[11px] ${done ? "text-primary font-semibold" : "text-muted-foreground"}`}>
                              {done ? (
                                <span className="inline-flex items-center gap-1">
                                  <Check className="h-3 w-3" /> Complete
                                </span>
                              ) : (
                                step.hint
                              )}
                            </div>
                          </div>
                        )
                      })}
                    </div>

                    {selected.submission?.rejectionReason && (
                      <div className={`text-xs font-medium ${ALERT_CLASS}`}>
                        Rejected from {STATUS_LABELS[selected.submission.rejectedFromStatus ?? ""] ?? selected.submission.rejectedFromStatus} by{" "}
                        {selected.submission.rejectedBy}: {selected.submission.rejectionReason}
                      </div>
                    )}

                    {/* the weekly plan grid: Budget · Target · Scheduled */}
                    <div className="overflow-x-auto">
                      <table className="w-full text-xs">
                        <thead>
                          <tr className="border-b text-muted-foreground">
                            <th className="text-left py-2 pr-3 font-medium">Line</th>
                            <th className="text-right py-2 px-2 font-medium">Budget</th>
                            <th className="text-right py-2 px-2 font-medium">Target (Ross)</th>
                            <th className="text-right py-2 px-2 font-medium">Scheduled (TeamWork)</th>
                            <th className="text-right py-2 px-2 font-medium">Δ Target vs Budget</th>
                            <th className="text-right py-2 pl-2 font-medium">Δ Sched vs Target</th>
                          </tr>
                        </thead>
                        <tbody>
                          <tr className="border-b">
                            <td className="py-2 pr-3 text-muted-foreground">Revenue</td>
                            <td className="py-2 px-2 text-right font-semibold tabular-nums">{fmtUsd(selected.revenue.budget)}</td>
                            <td className="py-2 px-2 text-right font-semibold tabular-nums">{fmtUsd(selected.revenue.forecast)}</td>
                            <td className="py-2 px-2 text-right tabular-nums">
                              {fmtUsd(selected.revenue.forecast)}
                              <span className="block text-[10px] text-muted-foreground font-normal">= Target</span>
                            </td>
                            <td className="py-2 px-2 text-right"><DeltaCell variance={selected.revenue.variance} /></td>
                            <td className="py-2 pl-2 text-right tabular-nums text-muted-foreground">—</td>
                          </tr>
                          {([
                            ["FOH Labor", selected.labor.foh],
                            ["BOH Labor", selected.labor.boh],
                            ["Total Labor", selected.labor.total],
                          ] as [string, LaborLine][]).map(([label, line]) => {
                            const revB = selected.revenue.budget
                            const revT = selected.revenue.forecast
                            return (
                              <Fragment key={label}>
                                <tr className={label === "Total Labor" ? "font-semibold" : ""}>
                                  <td className="py-2 pr-3 text-muted-foreground">{label}</td>
                                  <td className="py-2 px-2 text-right font-semibold tabular-nums">{fmtUsd(line.budget)}</td>
                                  <td className="py-2 px-2 text-right font-semibold tabular-nums">{fmtUsd(line.guidance)}</td>
                                  <td className="py-2 px-2 text-right font-semibold tabular-nums">{fmtUsd(line.scheduled)}</td>
                                  <td className="py-2 px-2 text-right"><DeltaCell variance={line.guidanceVsBudget} /></td>
                                  <td className="py-2 pl-2 text-right"><DeltaCell variance={line.scheduledVsGuidance} /></td>
                                </tr>
                                <tr className="border-b">
                                  <td className="py-1 pr-3 pl-6 text-muted-foreground text-[11px]">{label} % of Revenue</td>
                                  <td className="py-1 px-2 text-right tabular-nums text-muted-foreground text-[11px]">
                                    {fmtPct(revB > 0 ? line.budget / revB : null)}
                                  </td>
                                  <td className="py-1 px-2 text-right tabular-nums text-muted-foreground text-[11px]">
                                    {fmtPct(line.guidance != null && revT > 0 ? line.guidance / revT : null)}
                                  </td>
                                  <td className="py-1 px-2 text-right tabular-nums text-muted-foreground text-[11px]">
                                    {fmtPct(line.scheduled != null && revT > 0 ? line.scheduled / revT : null)}
                                  </td>
                                  <td className="py-1 px-2 text-right text-muted-foreground">—</td>
                                  <td className="py-1 pl-2 text-right text-muted-foreground">—</td>
                                </tr>
                              </Fragment>
                            )
                          })}
                        </tbody>
                      </table>
                      <p className="text-[10px] text-muted-foreground italic mt-2">
                        Scheduled FOH/BOH labor $ are entered manually from TeamWork; scheduled revenue is held at the approved
                        Target. Labor % uses Budget revenue in the Budget column and Target revenue in the Target and Scheduled columns.
                      </p>
                    </div>

                    {/* generated targets sheet (SOP sheet 2) — auto-spread by day */}
                    {selected.dailyTargets.length > 0 && (
                      <div className="overflow-x-auto rounded-lg border p-3">
                        <div className="text-[9px] uppercase tracking-widest text-muted-foreground mb-2">
                          Labor Targets by Day — auto-spread pro-rata to the daily forecast
                        </div>
                        <table className="w-full text-xs">
                          <thead>
                            <tr className="border-b text-muted-foreground">
                              <th className="text-left py-1.5 pr-3 font-medium">Day</th>
                              <th className="text-right py-1.5 px-2 font-medium">Fcst Sales</th>
                              <th className="text-right py-1.5 px-2 font-medium">Target FOH $</th>
                              <th className="text-right py-1.5 px-2 font-medium">Target BOH $</th>
                              <th className="text-right py-1.5 pl-2 font-medium">Labor %</th>
                            </tr>
                          </thead>
                          <tbody>
                            {selected.dailyTargets.map((t) => (
                              <tr key={t.date} className="border-b">
                                <td className="py-1.5 pr-3">{dayLabel(t.date)}</td>
                                <td className="py-1.5 px-2 text-right tabular-nums">{fmtUsd(t.forecastRevenue)}</td>
                                <td className="py-1.5 px-2 text-right font-semibold tabular-nums">{fmtUsd(t.targetFoh)}</td>
                                <td className="py-1.5 px-2 text-right font-semibold tabular-nums">{fmtUsd(t.targetBoh)}</td>
                                <td className="py-1.5 pl-2 text-right tabular-nums">{fmtPct(t.laborPct)}</td>
                              </tr>
                            ))}
                            <tr className="font-semibold">
                              <td className="py-1.5 pr-3">Week Total</td>
                              <td className="py-1.5 px-2 text-right tabular-nums">{fmtUsd(selected.revenue.forecast)}</td>
                              <td className="py-1.5 px-2 text-right tabular-nums">{fmtUsd(selected.submission?.guidanceFohLabor)}</td>
                              <td className="py-1.5 px-2 text-right tabular-nums">{fmtUsd(selected.submission?.guidanceBohLabor)}</td>
                              <td className="py-1.5 pl-2 text-right tabular-nums">{fmtPct(selected.laborPct.guidance)}</td>
                            </tr>
                          </tbody>
                        </table>
                      </div>
                    )}

                    {/* stage-specific actions (SOP ticket rail) */}
                    <div className="rounded-lg border p-4 space-y-3">
                      <div className="text-[9px] uppercase tracking-widest text-muted-foreground">Next Action</div>

                      {(status === "NOT_STARTED" || status === "DRAFT") && (
                        <div className="flex flex-wrap items-center gap-3">
                          <p className="text-xs text-muted-foreground flex-1 min-w-[220px]">
                            GM + Directors: set the weekly sales forecast in Helixo, then submit{" "}
                            {fmtUsd(selected.revenue.forecast)} for approval (Mon 10:00 AM).
                          </p>
                          <Button
                            size="sm"
                            disabled={actionBusy}
                            onClick={() => runAction("submit", { forecast_revenue: selected.revenue.forecast })}
                          >
                            Submit Forecast
                          </Button>
                        </div>
                      )}

                      {status === "SUBMITTED" && (
                        <div className="space-y-3">
                          <p className="text-xs text-muted-foreground">
                            Forecast of {fmtUsd(selected.revenue.forecast)} (
                            {fmtPct(selected.revenue.variance.pct, { sign: true })} vs budget) set & submitted by{" "}
                            {selected.submission?.submittedBy ?? "—"}. Approving here returns the FOH/BOH labor targets in
                            one step (due Mon EOD*). Helixo suggests FOH {fmtUsd(selected.labor.foh.helixoTarget)} · BOH{" "}
                            {fmtUsd(selected.labor.boh.helixoTarget)}; the daily targets sheet is generated automatically.
                          </p>
                          <div className="flex flex-wrap items-end gap-3">
                            <div>
                              <div className="text-[10px] uppercase tracking-wide text-muted-foreground mb-1">Target FOH $</div>
                              <Input className="h-8 w-32 text-xs" type="number" value={guidanceFoh} onChange={(e) => setGuidanceFoh(e.target.value)} />
                            </div>
                            <div>
                              <div className="text-[10px] uppercase tracking-wide text-muted-foreground mb-1">Target BOH $</div>
                              <Input className="h-8 w-32 text-xs" type="number" value={guidanceBoh} onChange={(e) => setGuidanceBoh(e.target.value)} />
                            </div>
                            <div className="flex-1 min-w-[220px]">
                              <div className="text-[10px] uppercase tracking-wide text-muted-foreground mb-1">Notes</div>
                              <Textarea
                                className="text-xs min-h-8 h-8"
                                value={guidanceNotes}
                                onChange={(e) => setGuidanceNotes(e.target.value)}
                                placeholder="Target notes for the GM…"
                              />
                            </div>
                            <Button
                              size="sm"
                              disabled={actionBusy || guidanceFoh === "" || guidanceBoh === ""}
                              onClick={() =>
                                runAction("issue_targets", {
                                  target_foh_labor: Number(guidanceFoh),
                                  target_boh_labor: Number(guidanceBoh),
                                  target_notes: guidanceNotes,
                                })
                              }
                            >
                              Approve Forecast &amp; Return Targets (Ross)
                            </Button>
                            <Input
                              className="h-8 w-48 text-xs"
                              placeholder="Rejection reason"
                              value={rejectReason}
                              onChange={(e) => setRejectReason(e.target.value)}
                            />
                            <Button
                              size="sm"
                              variant="outline"
                              disabled={actionBusy || !rejectReason.trim()}
                              onClick={() => runAction("reject", { reason: rejectReason })}
                            >
                              Reject Forecast
                            </Button>
                          </div>
                        </div>
                      )}

                      {status === "TARGETS_ISSUED" && (
                        <div className="space-y-3">
                          <p className="text-xs text-muted-foreground">
                            Targets returned by {selected.submission?.guidanceIssuedBy ?? "—"}: FOH{" "}
                            {fmtUsd(selected.submission?.guidanceFohLabor)} · BOH {fmtUsd(selected.submission?.guidanceBohLabor)}
                            {selected.submission?.guidanceNotes ? ` — “${selected.submission.guidanceNotes}”` : ""}. Build the
                            schedule by person in TeamWork (due Tue*), then enter the scheduled labor dollars — submitting
                            them is the approval request.
                          </p>
                          <div className="flex flex-wrap items-end gap-3">
                            <div>
                              <div className="text-[10px] uppercase tracking-wide text-muted-foreground mb-1">Scheduled FOH $</div>
                              <Input className="h-8 w-32 text-xs" type="number" value={schedFoh} onChange={(e) => setSchedFoh(e.target.value)} />
                            </div>
                            <div>
                              <div className="text-[10px] uppercase tracking-wide text-muted-foreground mb-1">Scheduled BOH $</div>
                              <Input className="h-8 w-32 text-xs" type="number" value={schedBoh} onChange={(e) => setSchedBoh(e.target.value)} />
                            </div>
                            <div className="flex-1 min-w-[220px]">
                              <div className="text-[10px] uppercase tracking-wide text-muted-foreground mb-1">Notes</div>
                              <Textarea
                                className="text-xs min-h-8 h-8"
                                value={schedNotes}
                                onChange={(e) => setSchedNotes(e.target.value)}
                                placeholder="e.g. FOH 412 hrs / BOH 358 hrs, within target…"
                              />
                            </div>
                            <Button
                              size="sm"
                              disabled={actionBusy || schedFoh === "" || schedBoh === ""}
                              onClick={() =>
                                runAction("submit_schedule", {
                                  scheduled_foh_labor: Number(schedFoh),
                                  scheduled_boh_labor: Number(schedBoh),
                                  schedule_notes: schedNotes,
                                })
                              }
                            >
                              Request Approval
                            </Button>
                          </div>
                        </div>
                      )}

                      {status === "APPROVAL_REQUESTED" && (
                        <div className="space-y-3">
                          <p className="text-xs text-muted-foreground">
                            Schedule built — approval requested by {selected.submission?.scheduleSubmittedBy ?? "—"}: FOH{" "}
                            {fmtUsd(selected.submission?.scheduledFohLabor)} · BOH {fmtUsd(selected.submission?.scheduledBohLabor)}
                            {selected.labor.total.scheduled != null && selected.labor.total.guidance != null && (
                              <span
                                className={
                                  selected.labor.total.scheduled - selected.labor.total.guidance > 0
                                    ? ` font-medium ${ALERT_CLASS}`
                                    : " font-medium text-primary"
                                }
                              >
                                {" "}
                                {selected.labor.total.scheduled - selected.labor.total.guidance > 0
                                  ? `(+${fmtUsd(selected.labor.total.scheduled - selected.labor.total.guidance)} over target)`
                                  : "(✓ within target)"}
                              </span>
                            )}
                            {selected.submission?.scheduleNotes ? ` — “${selected.submission.scheduleNotes}”` : ""}
                          </p>
                          <div className="flex flex-wrap items-center gap-2">
                            <Button size="sm" disabled={actionBusy} onClick={() => runAction("approve_schedule")}>
                              Schedule is Approved ✅ (Ross)
                            </Button>
                            <Input
                              className="h-8 w-64 text-xs"
                              placeholder="Rejection reason"
                              value={rejectReason}
                              onChange={(e) => setRejectReason(e.target.value)}
                            />
                            <Button
                              size="sm"
                              variant="outline"
                              disabled={actionBusy || !rejectReason.trim()}
                              onClick={() => runAction("reject", { reason: rejectReason })}
                            >
                              Reject
                            </Button>
                          </div>
                        </div>
                      )}

                      {status === "APPROVED" && (
                        <div className="flex flex-wrap items-center gap-3">
                          <p className="text-xs text-muted-foreground flex-1 min-w-[220px]">
                            Approved by {selected.submission?.approvedBy ?? "—"} on{" "}
                            {selected.submission?.approvedAt?.slice(0, 10) ?? "—"}. Publish the schedule in TeamWork so
                            it&apos;s live to the team, then confirm here.
                          </p>
                          <Button size="sm" disabled={actionBusy} onClick={() => runAction("publish")}>
                            Mark Published in TeamWork
                          </Button>
                        </div>
                      )}

                      {status === "PUBLISHED" && (
                        <p className="text-xs font-medium text-primary">
                          Published in TeamWork by {selected.submission?.publishedBy ?? "—"} on{" "}
                          {selected.submission?.publishedAt?.slice(0, 10) ?? "—"} — live to the team. Track the week on
                          the In-Week Actuals tab; the End-of-Week Variance closes the loop on Monday.
                        </p>
                      )}
                    </div>
                  </CardContent>
                </Card>
              )}
            </TabsContent>

            {/* ----------------------------------------- */}
            {/* TAB 2: in-week actuals with moving targets */}
            {/* ----------------------------------------- */}
            <TabsContent value="actuals" className="space-y-6 mt-4">
              <div className="flex flex-wrap items-center gap-2">
                <Select value={actualsLocation ?? ""} onValueChange={setActualsLocation}>
                  <SelectTrigger className="w-[220px]">
                    <SelectValue placeholder="Select location" />
                  </SelectTrigger>
                  <SelectContent>
                    {weekData?.scorecards.map((s) => (
                      <SelectItem key={s.location.id} value={s.location.id}>
                        {s.location.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                {actualsData && (
                  <span className="text-xs text-muted-foreground">
                    {actualsData.meta.elapsedDays} day(s) in · {actualsData.meta.remainingDays} remaining
                  </span>
                )}
              </div>

              {actualsLoading || !actualsData ? (
                <div className="space-y-2">
                  <Skeleton className="h-24 w-full" />
                  <Skeleton className="h-48 w-full" />
                </div>
              ) : (
                <>
                  <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                    <Card>
                      <CardContent className="pt-4">
                        <div className="text-[9px] uppercase tracking-widest text-muted-foreground">WTD Revenue</div>
                        <div className="text-2xl font-light tabular-nums">{fmtUsd(actualsData.wtd.revenueActual)}</div>
                        <div className="text-xs font-semibold text-primary inline-flex items-center gap-1">
                          {(actualsData.wtd.revenueVariance.dollars ?? 0) >= 0 ? (
                            <ArrowUp className="h-3 w-3" />
                          ) : (
                            <ArrowDown className="h-3 w-3" />
                          )}
                          {fmtUsd(actualsData.wtd.revenueVariance.dollars, { sign: true })} vs forecast-to-date
                        </div>
                      </CardContent>
                    </Card>
                    <Card>
                      <CardContent className="pt-4">
                        <div className="text-[9px] uppercase tracking-widest text-muted-foreground">WTD Labor</div>
                        <div className="text-2xl font-light tabular-nums">{fmtUsd(actualsData.wtd.laborDollars)}</div>
                        <div className="text-xs text-muted-foreground">
                          FOH {fmtUsd(actualsData.wtd.fohLabor)} · BOH {fmtUsd(actualsData.wtd.bohLabor)} ·{" "}
                          {fmtPct(actualsData.wtd.laborPct)} of revenue
                        </div>
                      </CardContent>
                    </Card>
                    <Card>
                      <CardContent className="pt-4">
                        <div className="text-[9px] uppercase tracking-widest text-muted-foreground">Required Pace</div>
                        <div
                          className={`text-2xl font-light tabular-nums ${
                            actualsData.movingTarget.requiredRevenuePerDay !== null &&
                            actualsData.movingTarget.forecastRemainingPerDay !== null &&
                            actualsData.movingTarget.requiredRevenuePerDay >
                              actualsData.movingTarget.forecastRemainingPerDay
                              ? ALERT_CLASS
                              : ""
                          }`}
                        >
                          {actualsData.movingTarget.requiredRevenuePerDay !== null
                            ? `${fmtUsd(Math.max(actualsData.movingTarget.requiredRevenuePerDay, 0))}/day`
                            : "—"}
                        </div>
                        <div className="text-xs text-muted-foreground">
                          to land the {fmtUsd(actualsData.movingTarget.weekForecastRevenue)} week forecast
                        </div>
                      </CardContent>
                    </Card>
                    <Card>
                      <CardContent className="pt-4">
                        <div className="text-[9px] uppercase tracking-widest text-muted-foreground">Labor Remaining</div>
                        <div
                          className={`text-2xl font-light tabular-nums ${
                            (actualsData.movingTarget.laborRemaining ?? 0) < 0 ? ALERT_CLASS : ""
                          }`}
                        >
                          {fmtUsd(actualsData.movingTarget.laborRemaining)}
                        </div>
                        <div className="text-xs text-muted-foreground">
                          of {fmtUsd(actualsData.movingTarget.weekLaborAllowance)} allowance ·{" "}
                          {actualsData.movingTarget.laborPerDayRemaining !== null
                            ? `≈ ${fmtUsd(Math.max(actualsData.movingTarget.laborPerDayRemaining, 0))}/day`
                            : "no guidance on file"}
                        </div>
                      </CardContent>
                    </Card>
                  </div>

                  <Card>
                    <CardHeader className="pb-2">
                      <div className="text-[9px] uppercase tracking-widest text-muted-foreground">
                        Moving target · stay on forecast
                      </div>
                      <CardTitle className="font-serif text-lg font-semibold">Labor Suggestions</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-2">
                      {actualsData.suggestions.length === 0 ? (
                        <p className="text-xs text-muted-foreground">
                          The week is complete — no remaining days to manage.
                        </p>
                      ) : (
                        actualsData.suggestions.map((s, i) => (
                          <p key={i} className={`text-xs ${s.alert ? `font-medium ${ALERT_CLASS}` : "text-muted-foreground"}`}>
                            {s.text}
                          </p>
                        ))
                      )}
                      <div className="flex flex-wrap gap-4 pt-2 text-xs text-muted-foreground">
                        <span>
                          FOH remaining:{" "}
                          <span className={`font-semibold tabular-nums ${(actualsData.movingTarget.fohRemaining ?? 0) < 0 ? ALERT_CLASS : "text-primary"}`}>
                            {fmtUsd(actualsData.movingTarget.fohRemaining)}
                          </span>{" "}
                          of {fmtUsd(actualsData.movingTarget.fohAllowance)}
                        </span>
                        <span>
                          BOH remaining:{" "}
                          <span className={`font-semibold tabular-nums ${(actualsData.movingTarget.bohRemaining ?? 0) < 0 ? ALERT_CLASS : "text-primary"}`}>
                            {fmtUsd(actualsData.movingTarget.bohRemaining)}
                          </span>{" "}
                          of {fmtUsd(actualsData.movingTarget.bohAllowance)}
                        </span>
                        <span>
                          Projected week labor %:{" "}
                          <span className="font-semibold tabular-nums text-primary">
                            {fmtPct(actualsData.movingTarget.projectedWeekLaborPct)}
                          </span>{" "}
                          vs {fmtPct(actualsData.movingTarget.targetLaborPct)} target
                        </span>
                      </div>
                    </CardContent>
                  </Card>

                  {actualsData.remainingPlan.length > 0 && (
                    <Card>
                      <CardHeader className="pb-2">
                        <div className="text-[9px] uppercase tracking-widest text-muted-foreground">
                          Remaining allowance pro-rated by each day&apos;s share of remaining Target revenue
                        </div>
                        <CardTitle className="font-serif text-lg font-semibold">Remaining-Day Plan</CardTitle>
                      </CardHeader>
                      <CardContent>
                        <div className="overflow-x-auto">
                          <table className="w-full text-xs">
                            <thead>
                              <tr className="border-b text-muted-foreground">
                                <th className="text-left py-2 pr-3 font-medium">Day</th>
                                <th className="text-right py-2 px-2 font-medium">Target Rev</th>
                                <th className="text-right py-2 px-2 font-medium">Share</th>
                                <th className="text-right py-2 px-2 font-medium">Sugg FOH $</th>
                                <th className="text-right py-2 px-2 font-medium">Sugg BOH $</th>
                                <th className="text-right py-2 px-2 font-medium">Sugg Total</th>
                                <th className="text-right py-2 pl-2 font-medium">Implied Labor %</th>
                              </tr>
                            </thead>
                            <tbody>
                              {actualsData.remainingPlan.map((p) => (
                                <tr key={p.date} className="border-b">
                                  <td className="py-2 pr-3">{dayLabel(p.date)}</td>
                                  <td className="py-2 px-2 text-right tabular-nums">{fmtUsd(p.forecastRevenue)}</td>
                                  <td className="py-2 px-2 text-right tabular-nums text-muted-foreground">
                                    {fmtPct(p.share)}
                                  </td>
                                  <td className="py-2 px-2 text-right font-semibold tabular-nums">{fmtUsd(p.suggestedFoh)}</td>
                                  <td className="py-2 px-2 text-right font-semibold tabular-nums">{fmtUsd(p.suggestedBoh)}</td>
                                  <td className="py-2 px-2 text-right font-semibold tabular-nums">{fmtUsd(p.suggestedTotal)}</td>
                                  <td className="py-2 pl-2 text-right tabular-nums">{fmtPct(p.impliedLaborPct)}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                          <p className="text-[10px] text-muted-foreground italic mt-2">
                            Suggested $ = remaining FOH/BOH allowance spread across the days ahead in proportion to each
                            day&apos;s Target revenue — busier days get more labor while the week still lands inside the
                            approved targets. Requires issued targets; unavailable until then.
                          </p>
                        </div>
                      </CardContent>
                    </Card>
                  )}

                  <Card>
                    <CardHeader className="pb-2">
                      <div className="text-[9px] uppercase tracking-widest text-muted-foreground">
                        Daily actuals vs Target
                      </div>
                      <CardTitle className="font-serif text-lg font-semibold">Day by Day</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <div className="overflow-x-auto">
                        <table className="w-full text-xs">
                          <thead>
                            <tr className="border-b text-muted-foreground">
                              <th className="text-left py-2 pr-3 font-medium">Day</th>
                              <th className="text-right py-2 px-2 font-medium">Actual Rev</th>
                              <th className="text-right py-2 px-2 font-medium">Forecast Rev</th>
                              <th className="text-right py-2 px-2 font-medium">Δ</th>
                              <th className="text-right py-2 px-2 font-medium">FOH $</th>
                              <th className="text-right py-2 px-2 font-medium">BOH $</th>
                              <th className="text-right py-2 px-2 font-medium">Total Labor</th>
                              <th className="text-right py-2 pl-2 font-medium">Labor %</th>
                            </tr>
                          </thead>
                          <tbody>
                            {actualsData.days.map((d) => (
                              <tr key={d.date} className={`border-b ${d.elapsed ? "" : "text-muted-foreground"}`}>
                                <td className="py-2 pr-3">
                                  {dayLabel(d.date)}
                                  {!d.elapsed && <span className="ml-1 text-[10px] uppercase tracking-wide">· ahead</span>}
                                </td>
                                <td className="py-2 px-2 text-right font-semibold tabular-nums">
                                  {d.elapsed ? fmtUsd(d.actualRevenue) : "—"}
                                </td>
                                <td className="py-2 px-2 text-right tabular-nums">{fmtUsd(d.forecastRevenue)}</td>
                                <td className="py-2 px-2 text-right">
                                  {d.elapsed ? <DeltaCell variance={d.revenueVariance} /> : "—"}
                                </td>
                                <td className="py-2 px-2 text-right tabular-nums">{d.elapsed ? fmtUsd(d.fohLabor) : "—"}</td>
                                <td className="py-2 px-2 text-right tabular-nums">{d.elapsed ? fmtUsd(d.bohLabor) : "—"}</td>
                                <td className="py-2 px-2 text-right font-semibold tabular-nums">
                                  {d.elapsed ? fmtUsd(d.laborDollars) : "—"}
                                </td>
                                <td className="py-2 pl-2 text-right tabular-nums">{d.elapsed ? fmtPct(d.laborPct) : "—"}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </CardContent>
                  </Card>
                </>
              )}
            </TabsContent>

            {/* --------------------------------------------------------- */}
            {/* TAB 3: end-of-week variance — budget vs scheduled vs actual */}
            {/* --------------------------------------------------------- */}
            <TabsContent value="variance" className="space-y-6 mt-4">
              <div className="flex flex-wrap items-center gap-2">
                <Select value={actualsLocation ?? ""} onValueChange={setActualsLocation}>
                  <SelectTrigger className="w-[220px]">
                    <SelectValue placeholder="Select location" />
                  </SelectTrigger>
                  <SelectContent>
                    {weekData?.scorecards.map((s) => (
                      <SelectItem key={s.location.id} value={s.location.id}>
                        {s.location.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <span className="text-xs text-muted-foreground">
                  Closed out after the week ends — this is the Monday conversation.
                </span>
              </div>

              {actualsLoading || !actualsData ? (
                <Skeleton className="h-64 w-full" />
              ) : (
                <Card>
                  <CardHeader className="pb-2">
                    <div className="text-[9px] uppercase tracking-widest text-muted-foreground">
                      Budget vs Scheduled vs Actual · green = under (favorable) · red = over
                    </div>
                    <CardTitle className="font-serif text-lg font-semibold">End-of-Week Variance</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="overflow-x-auto">
                      <table className="w-full text-xs">
                        <thead>
                          <tr className="border-b text-muted-foreground">
                            <th className="text-left py-2 pr-3 font-medium">Day</th>
                            <th className="text-right py-2 px-2 font-medium">Budget</th>
                            <th className="text-right py-2 px-2 font-medium">Scheduled</th>
                            <th className="text-right py-2 px-2 font-medium">Actual</th>
                            <th className="text-right py-2 px-2 font-medium">Var Sched−Bud</th>
                            <th className="text-right py-2 px-2 font-medium">Var Act−Sched</th>
                            <th className="text-right py-2 pl-2 font-medium">Var Act−Bud</th>
                          </tr>
                        </thead>
                        <tbody>
                          {(["foh", "boh"] as const).map((grp) => {
                            const tot = actualsData.varianceSheet.totals[grp]
                            return (
                              <Fragment key={grp}>
                                <tr className="border-b bg-secondary/60">
                                  <td colSpan={7} className="py-1.5 pr-3 text-left text-[10px] uppercase tracking-widest font-medium">
                                    {grp === "foh" ? "Front of House" : "Back of House"}
                                  </td>
                                </tr>
                                {actualsData.varianceSheet.rows.map((r) => {
                                  const g = r[grp]
                                  return (
                                    <tr key={`${grp}-${r.date}`} className="border-b">
                                      <td className="py-1.5 pr-3">{dayLabel(r.date)}</td>
                                      <td className="py-1.5 px-2 text-right tabular-nums">{fmtUsd(g.budget)}</td>
                                      <td className="py-1.5 px-2 text-right tabular-nums">{fmtUsd(g.scheduled)}</td>
                                      <td className="py-1.5 px-2 text-right font-semibold tabular-nums">{fmtUsd(g.actual)}</td>
                                      <td className="py-1.5 px-2 text-right"><VarCell value={g.scheduled != null ? g.scheduled - g.budget : null} /></td>
                                      <td className="py-1.5 px-2 text-right"><VarCell value={g.actual != null && g.scheduled != null ? g.actual - g.scheduled : null} /></td>
                                      <td className="py-1.5 pl-2 text-right"><VarCell value={g.actual != null ? g.actual - g.budget : null} /></td>
                                    </tr>
                                  )
                                })}
                                <tr className="border-b font-semibold">
                                  <td className="py-2 pr-3">{grp.toUpperCase()} Subtotal</td>
                                  <td className="py-2 px-2 text-right tabular-nums">{fmtUsd(tot.budget)}</td>
                                  <td className="py-2 px-2 text-right tabular-nums">{fmtUsd(tot.scheduled)}</td>
                                  <td className="py-2 px-2 text-right tabular-nums">{fmtUsd(tot.actual)}</td>
                                  <td className="py-2 px-2 text-right"><VarCell value={tot.scheduled != null && tot.budget != null ? tot.scheduled - tot.budget : null} /></td>
                                  <td className="py-2 px-2 text-right"><VarCell value={tot.actual != null && tot.scheduled != null ? tot.actual - tot.scheduled : null} /></td>
                                  <td className="py-2 pl-2 text-right"><VarCell value={tot.actual != null && tot.budget != null ? tot.actual - tot.budget : null} /></td>
                                </tr>
                              </Fragment>
                            )
                          })}
                          {(() => {
                            const f = actualsData.varianceSheet.totals.foh
                            const b = actualsData.varianceSheet.totals.boh
                            const add = (x: number | null, y: number | null) => (x != null && y != null ? x + y : null)
                            const bud = add(f.budget, b.budget)
                            const sch = add(f.scheduled, b.scheduled)
                            const act = add(f.actual, b.actual)
                            return (
                              <tr className="font-semibold">
                                <td className="py-2 pr-3">TOTAL LABOR</td>
                                <td className="py-2 px-2 text-right tabular-nums">{fmtUsd(bud)}</td>
                                <td className="py-2 px-2 text-right tabular-nums">{fmtUsd(sch)}</td>
                                <td className="py-2 px-2 text-right tabular-nums">{fmtUsd(act)}</td>
                                <td className="py-2 px-2 text-right"><VarCell value={sch != null && bud != null ? sch - bud : null} /></td>
                                <td className="py-2 px-2 text-right"><VarCell value={act != null && sch != null ? act - sch : null} /></td>
                                <td className="py-2 pl-2 text-right"><VarCell value={act != null && bud != null ? act - bud : null} /></td>
                              </tr>
                            )
                          })()}
                        </tbody>
                      </table>
                      <p className="text-[10px] text-muted-foreground italic mt-2">
                        Budget from Helixo daily position budgets; Actual from Toast labor. Daily Scheduled is the
                        approved weekly TeamWork total pro-rated by each day&apos;s forecast share until a TeamWork sync
                        provides true daily schedule data. Days not yet played show no Actual.
                      </p>
                    </div>
                  </CardContent>
                </Card>
              )}
            </TabsContent>
          </Tabs>
        </main>
      </DashboardShell>
    </ProtectedRoute>
  )
}
