import { useState } from 'react'
import { Lightbulb, MapPinned, Repeat } from 'lucide-react'
import AppLayout from '../layouts/AppLayout'
import DistributionChart from '../components/DistributionChart'
import TrendChart from '../components/TrendChart'
import { LoadingState, ErrorState, EmptyState } from '../components/StateViews'
import { useCity } from '../hooks/CityContext'
import { useApi } from '../hooks/useApi'
import { api } from '../services/api'
import { typeLabel } from '../utils/constants'

export default function Insights() {
  const { selectedCityId, selectedCity } = useCity()
  const [granularity, setGranularity] = useState('week')

  const { data: overview, loading, error, reload } = useApi(
    () => api.getOverview(selectedCityId), [selectedCityId], { skip: !selectedCityId }
  )
  const { data: trends } = useApi(
    () => api.getTrends(selectedCityId, granularity), [selectedCityId, granularity], { skip: !selectedCityId }
  )
  const { data: hotspots } = useApi(() => api.getHotspots(selectedCityId), [selectedCityId], { skip: !selectedCityId })
  const { data: recurring } = useApi(() => api.getRecurring(selectedCityId), [selectedCityId], { skip: !selectedCityId })

  const clusters = groupHotspotsByCluster(hotspots?.hotspots)
  const allInsights = [
    ...(overview?.insights || []),
    ...(trends?.insights || []),
    ...(hotspots?.insights || []),
  ]

  return (
    <AppLayout title="Insights" description={selectedCity ? `Data analytics for ${selectedCity.name}` : undefined}>
      {loading && <LoadingState label="Loading analytics" />}
      {error && <ErrorState error={error} onRetry={reload} />}

      {overview && (
        <div className="space-y-6">
          {allInsights.length > 0 && (
            <section className="panel p-5">
              <h2 className="text-sm font-semibold text-ink-900 mb-3 flex items-center gap-2">
                <Lightbulb className="h-4 w-4 text-orange-500" /> Data insights
              </h2>
              <ul className="space-y-2">
                {allInsights.map((insight, i) => (
                  <li key={i} className="text-sm text-ink-700 flex gap-2">
                    <span className="text-orange-500 mt-0.5">&bull;</span>
                    {insight.text}
                  </li>
                ))}
              </ul>
            </section>
          )}

          <div className="grid lg:grid-cols-2 gap-6">
            <section className="panel p-5">
              <h2 className="text-sm font-semibold text-ink-900 mb-4">Problems by type</h2>
              <DistributionChart
                data={overview.by_type.map((t) => ({ label: typeLabel(t.problem_type), count: t.count }))}
                colorFn={() => '#0B2A52'}
              />
            </section>
            <section className="panel p-5">
              <h2 className="text-sm font-semibold text-ink-900 mb-4">Problems by area</h2>
              {overview.by_area.length > 0 ? (
                <DistributionChart
                  data={overview.by_area.slice(0, 8).map((a) => ({ label: a.ward_name, count: a.count }))}
                  colorFn={() => '#FD6001'}
                />
              ) : (
                <EmptyState title="No area/ward data available yet." />
              )}
            </section>
          </div>

          <section className="panel p-5">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-sm font-semibold text-ink-900">Problem trends over time</h2>
              <div className="flex rounded-full border border-slate-200 overflow-hidden text-xs bg-slate-50">
                {['week', 'month'].map((g) => (
                  <button
                    key={g}
                    onClick={() => setGranularity(g)}
                    className={`px-4 py-1.5 capitalize rounded-full transition-colors ${granularity === g ? 'bg-navy-900 text-white' : 'text-ink-700 hover:bg-white'}`}
                  >
                    {g}ly
                  </button>
                ))}
              </div>
            </div>
            <p className="text-[11px] text-ink-300 mb-3">pandas · time-series resampling</p>
            {trends && trends.points.length > 0 ? (
              <TrendChart points={trends.points} />
            ) : (
              <EmptyState title="Not enough data yet to show a trend." />
            )}
          </section>

          <div className="grid lg:grid-cols-2 gap-6">
            <section className="panel">
              <div className="px-6 py-5 border-b border-slate-100 flex items-center gap-2">
                <MapPinned className="h-4 w-4 text-ink-500" />
                <div>
                  <h2 className="text-sm font-semibold text-ink-900">Hotspot clusters (DBSCAN)</h2>
                  <p className="text-[11px] text-ink-300">scikit-learn · density-based spatial clustering</p>
                </div>
              </div>
              {clusters.length > 0 ? (
                <ul className="divide-y divide-slate-100">
                  {clusters.map((c) => (
                    <li key={c.cluster_id} className="px-6 py-4 flex items-center justify-between">
                      <div>
                        <div className="text-sm font-medium text-ink-900">Cluster {c.cluster_id + 1}</div>
                        <div className="text-xs text-ink-500">Dominant: {typeLabel(c.dominant_type)}</div>
                      </div>
                      <span className="text-sm font-semibold tabular-nums text-ink-900">{c.count} problems</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <EmptyState title="No significant hotspots detected yet." icon={MapPinned} />
              )}
            </section>

            <section className="panel">
              <div className="px-6 py-5 border-b border-slate-100 flex items-center gap-2">
                <Repeat className="h-4 w-4 text-ink-500" />
                <h2 className="text-sm font-semibold text-ink-900">Recurring problems</h2>
              </div>
              {recurring && recurring.length > 0 ? (
                <ul className="divide-y divide-slate-100">
                  {recurring.map((r) => (
                    <li key={r.problem_id} className="px-6 py-4 flex items-center justify-between gap-3">
                      <div className="min-w-0">
                        <div className="text-sm font-medium text-ink-900 truncate">{typeLabel(r.problem_type)}</div>
                        <div className="text-xs text-ink-500 truncate">{r.road_name || 'Unnamed location'}</div>
                      </div>
                      <span className="text-sm font-semibold tabular-nums text-orange-500 shrink-0">{r.recurrence_count}x</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <EmptyState title="No recurring problems detected." icon={Repeat} />
              )}
            </section>
          </div>
        </div>
      )}
    </AppLayout>
  )
}

function groupHotspotsByCluster(hotspots) {
  if (!hotspots) return []
  const map = new Map()
  for (const h of hotspots) {
    if (!map.has(h.cluster_id)) map.set(h.cluster_id, { cluster_id: h.cluster_id, dominant_type: h.dominant_type, count: 0 })
    map.get(h.cluster_id).count += 1
  }
  return Array.from(map.values()).sort((a, b) => b.count - a.count)
}
