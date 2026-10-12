import { Check, Eraser, X } from 'lucide-react'
import ManualEntryForm from './ManualEntryForm'

/**
 * Shown after the user draws an area on the photo: pick what the problem is
 * and how serious it is, then add it to the report (or redraw / cancel).
 */
export default function RegionDraftPanel({
  problemType, setProblemType, severity, setSeverity, saving, error, onAdd, onRedraw, onCancel,
}) {
  return (
    <div className="space-y-3 rounded-lg border border-orange-500/40 bg-orange-50/40 p-3">
      <p className="text-sm font-medium text-ink-900">What is in the highlighted area?</p>
      <ManualEntryForm
        problemType={problemType}
        setProblemType={setProblemType}
        severity={severity}
        setSeverity={setSeverity}
      />
      {error && <p className="text-xs text-danger">{error}</p>}
      <div className="flex flex-wrap gap-2">
        <button className="btn-accent flex-1" onClick={onAdd} disabled={saving}>
          <Check className="h-4 w-4" /> {saving ? 'Adding…' : 'Add to report'}
        </button>
        <button className="btn-secondary" onClick={onRedraw} disabled={saving}>
          <Eraser className="h-4 w-4" /> Redraw
        </button>
        <button className="btn-secondary" onClick={onCancel} disabled={saving}>
          <X className="h-4 w-4" /> Cancel
        </button>
      </div>
    </div>
  )
}
