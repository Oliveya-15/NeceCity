import { X } from 'lucide-react'
import { SeverityBadge, StatusBadge } from './Badge'
import { LoadingState } from './StateViews'
import { api } from '../services/api'
import { typeLabel } from '../utils/constants'
import { formatDateTime } from '../utils/format'

export default function ProblemDetailPanel({ problem, loading, onClose }) {
  return (
    <div className="panel h-full flex flex-col">
      <div className="flex items-center justify-between px-4 py-3 border-b border-line">
        <h2 className="text-sm font-semibold text-ink-900">Location details</h2>
        <button onClick={onClose} className="text-ink-500 hover:text-ink-900" aria-label="Close details">
          <X className="h-4 w-4" />
        </button>
      </div>

      {loading && <LoadingState label="Loading" />}

      {problem && !loading && (
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {problem.image && (
            <img
              src={api.uploadsUrl(problem.image.url)}
              alt={`Photo of ${typeLabel(problem.problem_type).toLowerCase()}`}
              className="w-full rounded border border-line object-cover max-h-48"
            />
          )}

          <div>
            <div className="text-base font-semibold text-ink-900">{typeLabel(problem.problem_type)}</div>
            <div className="text-sm text-ink-500">{problem.location.road_name || 'Unnamed location'}</div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <SeverityBadge severity={problem.severity} />
            <StatusBadge status={problem.status} />
          </div>

          <dl className="text-sm space-y-2">
            {problem.confidence !== null && problem.confidence !== undefined && (
              <div className="flex justify-between">
                <dt className="text-ink-500">Detection confidence</dt>
                <dd className="font-medium text-ink-900">{Math.round(problem.confidence * 100)}%</dd>
              </div>
            )}
            {problem.risk && (
              <div className="flex justify-between">
                <dt className="text-ink-500">Risk score</dt>
                <dd className="font-medium text-ink-900">{Math.round(problem.risk.score)} / 100</dd>
              </div>
            )}
            <div className="flex justify-between">
              <dt className="text-ink-500">Detected</dt>
              <dd className="font-medium text-ink-900">{formatDateTime(problem.first_detected_at)}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-ink-500">Recurrence</dt>
              <dd className="font-medium text-ink-900">{problem.recurrence_count}x reported</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-ink-500">Coordinates</dt>
              <dd className="font-medium text-ink-900 tabular-nums">
                {problem.location.latitude.toFixed(5)}, {problem.location.longitude.toFixed(5)}
              </dd>
            </div>
          </dl>

          {problem.risk && (
            <div className="border-t border-line pt-3">
              <div className="text-xs font-medium text-ink-500 mb-1.5">Why this priority</div>
              <ul className="text-sm text-ink-700 space-y-1 list-disc list-inside">
                {problem.risk.reasons?.map((r, i) => <li key={i}>{r}</li>)}
              </ul>
              <p className="text-sm text-ink-900 font-medium mt-2">{problem.risk.recommended_action}</p>
            </div>
          )}

          {problem.is_demo && (
            <p className="text-xs text-ink-500 border-t border-line pt-3">This is a demo/seed record.</p>
          )}
        </div>
      )}
    </div>
  )
}
