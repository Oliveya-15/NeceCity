import { Loader2, Send } from 'lucide-react'
import { SeverityBadge } from './Badge'
import { typeLabel } from '../utils/constants'
import { formatDateTime } from '../utils/format'

export default function ReportReviewSummary({ items, cityName, location, imageUrl, submitting, onSubmit, onBack }) {
  return (
    <div className="panel p-5 space-y-5">
      <div>
        <h2 className="text-sm font-semibold text-ink-900">Review before submitting</h2>
        <p className="text-xs text-ink-500 mt-0.5">
          {items.length} problem{items.length > 1 ? 's' : ''} will be added to City Monitor as{' '}
          {items.length > 1 ? 'reports' : 'a report'}.
        </p>
      </div>

      <div className="flex gap-4">
        {imageUrl && (
          <img src={imageUrl} alt="Report evidence" className="w-24 h-24 object-cover rounded-md border border-slate-100 shrink-0" />
        )}
        <dl className="text-sm space-y-1.5 flex-1 min-w-0">
          <div className="flex justify-between gap-2">
            <dt className="text-ink-500">Location</dt>
            <dd className="font-medium text-ink-900 text-right">
              {location.road_name || `${Number(location.latitude).toFixed(4)}, ${Number(location.longitude).toFixed(4)}`}
            </dd>
          </div>
          <div className="flex justify-between gap-2">
            <dt className="text-ink-500">City</dt>
            <dd className="font-medium text-ink-900">{cityName}</dd>
          </div>
          <div className="flex justify-between gap-2">
            <dt className="text-ink-500">Date/time</dt>
            <dd className="font-medium text-ink-900">{formatDateTime(new Date().toISOString())}</dd>
          </div>
        </dl>
      </div>

      <ul className="divide-y divide-slate-100 border-t border-slate-100">
        {items.map((item) => (
          <li key={item.key} className="py-3 flex items-center justify-between gap-3">
            <div className="min-w-0">
              <div className="text-sm font-medium text-ink-900">{typeLabel(item.problemType)}</div>
              <div className="text-xs text-ink-500">
                {item.confidence !== null && item.confidence !== undefined
                  ? `Detected at ${Math.round(item.confidence * 100)}% model confidence, verified by you`
                  : 'Reported manually by you'}
              </div>
            </div>
            <SeverityBadge severity={item.severity} />
          </li>
        ))}
      </ul>

      <div className="flex gap-2">
        <button type="button" className="btn-secondary flex-1" onClick={onBack} disabled={submitting}>
          Back
        </button>
        <button type="button" className="btn-accent flex-1" onClick={onSubmit} disabled={submitting}>
          {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
          {submitting ? 'Submitting...' : `Submit report${items.length > 1 ? 's' : ''}`}
        </button>
      </div>
    </div>
  )
}