import { useState } from 'react'
import { ChevronDown, Download, FileSpreadsheet, FileText } from 'lucide-react'
import AppLayout from '../layouts/AppLayout'
import { SeverityBadge, StatusBadge } from '../components/Badge'
import { LoadingState, ErrorState, EmptyState } from '../components/StateViews'
import { useCity } from '../hooks/CityContext'
import { useApi } from '../hooks/useApi'
import { api, ApiError } from '../services/api'
import { STATUS_ORDER, typeLabel } from '../utils/constants'

const NEXT_STATUS_LABEL = { detected: 'Mark verified', verified: 'Start in progress', in_progress: 'Mark resolved' }

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}

function PriorityRow({ problem, onAdvance, advancing }) {
  const [expanded, setExpanded] = useState(false)
  const nextLabel = NEXT_STATUS_LABEL[problem.status]

  return (
    <li className="border-b border-slate-100 last:border-b-0">
      <div className="px-6 py-4 flex items-center gap-3">
        <button
          className="flex items-center gap-2 text-ink-500 hover:text-ink-900 shrink-0"
          onClick={() => setExpanded((e) => !e)}
          aria-expanded={expanded}
          aria-label={expanded ? 'Collapse details' : 'Expand details'}
        >
          <ChevronDown className={`h-4 w-4 transition-transform ${expanded ? 'rotate-180' : ''}`} />
        </button>

        <div className="min-w-0 flex-1">
          <div className="text-sm font-medium text-ink-900 truncate">{typeLabel(problem.problem_type)}</div>
          <div className="text-xs text-ink-500 truncate">{problem.road_name || 'Unnamed location'}</div>
        </div>

        <SeverityBadge severity={problem.severity} />
        <StatusBadge status={problem.status} />

        <div className="text-right shrink-0 w-12">
          <div className="text-sm font-bold tabular-nums text-ink-900">{Math.round(problem.risk_score)}</div>
          <div className="text-[10px] text-ink-500">risk</div>
        </div>

        {nextLabel && (
          <button
            className="btn-secondary text-xs shrink-0 whitespace-nowrap"
            onClick={() => onAdvance(problem)}
            disabled={advancing}
          >
            {nextLabel}
          </button>
        )}
      </div>

      {expanded && (
        <div className="px-6 pb-5 pl-14 text-sm text-ink-700 space-y-2">
          <p className="font-medium text-ink-900">{problem.recommended_action}</p>
          {problem.recurrence_count > 1 && <p>Reported {problem.recurrence_count} times at this location.</p>}
        </div>
      )}
    </li>
  )
}

export default function ActionCenter() {
  const { selectedCityId, selectedCity } = useCity()
  const [showResolved, setShowResolved] = useState(false)
  const [advancingId, setAdvancingId] = useState(null)
  const [reportBusy, setReportBusy] = useState(null)

  const { data: priorities, loading, error, reload } = useApi(
    () => api.getPriorities(selectedCityId, 50, !showResolved),
    [selectedCityId, showResolved],
    { skip: !selectedCityId }
  )

  async function handleAdvance(problem) {
    const currentIdx = STATUS_ORDER.indexOf(problem.status)
    const nextStatus = STATUS_ORDER[currentIdx + 1]
    if (!nextStatus) return
    setAdvancingId(problem.id)
    try {
      await api.updateProblemStatus(problem.id, nextStatus)
      reload()
    } catch (err) {
      window.alert(err instanceof ApiError ? err.message : 'Failed to update status.')
    } finally {
      setAdvancingId(null)
    }
  }

  async function handleReport(format) {
    setReportBusy(format)
    try {
      const blob = await api.downloadReport(selectedCityId, format, 30)
      downloadBlob(blob, `nececity_${selectedCity?.slug || 'report'}.${format}`)
    } catch (err) {
      window.alert('Failed to generate report.')
    } finally {
      setReportBusy(null)
    }
  }

  return (
    <AppLayout
      title="Action Center"
      description={selectedCity ? `Risk-ranked priorities for ${selectedCity.name}` : undefined}
      actions={
        <div className="hidden sm:flex gap-2">
          <button className="btn-secondary text-sm" onClick={() => handleReport('csv')} disabled={reportBusy === 'csv'}>
            <FileSpreadsheet className="h-4 w-4" /> CSV
          </button>
          <button className="btn-secondary text-sm" onClick={() => handleReport('pdf')} disabled={reportBusy === 'pdf'}>
            <FileText className="h-4 w-4" /> PDF Report
          </button>
        </div>
      }
    >
      <div className="sm:hidden flex gap-2 mb-4">
        <button className="btn-secondary text-sm flex-1" onClick={() => handleReport('csv')} disabled={reportBusy === 'csv'}>
          <Download className="h-4 w-4" /> CSV
        </button>
        <button className="btn-secondary text-sm flex-1" onClick={() => handleReport('pdf')} disabled={reportBusy === 'pdf'}>
          <Download className="h-4 w-4" /> PDF
        </button>
      </div>

      {loading && <LoadingState label="Loading priorities" />}
      {error && <ErrorState error={error} onRetry={reload} />}

      {priorities && (
        <section className="panel">
          <div className="flex items-center justify-between px-6 py-5 border-b border-slate-100">
            <h2 className="text-sm font-semibold text-ink-900">Priority queue</h2>
            <label className="flex items-center gap-2 text-sm text-ink-700">
              <input type="checkbox" checked={showResolved} onChange={(e) => setShowResolved(e.target.checked)} />
              Show resolved
            </label>
          </div>
          {priorities.length > 0 ? (
            <ul>
              {priorities.map((p) => (
                <PriorityRow key={p.id} problem={p} onAdvance={handleAdvance} advancing={advancingId === p.id} />
              ))}
            </ul>
          ) : (
            <EmptyState title="No prioritized problems to show." description="Confirm some detections in Inspect & Analyze to populate this list." />
          )}
        </section>
      )}
    </AppLayout>
  )
}
