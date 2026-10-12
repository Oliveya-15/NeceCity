import { Check, X } from 'lucide-react'
import { SeverityBadge } from './Badge'
import { SEVERITIES, typeLabel } from '../utils/constants'

export default function DetectionReviewCard({ detection, reviewState, onHover, isActive, onSeverityChange, onConfirm, onReject, disabled }) {
  const { status, severity } = reviewState

  return (
    <div
      className={`panel p-4 transition-colors ${isActive ? 'border-orange-500' : ''}`}
      onMouseEnter={onHover}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-sm font-semibold text-ink-900">{typeLabel(detection.problem_type)}</div>
          <div className="text-xs text-ink-500 mt-0.5">
            {detection.source === 'user'
              ? 'Area marked by you'
              : `Model confidence: ${Math.round(detection.confidence * 100)}%`}
          </div>
          {detection.low_confidence && status === 'pending' && (
            <div className="text-[11px] text-warning mt-1">
              Low confidence — check that the dashed box really shows this problem before confirming.
            </div>
          )}
        </div>
        {status !== 'pending' && (
          <span className={`text-xs font-medium px-2 py-0.5 rounded-sm ${status === 'confirmed' ? 'bg-success-bg text-success' : 'bg-line text-ink-500'}`}>
            {status === 'confirmed' ? 'Added' : 'Rejected'}
          </span>
        )}
      </div>

      {status === 'pending' && (
        <>
          <div className="mt-3">
            <label className="label" htmlFor={`severity-${detection._key}`}>
              Severity {severity !== detection.severity_suggested && <span className="text-orange-500">(edited)</span>}
            </label>
            <p className="text-[11px] text-ink-300 mb-1.5">
              Confidence is how sure the model is about what it saw; severity is how serious you judge the problem to be — set it based on what you see, not the confidence number.
            </p>
            <div className="flex flex-wrap gap-1.5" id={`severity-${detection._key}`}>
              {SEVERITIES.map((s) => (
                <button
                  key={s.value}
                  type="button"
                  onClick={() => onSeverityChange(s.value)}
                  className={`pill-toggle ${severity === s.value ? 'text-white border-transparent' : 'pill-toggle-inactive'}`}
                  style={severity === s.value ? { backgroundColor: s.color } : undefined}
                >
                  {s.label}
                </button>
              ))}
            </div>
          </div>

          <div className="flex gap-2 mt-4">
            <button className="btn-accent flex-1" onClick={onConfirm} disabled={disabled}>
              <Check className="h-4 w-4" /> Confirm
            </button>
            <button className="btn-secondary flex-1" onClick={onReject} disabled={disabled}>
              <X className="h-4 w-4" /> Reject
            </button>
          </div>
        </>
      )}

      {status !== 'pending' && (
        <div className="mt-2">
          <SeverityBadge severity={severity} />
        </div>
      )}
    </div>
  )
}