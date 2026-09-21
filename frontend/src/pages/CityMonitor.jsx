import { useState } from 'react'
import AppLayout from '../layouts/AppLayout'
import MapView from '../components/MapView'
import MonitorFilters from '../components/MonitorFilters'
import ProblemDetailPanel from '../components/ProblemDetailPanel'
import { LoadingState, ErrorState, EmptyState } from '../components/StateViews'
import { useCity } from '../hooks/CityContext'
import { useApi } from '../hooks/useApi'
import { api } from '../services/api'
import { Map as MapIcon } from 'lucide-react'

export default function CityMonitor() {
  const { selectedCityId, selectedCity } = useCity()
  const [filters, setFilters] = useState({
    problem_type: [], severity: [], status: [], ward_id: null, date_from: null, date_to: null,
  })
  const [selectedId, setSelectedId] = useState(null)

  const { data: wards } = useApi(() => api.listWards(selectedCityId), [selectedCityId], { skip: !selectedCityId })

  const { data: problems, loading, error, reload } = useApi(
    () => api.getMapProblems({ city_id: selectedCityId, ...filters }),
    [selectedCityId, JSON.stringify(filters)],
    { skip: !selectedCityId }
  )

  const { data: selectedProblem, loading: detailLoading } = useApi(
    () => api.getProblem(selectedId),
    [selectedId],
    { skip: !selectedId }
  )

  return (
    <AppLayout title="City Monitor" description={selectedCity ? `Interactive map of ${selectedCity.name}` : undefined}>
      {loading && !problems && <LoadingState label="Loading map data" />}
      {error && <ErrorState error={error} onRetry={reload} />}

      {selectedCity && (
        <div className="grid lg:grid-cols-[280px_1fr] gap-6 items-start">
          <MonitorFilters filters={filters} setFilters={setFilters} wards={wards} />

          <div className="grid gap-4" style={{ gridTemplateColumns: selectedId ? '1fr 320px' : '1fr' }}>
            <div className="h-[560px] panel overflow-hidden">
              {problems && problems.length === 0 ? (
                <EmptyState
                  title="No infrastructure problems match the selected filters."
                  description="Try clearing a filter or selecting a different ward."
                  icon={MapIcon}
                />
              ) : (
                <MapView
                  center={[selectedCity.center_latitude, selectedCity.center_longitude]}
                  zoom={selectedCity.default_zoom}
                  problems={problems || []}
                  onSelect={(p) => setSelectedId(p.id)}
                />
              )}
            </div>

            {selectedId && (
              <div className="h-[560px]">
                <ProblemDetailPanel problem={selectedProblem} loading={detailLoading} onClose={() => setSelectedId(null)} />
              </div>
            )}
          </div>
        </div>
      )}
    </AppLayout>
  )
}
