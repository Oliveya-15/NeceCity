import { useMemo } from 'react'
import { Link } from 'react-router-dom'
import { AlertOctagon, CheckCircle2, HeartPulse, Info, ListChecks, TriangleAlert, CircleDashed } from 'lucide-react'
import AppLayout from '../layouts/AppLayout'
import StatStrip from '../components/StatStrip'
import DistributionChart from '../components/DistributionChart'
import { SeverityBadge, StatusBadge } from '../components/Badge'
import { LoadingState, ErrorState, EmptyState } from '../components/StateViews'
import { useCity } from '../hooks/CityContext'
import { useApi } from '../hooks/useApi'
import { api } from '../services/api'
import { SEVERITIES, severityMeta, typeLabel } from '../utils/constants'
import { formatRelative, titleCase } from '../utils/format'

const HEALTH_COLOR = { Good: '#1E8E5A', Fair: '#B4680A', Poor: '#E15400', Critical: '#C6303E' }

export default function CommandCenter() {
  const { selectedCityId, selectedCity } = useCity()

  const { data: summary, loading, error, reload } = useApi(
    () => api.getCitySummary(selectedCityId),
    [selectedCityId],
    { skip: !selectedCityId }
  )

  const { data: priorities } = useApi(
    () => api.getPriorities(selectedCityId, 5),
    [selectedCityId],
    { skip: !selectedCityId }
  )

  const { data: recentCritical } = useApi(
    () => api.listProblems({ city_id: selectedCityId, severity: 'critical', page_size: 5 }),
    [selectedCityId],
    { skip: !selectedCityId }
  )

  const severityChartData = useMemo(() => {
    if (!summary) return []
    return SEVERITIES.map((s) => ({ label: s.label, count: summary.severity_breakdown[s.value], key: s.value }))
  }, [summary])

  const typeChartData = useMemo(() => {
    if (!summary) return []
    return Object.entries(summary.problem_type_breakdown)
      .map(([type, count]) => ({ label: typeLabel(type), count }))
      .sort((a, b) => b.count - a.count)
  }, [summary])

  return (
    <AppLayout title="Command Center" description={selectedCity ? `${selectedCity.name}, ${selectedCity.state}` : undefined}>
      {loading && <LoadingState label="Loading city overview" />}
      {error && <ErrorState error={error} onRetry={reload} />}

      {summary && (
        <div className="space-y-6">
          {summary.has_demo_data && (
            <div className="flex items-start gap-3 rounded-md border border-info/20 bg-info/[0.06] px-5 py-4 text-sm text-info">
              <Info className="h-4 w-4 shrink-0 mt-0.5" aria-hidden="true" />
              <span>This city's data includes demonstration/seed records for evaluation purposes, not official municipal records.</span>
            </div>
          )}

          <StatStrip
            items={[
              { label: 'Total Problems', value: summary.total_problems, icon: ListChecks, color: '#0B2A52' },
              { label: 'Critical', value: summary.critical_problems, color: '#C6303E', icon: AlertOctagon },
              { label: 'High Priority', value: summary.high_priority_problems, color: '#E15400', icon: TriangleAlert },
              { label: 'Resolved', value: summary.resolved_problems, color: '#1E8E5A', icon: CheckCircle2 },
              { label: 'Unresolved', value: summary.unresolved_problems, color: '#64748B', icon: CircleDashed },
              {
                label: 'Infrastructure Health',
                value: summary.infrastructure_health_score,
                suffix: `/ 100 · ${summary.infrastructure_health_label}`,
                color: HEALTH_COLOR[summary.infrastructure_health_label],
                icon: HeartPulse,
              },
            ]}
          />

          <div className="grid lg:grid-cols-2 gap-6">
            <section className="panel p-5">
              <h2 className="text-sm font-semibold text-ink-900 mb-4">Severity distribution</h2>
              <DistributionChart
                data={severityChartData}
                colorFn={(entry) => severityMeta(entry.key).color}
              />
            </section>
            <section className="panel p-5">
              <h2 className="text-sm font-semibold text-ink-900 mb-4">Problem distribution by type</h2>
              <DistributionChart data={typeChartData} colorFn={() => '#0B2A52'} />
            </section>
          </div>

          <div className="grid lg:grid-cols-2 gap-6">
            <section className="panel">
              <div className="flex items-center justify-between px-6 py-5 border-b border-slate-100">
                <h2 className="text-sm font-semibold text-ink-900">Top priority locations</h2>
                <Link to="/action-center" className="text-sm text-orange-500 hover:text-orange-600 font-medium">
                  View all
                </Link>
              </div>
              {priorities && priorities.length > 0 ? (
                <ul className="divide-y divide-slate-100">
                  {priorities.map((p) => (
                    <li key={p.id} className="px-6 py-4 flex items-center justify-between gap-3">
                      <div className="min-w-0">
                        <div className="text-sm font-medium text-ink-900 truncate">{typeLabel(p.problem_type)}</div>
                        <div className="text-xs text-ink-500 truncate">{p.road_name || 'Unnamed location'}</div>
                      </div>
                      <div className="flex items-center gap-3 shrink-0">
                        <SeverityBadge severity={p.severity} />
                        <span className="text-sm font-semibold tabular-nums text-ink-900 w-8 text-right">
                          {Math.round(p.risk_score)}
                        </span>
                      </div>
                    </li>
                  ))}
                </ul>
              ) : (
                <EmptyState title="No prioritized locations yet" icon={HeartPulse} />
              )}
            </section>

            <section className="panel">
              <div className="px-6 py-5 border-b border-slate-100">
                <h2 className="text-sm font-semibold text-ink-900">Recent critical detections</h2>
              </div>
              {recentCritical && recentCritical.items.length > 0 ? (
                <ul className="divide-y divide-slate-100">
                  {recentCritical.items.map((p) => (
                    <li key={p.id} className="px-6 py-4 flex items-center justify-between gap-3">
                      <div className="min-w-0">
                        <div className="text-sm font-medium text-ink-900 truncate">{typeLabel(p.problem_type)}</div>
                        <div className="text-xs text-ink-500 truncate">{p.road_name || 'Unnamed location'}</div>
                      </div>
                      <div className="flex items-center gap-3 shrink-0">
                        <StatusBadge status={p.status} />
                        <span className="text-xs text-ink-500 whitespace-nowrap">{formatRelative(p.last_detected_at)}</span>
                      </div>
                    </li>
                  ))}
                </ul>
              ) : (
                <EmptyState title="No critical detections" description="Nothing critical has been reported recently." icon={AlertOctagon} />
              )}
            </section>
          </div>
        </div>
      )}
    </AppLayout>
  )
}
